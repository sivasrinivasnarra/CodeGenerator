import streamlit as st
from firebase_utils import (
    sign_in, sign_up, get_user_id,
    list_user_chats, create_new_chat, get_chat_history, add_message_to_chat, set_chat_title
)
from gemini_utils import generate_gemini_response
from openai_utils import generate_openai_response
from dotenv import load_dotenv
import os
from streamlit.components.v1 import html
import PyPDF2
from io import BytesIO
import re
from datetime import datetime
import tempfile
from typing import Dict, List, Optional
import zipfile
import json
try:
    from docx import Document
    import docx2txt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Enhanced imports (with fallbacks)
try:
    import sentence_transformers
    import numpy as np
    import faiss
    from rag_system import ProjectRAG
    from model_adapter import ModelClient
    from git_repository_integration import GitRepositoryIntegration
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    st.warning("⚠️ RAG features not available. Install: `pip install sentence-transformers faiss-cpu scikit-learn numpy`")

# Project Generation imports (with fallbacks)
try:
    from project_orchestrator import (
        ProjectOrchestrator, GenerationOptions, GenerationResult,
        generate_project_from_upload, generate_project_from_description
    )
    PROJECT_GENERATOR_AVAILABLE = True
except ImportError:
    PROJECT_GENERATOR_AVAILABLE = False
    st.warning("⚠️ Project Generator not available. Some advanced features may be limited.")

load_dotenv()

st.set_page_config(page_title="MultiModel ChatBot", layout="wide")

# Initialize session state
if "project_rag" not in st.session_state:
    st.session_state.project_rag = None
if "project_context" not in st.session_state:
    st.session_state.project_context = {}
if "git_integration" not in st.session_state:
    st.session_state.git_integration = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = "🚀 Project Generator"
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gemini-2.5-pro"
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "Gemini"
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "auto_send_prompt" not in st.session_state:
    st.session_state.auto_send_prompt = ""
if "project_generation_state" not in st.session_state:
    st.session_state.project_generation_state = {
        "is_generating": False,
        "current_step": None,
        "generated_files": [],
        "project_name": "",
        "tech_stack": [],
        "architecture": "",
        "user_feedback": "",
        "generation_complete": False,
        "zip_data": None,
        # New interactive workflow states
        "workflow_step": "initial",  # initial, tech_stack_selection, architecture_review, group_generation, complete
        "requirements": "",
        "suggested_tech_stack": [],
        "selected_tech_stack": [],
        "project_architecture": "",
        "file_groups": [],
        "current_group_index": 0,
        "generated_groups": [],
        "user_confirmations": {},
        "project_description": ""
    }
if "project_generation_history" not in st.session_state:
    st.session_state.project_generation_history = []

# Helper functions
def render_mermaid(mermaid_code: str):
    """Render Mermaid diagram in Streamlit using HTML and Mermaid.js CDN."""
    try:
        if mermaid_code.strip().startswith('```mermaid'):
            mermaid_code = mermaid_code.strip().removeprefix('```mermaid').removesuffix('```').strip()
        
        # Basic validation of mermaid code
        if not mermaid_code or len(mermaid_code.strip()) < 10:
            st.warning("⚠️ Invalid Mermaid diagram code")
            return
        
        mermaid_html = f'''
        <div style="overflow:auto; max-width:100%; max-height:600px; border: 1px solid #ddd; border-radius: 8px; padding: 10px;">
          <div class="mermaid">
            {mermaid_code}
          </div>
        </div>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        '''
        html(mermaid_html, height=600)
    except Exception as e:
        st.error(f"❌ Error rendering Mermaid diagram: {str(e)}")
        st.code(mermaid_code, language="mermaid")

def extract_files_from_uploaded(uploaded_files):
    """Extract content from uploaded files including zip archives and Word documents."""
    files_content = {}
    
    for uploaded_file in uploaded_files:
        try:
            file_name = uploaded_file.name.lower()
            
            if file_name.endswith('.zip'):
                # Handle zip files
                file_bytes = uploaded_file.read()
                with zipfile.ZipFile(BytesIO(file_bytes)) as zip_file:
                    for file_info in zip_file.infolist():
                        if not file_info.is_dir() and file_info.file_size < 500000:  # 500KB limit per file
                            try:
                                with zip_file.open(file_info) as inner_file:
                                    inner_content = inner_file.read().decode('utf-8')
                                    # Preserve folder structure in filename
                                    display_name = f"{uploaded_file.name[:-4]}/{file_info.filename}"
                                    files_content[display_name] = inner_content
                            except UnicodeDecodeError:
                                # Skip binary files
                                continue
                            except Exception as e:
                                # Skip files with other errors
                                continue
                                
            elif file_name.endswith('.docx') and DOCX_AVAILABLE:
                # Handle Word .docx files
                try:
                    file_bytes = uploaded_file.read()
                    # Method 1: Try using python-docx
                    try:
                        doc = Document(BytesIO(file_bytes))
                        content = []
                        for paragraph in doc.paragraphs:
                            content.append(paragraph.text)
                        files_content[uploaded_file.name] = '\n'.join(content)
                    except Exception as e:
                        # Method 2: Fallback to docx2txt
                        try:
                            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                                tmp_file.write(file_bytes)
                                tmp_file.flush()
                                content = docx2txt.process(tmp_file.name)
                                files_content[uploaded_file.name] = content
                                os.unlink(tmp_file.name)  # Clean up temp file
                        except Exception as e2:
                            files_content[uploaded_file.name] = f"[Error extracting Word document: {str(e2)}]"
                except Exception as e:
                    files_content[uploaded_file.name] = f"[Error extracting Word document: {str(e)}]"
                    
            elif file_name.endswith('.doc') and DOCX_AVAILABLE:
                # Handle older Word .doc files (limited support)
                try:
                    file_bytes = uploaded_file.read()
                    with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_file.flush()
                        try:
                            content = docx2txt.process(tmp_file.name)
                            files_content[uploaded_file.name] = content
                        except:
                            # If docx2txt fails, mark as unsupported
                            files_content[uploaded_file.name] = f"[Unsupported .doc format - please save as .docx: {uploaded_file.name}]"
                        os.unlink(tmp_file.name)  # Clean up temp file
                except Exception as e:
                    files_content[uploaded_file.name] = f"[Error processing .doc file: {str(e)}]"
                    
            elif file_name.endswith('.pdf'):
                # Handle PDF files
                try:
                    file_bytes = uploaded_file.read()
                    pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
                    content = []
                    for page in pdf_reader.pages:
                        content.append(page.extract_text())
                    files_content[uploaded_file.name] = '\n'.join(content)
                except Exception as e:
                    files_content[uploaded_file.name] = f"[Error reading PDF: {str(e)}]"
                    
            else:
                # Handle regular text files
                content = uploaded_file.read().decode('utf-8')
                files_content[uploaded_file.name] = content
                
        except UnicodeDecodeError:
            # Check if Word documents are not supported
            if (file_name.endswith('.docx') or file_name.endswith('.doc')) and not DOCX_AVAILABLE:
                files_content[uploaded_file.name] = f"[Word document support not available - install: pip install python-docx docx2txt]"
            else:
                files_content[uploaded_file.name] = f"[Binary file: {uploaded_file.name}]"
        except Exception as e:
            files_content[uploaded_file.name] = f"[Error reading {uploaded_file.name}: {str(e)}]"
    
    return files_content

def initialize_rag_system(files_content, user_id=None, chat_id=None):
    """Initialize RAG system with project files for a specific chat session."""
    if not RAG_AVAILABLE:
        return False
        
    try:
        if st.session_state.project_rag is None:
            st.session_state.project_rag = ProjectRAG()
        
        # Use chat-specific project ID if available
        if chat_id:
            project_id = f"chat_{chat_id}"
        else:
            project_id = "current"
            
        if not user_id:
            user_id = "default"
        
        # Index the project files with chat-specific context
        with st.spinner("🧠 Creating semantic embeddings with RAG..."):
            st.session_state.project_rag.index_project_files(
                files_content, 
                user_id=user_id, 
                project_id=project_id
            )
            
        # Store project context
        project_context = {
            'files': files_content,
            'total_files': len(files_content),
            'indexed': True,
            'last_updated': datetime.now().isoformat(),
            'chat_id': chat_id,
            'user_id': user_id,
            'project_id': project_id
        }
        
        st.session_state.project_context = project_context
        
        # Save context to Firebase if we have a chat ID
        if chat_id and user_id:
            save_chat_context(user_id, chat_id, project_context)
        
        return True
    except Exception as e:
        st.error(f"❌ Failed to initialize RAG system: {str(e)}")
        return False

def get_rag_context(query, max_results=5):
    """Get relevant context from RAG system using chat-specific context."""
    if not RAG_AVAILABLE or not st.session_state.project_rag or not st.session_state.project_context.get('indexed'):
        return []
        
    try:
        # Use chat-specific project ID if available
        user_id = st.session_state.project_context.get('user_id', 'default')
        project_id = st.session_state.project_context.get('project_id', 'current')
        
        results = st.session_state.project_rag.search_similar_code(
            query, 
            top_k=max_results,
            user_id=user_id,
            project_id=project_id
        )
        return results
    except Exception as e:
        st.warning(f"⚠️ RAG search failed: {str(e)}")
        return []

def save_chat_context(user_id, chat_id, project_context):
    """Save the project context (files) for a specific chat."""
    try:
        from firebase_utils import db
        chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
        chat_ref.update({
            'project_context': project_context,
            'has_project_files': project_context.get('indexed', False)
        })
        return True
    except Exception as e:
        st.error(f"Failed to save chat context: {str(e)}")
        return False

def load_chat_context(user_id, chat_id):
    """Load the project context for a specific chat."""
    try:
        from firebase_utils import db
        chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
        chat_doc = chat_ref.get()
        
        if chat_doc.exists:
            data = chat_doc.to_dict()
            return data.get('project_context', {})
        return {}
    except Exception as e:
        st.warning(f"Could not load chat context: {str(e)}")
        return {}

def restore_chat_context(user_id, chat_id):
    """Restore project context and RAG for an existing chat."""
    if not RAG_AVAILABLE:
        return False
        
    saved_context = load_chat_context(user_id, chat_id)
    
    if saved_context.get('indexed'):
        # Restore project context
        st.session_state.project_context = saved_context
        
        # Rebuild RAG if files are available
        if saved_context.get('files'):
            try:
                if st.session_state.project_rag is None:
                    st.session_state.project_rag = ProjectRAG()
                
                # Re-index the files for this chat session
                chat_specific_project_id = f"chat_{chat_id}"
                st.session_state.project_rag.index_project_files(
                    saved_context['files'], 
                    user_id=user_id, 
                    project_id=chat_specific_project_id
                )
                
                st.success(f"🧠 Restored {len(saved_context['files'])} files with RAG for this chat session")
                return True
            except Exception as e:
                st.warning(f"⚠️ Could not restore RAG context: {str(e)}")
    
    return False

def reset_session_for_new_chat():
    """Reset all session state for a completely fresh chat"""
    # Clear project context completely
    st.session_state.project_context = {}
    
    # Reset RAG system thoroughly
    if st.session_state.project_rag:
        try:
            # Clear the RAG system's memory and vector stores
            st.session_state.project_rag.vector_stores.clear()
            # Also clear any cached data
            if hasattr(st.session_state.project_rag, 'metadata_store'):
                st.session_state.project_rag.metadata_store.clear()
        except:
            pass
    st.session_state.project_rag = None
    
    # Clear file uploader state by removing all uploader keys
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith('file_uploader_'):
            del st.session_state[key]
    
    # Clear any file upload state
    if hasattr(st.session_state, 'uploaded_files_temp'):
        st.session_state.uploaded_files_temp = []
    
    # Reset any other session-specific variables
    if hasattr(st.session_state, 'show_uploader'):
        st.session_state.show_uploader = False
    
    # Reset project generation state
    st.session_state.project_generation_state = {
        "is_generating": False,
        "current_step": None,
        "generated_files": [],
        "project_name": "",
        "tech_stack": [],
        "architecture": "",
        "user_feedback": "",
        "generation_complete": False,
        "zip_data": None,
        # New interactive workflow states
        "workflow_step": "initial",  # initial, tech_stack_selection, architecture_review, group_generation, complete
        "requirements": "",
        "suggested_tech_stack": [],
        "selected_tech_stack": [],
        "project_architecture": "",
        "file_groups": [],
        "current_group_index": 0,
        "generated_groups": [],
        "user_confirmations": {},
        "project_description": ""
    }
    st.session_state.project_generation_history = []

def create_project_zip(files_content, project_name="generated_project"):
    """Create a ZIP file from generated project files."""
    import zipfile
    from io import BytesIO
    
    try:
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all project files with proper directory structure
            for file_path, content in files_content.items():
                try:
                    # Ensure proper path separators and clean the path
                    clean_path = file_path.replace('\\', '/').strip()
                    # Remove any invalid characters
                    clean_path = re.sub(r'[<>:"|?*]', '_', clean_path)
                    
                    if clean_path and content:
                        zip_file.writestr(clean_path, content)
                except Exception as e:
                    st.warning(f"⚠️ Skipping file {file_path}: {str(e)}")
                    continue
            
            # Add project metadata
            metadata = {
                "project_name": project_name,
                "generated_at": datetime.now().isoformat(),
                "total_files": len(files_content),
                "file_list": list(files_content.keys())
            }
            zip_file.writestr("PROJECT_METADATA.json", json.dumps(metadata, indent=2))
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    except Exception as e:
        st.error(f"❌ Error creating ZIP file: {str(e)}")
        return None

