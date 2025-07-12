"""
Model Adapter for AI Agents and RAG System
Bridges the AI agents with existing model utilities (Gemini, OpenAI, etc.)
"""

from typing import List, Dict, Optional
from gemini_utils import generate_gemini_response
from openai_utils import generate_openai_response
import os
import tempfile
from io import BytesIO

try:
    from docx import Document
    import docx2txt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

class ModelClient:
    """Unified client for different AI models."""
    
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name
        self.provider = self._get_provider(model_name)
    
    def _get_provider(self, model_name: str) -> str:
        """Determine provider from model name."""
        if model_name.startswith("gemini"):
            return "gemini"
        elif model_name.startswith("gpt") or model_name.startswith("o1"):
            return "openai"
        else:
            return "gemini"  # default
    
    def generate_response(self, prompt: str, files: Optional[List[Dict]] = None) -> str:
        """Generate response using the appropriate model."""
        chat_history = [{"role": "user", "content": prompt}]
        
        try:
            if self.provider == "gemini":
                return generate_gemini_response(chat_history, files=files, model_name=self.model_name)
            elif self.provider == "openai":
                return generate_openai_response(chat_history, files=files, model_name=self.model_name)
            else:
                return generate_gemini_response(chat_history, files=files, model_name=self.model_name)
        except Exception as e:
            return f"Error generating response: {str(e)}"

# Utility functions for Streamlit integration
def extract_files_from_uploaded(uploaded_files) -> Dict[str, str]:
    """Extract content from Streamlit uploaded files including Word documents."""
    files_content = {}
    
    for uploaded_file in uploaded_files:
        try:
            file_name = uploaded_file.name
            file_name_lower = file_name.lower()
            file_bytes = uploaded_file.read()
            
            if file_name_lower.endswith('.docx') and DOCX_AVAILABLE:
                # Handle Word .docx files
                try:
                    # Method 1: Try using python-docx
                    try:
                        doc = Document(BytesIO(file_bytes))
                        content = []
                        for paragraph in doc.paragraphs:
                            content.append(paragraph.text)
                        files_content[file_name] = '\n'.join(content)
                    except:
                        # Method 2: Fallback to docx2txt
                        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                            tmp_file.write(file_bytes)
                            tmp_file.flush()
                            content = docx2txt.process(tmp_file.name)
                            files_content[file_name] = content
                            os.unlink(tmp_file.name)  # Clean up temp file
                except Exception as e:
                    files_content[file_name] = f"[Error extracting Word document: {str(e)}]"
                    
            elif file_name_lower.endswith('.doc') and DOCX_AVAILABLE:
                # Handle older Word .doc files (limited support)
                try:
                    with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_file.flush()
                        try:
                            content = docx2txt.process(tmp_file.name)
                            files_content[file_name] = content
                        except:
                            # If docx2txt fails, mark as unsupported
                            files_content[file_name] = f"[Unsupported .doc format - please save as .docx: {file_name}]"
                        os.unlink(tmp_file.name)  # Clean up temp file
                except Exception as e:
                    files_content[file_name] = f"[Error processing .doc file: {str(e)}]"
            else:
                # Try to decode as text
                try:
                    content = file_bytes.decode('utf-8')
                    files_content[file_name] = content
                except UnicodeDecodeError:
                    # Check if Word documents are not supported
                    if (file_name_lower.endswith('.docx') or file_name_lower.endswith('.doc')) and not DOCX_AVAILABLE:
                        files_content[file_name] = f"[Word document support not available - install: pip install python-docx docx2txt]"
                    else:
                        # For other binary files, create a description
                        files_content[file_name] = f"[Binary file: {file_name}, Size: {len(file_bytes)} bytes]"
        
        except Exception as e:
            files_content[uploaded_file.name] = f"[Error reading file: {str(e)}]"
    
    return files_content 