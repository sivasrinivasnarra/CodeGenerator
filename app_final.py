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

# Helper functions
def render_mermaid(mermaid_code: str):
    """Render Mermaid diagram in Streamlit using HTML and Mermaid.js CDN."""
    if mermaid_code.strip().startswith('```mermaid'):
        mermaid_code = mermaid_code.strip().removeprefix('```mermaid').removesuffix('```').strip()
    
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
                            except:
                                pass  # Skip binary/unreadable files
                                
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
                    except:
                        # Method 2: Fallback to docx2txt
                        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                            tmp_file.write(file_bytes)
                            tmp_file.flush()
                            content = docx2txt.process(tmp_file.name)
                            files_content[uploaded_file.name] = content
                            os.unlink(tmp_file.name)  # Clean up temp file
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
        
        # Enhanced system instruction for comprehensive project generation (first-time or major requests)
        if st.session_state.project_context.get('indexed') and context_info and not (is_followup and is_followup_request) and not is_simple_request:
            context_prompt = f"""🚀 SYSTEMATIC PROJECT GENERATOR - Interactive & Complete

Role: Senior Full-Stack Developer & Project Architect
Task: Create complete, production-ready project through structured approach

**UPLOADED REQUIREMENTS:**
{context_info}

**USER REQUEST:** {prompt}

**SYSTEMATIC APPROACH - PHASE 1: TECH STACK CLARIFICATION**

Before generating any code, present the user with tech stack options:

**STEP 1: Tech Stack Selection**
Generate 3 specific tech stack options based on the IVR project requirements:

🔧 **TECH STACK OPTIONS FOR YOUR IVR PROJECT:**

**Option 1: Modern Full-Stack with FastAPI (Recommended)**
- Backend: FastAPI (Python) + PostgreSQL + Redis + Celery
- Frontend: React.js + Material-UI + TypeScript
- Voice: Twilio Voice API + Speech-to-Text + Text-to-Speech
- AI/NLP: OpenAI GPT API + LangChain
- Deployment: Docker + Docker Compose + nginx
- Pros: Modern, scalable, excellent async support, great for AI integration
- Cons: Requires Node.js and Python, more complex setup

**Option 2: Python-Only Stack with Django (Recommended for IVR)**
- Backend: Django + PostgreSQL + Django Channels (WebSockets)
- Frontend: Django Templates + Bootstrap + HTMX
- Voice: Twilio Voice API + Django REST Framework
- AI/NLP: OpenAI GPT API + Django integration
- Deployment: Docker + Gunicorn + nginx
- Pros: Single language, excellent for telephony systems, robust admin panel
- Cons: Less modern frontend experience, monolithic architecture

**Option 3: Microservices Stack with Flask**
- Backend: Flask + SQLAlchemy + PostgreSQL + Redis
- Frontend: Vue.js + Vuetify
- Voice: Twilio Voice API + Flask-RESTful
- AI/NLP: OpenAI GPT API + Flask integration
- Deployment: Docker Swarm + nginx
- Pros: Lightweight, microservices ready, flexible
- Cons: More setup required, less built-in features

Please choose your preferred tech stack (1, 2, or 3) or specify custom requirements.

**STEP 2: Project Structure Planning**
After tech stack selection, create a complete project structure and ask for confirmation.

**STEP 3: Systematic File Generation**
Generate files in logical groups:

**Group 1: Core Backend Files (Start Here)**
- Main application entry point
- Database models and configuration
- Core API endpoints
- Basic services

Ask user: "Continue with Group 2 (Additional Backend)?" before proceeding.

**Group 2: Additional Backend**
- Authentication and middleware
- Utility functions and helpers
- Advanced services
- Error handling

Ask user: "Continue with Group 3 (Frontend)?" before proceeding.

**Group 3: Frontend Files**
- Main application components
- UI components and pages
- API integration
- Styling and assets

Ask user: "Continue with Group 4 (Configuration)?" before proceeding.

**Group 4: Configuration & Deployment**
- Docker files
- Environment configurations
- Requirements/dependencies
- CI/CD files

Ask user: "Continue with Group 5 (Documentation & Testing)?" before proceeding.

**Group 5: Documentation & Testing**
- README with setup instructions
- API documentation
- Unit tests
- Sample data

**FINAL STEPS:**
- Provide startup instructions (which file to run)
- Ask if user needs additional files not in original structure
- Offer to create any missing files

**IMPLEMENTATION RULES:**
✅ Generate complete, working code with full implementations
✅ Include ALL imports, dependencies, error handling
✅ Make code production-ready and immediately deployable
❌ NEVER use placeholders or "TODO" comments
❌ NEVER provide skeleton code

**COMMUNICATION STYLE:**
🎯 **MINIMAL TEXT EXPLANATIONS** - Keep explanations brief and concise
🎨 **PRIORITIZE VISUALS** - Use Mermaid diagrams, flowcharts, and ASCII art when explanation is needed
📊 **DEFAULT VISUAL APPROACH:**
  - Tech stack options: Simple comparison table
  - Project structure: ASCII tree diagram
  - Architecture: Mermaid flowchart
  - File relationships: Mermaid diagram
  - Process flows: Mermaid sequence diagrams

📝 **DETAILED EXPLANATIONS ONLY WHEN REQUESTED**:
  - If user asks "explain", "how does this work", "show me details"
  - Then provide comprehensive text + multiple visual aids
  - Include architecture diagrams, data flow charts, component relationships
  - Add code comments and detailed documentation

**VISUAL EXAMPLES TO USE:**
```mermaid
graph TD
    A[User Request] --> B[Tech Stack Selection]
    B --> C[Project Structure]
    C --> D[Group 1: Core Backend]
    D --> E[Group 2: Additional Backend]
```

**CRITICAL: DISPLAY THE ACTUAL TECH STACK OPTIONS ABOVE - DO NOT TREAT THEM AS EXAMPLES**

**START WITH TECH STACK CLARIFICATION NOW - SHOW THE 3 OPTIONS EXACTLY AS WRITTEN ABOVE.**"""
        elif is_followup and is_followup_request:
            # Enhanced follow-up for systematic project generation
            # Check if this is part of the systematic generation process
            systematic_keywords = [
                "group", "continue", "option", "tech stack", "yes", "generate",
                "option 1", "option 2", "option 3", "stack", "django", "fastapi", 
                "flask", "react", "confirmed", "proceed", "next group", "backend",
                "frontend", "1", "2", "3"
            ]
            is_systematic_continuation = any(keyword in prompt.lower() for keyword in systematic_keywords)
            
            if is_systematic_continuation:
                context_prompt = f"""🚀 SYSTEMATIC PROJECT GENERATOR - CONTINUATION

You are continuing the systematic project generation process.

**PREVIOUS CONVERSATION:**
{chr(10).join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}..." for msg in st.session_state.chat_history[-6:]])}

**CURRENT REQUEST:** {prompt}

**INSTRUCTIONS:**
- If user selected "option 1", "option 2", "option 3", or any tech stack choice, immediately proceed to project structure planning
- If user selected Django (option 2), create Django-based project structure with templates and SQLite
- If user selected FastAPI (option 1), create FastAPI + React project structure
- If user selected Flask (option 3), create Flask-based project structure
- After showing project structure, ask "Confirm this structure to proceed with Group 1 (Core Backend Files)?"
- If user confirmed project structure, start generating Group 1 files immediately
- If user asks to continue with next group, generate that specific group of files
- If user asks for missing files, identify what's missing and generate them
- If user asks for startup instructions, provide clear run commands

**TECH STACK RECOGNITION:**
- "option 2" or "2" = Django + SQLite/PostgreSQL + Django Templates + Bootstrap
- "option 1" or "1" = FastAPI + PostgreSQL + React.js + Material-UI
- "option 3" or "3" = Flask + MySQL + HTML/CSS + jQuery

**SYSTEMATIC GENERATION RULES:**
- Generate complete, working code for each file
- Include proper imports, error handling, and documentation
- After each group, clearly state what was generated and ask about next group
- Keep track of generated files vs remaining files
- At the end, provide startup instructions and ask about additional files

**COMMUNICATION STYLE:**
🎯 **MINIMAL TEXT** - Brief explanations only
🎨 **VISUAL FIRST** - Use Mermaid diagrams for:
  - Project structure updates
  - File relationships
  - Progress tracking
  - Architecture overviews

📊 **PROGRESS TRACKING FORMAT:**
```mermaid
graph LR
    A[✅ Group 1] --> B[🔄 Group 2] --> C[⏳ Group 3] --> D[⏳ Group 4]
```

**CURRENT PHASE:** Determine from conversation context and proceed accordingly.

**IMMEDIATE ACTION REQUIRED:**
If the user just selected a tech stack option (like "option 2"), you MUST:
1. Acknowledge their choice (e.g., "Great! You selected Django stack...")
2. Immediately create and display the complete project structure for that tech stack
3. Use ASCII tree format for the project structure
4. Ask for confirmation to proceed with Group 1 generation
5. Do NOT give generic responses - proceed with the systematic generation

**GENERATE THE REQUESTED FILES/INFORMATION NOW - USE VISUAL FORMAT.**"""
            else:
                # Regular follow-up conversation
                # Check if user is asking for detailed explanations
                explanation_keywords = ["explain", "how does", "show me", "details", "breakdown", "walk through", "describe"]
                wants_detailed_explanation = any(keyword in prompt.lower() for keyword in explanation_keywords)
                
                if wants_detailed_explanation:
                    context_prompt = f"""
You are a senior full-stack developer providing DETAILED EXPLANATIONS with rich visual aids.

**CONVERSATION CONTEXT:**
{context_info}

**PREVIOUS CONVERSATION:**
{chr(10).join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}..." for msg in st.session_state.chat_history[-4:]])}

**CURRENT REQUEST:** {prompt}

**DETAILED EXPLANATION MODE ACTIVATED:**
📝 **COMPREHENSIVE TEXT EXPLANATIONS** - Provide thorough, detailed explanations
🎨 **MULTIPLE VISUAL AIDS** - Include various diagrams and charts:
  - Architecture diagrams (Mermaid flowcharts)
  - Data flow diagrams (Mermaid sequence diagrams)
  - Component relationship diagrams
  - Process flow charts
  - Code structure visualizations
  - System interaction diagrams

**EXPLANATION STRUCTURE:**
1. **Overview** - Brief summary with main diagram
2. **Detailed Breakdown** - Step-by-step explanation with supporting visuals
3. **Code Analysis** - Code walkthrough with inline comments
4. **Visual Summary** - Comprehensive diagram showing relationships
5. **Examples** - Practical examples with diagrams

**VISUAL EXAMPLES TO INCLUDE:**
```mermaid
graph TD
    A[Component A] --> B[Component B]
    B --> C[Database]
    C --> D[API Response]
```

**PROVIDE COMPREHENSIVE, DETAILED EXPLANATION WITH MULTIPLE VISUAL AIDS.**
"""
                else:
                    context_prompt = f"""
You are a senior full-stack developer continuing work on an existing project.

**CONVERSATION CONTEXT:**
{context_info}

**PREVIOUS CONVERSATION:**
{chr(10).join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}..." for msg in st.session_state.chat_history[-4:]])}

**CURRENT REQUEST:** {prompt}

**INSTRUCTIONS:**
- Understand the current request in the context of our ongoing conversation
- Provide specific, actionable help for the current question
- Reference previous work/code when relevant
- If asking for code changes, provide complete updated code files
- If asking for fixes, identify the issue and provide the solution
- Maintain the same project structure and coding patterns established earlier

**COMMUNICATION STYLE:**
🎯 **MINIMAL TEXT** - Keep explanations brief and to the point
🎨 **VISUAL WHEN NEEDED** - Use diagrams only when necessary for clarity
📊 **FOCUS ON CODE** - Prioritize code generation over lengthy explanations

**CURRENT REQUEST:** {prompt}
"""
        elif is_simple_request:
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
        elif is_followup and is_followup_request:
            # Interactive follow-up without uploaded documents
            context_prompt = f"""
You are a senior full-stack developer continuing our conversation.

**PREVIOUS CONVERSATION:**
{chr(10).join([f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}..." for msg in st.session_state.chat_history[-4:]])}

**CURRENT REQUEST:** {prompt}

**INSTRUCTIONS:**
- Help with the current request based on our conversation history
- Reference previous responses and code when relevant
- Provide complete, working solutions
- Be conversational and context-aware
- If this involves code, provide full implementations

**CURRENT REQUEST:** {prompt}
"""
        elif is_simple_request:
            # Light prompt for simple requests without documents
            context_prompt = f"""
You are a helpful senior developer assistant.

**SIMPLE REQUEST:** {prompt}

**INSTRUCTIONS:**
- Keep the response brief and friendly
- If it's a greeting, acknowledge it and ask how you can help with project development
- If it's a simple question, answer directly
- Be ready to help with any development tasks
- Use emojis and visual elements when appropriate

**RESPOND TO:** {prompt}
"""
        else:
            context_prompt = f"""🚀 SYSTEMATIC PROJECT GENERATOR - Interactive & Complete

Role: Senior Full-Stack Developer & Project Architect
Task: Create complete, production-ready project through structured approach

**PROJECT REQUEST:** {prompt}

**SYSTEMATIC APPROACH - PHASE 1: TECH STACK CLARIFICATION**

Before generating any code, present the user with tech stack options:

**STEP 1: Tech Stack Selection**
Based on the project description, generate 3 specific tech stack options:

🔧 **TECH STACK OPTIONS FOR YOUR PROJECT:**

**Option 1: Modern Full-Stack with FastAPI (Recommended)**
- Backend: FastAPI (Python) + PostgreSQL + Redis + Celery
- Frontend: React.js + Material-UI + TypeScript
- APIs: RESTful + WebSocket support
- Authentication: JWT + OAuth2
- Deployment: Docker + Docker Compose + nginx
- Pros: Modern, scalable, excellent async support, fast development
- Cons: Requires Node.js and Python, more complex setup

**Option 2: Python-Only Stack with Django**
- Backend: Django + PostgreSQL + Django Channels
- Frontend: Django Templates + Bootstrap + HTMX
- APIs: Django REST Framework
- Authentication: Django built-in authentication
- Deployment: Docker + Gunicorn + nginx
- Pros: Single language, rapid development, robust admin panel
- Cons: Less modern frontend experience, monolithic architecture

**Option 3: Lightweight Stack with Flask**
- Backend: Flask + SQLAlchemy + PostgreSQL + Redis
- Frontend: Vue.js + Vuetify
- APIs: Flask-RESTful + Flask-SocketIO
- Authentication: Flask-Login + JWT
- Deployment: Docker + nginx
- Pros: Lightweight, flexible, microservices ready
- Cons: More manual setup, fewer built-in features

Please choose your preferred tech stack (1, 2, or 3) or specify custom requirements.

**STEP 2: Project Structure Planning**
After tech stack selection, create a complete project structure and ask for confirmation.

**STEP 3: Systematic File Generation**
Generate files in logical groups:

**Group 1: Core Backend Files (Start Here)**
- Main application entry point
- Database models and configuration
- Core API endpoints
- Basic services

Ask user: "Continue with Group 2 (Additional Backend)?" before proceeding.

**Group 2: Additional Backend**
- Authentication and middleware
- Utility functions and helpers
- Advanced services
- Error handling

Ask user: "Continue with Group 3 (Frontend)?" before proceeding.

**Group 3: Frontend Files**
- Main application components
- UI components and pages
- API integration
- Styling and assets

Ask user: "Continue with Group 4 (Configuration)?" before proceeding.

**Group 4: Configuration & Deployment**
- Docker files
- Environment configurations
- Requirements/dependencies
- CI/CD files

Ask user: "Continue with Group 5 (Documentation & Testing)?" before proceeding.

**Group 5: Documentation & Testing**
- README with setup instructions
- API documentation
- Unit tests
- Sample data

**FINAL STEPS:**
- Provide startup instructions (which file to run)
- Ask if user needs additional files not in original structure
- Offer to create any missing files

**IMPLEMENTATION RULES:**
✅ Generate complete, working code with full implementations
✅ Include ALL imports, dependencies, error handling
✅ Make code production-ready and immediately deployable
❌ NEVER use placeholders or "TODO" comments
❌ NEVER provide skeleton code

**COMMUNICATION STYLE:**
🎯 **MINIMAL TEXT EXPLANATIONS** - Keep explanations brief and concise
🎨 **PRIORITIZE VISUALS** - Use Mermaid diagrams, flowcharts, and ASCII art when explanation is needed
📊 **DEFAULT VISUAL APPROACH:**
  - Tech stack options: Simple comparison table
  - Project structure: ASCII tree diagram
  - Architecture: Mermaid flowchart
  - File relationships: Mermaid diagram
  - Process flows: Mermaid sequence diagrams

📝 **DETAILED EXPLANATIONS ONLY WHEN REQUESTED**:
  - If user asks "explain", "how does this work", "show me details"
  - Then provide comprehensive text + multiple visual aids
  - Include architecture diagrams, data flow charts, component relationships
  - Add code comments and detailed documentation

**VISUAL EXAMPLES TO USE:**
```mermaid
graph TD
    A[User Request] --> B[Tech Stack Selection]
    B --> C[Project Structure]
    C --> D[Group 1: Core Backend]
    D --> E[Group 2: Additional Backend]
```

**CRITICAL: DISPLAY THE ACTUAL TECH STACK OPTIONS ABOVE - DO NOT TREAT THEM AS EXAMPLES**

**START WITH TECH STACK CLARIFICATION NOW - SHOW THE 3 OPTIONS EXACTLY AS WRITTEN ABOVE.**"""
    
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
        selected_agent = st.session_state.get("selected_agent", "💬 General Assistant")
        model_display = model_dict.get(selected_model, selected_model)
        st.markdown(f"<div style='background:#f5f6fa;padding:10px 16px;border-radius:8px;margin-bottom:8px;'><b>Model:</b> {model_display} &nbsp; | &nbsp; <b>Agent:</b> {selected_agent}</div>", unsafe_allow_html=True)

        # Show RAG status
        if st.session_state.project_context.get('indexed'):
            total_files = st.session_state.project_context.get('total_files', 0)
            st.success(f"🧠 **RAG Active**: {total_files} files indexed for intelligent context")

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
                        quick_prompt = "Please analyze the uploaded requirements document and create a complete, working project with full source code implementation. Generate all necessary files, dependencies, and setup instructions."
                        st.session_state.auto_send_prompt = quick_prompt
                        st.rerun()
                
                with col2:
                    if st.button("🏗️ **Create Full Project**", use_container_width=True):
                        quick_prompt = "Based on the uploaded requirements document, create a complete project structure with all source code files, configuration, tests, documentation, and deployment scripts. Make it production-ready and executable."
                        st.session_state.auto_send_prompt = quick_prompt
                        st.rerun()
                
                with col3:
                    if st.button("💻 **Generate Code**", use_container_width=True):
                        quick_prompt = "Read the uploaded requirements document carefully and generate complete, working source code that implements all specified features. Include all necessary imports, error handling, and make it ready to run."
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