def extract_project_files_from_response(response_text):
    """Extract project files from AI response text."""
    files = {}
    import re
    
    # Check if response is empty
    if not response_text or len(response_text.strip()) < 10:
        return files
    
    # Multiple patterns to handle different formats
    patterns = [
        # Pattern 1: **filename.ext** [whitespace] ```[lang]\n...```
        r'\*\*([^*]+)\*\*\s*```[a-zA-Z0-9]*\n(.*?)```',
        # Pattern 2: 📄 **filename.ext** [whitespace] ```[lang]\n...```
        r'📄\s*\*\*([^*]+)\*\*\s*```[a-zA-Z0-9]*\n(.*?)```',
        # Pattern 3: **filename.ext** followed by code block
        r'\*\*([^*]+)\*\*\s*\n\s*```[a-zA-Z0-9]*\n(.*?)```',
        # Pattern 4: filename.ext in code block with comment
        r'```[a-zA-Z0-9]*\s*#\s*([^\n]+)\n(.*?)```',
        # Pattern 5: filename.ext with ```lang\n...```
        r'([^\s]+\.(?:py|js|ts|html|css|json|md|txt|yml|yaml|sh|dockerfile|env|gitignore|sql|java|cpp|c|php|rb|go|rs|swift|kt|scala))\s*```[a-zA-Z0-9]*\n(.*?)```',
        # Pattern 6: filename.ext with ```\n...```
        r'([^\s]+\.(?:py|js|ts|html|css|json|md|txt|yml|yaml|sh|dockerfile|env|gitignore|sql|java|cpp|c|php|rb|go|rs|swift|kt|scala))\s*```\n(.*?)```'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        for file_path, content in matches:
            if file_path and content:
                # Clean up file path
                clean_path = file_path.strip()
                # Remove any leading/trailing punctuation and quotes
                clean_path = re.sub(r'^[^\w./-]+|[^\w./-]+$', '', clean_path)
                clean_path = clean_path.strip('"\'`')
                if clean_path and len(clean_path) > 1:
                    files[clean_path] = content.strip()
    
    # Remove duplicates (keep the last occurrence)
    unique_files = {}
    for file_path, content in files.items():
        unique_files[file_path] = content
    
    # Debug: If no files found, try to identify why
    if not unique_files and len(response_text) > 50:
        # Look for any code blocks that might contain files
        code_blocks = re.findall(r'```[a-zA-Z0-9]*\n(.*?)```', response_text, re.DOTALL)
        if code_blocks:
            # Create generic files from code blocks
            for i, code_block in enumerate(code_blocks):
                if len(code_block.strip()) > 10:  # Only if there's actual content
                    # Try to determine file type from context
                    if 'def ' in code_block or 'import ' in code_block or 'class ' in code_block:
                        file_name = f"file_{i+1}.py"
                    elif '<html' in code_block or '<!DOCTYPE' in code_block:
                        file_name = f"file_{i+1}.html"
                    elif 'function ' in code_block or 'const ' in code_block or 'let ' in code_block:
                        file_name = f"file_{i+1}.js"
                    else:
                        file_name = f"file_{i+1}.txt"
                    unique_files[file_name] = code_block.strip()
    
    return unique_files

def generate_comprehensive_project_prompt(prompt, context_info, is_followup=False):
    """Generate a comprehensive prompt for complete project generation."""
    
    if is_followup:
        return f"""
You are a SENIOR FULL-STACK DEVELOPER with 15+ years of experience building enterprise-scale applications.

**PREVIOUS CONTEXT:**
{context_info}

**CURRENT REQUEST:** {prompt}

**MISSION:** Continue project generation with sophisticated, enterprise-grade implementations.

**CONTINUATION FRAMEWORK:**
1. **ANALYZE PREVIOUS WORK** - Understand what's already been implemented
2. **IDENTIFY GAPS** - Find missing components or incomplete implementations
3. **ENHANCE EXISTING CODE** - Improve and extend current implementations
4. **ADD MISSING FEATURES** - Implement any remaining requirements
5. **ENSURE INTEGRATION** - Make sure all components work together seamlessly

**ENTERPRISE-LEVEL REQUIREMENTS:**
- **ARCHITECTURE PATTERNS**: Use appropriate design patterns (Repository, Service, Factory, etc.)
- **SECURITY LAYERS**: Implement authentication, authorization, input validation
- **PERFORMANCE OPTIMIZATION**: Caching, database optimization, async patterns
- **OBSERVABILITY**: Comprehensive logging, monitoring, error tracking
- **TESTABILITY**: Unit tests, integration tests, testable code design
- **MAINTAINABILITY**: Clean code, documentation, modular design

**OUTPUT FORMAT:**
For each file, use this exact format:
```
📄 **filename.ext**
```ext
[SOPHISTICATED, ENTERPRISE-GRADE CODE WITH ALL IMPORTS, ERROR HANDLING, LOGGING, SECURITY, ETC.]
```
```

**INTERACTIVE ELEMENTS:**
- Provide architectural recommendations
- Suggest performance improvements
- Offer security enhancements
- Request clarification for complex requirements
- Propose scalability solutions

**CURRENT REQUEST:** {prompt}
"""
    else:
        return f"""
You are a SENIOR FULL-STACK DEVELOPER with 15+ years of experience building enterprise-scale applications.

**PROJECT REQUIREMENTS:**
{context_info}

**USER REQUEST:** {prompt}

**MISSION:** Create a SOPHISTICATED, ENTERPRISE-GRADE, PRODUCTION-READY project that matches the complexity and scale of the requirements.

**PROJECT ANALYSIS FRAMEWORK:**
1. **COMPLEXITY ASSESSMENT**: Analyze requirements to determine project scale (simple CRUD vs enterprise system)
2. **ARCHITECTURE DESIGN**: Choose appropriate patterns (Monolithic, Microservices, Layered, Event-Driven)
3. **TECH STACK SELECTION**: Recommend technologies based on requirements and scale
4. **SECURITY STRATEGY**: Design comprehensive security measures
5. **PERFORMANCE PLANNING**: Optimize for scalability and efficiency
6. **MAINTAINABILITY**: Ensure long-term code quality and team collaboration

**ENTERPRISE-LEVEL DELIVERABLES**:
1. **Sophisticated Architecture** - Clean architecture, SOLID principles, design patterns
2. **Production-Ready Code** - Error handling, logging, monitoring, security
3. **Comprehensive Testing** - Unit, integration, e2e tests with high coverage
4. **Security Implementation** - Authentication, authorization, input validation, protection
5. **Performance Optimization** - Caching, database optimization, async patterns
6. **Deployment Infrastructure** - Docker, Kubernetes, CI/CD, monitoring
7. **Documentation** - API docs, architecture decisions, deployment guides

🏗️ **GENERATION PROCESS**:
1. **DEEP ANALYSIS** - Understand requirements complexity and scale
2. **ARCHITECTURE DESIGN** - Create sophisticated, scalable architecture
3. **TECH STACK SELECTION** - Choose appropriate technologies
4. **IMPLEMENTATION** - Generate enterprise-grade code files
5. **QUALITY ASSURANCE** - Validate, test, and optimize
6. **DEPLOYMENT READY** - Complete infrastructure and documentation

📁 **ENTERPRISE FILE STRUCTURE**:
```
project-name/
├── src/ (or app/)
│   ├── api/ (API layer with routes, middleware, validation)
│   ├── core/ (business logic with services, models, repositories)
│   ├── infrastructure/ (database, cache, external integrations)
│   ├── utils/ (shared utilities, helpers, constants)
│   └── tests/ (comprehensive test suite)
├── config/ (environment-specific configurations)
├── docs/ (comprehensive documentation)
├── deployment/ (Docker, K8s, infrastructure as code)
├── monitoring/ (logging, metrics, alerts)
├── scripts/ (build, deployment, maintenance)
└── [architecture-specific directories]
```

💻 **ENTERPRISE CODE REQUIREMENTS**:
- **Production-Ready**: Handle edge cases, errors, real-world scenarios
- **Security-First**: Authentication, authorization, input validation, protection
- **Performance-Optimized**: Efficient algorithms, caching, database optimization
- **Observable**: Comprehensive logging, monitoring, error tracking
- **Testable**: Unit tests, integration tests, testable design
- **Maintainable**: Clean code, documentation, modular design
- **Scalable**: Designed for growth and high load
- **Deployable**: Complete infrastructure and deployment configs

🎨 **OUTPUT FORMAT**:
For each file, use EXACTLY this format:
```
📄 **path/to/filename.ext**
```ext
[SOPHISTICATED, ENTERPRISE-GRADE CODE WITH ALL IMPORTS, ERROR HANDLING, LOGGING, SECURITY, PERFORMANCE OPTIMIZATION, ETC.]
```
```

🔍 **INTERACTIVE FEATURES**:
- Provide architectural recommendations based on complexity
- Suggest performance and security improvements
- Offer scalability solutions
- Request clarification for complex requirements
- Propose enterprise-grade patterns and practices

📊 **QUALITY ASSURANCE**:
- Validate all generated code for production readiness
- Ensure security best practices are implemented
- Check performance and scalability considerations
- Verify deployment and infrastructure configurations
- Test setup and deployment instructions

**CONTEXT-AWARE IMPLEMENTATION:**
- If simple CRUD app: Clean, simple, maintainable code
- If complex enterprise system: Sophisticated patterns, security, scalability
- If real-time features: Async/event-driven patterns
- If high security: Comprehensive security measures
- If high performance: Optimization strategies

**USER REQUEST:** {prompt}

**GENERATE A SOPHISTICATED, ENTERPRISE-GRADE, PRODUCTION-READY PROJECT WITH ALL FILES.**
"""

def fetch_git_repository(repo_url):
    """Fetch repository files from Git URL"""
    try:
        if st.session_state.git_integration is None:
            try:
                github_token = st.secrets.get("GITHUB_TOKEN", None)
            except (FileNotFoundError, KeyError):
                github_token = None
            st.session_state.git_integration = GitRepositoryIntegration(github_token)
        
        repo_info, files = st.session_state.git_integration.fetch_repository(repo_url)
        return repo_info, files
    except Exception as e:
        st.error(f"❌ Failed to fetch repository: {str(e)}")
        return None, {}

def _create_agent_specific_project_prompt(action_type, prompt, selected_agent, rag_context):
    """Create enhanced prompts for agent-specific project generation."""
    
    context_info = ""
    if rag_context:
        context_files = "\n".join([f"File: {result['file']}\nContent: {result['content'][:800]}..." 
                                 for result in rag_context])
        context_info = f"\nRELEVANT PROJECT CONTEXT (from RAG):\n{context_files}\n"
    
    if action_type == "code":
        return f"""
        Generate a complete code solution with multiple files for: {prompt}
        
        {context_info}
        
        Create a project structure with:
        1. Main implementation files
        2. Supporting utility files
        3. Configuration files
        4. Test files
        5. Documentation files
        
        Ensure all code is production-ready and follows best practices.
        """
    
    elif action_type == "review":
        return f"""
        Perform comprehensive code review and generate improved code files for: {prompt}
        
        {context_info}
        
        Generate:
        1. Detailed code review report
        2. Improved/fixed code files
        3. Best practices recommendations
        4. Performance optimization suggestions
        5. Security improvements
        
        Provide complete, working implementations of all improvements.
        """
    
    elif action_type == "security":
        return f"""
        Perform security analysis and generate secure code implementations for: {prompt}
        
        {context_info}
        
        Generate:
        1. Security vulnerability report
        2. Secure code implementations
        3. Security best practices guide
        4. Authentication and authorization code
        5. Input validation and sanitization examples
        
        Provide production-ready secure code files.
        """
    
    return prompt

def generate_agent_response(prompt, agent_type, model_name, rag_context=None, files_context=None):
    """Generate response using selected agent type with RAG context."""
    
    # Build enhanced prompt based on agent type and available context
    context_info = ""
    
    # Detect simple requests early to avoid loading large context
    if agent_type == "🚀 Project Generator":
        simple_keywords = ["hi", "hello", "thanks", "thank you", "ok", "okay", "good", "great"]
        # Exclude systematic generation keywords from simple request detection
        systematic_keywords = ["option", "stack", "group", "continue", "generate", "django", "fastapi", "flask", "react", "1", "2", "3"]
        has_systematic_keyword = any(keyword in prompt.lower() for keyword in systematic_keywords)
        
        is_simple_request = (
            not has_systematic_keyword and (
                len(prompt.split()) <= 2 or 
                any(prompt.lower().strip() in [word, word + "!", word + "."] for word in simple_keywords) or
                (len(prompt) < 15 and not any(char.isdigit() for char in prompt))
            )
        )
    else:
        is_simple_request = False

    # For ALL agents, use uploaded project files when available (but skip for simple requests to avoid size issues)
    if st.session_state.project_context.get('indexed') and not is_simple_request:
        # Include complete project files context for all agents
        files_dict = st.session_state.project_context.get('files', {})
        if files_dict:
            project_files = []
            for filename, content in files_dict.items():
                # For Project Generator, include much more content from requirements documents
                if agent_type == "🚀 Project Generator":
                    # Include full content for requirements documents (Word docs, PDFs, etc.)
                    if any(ext in filename.lower() for ext in ['.docx', '.doc', '.pdf', '.txt', '.md']):
                        # Keep full content for requirements documents
                        truncated_content = content[:8000] + "..." if len(content) > 8000 else content
                    else:
                        # Regular truncation for code files
                        truncated_content = content[:2000] + "..." if len(content) > 2000 else content
                else:
                    # Regular truncation for other agents
                    truncated_content = content[:2000] + "..." if len(content) > 2000 else content
                project_files.append(f"📄 **{filename}**:\n```\n{truncated_content}\n```")
            context_info = f"\n🔍 **UPLOADED PROJECT FILES**:\n\n" + "\n\n---\n\n".join(project_files) + "\n"
        elif rag_context:
            # Only fallback to RAG if no direct files available
            context_files = "\n".join([f"File: {result['file']}\nContent: {result['content'][:800]}..." 
                                     for result in rag_context])
            context_info = f"\nRELEVANT PROJECT CONTEXT (from RAG):\n{context_files}\n"
    elif not is_simple_request:
        # If no project uploaded, use RAG or file context (but not for simple requests)
        if rag_context:
            context_files = "\n".join([f"File: {result['file']}\nContent: {result['content'][:800]}..." 
                                     for result in rag_context])
            context_info = f"\nRELEVANT PROJECT CONTEXT (from RAG):\n{context_files}\n"
        elif files_context:
            context_info = f"\nUploaded Files Context:\n{files_context[:2000]}...\n"
    
    if agent_type == "🚀 Project Generator":
        # Check if this is a follow-up conversation or fresh project request
        is_followup = len(st.session_state.chat_history) > 1 and any(
            msg.get("role") == "assistant" for msg in st.session_state.chat_history
        )
        
        # Detect follow-up keywords
        followup_keywords = ["fix", "add", "modify", "change", "update", "improve", "explain", "how", "why", "error", "issue", "problem", "help"]
        is_followup_request = any(keyword in prompt.lower() for keyword in followup_keywords)
        
        # Use interactive workflow for Project Generator
        if not is_simple_request:
            # Check if this is the start of a new project generation
            if st.session_state.project_generation_state["workflow_step"] == "initial":
                # Start the interactive workflow
                context_prompt = f"""
You are a senior software architect starting a new project generation workflow.

**PROJECT REQUIREMENTS:**
{context_info}

**USER REQUEST:** {prompt}

**WORKFLOW INITIATION:**
I'm starting the interactive project generation process. Here's what will happen:

1. **Requirements Analysis** - I'll analyze your requirements and suggest tech stack options
2. **Tech Stack Selection** - You'll choose from suggested options or provide custom tech stack
3. **Architecture Design** - I'll design the complete project architecture for your review
4. **Group-by-Group Generation** - I'll generate complete, working code files in logical groups
5. **Final Download** - You'll get the complete project as a downloadable ZIP

**NEXT STEP:** I'll analyze your requirements and suggest the best technology stack options.

Let me start by analyzing your requirements and suggesting appropriate technology stacks...
"""
            else:
                # Continue with existing workflow or handle follow-up requests
                context_prompt = generate_comprehensive_project_prompt(prompt, context_info, is_followup and is_followup_request)
        else:
            # Light prompt for simple requests like greetings
            context_prompt = f"""
You are a helpful senior developer assistant. 

**SIMPLE REQUEST:** {prompt}

**CONTEXT:** We're working on a project together. Respond naturally and helpfully to this simple request.

**INSTRUCTIONS:**
- Keep the response brief and friendly
- If it's a greeting, acknowledge it and ask how you can help
- If it's a simple question, answer directly
- Reference our ongoing work if relevant
- Use emojis and visual elements when appropriate

**RESPOND TO:** {prompt}
"""
    
    elif agent_type == "🔍 Project Analyzer":
        if st.session_state.project_context.get('indexed'):
            context_prompt = f"""
You are a Senior Technical Lead providing project onboarding. Analyze the uploaded project: {prompt}

{context_info}

ONBOARDING MISSION:
Help new team members understand this project quickly and thoroughly for seamless onboarding.

ANALYSIS FRAMEWORK:
1. **Project Overview**: What this project does and its main purpose
2. **Architecture & Structure**: How the code is organized and why
3. **Technology Stack**: Languages, frameworks, libraries used
4. **Key Components**: Main modules, classes, and their relationships
5. **Data Flow**: How data moves through the system
6. **Setup Instructions**: How to get the project running locally
7. **Development Workflow**: How to contribute and make changes
8. **Dependencies**: External services, databases, APIs needed
9. **Testing Strategy**: How testing is organized and executed
10. **Deployment Process**: How the project goes to production

ONBOARDING DELIVERABLES:
- Clear project summary for quick understanding
- Folder structure explanation with purpose of each directory
- Key files and their roles
- Setup and run instructions
- Development best practices for this project
- Common tasks and how to perform them

Base analysis on the ACTUAL uploaded project files. Be thorough yet accessible for new team members.
"""
        else:
            context_prompt = f"""
You are a Senior Technical Lead. Analyze this project concept: {prompt}

{context_info}

Note: No project files uploaded. Upload your project files for detailed analysis and onboarding guidance.

Provide general project planning guidance:
1. **Project Planning**: How to structure and organize the project
2. **Technology Recommendations**: Suitable tech stack suggestions
3. **Architecture Patterns**: Recommended design patterns and structures
4. **Development Process**: Best practices for development workflow
5. **Documentation Strategy**: How to document the project effectively
"""
    
    elif agent_type == "🛠️ Code Assistant":
        if st.session_state.project_context.get('indexed'):
            context_prompt = f"""
You are an Expert Developer Assistant working on an existing project. Task: {prompt}

{context_info}

PROJECT EXTENSION MISSION:
Understand the existing codebase and create new functionality that integrates seamlessly.

TASK APPROACH:
1. **Analyze Existing Code**: Understand current architecture, patterns, and conventions
2. **Identify Integration Points**: Where new code should connect to existing system
3. **Maintain Consistency**: Follow existing code style, naming conventions, and patterns
4. **Create New Features**: Build requested functionality with proper integration
5. **Update Dependencies**: Add any new required packages or configurations
6. **Provide Integration Guide**: Clear instructions on how to integrate the new code

DELIVERABLES:
- New source code files that follow existing project conventions
- Modified existing files (if needed) with clear change indicators
- Updated configuration files (dependencies, environment variables)
- Integration instructions and testing guidance
- Documentation updates for new features

CODE REQUIREMENTS:
- Follow the EXACT coding style and patterns found in existing files
- Use the same frameworks, libraries, and design patterns already in use
- Ensure new code integrates smoothly without breaking existing functionality
- Include proper error handling and logging consistent with existing code
- Add appropriate tests following existing test patterns

Request: {prompt}
"""
        else:
            context_prompt = f"""
You are an Expert Developer Assistant. Task: {prompt}

{context_info}

Note: No existing project uploaded. Upload your project files first for me to:
- Understand your current codebase
- Follow your existing patterns and conventions  
- Create code that integrates seamlessly
- Maintain consistency with your project structure

For now, I can provide general development guidance:
1. **Code Generation**: Best practices for writing clean, maintainable code
2. **Integration Patterns**: Common ways to extend existing applications
3. **Development Workflow**: Recommended approaches for adding new features
4. **Security**: General security considerations
5. **Performance**: Common optimization opportunities
6. **Testing**: General testability suggestions

Provide actionable feedback and best practices.
"""
    
    
    else:
        context_prompt = f"{context_info}\n{prompt}"
    
    # Generate response based on model
    if model_name.startswith("gemini"):
        return generate_gemini_response([{"role": "user", "content": context_prompt}], model_name=model_name)
    elif model_name.startswith("openai"):
        return generate_openai_response([{"role": "user", "content": context_prompt}], model_name=model_name)
    else:
        return generate_openai_response([{"role": "user", "content": context_prompt}], model_name=model_name)

def analyze_requirements_and_suggest_tech_stack(prompt, context_info):
    """Analyze requirements and suggest appropriate tech stack."""
    analysis_prompt = f"""
You are a senior software architect analyzing project requirements.

**PROJECT REQUIREMENTS:**
{context_info}

**USER REQUEST:** {prompt}

**TASK:** Analyze the requirements and suggest the most appropriate technology stack.

**OUTPUT FORMAT:**
```
PROJECT ANALYSIS:
[Brief analysis of requirements]

TECH STACK OPTIONS:

Option 1: [Name] - [Brief description]
- Frontend: [Technology]
- Backend: [Technology] 
- Database: [Technology]
- Additional: [Other tools]

Option 2: [Name] - [Brief description]
- Frontend: [Technology]
- Backend: [Technology]
- Database: [Technology]
- Additional: [Other tools]

Option 3: [Name] - [Brief description]
- Frontend: [Technology]
- Backend: [Technology]
- Database: [Technology]
- Additional: [Other tools]

RECOMMENDATION: [Which option is best and why]
```

Provide concise, focused recommendations.
"""
    
    # Generate analysis using the current model
    selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
    if selected_model.startswith("gemini"):
        return generate_gemini_response([{"role": "user", "content": analysis_prompt}], model_name=selected_model)
    else:
        return generate_openai_response([{"role": "user", "content": analysis_prompt}], model_name=selected_model)

def validate_custom_tech_stack(custom_tech_stack, requirements):
    """Validate if the custom tech stack is feasible for the requirements."""
    validation_prompt = f"""
You are a senior software architect validating a custom tech stack.

**PROJECT REQUIREMENTS:**
{requirements}

**CUSTOM TECH STACK:**
{custom_tech_stack}

**TASK:** Evaluate if this tech stack is feasible and appropriate for the requirements.

**EVALUATION CRITERIA:**
1. **Compatibility**: Are the technologies compatible with each other?
2. **Scalability**: Can this stack handle the expected load?
3. **Performance**: Will this stack meet performance requirements?
4. **Security**: Are there any security concerns with this stack?
5. **Maintainability**: Is this stack maintainable and well-supported?
6. **Learning Curve**: What's the complexity for development team?

**OUTPUT FORMAT:**
```
VALIDATION RESULT: [FEASIBLE/NEEDS_MODIFICATIONS/NOT_RECOMMENDED]

ANALYSIS:
[Detailed analysis of the tech stack]

STRENGTHS:
- [Strength 1]
- [Strength 2]

CONCERNS:
- [Concern 1]
- [Concern 2]

RECOMMENDATIONS:
- [Recommendation 1]
- [Recommendation 2]

ALTERNATIVE SUGGESTIONS:
[If not recommended, suggest alternatives]
```

Provide honest, thorough evaluation with specific recommendations.
"""
    
    selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
    if selected_model.startswith("gemini"):
        return generate_gemini_response([{"role": "user", "content": validation_prompt}], model_name=selected_model)
    else:
        return generate_openai_response([{"role": "user", "content": validation_prompt}], model_name=selected_model)

def generate_project_architecture(requirements, tech_stack):
    """Generate detailed project architecture and file structure."""
    # Truncate requirements to avoid large requests
    truncated_requirements = requirements[:1000] + "..." if len(requirements) > 1000 else requirements
    
    architecture_prompt = f"""
You are a SENIOR SOFTWARE ARCHITECT with 15+ years of experience designing enterprise-scale applications.

**PROJECT REQUIREMENTS:**
{truncated_requirements}

**SELECTED TECH STACK:**
{tech_stack}

**MISSION:** Analyze the project requirements deeply and design a sophisticated, enterprise-grade architecture that matches the complexity and scale of the project.

**ARCHITECTURE ANALYSIS FRAMEWORK:**
1. **COMPLEXITY ASSESSMENT**: Analyze the requirements to determine if this is a simple app, medium complexity, or enterprise-scale system
2. **SCALABILITY REQUIREMENTS**: Identify if the system needs to handle high load, multiple users, or complex data processing
3. **INTEGRATION NEEDS**: Determine what external services, APIs, or databases are required
4. **SECURITY REQUIREMENTS**: Assess authentication, authorization, data protection needs
5. **PERFORMANCE CONSIDERATIONS**: Identify bottlenecks and optimization opportunities
6. **MAINTAINABILITY**: Design for long-term code maintainability and team collaboration

**ARCHITECTURE DESIGN PRINCIPLES:**
- **Microservices vs Monolith**: Choose based on complexity and team size
- **Layered Architecture**: Separate concerns (presentation, business logic, data access)
- **Domain-Driven Design**: For complex business logic
- **Event-Driven Architecture**: For real-time features and scalability
- **API-First Design**: For modern applications
- **Security by Design**: Built-in security at every layer
- **Observability**: Comprehensive logging, monitoring, and debugging

**OUTPUT FORMAT:**
```
PROJECT COMPLEXITY ANALYSIS:
[Detailed analysis of project complexity and requirements]

ARCHITECTURE OVERVIEW:
[High-level architecture description with design patterns and rationale]

TECHNICAL DECISIONS:
- Architecture Pattern: [Monolithic/Microservices/Layered/Event-Driven]
- Design Patterns: [List of specific patterns used]
- Security Strategy: [Authentication, authorization, data protection]
- Performance Strategy: [Caching, optimization, scaling]
- Data Strategy: [Database design, ORM, migrations]
- API Strategy: [REST/GraphQL, versioning, documentation]

FILE STRUCTURE:
```
project-name/
├── src/ (or app/)
│   ├── api/ (API layer)
│   │   ├── routes/ (API endpoints)
│   │   ├── middleware/ (authentication, validation, etc.)
│   │   ├── serializers/ (request/response models)
│   │   └── validators/ (input validation)
│   ├── core/ (business logic)
│   │   ├── services/ (business services)
│   │   ├── models/ (domain models)
│   │   ├── repositories/ (data access)
│   │   └── exceptions/ (custom exceptions)
│   ├── infrastructure/ (external integrations)
│   │   ├── database/ (database setup, migrations)
│   │   ├── cache/ (caching layer)
│   │   ├── external/ (third-party APIs)
│   │   └── messaging/ (queues, events)
│   ├── utils/ (shared utilities)
│   │   ├── helpers/ (helper functions)
│   │   ├── decorators/ (custom decorators)
│   │   └── constants/ (application constants)
│   └── tests/ (comprehensive test suite)
│       ├── unit/ (unit tests)
│       ├── integration/ (integration tests)
│       ├── e2e/ (end-to-end tests)
│       └── fixtures/ (test data)
├── config/ (configuration management)
│   ├── environments/ (dev, staging, prod)
│   ├── logging/ (log configurations)
│   └── security/ (security settings)
├── docs/ (comprehensive documentation)
│   ├── api/ (API documentation)
│   ├── architecture/ (architecture decisions)
│   ├── deployment/ (deployment guides)
│   └── development/ (development guides)
├── deployment/ (deployment configurations)
│   ├── docker/ (Docker configurations)
│   ├── kubernetes/ (K8s manifests)
│   ├── terraform/ (infrastructure as code)
│   └── scripts/ (deployment scripts)
├── monitoring/ (observability)
│   ├── logging/ (log aggregation)
│   ├── metrics/ (performance metrics)
│   └── alerts/ (alerting rules)
└── [other directories based on complexity]
```

FILE GROUPS FOR GENERATION:
Group 1: Core Infrastructure & Configuration
- [List of foundational files]

Group 2: API Layer & Middleware
- [List of API-related files]

Group 3: Business Logic & Services
- [List of core business logic files]

Group 4: Data Layer & Models
- [List of data access and model files]

Group 5: External Integrations & Utilities
- [List of integration and utility files]

Group 6: Testing & Documentation
- [List of test and documentation files]

Group 7: Deployment & DevOps
- [List of deployment and monitoring files]

SETUP INSTRUCTIONS:
[Detailed setup instructions for the specific architecture]
```

**IMPORTANT:** Design the architecture based on the ACTUAL complexity of the requirements. If this is a simple CRUD app, keep it simple. If it's a complex enterprise system, design accordingly with proper layers, security, and scalability.
"""
    
    selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
    if selected_model.startswith("gemini"):
        return generate_gemini_response([{"role": "user", "content": architecture_prompt}], model_name=selected_model)
    else:
        return generate_openai_response([{"role": "user", "content": architecture_prompt}], model_name=selected_model)

def generate_file_group(group_name, file_list, requirements, tech_stack, architecture, previous_groups=None):
    """Generate a specific group of files with complete, working code."""
    
    # Truncate requirements to avoid large requests
    truncated_requirements = requirements[:800] + "..." if len(requirements) > 800 else requirements
    truncated_architecture = architecture[:1000] + "..." if len(architecture) > 1000 else architecture
    
    # Build minimal context from previous groups
    previous_context = ""
    if previous_groups:
        previous_context = "\n\nPREVIOUSLY GENERATED FILES:\n"
        for group in previous_groups:
            previous_context += f"\n{group['name']}:\n"
            for file_path in list(group['files'].keys())[:5]:  # Limit to 5 files
                previous_context += f"- {file_path}\n"
    
    group_prompt = f"""
You are a SENIOR FULL-STACK DEVELOPER with 10+ years of experience building enterprise-scale applications.

**PROJECT REQUIREMENTS:**
{truncated_requirements}

**SELECTED TECH STACK:**
{tech_stack}

**CURRENT GROUP:** {group_name}
**FILES TO GENERATE:**
{chr(10).join(f"- {file}" for file in file_list[:10])}

{previous_context}

**MISSION:** Create SOPHISTICATED, ENTERPRISE-GRADE, PRODUCTION-READY code files that match the complexity and scale of the project requirements.

**CODE GENERATION FRAMEWORK:**

🏗️ **ARCHITECTURE AWARENESS:**
- Analyze the file's role in the overall architecture
- Implement appropriate design patterns (Repository, Service, Factory, etc.)
- Follow SOLID principles and clean architecture
- Use dependency injection where appropriate
- Implement proper separation of concerns

🔒 **SECURITY FIRST:**
- Input validation and sanitization at every layer
- Authentication and authorization mechanisms
- SQL injection prevention
- XSS protection
- CSRF protection
- Secure configuration management
- Environment variable usage for secrets

📊 **PERFORMANCE & SCALABILITY:**
- Efficient algorithms and data structures
- Database query optimization
- Caching strategies (Redis, in-memory)
- Connection pooling
- Async/await patterns where appropriate
- Resource management and cleanup

🧪 **TESTABILITY & QUALITY:**
- Unit testable code with dependency injection
- Mock-friendly interfaces
- Comprehensive error handling
- Proper exception hierarchies
- Input validation and business rule enforcement
- Logging at appropriate levels (DEBUG, INFO, WARNING, ERROR)

📚 **MAINTAINABILITY:**
- Clear, descriptive variable and function names
- Comprehensive docstrings and comments
- Type hints throughout
- Consistent code style and formatting
- Modular design with single responsibility
- Configuration-driven behavior

**IMPLEMENTATION REQUIREMENTS:**

🎯 **FOR EACH FILE:**
1. **COMPLETE FUNCTIONALITY**: Every function, class, and method fully implemented
2. **ALL DEPENDENCIES**: Include all necessary imports and external libraries
3. **ERROR HANDLING**: Comprehensive try-catch blocks with proper error messages
4. **LOGGING**: Structured logging with appropriate levels and context
5. **CONFIGURATION**: Environment-based configuration with validation
6. **SECURITY**: Input validation, authentication, and security measures
7. **DOCUMENTATION**: Clear docstrings, type hints, and inline comments
8. **TESTING**: Unit tests and integration test examples
9. **VALIDATION**: Input validation and business rule enforcement
10. **OPTIMIZATION**: Performance considerations and best practices

💻 **CODE QUALITY STANDARDS:**
- **Production-Ready**: Handle edge cases, errors, and real-world scenarios
- **Best Practices**: Follow language and framework conventions
- **Documentation**: Comprehensive docstrings and comments
- **Logging**: Structured logging with proper levels
- **Configuration**: Environment-based with validation
- **Security**: Input validation, authentication, and protection
- **Performance**: Efficient algorithms and resource management
- **Maintainability**: Clean, readable, and modular code
- **Testability**: Easy to test with proper abstractions
- **Scalability**: Designed for growth and high load

📁 **OUTPUT FORMAT:**
For each file, use EXACTLY this format:
```
📄 **path/to/filename.ext**
```ext
[COMPLETE, SOPHISTICATED FILE CONTENT WITH ALL IMPORTS, FUNCTIONS, CLASSES, ERROR HANDLING, LOGGING, SECURITY, ETC.]
```
```

🚨 **CRITICAL REQUIREMENTS:**
- **NO PLACEHOLDER CODE**: Every function must be fully implemented
- **NO TODO COMMENTS**: Complete all implementations
- **NO SKELETON FILES**: Full, working, executable code
- **ENTERPRISE QUALITY**: Production-ready with proper error handling
- **SECURITY FOCUSED**: Built-in security at every layer
- **PERFORMANCE OPTIMIZED**: Efficient and scalable implementations
- **WELL DOCUMENTED**: Clear documentation and comments
- **TESTABLE**: Easy to test with proper abstractions

**CONTEXT-AWARE IMPLEMENTATION:**
- If this is a simple CRUD app, implement clean, simple code
- If this is a complex enterprise system, implement sophisticated patterns
- If this involves real-time features, implement async/event-driven patterns
- If this involves high security, implement comprehensive security measures
- If this involves high performance, implement optimization strategies

Generate ALL files in this group with sophisticated, enterprise-grade, production-ready code that can be immediately executed and deployed.
"""
    
    selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
    if selected_model.startswith("gemini"):
        return generate_gemini_response([{"role": "user", "content": group_prompt}], model_name=selected_model)
    else:
        return generate_openai_response([{"role": "user", "content": group_prompt}], model_name=selected_model)

def parse_file_groups_from_architecture(architecture_response):
    """Parse file groups from the architecture response."""
    import re
    
    # Check if response is empty or too short
    if not architecture_response or len(architecture_response.strip()) < 50:
        return []
    
    # Look for group sections allowing file lists with or without leading dashes
    groups_pattern = r'Group \d+:\s*([^\n]+?)\s*\n(.*?)(?=\n\s*Group \d+|$)'
    matches = re.findall(groups_pattern, architecture_response, re.DOTALL)
    
    file_groups = []
    for group_name, files_text in matches:
        # Extract file paths from the list
        files = []
        for line in files_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('-'):
                line = line[1:].strip()
            if line:
                files.append(line)
        
        if files:
            file_groups.append({
                'name': group_name.strip(),
                'files': files
            })
    
    # If no groups found, try alternative pattern
    if not file_groups:
        # Look for any pattern that might contain file groups
        alt_pattern = r'([A-Za-z\s&]+Files?|Configuration|Setup|Documentation|Tests?|Deployment)\s*:\s*\n(.*?)(?=\n\s*(?:[A-Za-z\s&]+Files?|Configuration|Setup|Documentation|Tests?|Deployment)\s*:|$)'
        alt_matches = re.findall(alt_pattern, architecture_response, re.DOTALL)
        
        for group_name, files_text in alt_matches:
            files = []
            for line in files_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith('-'):
                    line = line[1:].strip()
                if line:
                    files.append(line)
            
            if files:
                file_groups.append({
                    'name': group_name.strip(),
                    'files': files
                })
    
    # If still no groups found, create default groups based on tech stack
    if not file_groups:
        file_groups = create_default_file_groups()
    
    return file_groups

def create_default_file_groups():
    """Create default file groups when parsing fails."""
    return [
        {
            'name': 'Core Application Files',
            'files': [
                'src/main.py',
                'src/app.py',
                'src/__init__.py',
                'src/config.py',
                'src/utils.py'
            ]
        },
        {
            'name': 'Configuration & Setup',
            'files': [
                'requirements.txt',
                'package.json',
                '.env.example',
                '.gitignore',
                'README.md'
            ]
        },
        {
            'name': 'Documentation & Tests',
            'files': [
                'tests/__init__.py',
                'tests/test_main.py',
                'docs/README.md',
                'docs/API.md'
            ]
        },
        {
            'name': 'Deployment & DevOps',
            'files': [
                'Dockerfile',
                'docker-compose.yml',
                'deployment/scripts/start.sh'
            ]
        }
    ]

def get_file_extension(file_path):
    """Get the file extension for syntax highlighting."""
    import os
    _, ext = os.path.splitext(file_path)
    ext = ext.lower().lstrip('.')
    
    # Map common extensions to language identifiers
    extension_map = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'md': 'markdown',
        'txt': 'text',
        'yml': 'yaml',
        'yaml': 'yaml',
        'sh': 'bash',
        'dockerfile': 'dockerfile',
        'env': 'bash',
        'gitignore': 'gitignore',
        'sql': 'sql',
        'java': 'java',
        'cpp': 'cpp',
        'c': 'c',
        'php': 'php',
        'rb': 'ruby',
        'go': 'go',
        'rs': 'rust',
        'swift': 'swift',
        'kt': 'kotlin',
        'scala': 'scala'
    }
    
    return extension_map.get(ext, 'text')

def create_basic_files_for_group(group):
    """Create basic file content for a group when API generation fails."""
    basic_files = {}
    
    if group['name'] == 'Core Application Files':
        basic_files['src/main.py'] = '''#!/usr/bin/env python3
"""
Main application entry point.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main application function."""
    try:
        logger.info("Starting application...")
        
        # Initialize application
        from src.app import App
        app = App()
        
        # Run the application
        success = app.run()
        
        if success:
            logger.info("Application completed successfully")
            return 0
        else:
            logger.error("Application failed")
            return 1
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
        basic_files['src/app.py'] = '''"""
Main application module.
"""

import os
import logging
from typing import Optional, Dict, Any
from src.config import Config
from src.utils import setup_logging, validate_input

logger = logging.getLogger(__name__)

class App:
    """Main application class."""
    
    def __init__(self):
        """Initialize the application."""
        self.name = "My Application"
        self.config = Config()
        self.logger = logger
        self.is_running = False
        
        # Setup logging
        setup_logging()
        
        logger.info(f"Initializing {self.name}")
    
    def run(self) -> bool:
        """Run the application."""
        try:
            logger.info(f"Starting {self.name}")
            self.is_running = True
            
            # Main application logic here
            self._initialize_components()
            self._start_services()
            self._run_main_loop()
            
            logger.info(f"{self.name} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error running {self.name}: {str(e)}")
            return False
        finally:
            self.is_running = False
    
    def _initialize_components(self):
        """Initialize application components."""
        logger.info("Initializing components...")
        # Add your component initialization here
        
    def _start_services(self):
        """Start application services."""
        logger.info("Starting services...")
        # Add your service startup here
        
    def _run_main_loop(self):
        """Run the main application loop."""
        logger.info("Running main loop...")
        # Add your main application logic here
        
    def stop(self):
        """Stop the application."""
        logger.info(f"Stopping {self.name}")
        self.is_running = False

if __name__ == "__main__":
    app = App()
    success = app.run()
    exit(0 if success else 1)
'''
        basic_files['src/config.py'] = '''"""
Configuration settings and environment management.
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """Application configuration manager."""
    
    def __init__(self):
        """Initialize configuration."""
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables."""
        # Application settings
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
        self.APP_NAME = os.getenv('APP_NAME', 'My Application')
        self.APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
        
        # Database settings
        self.DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        self.DATABASE_POOL_SIZE = int(os.getenv('DATABASE_POOL_SIZE', '10'))
        self.DATABASE_MAX_OVERFLOW = int(os.getenv('DATABASE_MAX_OVERFLOW', '20'))
        
        # Server settings
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.PORT = int(os.getenv('PORT', '8000'))
        
        # Security settings
        self.ENABLE_CORS = os.getenv('ENABLE_CORS', 'True').lower() == 'true'
        self.CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
        
        # Logging settings
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE = os.getenv('LOG_FILE', 'app.log')
        
        logger.info("Configuration loaded successfully")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return getattr(self, key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'DEBUG': self.DEBUG,
            'APP_NAME': self.APP_NAME,
            'APP_VERSION': self.APP_VERSION,
            'DATABASE_URL': self.DATABASE_URL,
            'HOST': self.HOST,
            'PORT': self.PORT,
            'ENABLE_CORS': self.ENABLE_CORS,
            'LOG_LEVEL': self.LOG_LEVEL
        }
    
    def validate(self) -> bool:
        """Validate configuration."""
        required_fields = ['SECRET_KEY', 'DATABASE_URL']
        for field in required_fields:
            if not getattr(self, field, None):
                logger.error(f"Missing required configuration: {field}")
                return False
        return True

# Global configuration instance
config = Config()
'''
        basic_files['src/utils.py'] = '''"""
Utility functions and helper modules.
"""

import os
import sys
import logging
import json
import hashlib
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        format_string: Optional custom format string
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=handlers
    )
    
    logger.info(f"Logging configured with level: {level}")

def validate_input(data: Any, required_type: type = str, min_length: int = 1) -> bool:
    """Validate input data.
    
    Args:
        data: Data to validate
        required_type: Expected data type
        min_length: Minimum length for string data
    
    Returns:
        True if valid, False otherwise
    """
    if data is None:
        return False
    
    if not isinstance(data, required_type):
        return False
    
    if isinstance(data, str) and len(data.strip()) < min_length:
        return False
    
    return True

def sanitize_input(data: str) -> str:
    """Sanitize user input to prevent injection attacks.
    
    Args:
        data: Input string to sanitize
    
    Returns:
        Sanitized string
    """
    if not isinstance(data, str):
        return str(data)
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', data)
    return sanitized.strip()

def generate_hash(data: str, algorithm: str = 'sha256') -> str:
    """Generate hash of data.
    
    Args:
        data: Data to hash
        algorithm: Hash algorithm to use
    
    Returns:
        Hash string
    """
    if algorithm == 'sha256':
        return hashlib.sha256(data.encode()).hexdigest()
    elif algorithm == 'md5':
        return hashlib.md5(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON file safely.
    
    Args:
        file_path: Path to JSON file
    
    Returns:
        Dictionary containing JSON data
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(data: Dict[str, Any], file_path: str) -> None:
    """Save data to JSON file safely.
    
    Args:
        data: Data to save
        file_path: Path to save file
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def format_timestamp(timestamp: Optional[datetime] = None) -> str:
    """Format timestamp for display.
    
    Args:
        timestamp: Timestamp to format (defaults to current time)
    
    Returns:
        Formatted timestamp string
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def ensure_directory(path: str) -> None:
    """Ensure directory exists, create if it doesn't.
    
    Args:
        path: Directory path to ensure
    """
    os.makedirs(path, exist_ok=True)

def get_file_size(file_path: str) -> int:
    """Get file size in bytes.
    
    Args:
        file_path: Path to file
    
    Returns:
        File size in bytes
    """
    if not os.path.exists(file_path):
        return 0
    
    return os.path.getsize(file_path)
'''
    
    elif group['name'] == 'Configuration & Setup':
        basic_files['requirements.txt'] = '''# Core dependencies
python-dotenv>=1.0.0
requests>=2.31.0
typing-extensions>=4.0.0

# Web framework (uncomment based on your needs)
# flask>=2.3.0
# fastapi>=0.100.0
# django>=4.2.0

# Database (uncomment based on your needs)
# sqlalchemy>=2.0.0
# psycopg2-binary>=2.9.0
# pymongo>=4.0.0

# Testing
pytest>=7.0.0
pytest-cov>=4.0.0

# Development
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0

# Add your specific dependencies here
'''
        basic_files['README.md'] = '''# My Application

## Description
A production-ready Python application with comprehensive error handling, logging, and configuration management.

## Features
- ✅ Production-ready with proper error handling
- ✅ Comprehensive logging system
- ✅ Environment-based configuration
- ✅ Input validation and sanitization
- ✅ Security best practices
- ✅ Modular architecture
- ✅ Type hints and documentation

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup
1. Clone the repository:
```bash
git clone <repository-url>
cd my-application
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Usage

### Running the Application
```bash
python src/main.py
```

### Development Mode
```bash
# Set debug mode
export DEBUG=True
python src/main.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_main.py
```

## Configuration

### Environment Variables
Copy `.env.example` to `.env` and configure:

```bash
# Application settings
DEBUG=False
SECRET_KEY=your-secret-key-change-this-in-production
APP_NAME=My Application
APP_VERSION=1.0.0

# Database settings
DATABASE_URL=sqlite:///app.db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Server settings
HOST=0.0.0.0
PORT=8000

# Security settings
ENABLE_CORS=True
CORS_ORIGINS=*

# Logging settings
LOG_LEVEL=INFO
LOG_FILE=app.log
```

## Project Structure
```
my-application/
├── src/
│   ├── main.py          # Application entry point
│   ├── app.py           # Main application class
│   ├── config.py        # Configuration management
│   └── utils.py         # Utility functions
├── tests/
│   └── test_main.py     # Test files
├── docs/                # Documentation
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .env.example        # Environment template
└── .gitignore          # Git ignore rules
```

## Development

### Code Style
This project uses:
- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking

```bash
# Format code
black src/ tests/

# Check code style
flake8 src/ tests/

# Type checking
mypy src/
```

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement your changes
3. Add tests for new functionality
4. Run tests: `pytest`
5. Submit pull request

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_main.py::test_main_function
```

### Test Structure
- Unit tests in `tests/` directory
- Test files follow `test_*.py` naming convention
- Use pytest fixtures for common setup

## Deployment

### Docker
```bash
# Build image
docker build -t my-application .

# Run container
docker run -p 8000:8000 my-application
```

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure secure `SECRET_KEY`
- [ ] Set up proper database
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline

## Troubleshooting

### Common Issues
1. **Import errors**: Ensure virtual environment is activated
2. **Configuration errors**: Check `.env` file exists and is properly formatted
3. **Permission errors**: Check file permissions for logs and data directories

### Logs
Application logs are written to:
- Console output (stdout)
- `app.log` file (if configured)

## Contributing
1. Fork the repository
2. Create feature branch
3. Make your changes
4. Add tests
5. Submit pull request

## License
MIT License - see LICENSE file for details.

## Support
For support and questions:
- Create an issue in the repository
- Check the documentation in `docs/` directory
- Review the troubleshooting section above
'''
        basic_files['.env.example'] = '''# Application Configuration
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///app.db

# Add your environment variables here
'''
        basic_files['.gitignore'] = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
'''
    
    elif group['name'] == 'Documentation & Tests':
        basic_files['tests/test_main.py'] = '''"""
Tests for main application module.
"""

import unittest
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock
from io import StringIO

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.main import main
from src.app import App
from src.config import Config
from src.utils import validate_input, sanitize_input, generate_hash

class TestMain(unittest.TestCase):
    """Test cases for main module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.main.logging.getLogger')
    @patch('src.main.App')
    def test_main_function_success(self, mock_app_class, mock_logger):
        """Test that main function runs successfully."""
        # Mock the App class
        mock_app = MagicMock()
        mock_app.run.return_value = True
        mock_app_class.return_value = mock_app
        
        # Mock logger
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Test main function
        result = main()
        
        # Assertions
        self.assertEqual(result, 0)
        mock_app_class.assert_called_once()
        mock_app.run.assert_called_once()
        mock_log.info.assert_called()
    
    @patch('src.main.logging.getLogger')
    @patch('src.main.App')
    def test_main_function_failure(self, mock_app_class, mock_logger):
        """Test that main function handles failures gracefully."""
        # Mock the App class to raise an exception
        mock_app = MagicMock()
        mock_app.run.side_effect = Exception("Test error")
        mock_app_class.return_value = mock_app
        
        # Mock logger
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Test main function
        result = main()
        
        # Assertions
        self.assertEqual(result, 1)
        mock_log.error.assert_called()
    
    @patch('src.main.logging.getLogger')
    @patch('src.main.App')
    def test_main_function_app_failure(self, mock_app_class, mock_logger):
        """Test that main function handles app.run() returning False."""
        # Mock the App class
        mock_app = MagicMock()
        mock_app.run.return_value = False
        mock_app_class.return_value = mock_app
        
        # Mock logger
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Test main function
        result = main()
        
        # Assertions
        self.assertEqual(result, 1)
        mock_log.error.assert_called()

class TestApp(unittest.TestCase):
    """Test cases for App class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = App()
    
    def test_app_initialization(self):
        """Test App initialization."""
        self.assertEqual(self.app.name, "My Application")
        self.assertFalse(self.app.is_running)
        self.assertIsNotNone(self.app.config)
        self.assertIsNotNone(self.app.logger)
    
    @patch('src.app.logging.getLogger')
    def test_app_run_success(self, mock_logger):
        """Test successful app run."""
        # Mock logger
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Test run method
        result = self.app.run()
        
        # Assertions
        self.assertTrue(result)
        self.assertFalse(self.app.is_running)
        mock_log.info.assert_called()
    
    @patch('src.app.logging.getLogger')
    def test_app_run_exception(self, mock_logger):
        """Test app run with exception."""
        # Mock logger
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        
        # Mock _initialize_components to raise exception
        self.app._initialize_components = MagicMock(side_effect=Exception("Test error"))
        
        # Test run method
        result = self.app.run()
        
        # Assertions
        self.assertFalse(result)
        self.assertFalse(self.app.is_running)
        mock_log.error.assert_called()
    
    def test_app_stop(self):
        """Test app stop method."""
        self.app.is_running = True
        self.app.stop()
        self.assertFalse(self.app.is_running)

class TestConfig(unittest.TestCase):
    """Test cases for Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config()
    
    def test_config_initialization(self):
        """Test Config initialization."""
        self.assertIsNotNone(self.config.DEBUG)
        self.assertIsNotNone(self.config.SECRET_KEY)
        self.assertIsNotNone(self.config.DATABASE_URL)
        self.assertIsNotNone(self.config.APP_NAME)
        self.assertIsNotNone(self.config.APP_VERSION)
    
    def test_config_get_method(self):
        """Test Config get method."""
        value = self.config.get('APP_NAME')
        self.assertEqual(value, self.config.APP_NAME)
        
        # Test with default value
        value = self.config.get('NONEXISTENT', 'default')
        self.assertEqual(value, 'default')
    
    def test_config_to_dict(self):
        """Test Config to_dict method."""
        config_dict = self.config.to_dict()
        self.assertIsInstance(config_dict, dict)
        self.assertIn('DEBUG', config_dict)
        self.assertIn('APP_NAME', config_dict)
        self.assertIn('DATABASE_URL', config_dict)
    
    def test_config_validate(self):
        """Test Config validate method."""
        # Should pass with default values
        self.assertTrue(self.config.validate())

class TestUtils(unittest.TestCase):
    """Test cases for utility functions."""
    
    def test_validate_input_string(self):
        """Test validate_input with string data."""
        self.assertTrue(validate_input("test"))
        self.assertTrue(validate_input("a"))
        self.assertFalse(validate_input(""))
        self.assertFalse(validate_input(None))
    
    def test_validate_input_with_type(self):
        """Test validate_input with type checking."""
        self.assertTrue(validate_input("test", str))
        self.assertTrue(validate_input(123, int))
        self.assertFalse(validate_input("test", int))
    
    def test_validate_input_with_min_length(self):
        """Test validate_input with minimum length."""
        self.assertTrue(validate_input("test", str, 1))
        self.assertTrue(validate_input("test", str, 4))
        self.assertFalse(validate_input("test", str, 5))
    
    def test_sanitize_input(self):
        """Test sanitize_input function."""
        # Test normal string
        self.assertEqual(sanitize_input("hello"), "hello")
        
        # Test string with dangerous characters
        self.assertEqual(sanitize_input("<script>alert('xss')</script>"), "scriptalert(xss)/script")
        
        # Test non-string input
        self.assertEqual(sanitize_input(123), "123")
    
    def test_generate_hash(self):
        """Test generate_hash function."""
        # Test SHA256
        hash_sha256 = generate_hash("test", "sha256")
        self.assertIsInstance(hash_sha256, str)
        self.assertEqual(len(hash_sha256), 64)  # SHA256 produces 64 character hex string
        
        # Test MD5
        hash_md5 = generate_hash("test", "md5")
        self.assertIsInstance(hash_md5, str)
        self.assertEqual(len(hash_md5), 32)  # MD5 produces 32 character hex string
        
        # Test invalid algorithm
        with self.assertRaises(ValueError):
            generate_hash("test", "invalid")

if __name__ == '__main__':
    unittest.main()
'''
        basic_files['docs/README.md'] = '''# Documentation

## Overview
This document provides an overview of the project.

## API Reference
Document your API endpoints here.

## Examples
Provide usage examples here.
'''
    
    elif group['name'] == 'Deployment & DevOps':
        basic_files['Dockerfile'] = '''# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "src/main.py"]
'''
        basic_files['docker-compose.yml'] = '''version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
    volumes:
      - .:/app
'''
    
    return basic_files

# --- Auth UI ---
def login_ui():
    st.title("🤖 MultiModel ChatBot")
    st.markdown("### Your Ultimate AI Assistant with RAG & Multi-Agent Intelligence")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("#### ✨ **Advanced Features**")
        st.markdown("""
        - 🧠 **RAG-Powered Analysis**: Upload files for intelligent context understanding
        - 🤖 **Multi-Agent System**: Specialized AI assistants for different tasks
        - 📊 **Diagram Generation**: Create visual workflows from conversations
        - 🔍 **Smart Search**: Find information across your uploaded projects
        - 💬 **Multi-Model Support**: Gemini, GPT, Claude, DeepSeek
        """)
        
        st.markdown("---")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@example.com")
            password = st.text_input("Password", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                login = st.form_submit_button("🚀 Login", use_container_width=True)
            with col2:
                signup = st.form_submit_button("📝 Sign Up", use_container_width=True)
    
    if login:
        user = sign_in(email, password)
        if user:
            st.session_state.user = user
            st.success("Welcome back!")
            st.rerun()
        else:
            st.error("Login failed. Please check your credentials.")
    
    if signup:
        user = sign_up(email, password)
        if user:
            if isinstance(user, dict) and user.get("error"):
                st.error(f"Sign up failed: {user['error']}")
            else:
                st.session_state.user = user
                st.success("Account created! Welcome!")
                st.rerun()

# --- Main Chat UI ---
def chat_ui():
    st.title("🤖 MultiModel ChatBot")
    user = st.session_state.user
    user_id = get_user_id(user)

    # Determine model type for use throughout the function
    selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
    if selected_model.startswith("gemini"):
        model_type = "gemini"
    elif selected_model.startswith("openai"):
        model_type = "openai"
    else:
        model_type = "gemini"  # Default fallback

    # --- Sidebar Layout ---
    with st.sidebar:
        st.header("🤖 AI Chat Navigation")
        
        # Model selection with provider grouping
        model_categories = {
            "Gemini": {
                "gemini-2.5-pro": "Gemini 2.5 Pro",
                "gemini-1.5-pro": "Gemini 1.5 Pro", 
                "gemini-1.5-flash": "Gemini 1.5 Flash"
            },
            "OpenAI": {
                "gpt-4o": "GPT-4o",
                "gpt-4o-mini": "GPT-4o Mini",
                "gpt-4-turbo": "GPT-4 Turbo",
                "gpt-3.5-turbo": "GPT-3.5 Turbo"
            }
        }
        
        if "selected_provider" not in st.session_state:
            st.session_state.selected_provider = "Gemini"
        if "selected_model" not in st.session_state:
            st.session_state.selected_model = "gemini-2.5-pro"
            
        provider_list = list(model_categories.keys())
        selected_provider = st.selectbox(
            "Model Provider",
            provider_list,
            index=provider_list.index(st.session_state.selected_provider),
            key="sidebar_provider"
        )
        
        if selected_provider != st.session_state.selected_provider:
            st.session_state.selected_provider = selected_provider
            st.session_state.selected_model = list(model_categories[selected_provider].keys())[0]
            st.rerun()
            
        model_dict = model_categories[selected_provider]
        model_keys = list(model_dict.keys())
        if st.session_state.selected_model not in model_keys:
            st.session_state.selected_model = model_keys[0]
            
        selected_model = st.selectbox(
            "Model Version",
            model_keys,
            format_func=lambda x: model_dict[x],
            index=model_keys.index(st.session_state.selected_model),
            key="sidebar_model"
        )
        
        if selected_model != st.session_state.selected_model:
            st.session_state.selected_model = selected_model
            st.rerun()
            
        # New Chat button
        if st.button("🆕 New Chat", key="sidebar_new_chat", use_container_width=True, type="primary"):
            # Reset session for fresh start
            reset_session_for_new_chat()
            
            new_chat_id = create_new_chat(user_id, model_type=model_type)
            st.session_state.selected_chat_id = new_chat_id
            st.session_state.chat_history = []
            st.session_state.search_query = ""
            st.rerun()
            
        # Search functionality
        search_query = st.text_input("🔍 Search chats", value=st.session_state.get("search_query", ""), key="sidebar_search")
        st.session_state.search_query = search_query
        
        # List chats (filtered)
        try:
            chat_sessions = list_user_chats(user_id, model_type)
            filtered_chats = [c for c in chat_sessions if search_query.lower() in c["title"].lower()]
            chat_ids = [c['chat_id'] for c in filtered_chats]
            
            # Use radio button for chat selection
            if chat_ids:
                selected_chat_idx = chat_ids.index(st.session_state.get("selected_chat_id")) if st.session_state.get("selected_chat_id") in chat_ids else 0
                selected_radio = st.radio(
                    "💬 Recent Chats:",
                    options=chat_ids,
                    format_func=lambda cid: (
                        ("📁 " if filtered_chats[chat_ids.index(cid)].get("has_project_files") else "") +
                        filtered_chats[chat_ids.index(cid)]["title"][:30] + 
                        ("..." if len(filtered_chats[chat_ids.index(cid)]["title"]) > 30 else "")
                    ),
                    index=selected_chat_idx,
                    key="sidebar_chat_radio"
                )
                if selected_radio != st.session_state.get("selected_chat_id"):
                    st.session_state.selected_chat_id = selected_radio
                    st.session_state.chat_history = get_chat_history(user_id, selected_radio)
                    
                    # Restore chat context with RAG
                    if RAG_AVAILABLE:
                        with st.spinner("🔄 Restoring chat context..."):
                            restore_chat_context(user_id, selected_radio)
                    
                    st.rerun()
            else:
                st.info("📝 No chats found. Create a new chat!")
                
        except Exception as e:
            st.error(f"❌ Error loading chats: {str(e)}")
            
        st.markdown("---")
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Logout", key="sidebar_logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        with col2:
            if st.session_state.get("selected_chat_id"):
                if st.button("🗑️ Delete Chat", key="sidebar_delete_chat", use_container_width=True):
                    try:
                        from firebase_utils import db
                        chat_ref = db.collection('users').document(user_id).collection('chats').document(st.session_state.selected_chat_id)
                        chat_ref.delete()
                        
                        # Refresh chat list and select new chat
                        chat_sessions = list_user_chats(user_id, model_type)
                        filtered_chats = [c for c in chat_sessions if search_query.lower() in c["title"].lower()]
                        chat_ids = [c['chat_id'] for c in filtered_chats]
                        
                        if chat_ids:
                            st.session_state.selected_chat_id = chat_ids[0]
                            st.session_state.chat_history = get_chat_history(user_id, chat_ids[0])
                        else:
                            st.session_state.selected_chat_id = None
                            st.session_state.chat_history = []
                        
                        # Reset session
                        reset_session_for_new_chat()
                        st.success("🗑️ Chat deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error deleting chat: {str(e)}")
            else:
                st.button("🗑️ Delete Chat", disabled=True, use_container_width=True)

    # --- Main Chat Window ---
    if st.session_state.get("selected_chat_id"):
        # Load chat history if needed
        if "chat_history" not in st.session_state or st.session_state.get("last_loaded_chat_id") != st.session_state.selected_chat_id:
            st.session_state.chat_history = get_chat_history(user_id, st.session_state.selected_chat_id)
            st.session_state.last_loaded_chat_id = st.session_state.selected_chat_id

        # --- ENHANCEMENT: Show current model and agent in chat header ---
        model_dict = {
            "gemini-2.5-pro": "Gemini 2.5 Pro",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
            "gpt-4-turbo": "GPT-4 Turbo",
            "gpt-3.5-turbo": "GPT-3.5 Turbo"
        }
        selected_model = st.session_state.get("selected_model", "gemini-2.5-pro")
        selected_agent = st.session_state.get("selected_agent", "🚀 Project Generator")
        model_display = model_dict.get(selected_model, selected_model)
        st.markdown(f"<div style='background:#f5f6fa;padding:10px 16px;border-radius:8px;margin-bottom:8px;'><b>Model:</b> {model_display} &nbsp; | &nbsp; <b>Agent:</b> {selected_agent}</div>", unsafe_allow_html=True)

        # Show RAG status
        if st.session_state.project_context.get('indexed'):
            total_files = st.session_state.project_context.get('total_files', 0)
            st.success(f"🧠 **RAG Active**: {total_files} files indexed for intelligent context")

        # Show project generation status
        if st.session_state.project_generation_state.get("is_generating"):
            with st.status("🚀 Generating Project...", expanded=True) as status:
                st.write("📋 Analyzing requirements...")
                st.write("🏗️ Planning architecture...")
                st.write("💻 Generating source code...")
                st.write("📝 Creating documentation...")
                st.write("🔧 Setting up configuration...")
                st.write("✅ Finalizing project structure...")
                status.update(label="🎉 Project Generation Complete!", state="complete")

        # Show project generation progress
        if st.session_state.project_generation_state.get("current_step"):
            current_step = st.session_state.project_generation_state.get("current_step")
            st.info(f"🔄 **Current Step**: {current_step}")
        
        # Show interactive workflow status
        workflow_step = st.session_state.project_generation_state.get("workflow_step", "initial")
        if workflow_step != "initial" and workflow_step != "complete":
            workflow_status = {
                "tech_stack_selection": "🎯 **Tech Stack Selection** - Choose your preferred technology stack",
                "architecture_review": "🏗️ **Architecture Review** - Review and confirm project structure",
                "group_generation": "💻 **File Generation** - Generating complete code files in groups"
            }
            
            if workflow_step in workflow_status:
                st.info(workflow_status[workflow_step])
                
                # Show progress for group generation
                if workflow_step == "group_generation":
                    file_groups = st.session_state.project_generation_state.get("file_groups", [])
                    current_group_index = st.session_state.project_generation_state.get("current_group_index", 0)
                    generated_groups = st.session_state.project_generation_state.get("generated_groups", [])
                    
                    if file_groups:
                        progress_text = f"📊 **Progress**: Group {current_group_index + 1} of {len(file_groups)}"
                        if generated_groups:
                            progress_text += f" ({len(generated_groups)} groups completed)"
                        st.success(progress_text)

        # Display chat history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                content = msg["content"]
                # --- ENHANCEMENT: Show RAG context summary above assistant responses ---
                if msg["role"] == "assistant" and msg.get("rag_context_files"):
                    rag_files = msg["rag_context_files"]
                    st.info(f"**RAG Context Used:** {', '.join(rag_files)}")
                # Check for mermaid diagrams in message
                if '```mermaid' in content:
                    mermaid_blocks = re.findall(r'```mermaid(.*?)```', content, re.DOTALL)
                    for block in mermaid_blocks:
                        render_mermaid(block.strip())
                    non_mermaid = re.sub(r'```mermaid.*?```', '', content, flags=re.DOTALL).strip()
                    if non_mermaid:
                        st.markdown(non_mermaid)
                else:
                    st.markdown(content)

        # --- PROJECT GENERATION DOWNLOAD UI ---
        if st.session_state.project_generation_state.get("generation_complete") and st.session_state.project_generation_state.get("zip_data"):
            st.markdown("---")
            st.markdown("### 🎉 **Project Generation Complete!**")
            
            # Show generated files
            generated_files = st.session_state.project_generation_state.get("generated_files", {})
            if generated_files:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("**📁 Generated Files:**")
                    with st.expander("View all generated files", expanded=False):
                        for file_path in generated_files.keys():
                            st.code(f"{file_path}")
                
                with col2:
                    # Download button
                    zip_data = st.session_state.project_generation_state.get("zip_data")
                    if zip_data:
                        st.download_button(
                            label="💾 Download Complete Project",
                            data=zip_data,
                            file_name="generated_project.zip",
                            mime="application/zip",
                            use_container_width=True,
                            type="primary"
                        )
                        
                        # Project info
                        st.info(f"📊 **Project Stats:**\n- {len(generated_files)} files\n- Ready to extract and run")
            
            # Interactive feedback section
            st.markdown("### 🔄 **Project Feedback & Iteration**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 **Regenerate Project**", use_container_width=True):
                    st.session_state.project_generation_state["generation_complete"] = False
                    st.session_state.project_generation_state["zip_data"] = None
                    st.rerun()
            
            with col2:
                if st.button("📝 **Request Changes**", use_container_width=True):
                    st.session_state.auto_send_prompt = "Please modify the generated project with the following changes: [describe your changes here]"
                    st.rerun()
            
            with col3:
                if st.button("✅ **Project Complete**", use_container_width=True):
                    st.session_state.project_generation_state = {
                        "is_generating": False,
                        "current_step": None,
                        "generated_files": [],
                        "project_name": "",
                        "tech_stack": [],
                        "architecture": "",
                        "user_feedback": "",
                        "generation_complete": False,
                        "zip_data": None,
                        # Reset interactive workflow states
                        "workflow_step": "initial",
                        "requirements": "",
                        "suggested_tech_stack": [],
                        "selected_tech_stack": [],
                        "project_architecture": "",
                        "file_groups": [],
                        "current_group_index": 0,
                        "generated_groups": [],
                        "user_confirmations": {},
                        "project_description": ""
                    }
                    st.success("🎉 Project marked as complete!")
                    st.rerun()

        # Enhanced chat actions
        if st.session_state.chat_history:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Download chat button
                chat_md = ""
                for msg in st.session_state.chat_history:
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    chat_md += f"\n**{role}:**\n\n{content}\n\n"
                st.download_button(
                    label="💾 Download",
                    data=chat_md,
                    file_name="chat.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            
            with col2:
                # Generate Mermaid Diagram Button
                if st.button("📊 Diagram", use_container_width=True):
                    # Get the last assistant response
                    last_assistant_msg = None
                    for msg in reversed(st.session_state.chat_history):
                        if msg.get("role") == "assistant":
                            last_assistant_msg = msg.get("content", "")
                            break
                    
                    if last_assistant_msg:
                        with st.spinner("Creating diagram..."):
                            try:
                                # Generate Mermaid diagram
                                diagram_prompt = (
                                    "Create a clear, professional workflow diagram in Mermaid syntax based on this content. "
                                    "Only output valid Mermaid code in a code block. Use flowchart format (graph TD).\n\n" + last_assistant_msg[:800]
                                )
                                mermaid_code = generate_gemini_response([
                                    {"role": "user", "content": diagram_prompt}
                                ], model_name="gemini-2.5-pro")
                                
                                if mermaid_code and '```mermaid' in mermaid_code:
                                    mermaid_blocks = re.findall(r'```mermaid(.*?)```', mermaid_code, re.DOTALL)
                                    for block in mermaid_blocks:
                                        with st.chat_message("assistant"):
                                            st.markdown("**📊 Generated Workflow Diagram:**")
                                            render_mermaid(block.strip())
                                            
                                            # Add to chat history
                                            diagram_msg = {"role": "assistant", "content": f"📊 **Generated Workflow Diagram:**\n\n```mermaid\n{block.strip()}\n```"}
                                            st.session_state.chat_history.append(diagram_msg)
                                            add_message_to_chat(user_id, st.session_state.selected_chat_id, diagram_msg, model_type=model_type)
                                else:
                                    st.error("Failed to generate diagram.")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    else:
                        st.warning("No assistant response found.")
            
            with col3:
                # Clear current chat button
                if st.button("🧹 Clear", use_container_width=True):
                    st.session_state.chat_history = []
                    from firebase_utils import db
                    chat_ref = db.collection('users').document(user_id).collection('chats').document(st.session_state.selected_chat_id)
                    chat_ref.update({'history': [], 'title': 'New Chat Session'})
                    reset_session_for_new_chat()
                    st.success("🧹 Chat cleared!")
                    st.rerun()
            
            with col4:
                # RAG status or file upload indicator
                if st.session_state.project_context.get('indexed'):
                    st.success("🧠 RAG")
                else:
                    st.info("📁 Upload")

        # AI Agent Selection and Project Upload
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            # Agent selection
            agent_options = [
                "🚀 Project Generator",
                "🔍 Project Analyzer", 
                "🛠️ Code Assistant"
            ]
            
            selected_agent = st.selectbox(
                "🤖 **AI Assistant Type**",
                agent_options,
                index=agent_options.index(st.session_state.get("selected_agent", "🚀 Project Generator")) if st.session_state.get("selected_agent") in agent_options else 0
            )
            st.session_state.selected_agent = selected_agent
        
        with col2:
            # Project upload options
            upload_method = st.selectbox(
                "📁 **Load Project**",
                ["📎 No Files", "📁 Upload Files", "🌐 Git Repository"],
                index=0,
                # help removed
            )

        # File upload interface
        if upload_method == "📁 Upload Files":
            # Show helpful instructions based on selected agent
            if selected_agent == "🚀 Project Generator":
                st.info("💡 **Tip for Project Generator**: Upload requirements documents (.docx, .pdf, .txt) that describe what you want to build. Then use prompts like 'create full project code' or 'implement the requirements'.")
            elif selected_agent == "🔍 Project Analyzer":
                st.info("💡 **Tip for Project Analyzer**: Upload your existing project files to get comprehensive onboarding documentation and architecture analysis.")
            elif selected_agent == "🛠️ Code Assistant":
                st.info("💡 **Tip for Code Assistant**: Upload your existing project, then ask to add new features or extend functionality. I'll maintain your coding patterns.")
            
            # Use chat-specific key for file uploader
            uploader_key = f"file_uploader_{st.session_state.selected_chat_id}"
            uploaded_files = st.file_uploader(
                label="**📁 Upload Project Files (supports ZIP archives and Word documents)**",
                type=["py", "js", "ts", "html", "css", "json", "md", "txt", "pdf", "zip", "java", "cpp", "c", "rb", "go", "yml", "yaml", "docx", "doc"],
                key=uploader_key,
                accept_multiple_files=True,
                # help removed
            )
            
            if uploaded_files:
                # Show preview of uploaded files
                with st.expander("📋 **Uploaded Files Preview**", expanded=False):
                    for file in uploaded_files:
                        file_type = "📄 Document" if any(ext in file.name.lower() for ext in ['.docx', '.doc', '.pdf', '.txt', '.md']) else "💻 Code"
                        st.write(f"{file_type} **{file.name}** ({file.size:,} bytes)")
                
                if st.button("🚀 **Process Files with RAG**", type="primary"):
                    # Extract files
                    files_content = extract_files_from_uploaded(uploaded_files)
                    
                    if files_content:
                        # Initialize RAG system
                        if RAG_AVAILABLE:
                            success = initialize_rag_system(files_content, user_id, st.session_state.selected_chat_id)
                            if success:
                                st.success(f"✅ Successfully indexed {len(files_content)} files with RAG!")
                                
                                # Show what was uploaded for Project Generator
                                if selected_agent == "🚀 Project Generator":
                                    req_docs = [f for f in files_content.keys() if any(ext in f.lower() for ext in ['.docx', '.doc', '.pdf', '.txt', '.md'])]
                                    if req_docs:
                                        st.info(f"📋 **Requirements documents uploaded**: {', '.join(req_docs)}\n\n**Next step**: Ask me to 'create full project code' or 'implement the requirements'")
                                
                                # Add message about file processing
                                file_msg = {"role": "user", "content": f"[Uploaded and indexed {len(files_content)} project files with RAG: {', '.join(list(files_content.keys())[:5])}{'...' if len(files_content) > 5 else ''}]"}
                                st.session_state.chat_history.append(file_msg)
                                add_message_to_chat(user_id, st.session_state.selected_chat_id, file_msg, model_type=model_type)
                                st.rerun()
                        else:
                            st.warning("⚠️ RAG not available. Files processed without semantic indexing.")
        
        elif upload_method == "🌐 Git Repository":
            col1, col2 = st.columns([3, 1])
            
            with col1:
                repo_url = st.text_input(
                    "**Repository URL**",
                    placeholder="https://github.com/owner/repository-name",
                    # help removed
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                if st.button("🔍 **Fetch & Index**", type="primary"):
                    if repo_url.strip():
                        try:
                            with st.spinner("🌐 Fetching repository..."):
                                repo_info, files = fetch_git_repository(repo_url)
                                
                                if files:
                                    if RAG_AVAILABLE:
                                        success = initialize_rag_system(files, user_id, st.session_state.selected_chat_id)
                                        if success:
                                            st.success(f"✅ Fetched and indexed {len(files)} files from {repo_info.name if repo_info else 'repository'} with RAG!")
                                            
                                            # Add message about repo processing
                                            repo_msg = {"role": "user", "content": f"[Fetched and indexed repository: {repo_url} ({len(files)} files) with RAG]"}
                                            st.session_state.chat_history.append(repo_msg)
                                            add_message_to_chat(user_id, st.session_state.selected_chat_id, repo_msg, model_type=model_type)
                                            st.rerun()
                                    else:
                                        st.warning("⚠️ RAG not available. Repository processed without semantic indexing.")
                                else:
                                    st.warning("No files found in repository")
                        
                        except Exception as e:
                            st.error(f"❌ Failed to fetch repository: {str(e)}")
                    else:
                        st.warning("Please enter a repository URL")

        # Quick action buttons for Project Generator
        if selected_agent == "🚀 Project Generator" and st.session_state.project_context.get('indexed'):
            req_docs = [f for f in st.session_state.project_context.get('files', {}).keys() if any(ext in f.lower() for ext in ['.docx', '.doc', '.pdf', '.txt', '.md'])]
            if req_docs:
                st.markdown("---")
                st.markdown("**🚀 Quick Actions for Project Generator:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📋 **Implement Requirements**", use_container_width=True):
                        quick_prompt = "Analyze the uploaded requirements document deeply and create a SOPHISTICATED, ENTERPRISE-GRADE project with FULL SOURCE CODE implementation. Generate ALL necessary files with COMPLETE, EXECUTABLE, PRODUCTION-READY code that matches the complexity of the requirements. Use appropriate architecture patterns, design principles, security measures, and performance optimizations. NO placeholders, NO TODOs, NO skeleton code - create sophisticated, working implementations with proper error handling, logging, security, and scalability."
                        st.session_state.auto_send_prompt = quick_prompt
                        st.rerun()
                
                with col2:
                    if st.button("🏗️ **Create Full Project**", use_container_width=True):
                        quick_prompt = "Based on the uploaded requirements document, create a COMPLETE, ENTERPRISE-GRADE project structure with ALL source code files containing SOPHISTICATED, PRODUCTION-READY code. Analyze the project complexity and implement appropriate architecture patterns (Clean Architecture, SOLID principles, design patterns). Include comprehensive security measures, performance optimizations, error handling, logging, and monitoring. Every file must be complete with all imports, functions, classes, and be immediately executable and deployable."
                        st.session_state.auto_send_prompt = quick_prompt
                        st.rerun()
                
                with col3:
                    if st.button("💻 **Generate Code**", use_container_width=True):
                        quick_prompt = "Read the uploaded requirements document carefully and generate SOPHISTICATED, ENTERPRISE-GRADE source code that implements all specified features with production-ready quality. Every file must contain FULL implementations with appropriate design patterns, comprehensive error handling, security measures, performance optimizations, proper logging, and monitoring. Use SOLID principles, clean architecture, and enterprise best practices. NO PLACEHOLDER CODE, NO TODOs, NO INCOMPLETE FUNCTIONS - create sophisticated, working, scalable implementations."
                        st.session_state.auto_send_prompt = quick_prompt
                        st.rerun()
        
        # Additional quick actions for Project Generator (always show)
        if selected_agent == "🚀 Project Generator":
            st.markdown("---")
            st.markdown("**🎯 Project Generation Options:**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("📁 **Generate All Files**", use_container_width=True):
                    quick_prompt = "Create a complete project with ALL necessary files containing FULL, WORKING, PRODUCTION-READY code. Every file must be complete with all imports, functions, classes, error handling, logging, and be immediately executable. NO PLACEHOLDER CODE, NO SKELETONS, NO INCOMPLETE IMPLEMENTATIONS - everything must be complete and runnable."
                    st.session_state.auto_send_prompt = quick_prompt
                    st.rerun()
            
            with col2:
                if st.button("🔧 **Setup & Config**", use_container_width=True):
                    quick_prompt = "Generate all configuration files, setup scripts, and deployment configurations for the project. Include package.json/requirements.txt, Dockerfile, .env.example, and other essential config files."
                    st.session_state.auto_send_prompt = quick_prompt
                    st.rerun()
            
            with col3:
                if st.button("📚 **Documentation**", use_container_width=True):
                    quick_prompt = "Create comprehensive documentation including README.md, API documentation, setup instructions, user guides, and developer documentation for the project."
                    st.session_state.auto_send_prompt = quick_prompt
                    st.rerun()
            
            with col4:
                if st.button("🧪 **Tests & Validation**", use_container_width=True):
                    quick_prompt = "Generate comprehensive test suites including unit tests, integration tests, and validation scripts. Include test configuration and coverage reports."
                    st.session_state.auto_send_prompt = quick_prompt
                    st.rerun()

        # Chat input form - ALWAYS show
        st.markdown("---")
        
        # Check for auto-send prompt from quick action buttons
        auto_prompt = st.session_state.get('auto_send_prompt', '')
        
        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input("💬 **Ask your AI assistant...**", 
                                 value=auto_prompt if auto_prompt else '',
                                 placeholder="Type your question or request here...", 
                                 label_visibility="collapsed")
            send = st.form_submit_button("Send", use_container_width=True)
        
        # If we have an auto_prompt and form was submitted, use the auto_prompt
        if send and auto_prompt:
            prompt = auto_prompt  # Ensure we use the auto_prompt value
            st.session_state.auto_send_prompt = ''  # Clear it after using

        if send and prompt:
            # Add user message to chat history
            user_msg = {"role": "user", "content": prompt}
            st.session_state.chat_history.append(user_msg)
            add_message_to_chat(user_id, st.session_state.selected_chat_id, user_msg, model_type=model_type)
            
            # Set generation state for Project Generator
            if selected_agent == "🚀 Project Generator":
                st.session_state.project_generation_state["is_generating"] = True
                st.session_state.project_generation_state["current_step"] = "Analyzing requirements and planning project structure"
            
            # Get enhanced RAG context if available
            rag_context = get_rag_context(prompt) if RAG_AVAILABLE else []
            rag_files = [r['file'] for r in rag_context] if rag_context else []
            
            # Enhanced RAG context for project generation agents
            if selected_agent in ["🚀 Project Generator", "🛠️ Code Assistant"]:
                # Get additional context for project generation
                additional_queries = [
                    "architecture patterns design structure",
                    "dependencies requirements configuration",
                    "testing validation best practices",
                    "security authentication authorization"
                ]
                for query in additional_queries:
                    extra_context = get_rag_context(query, max_results=2) if RAG_AVAILABLE else []
                    rag_context.extend(extra_context)
                
                # Remove duplicates
                seen_files = set()
                unique_context = []
                for context in rag_context:
                    if context['file'] not in seen_files:
                        unique_context.append(context)
                        seen_files.add(context['file'])
                rag_context = unique_context[:10]  # Limit to top 10 most relevant
            
            # Generate AI response using selected agent
            with st.spinner("🤖 Generating response..."):
                response = generate_agent_response(
                    prompt,
                    selected_agent,
                    selected_model,
                    rag_context=rag_context
                )
            
            # For Project Generator, handle interactive workflow
            if selected_agent == "🚀 Project Generator":
                # Update generation state
                st.session_state.project_generation_state["is_generating"] = False
                st.session_state.project_generation_state["current_step"] = None
                
                # Handle different workflow steps
                current_step = st.session_state.project_generation_state["workflow_step"]
                
                if current_step == "initial":
                    # Start the workflow - analyze requirements and suggest tech stack
                    requirements_text = f"{prompt}"
                    st.session_state.project_generation_state["requirements"] = requirements_text
                    
                    with st.spinner("🔍 Analyzing requirements and suggesting tech stack..."):
                        tech_analysis = analyze_requirements_and_suggest_tech_stack(prompt, requirements_text)
                    
                    # Update workflow state
                    st.session_state.project_generation_state["workflow_step"] = "tech_stack_selection"
                    st.session_state.project_generation_state["suggested_tech_stack"] = tech_analysis
                    
                    # Add tech stack analysis to response
                    response = f"🎯 **Step 1: Tech Stack Analysis**\n\n{tech_analysis}\n\n"
                    response += f"**Next Step:** Please choose your preferred tech stack:\n"
                    response += f"- 'I choose Option 1/2/3'\n"
                    response += f"- 'I want to use [custom tech stack]'\n"
                    response += f"- 'Can you explain [option]?'"
                
                elif current_step == "tech_stack_selection":
                    # Handle tech stack selection
                    if any(keyword in prompt.lower() for keyword in ["option 1", "option 2", "option 3", "choose", "select"]):
                        # User selected a suggested option
                        selected_option = None
                        if "option 1" in prompt.lower():
                            selected_option = "Option 1"
                        elif "option 2" in prompt.lower():
                            selected_option = "Option 2"
                        elif "option 3" in prompt.lower():
                            selected_option = "Option 3"
                        
                        if selected_option:
                            st.session_state.project_generation_state["selected_tech_stack"] = selected_option
                            st.session_state.project_generation_state["workflow_step"] = "architecture_review"
                            
                            # Generate architecture
                            try:
                                with st.spinner("🏗️ Designing project architecture..."):
                                    architecture = generate_project_architecture(
                                        st.session_state.project_generation_state["requirements"],
                                        selected_option
                                    )
                                
                                # Check if architecture generation failed
                                if not architecture or "error" in architecture.lower() or "500" in architecture:
                                    st.warning("⚠️ Architecture generation encountered an issue. Using default structure.")
                                    architecture = f"""
PROJECT ARCHITECTURE OVERVIEW:
Standard project structure for {selected_option}

FILE STRUCTURE:
```
project-name/
├── src/
│   ├── main.py
│   ├── app.py
│   ├── config.py
│   └── utils.py
├── tests/
├── docs/
├── requirements.txt
├── README.md
└── .env.example
```

FILE GROUPS FOR GENERATION:
Group 1: Core Application Files
- src/main.py
- src/app.py
- src/config.py
- src/utils.py

Group 2: Configuration & Setup
- requirements.txt
- README.md
- .env.example
- .gitignore

Group 3: Documentation & Tests
- tests/test_main.py
- docs/README.md

Group 4: Deployment & DevOps
- Dockerfile
- docker-compose.yml
"""
                                
                                st.session_state.project_generation_state["project_architecture"] = architecture
                                
                                # Parse file groups
                                file_groups = parse_file_groups_from_architecture(architecture)
                                st.session_state.project_generation_state["file_groups"] = file_groups
                                
                            except Exception as e:
                                st.error(f"❌ Error generating architecture: {str(e)}")
                                # Use default architecture
                                architecture = f"""
PROJECT ARCHITECTURE OVERVIEW:
Standard project structure for {selected_option}

FILE STRUCTURE:
```
project-name/
├── src/
│   ├── main.py
│   ├── app.py
│   ├── config.py
│   └── utils.py
├── tests/
├── docs/
├── requirements.txt
├── README.md
└── .env.example
```

FILE GROUPS FOR GENERATION:
Group 1: Core Application Files
- src/main.py
- src/app.py
- src/config.py
- src/utils.py

Group 2: Configuration & Setup
- requirements.txt
- README.md
- .env.example
- .gitignore

Group 3: Documentation & Tests
- tests/test_main.py
- docs/README.md

Group 4: Deployment & DevOps
- Dockerfile
- docker-compose.yml
"""
                                st.session_state.project_generation_state["project_architecture"] = architecture
                                file_groups = create_default_file_groups()
                                st.session_state.project_generation_state["file_groups"] = file_groups
                            
                            response = f"🏗️ **Step 2: Project Architecture**\n\n{architecture}\n\n"
                            response += f"**Next Step:** Please confirm the architecture:\n"
                            response += f"- 'Yes, proceed with this architecture'\n"
                            response += f"- 'I want to modify [specific part]'\n"
                            response += f"- 'Can you explain [aspect]?'\n\n"
                            response += f"**File Groups:** {len(file_groups)} groups ready for generation"
                    
                    elif any(keyword in prompt.lower() for keyword in ["react", "node", "python", "java", "django", "flask", "mongodb", "postgresql", "mysql", "typescript", "javascript", "vue", "angular", "spring", "express", "fastapi", "sqlite", "redis", "docker", "kubernetes"]):
                        # User provided custom tech stack
                        with st.spinner("🔍 Validating custom tech stack..."):
                            validation = validate_custom_tech_stack(prompt, st.session_state.project_generation_state["requirements"])
                        
                        response = f"🔍 **Tech Stack Validation**\n\n{validation}\n\n"
                        
                        # Check if validation is positive
                        if "FEASIBLE" in validation or "NEEDS_MODIFICATIONS" in validation:
                            response += f"✅ **Tech Stack Validated!**\n\n"
                            response += f"**Next Step:**\n"
                            response += f"- 'Yes, proceed with this tech stack'\n"
                            response += f"- 'I want to modify the tech stack'\n"
                            
                            st.session_state.project_generation_state["selected_tech_stack"] = prompt
                        else:
                            response += f"⚠️ **Tech Stack Issues Found**\n\n"
                            response += f"**Next Step:**\n"
                            response += f"- Choose one of the suggested alternatives\n"
                            response += f"- Modify your tech stack based on recommendations\n"
                            response += f"- Ask for clarification on any concerns"
                    
                    else:
                        # User asked questions or provided unclear input
                        response = f"🤔 **Tech Stack Selection Help**\n\n"
                        response += f"Please choose your preferred tech stack:\n\n"
                        response += f"**Options:**\n"
                        response += f"- 'I choose Option 1/2/3'\n"
                        response += f"- 'I want to use [specific technologies]'\n"
                        response += f"- 'Can you explain [option]?'\n\n"
                        response += f"**Available:**\n"
                        response += f"- Option 1: Modern & Popular\n"
                        response += f"- Option 2: Enterprise & Robust\n"
                        response += f"- Option 3: Rapid Development\n"
                        response += f"- Custom: Your preferred technologies"
                
                elif current_step == "architecture_review":
                    # Handle architecture review
                    if any(keyword in prompt.lower() for keyword in ["yes", "proceed", "confirm", "ok", "good", "continue"]):
                        # User confirmed architecture
                        st.session_state.project_generation_state["workflow_step"] = "group_generation"
                        st.session_state.project_generation_state["current_group_index"] = 0
                        
                        response += f"\n\n✅ **Architecture Confirmed!**\n\n"
                        response += f"Starting group-by-group file generation...\n\n"
                        
                        # Generate first group
                        file_groups = st.session_state.project_generation_state["file_groups"]
                        if file_groups:
                            current_group = file_groups[0]
                            try:
                                with st.spinner(f"💻 Generating {current_group['name']}..."):
                                    group_response = generate_file_group(
                                        current_group['name'],
                                        current_group['files'],
                                        st.session_state.project_generation_state["requirements"],
                                        st.session_state.project_generation_state["selected_tech_stack"],
                                        st.session_state.project_generation_state["project_architecture"]
                                    )
                                
                                # Check if generation failed
                                if not group_response or "error" in group_response.lower() or "500" in group_response:
                                    st.warning(f"⚠️ File generation for {current_group['name']} encountered an issue. Retrying with simplified prompt...")
                                    
                                    # Try again with a more sophisticated, context-aware prompt
                                    retry_prompt = f"""
You are a SENIOR DEVELOPER creating enterprise-grade code files.

**GROUP:** {current_group['name']}
**FILES NEEDED:**
{chr(10).join(f"- {file}" for file in current_group['files'][:5])}

**TECH STACK:** {st.session_state.project_generation_state["selected_tech_stack"]}
**REQUIREMENTS:** {st.session_state.project_generation_state["requirements"][:500]}...

**MISSION:** Create sophisticated, production-ready code files that match the project complexity.

**REQUIREMENTS:**
- FULL IMPLEMENTATION: Every function, class, method completely implemented
- ENTERPRISE QUALITY: Production-ready with error handling, logging, security
- ARCHITECTURE AWARE: Use appropriate design patterns and SOLID principles
- SECURITY FIRST: Input validation, authentication, protection measures
- PERFORMANCE OPTIMIZED: Efficient algorithms and resource management
- WELL DOCUMENTED: Clear docstrings, type hints, and comments
- TESTABLE: Easy to test with proper abstractions

**OUTPUT FORMAT:**
For each file:
```
📄 **filename.ext**
```ext
[COMPLETE, SOPHISTICATED CODE WITH ALL IMPORTS, ERROR HANDLING, LOGGING, SECURITY, ETC.]
```
```

**CRITICAL:** NO placeholders, NO TODOs, NO skeleton code. Create FULL, WORKING, ENTERPRISE-GRADE code.
"""
                                    
                                    try:
                                        with st.spinner(f"🔄 Retrying {current_group['name']} generation..."):
                                            retry_response = generate_agent_response(
                                                retry_prompt,
                                                "🚀 Project Generator",
                                                st.session_state.get("selected_model", "gemini-2.5-pro")
                                            )
                                        
                                        if retry_response and "error" not in retry_response.lower():
                                            extracted_files = extract_project_files_from_response(retry_response)
                                            if extracted_files:
                                                st.success(f"✅ Successfully generated {len(extracted_files)} files on retry!")
                                            else:
                                                st.warning("⚠️ Retry failed to extract files. Using basic files.")
                                                basic_files = create_basic_files_for_group(current_group)
                                                extracted_files = basic_files
                                        else:
                                            st.warning("⚠️ Retry also failed. Using basic files.")
                                            basic_files = create_basic_files_for_group(current_group)
                                            extracted_files = basic_files
                                    except Exception as e:
                                        st.error(f"❌ Retry failed: {str(e)}")
                                        basic_files = create_basic_files_for_group(current_group)
                                        extracted_files = basic_files
                                else:
                                    # Extract files from group response
                                    extracted_files = extract_project_files_from_response(group_response)
                                
                                # Store group
                                st.session_state.project_generation_state["generated_groups"].append({
                                    'name': current_group['name'],
                                    'files': extracted_files
                                })
                                
                                response = f"💻 **Step 3: Group 1 Complete - {current_group['name']}**\n\n"
                                
                                # Show the generated files
                                if extracted_files:
                                    response += f"**📁 Generated Files ({len(extracted_files)}):**\n"
                                    for file_path in extracted_files.keys():
                                        response += f"- `{file_path}`\n"
                                    response += f"\n"
                                    
                                    # Show file content in expandable sections
                                    response += f"**📄 File Contents:**\n"
                                    for file_path, content in extracted_files.items():
                                        response += f"\n**{file_path}:**\n"
                                        response += f"```{get_file_extension(file_path)}\n{content}\n```\n"
                                else:
                                    response += f"⚠️ **No files were extracted from the response.**\n"
                                    if "error" not in group_response.lower():
                                        response += f"**API Response:**\n{group_response}\n\n"
                                
                                response += f"**Next Step:**\n"
                                response += f"- 'Continue to next group'\n"
                                response += f"- 'I want to modify [specific file]'\n"
                                response += f"- 'Can you explain [code]?'\n\n"
                                response += f"**Remaining:** {len(file_groups) - 1} groups left"
                                
                            except Exception as e:
                                st.error(f"❌ Error generating files for {current_group['name']}: {str(e)}")
                                # Create basic files as fallback
                                basic_files = create_basic_files_for_group(current_group)
                                st.session_state.project_generation_state["generated_groups"].append({
                                    'name': current_group['name'],
                                    'files': basic_files
                                })
                                
                                response = f"💻 **Step 3: Group 1 Complete - {current_group['name']}**\n\n"
                                response += f"⚠️ **API Error encountered. Generated basic files as fallback.**\n\n"
                                
                                # Show the generated basic files
                                if basic_files:
                                    response += f"**📁 Generated Files ({len(basic_files)}):**\n"
                                    for file_path in basic_files.keys():
                                        response += f"- `{file_path}`\n"
                                    response += f"\n"
                                    
                                    # Show file content
                                    response += f"**📄 File Contents:**\n"
                                    for file_path, content in basic_files.items():
                                        response += f"\n**{file_path}:**\n"
                                        response += f"```{get_file_extension(file_path)}\n{content}\n```\n"
                                
                                response += f"**Next Step:**\n"
                                response += f"- 'Continue to next group'\n"
                                response += f"- 'I want to modify [specific file]'\n"
                                response += f"- 'Can you explain [code]?'\n\n"
                                response += f"**Remaining:** {len(file_groups) - 1} groups left"
                        else:
                            response += f"\n\n❌ **No file groups found in architecture.**\n"
                            response += f"Please ask me to 'regenerate architecture' or 'start over'."
                    
                    else:
                        # User wants changes or has questions
                        response = f"🏗️ **Architecture Review Help**\n\n"
                        response += f"Please specify what you'd like to do:\n\n"
                        response += f"**Options:**\n"
                        response += f"- 'I want to modify [specific part]'\n"
                        response += f"- 'Can you explain [aspect]?'\n"
                        response += f"- 'Yes, proceed with this architecture'\n\n"
                        response += f"**Current:**\n"
                        response += f"- Tech Stack: {st.session_state.project_generation_state['selected_tech_stack']}\n"
                        response += f"- File Groups: {len(st.session_state.project_generation_state['file_groups'])} groups"
                
                elif current_step == "group_generation":
                    # Handle group-by-group generation
                    if any(keyword in prompt.lower() for keyword in ["continue", "next group", "proceed", "next"]):
                        # Continue to next group
                        file_groups = st.session_state.project_generation_state["file_groups"]
                        current_index = st.session_state.project_generation_state["current_group_index"]
                        next_index = current_index + 1
                        
                        if next_index < len(file_groups):
                            # Generate next group
                            next_group = file_groups[next_index]
                            previous_groups = st.session_state.project_generation_state["generated_groups"]
                            
                            with st.spinner(f"💻 Generating {next_group['name']}..."):
                                group_response = generate_file_group(
                                    next_group['name'],
                                    next_group['files'],
                                    st.session_state.project_generation_state["requirements"],
                                    st.session_state.project_generation_state["selected_tech_stack"],
                                    st.session_state.project_generation_state["project_architecture"],
                                    previous_groups
                                )
                            
                            # Extract files from group response
                            extracted_files = extract_project_files_from_response(group_response)
                            
                            # Store group
                            st.session_state.project_generation_state["generated_groups"].append({
                                'name': next_group['name'],
                                'files': extracted_files
                            })
                            
                            # Update index
                            st.session_state.project_generation_state["current_group_index"] = next_index
                            
                            response = f"💻 **Step 3: Group {next_index + 1} Complete - {next_group['name']}**\n\n{group_response}\n\n"
                            response += f"**Generated {len(extracted_files)} files.**\n\n"
                            
                            if next_index + 1 < len(file_groups):
                                response += f"**Next Step:**\n"
                                response += f"- 'Continue to next group'\n"
                                response += f"- 'I want to modify [specific file]'\n"
                                response += f"- 'Can you explain [code]?'\n\n"
                                response += f"**Remaining:** {len(file_groups) - next_index - 1} groups left"
                            else:
                                # All groups complete
                                response += f"🎉 **All Groups Complete!**\n\n"
                                response += f"**Next Step:**\n"
                                response += f"- 'Complete project'\n"
                                response += f"- 'I want to modify [specific file]'\n"
                                response += f"- 'Can you explain [code]?'\n\n"
                                
                                st.session_state.project_generation_state["workflow_step"] = "complete"
                        else:
                            response += f"\n\n🎉 **All groups have been generated!**\n\n"
                            response += f"Please type 'Complete project' to finalize and download your project."
                    
                    elif any(keyword in prompt.lower() for keyword in ["complete", "finalize", "done", "finish"]):
                        # Complete the project
                        all_files = {}
                        for group in st.session_state.project_generation_state["generated_groups"]:
                            all_files.update(group['files'])
                        
                        if all_files:
                            # Create ZIP file
                            project_name = "generated_project"
                            zip_data = create_project_zip(all_files, project_name)
                            st.session_state.project_generation_state["zip_data"] = zip_data
                            st.session_state.project_generation_state["generated_files"] = all_files
                            st.session_state.project_generation_state["generation_complete"] = True
                            
                            response = f"🎉 **Step 4: Project Complete!**\n\n"
                            response += f"**Generated {len(all_files)} files in {len(st.session_state.project_generation_state['generated_groups'])} groups:**\n"
                            for group in st.session_state.project_generation_state["generated_groups"]:
                                response += f"- **{group['name']}**: {len(group['files'])} files\n"
                            response += f"\n💾 **Download your complete project below!**"
                        else:
                            response += f"\n\n❌ **No files were generated.**\n"
                            response += f"Please ask me to 'start over' or 'regenerate files'."
                    
                    else:
                        # User wants changes or has questions
                        response = f"💻 **File Generation Help**\n\n"
                        response += f"Please specify what you'd like to do:\n\n"
                        response += f"**Options:**\n"
                        response += f"- 'Continue to next group'\n"
                        response += f"- 'I want to modify [specific file]'\n"
                        response += f"- 'Complete project'\n"
                        response += f"- 'Can you explain [code]?'\n\n"
                        
                        current_group = st.session_state.project_generation_state["generated_groups"][-1] if st.session_state.project_generation_state["generated_groups"] else None
                        if current_group:
                            response += f"**Current:** {current_group['name']}\n"
                            response += f"**Files:** {len(current_group['files'])} generated"
                
                else:
                    # Handle other cases or restart workflow
                    if any(keyword in prompt.lower() for keyword in ["start over", "restart", "new project", "begin"]):
                        # Reset workflow
                        st.session_state.project_generation_state = {
                            "is_generating": False,
                            "current_step": None,
                            "generated_files": [],
                            "project_name": "",
                            "tech_stack": [],
                            "architecture": "",
                            "user_feedback": "",
                            "generation_complete": False,
                            "zip_data": None,
                            "workflow_step": "initial",
                            "requirements": "",
                            "suggested_tech_stack": [],
                            "selected_tech_stack": [],
                            "project_architecture": "",
                            "file_groups": [],
                            "current_group_index": 0,
                            "generated_groups": [],
                            "user_confirmations": {},
                            "project_description": ""
                        }
                        
                        response = f"🔄 **Workflow Reset**\n\n"
                        response += f"Starting fresh project generation. Please provide your project requirements."
                    else:
                        # Fallback to regular project generation
                        extracted_files = extract_project_files_from_response(response)
                        
                        if extracted_files:
                            # Store files in session state
                            st.session_state.project_generation_state["generated_files"] = extracted_files
                            st.session_state.project_generation_state["generation_complete"] = True
                            
                            # Create ZIP file
                            project_name = "generated_project"
                            zip_data = create_project_zip(extracted_files, project_name)
                            st.session_state.project_generation_state["zip_data"] = zip_data
                            
                            # Add ZIP download info to response
                            response += f"\n\n🎉 **Project Generation Complete!**\n\n"
                            response += f"📁 **Generated {len(extracted_files)} files:**\n"
                            for file_path in list(extracted_files.keys())[:10]:  # Show first 10 files
                                response += f"- `{file_path}`\n"
                            if len(extracted_files) > 10:
                                response += f"- ... and {len(extracted_files) - 10} more files\n"
                            response += f"\n💾 **Download your complete project below!**"
                        else:
                            # No files extracted, add guidance
                            response += f"\n\n💡 **Next Steps:**\n"
                            response += f"- If you need complete project files, ask me to 'generate all project files'\n"
                            response += f"- For specific files, ask me to 'create [filename]'\n"
                            response += f"- For modifications, ask me to 'modify [specific part]'"
                
            # Add assistant response to chat history
            bot_msg = {"role": "assistant", "content": response}
            if rag_files:
                bot_msg["rag_context_files"] = rag_files
            st.session_state.chat_history.append(bot_msg)
            add_message_to_chat(user_id, st.session_state.selected_chat_id, bot_msg, model_type=model_type)
            
            # Update chat title if it's a new chat
            try:
                from firebase_utils import regenerate_chat_title, db
                chat_doc = get_chat_history(user_id, st.session_state.selected_chat_id)
                user_msgs = [m for m in chat_doc if m.get("role") == "user"]
                chat_ref = db.collection('users').document(user_id).collection('chats').document(st.session_state.selected_chat_id)
                chat_data = chat_ref.get().to_dict()
                chat_title = chat_data.get('title', '') if chat_data else ''
                if len(user_msgs) >= 2 and (chat_title.startswith('New Chat') or chat_title == 'Chat'):
                    regenerate_chat_title(user_id, st.session_state.selected_chat_id, model_type)
            except:
                pass  # Skip title update if there's an error
                
            # Rerun to display updated chat history
            st.rerun()
    else:
        st.info("💬 No chat selected. Please create a new chat to start.")
        
        # Show comprehensive getting started guide
        st.markdown("""
        ## 🚀 **Getting Started with Your AI Assistant**
        
        ### **📋 Quick Setup:**
        1. **🆕 Create a new chat** using the sidebar button
        2. **🤖 Choose your AI model** (Gemini, GPT, Claude, DeepSeek)
        3. **📁 Upload project files** or paste Git URLs for intelligent analysis
        4. **🎯 Select an AI agent** for specialized expertise
        5. **💬 Start chatting** with context-aware responses!
        
        ### **🎯 AI Agent Specializations:**
        
        #### **🚀 Project Generator** 
        *From Idea to Complete Project*
        - **Use Case 1**: Give a project description → Get full project structure with code, docs, tests
        - **Use Case 2**: Upload requirements (Word/PDF/diagrams) → Generate complete implementation
        - **Deliverables**: Complete project with source code, documentation, deployment configs, tests
        
        #### **🔍 Project Analyzer**
        *Expert Project Onboarding*
        - **Use Case 3**: Upload existing project → Get comprehensive project explanation for onboarding
        - **Perfect for**: New team members, project handovers, understanding legacy code
        - **Deliverables**: Project overview, architecture analysis, setup guides, development workflows
        
        #### **🛠️ Code Assistant**
        *Extend Existing Projects*
        - **Use Case 4**: Upload project + request → Get new features that integrate seamlessly
        - **Perfect for**: Adding features, extending functionality, maintaining consistency
        - **Deliverables**: New code files, integration guides, updated documentation
        
        ### **🧠 RAG-Powered Intelligence:**
        - **Upload files** to enable semantic search and context understanding
        - **ZIP archives** supported for entire project analysis
        - **Git repositories** can be fetched and indexed automatically
        - **Smart context** retrieval for more accurate responses
        
        ### **📊 Advanced Features:**
        - **Mermaid diagrams** generated from conversations
        - **Chat history** with search and management
        - **File context** preserved across chat sessions
        - **Multi-model** comparison and selection
        """)

# --- Main App Logic ---
if "user" not in st.session_state:
    login_ui()
else:
    chat_ui() 