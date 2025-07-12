"""
Utilities for interacting with Gemini and other LLMs.
"""
import os
import io
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
import zipfile

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")


def format_history_for_gemini(chat_history):
    """Format chat history for Gemini prompt."""
    formatted = ""
    for msg in chat_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted += f"{role}: {content}\n"
    return formatted


def trim_history(chat_history, max_messages=20):
    """Trim chat history to the last max_messages."""
    if len(chat_history) > max_messages:
        return chat_history[-max_messages:]
    return chat_history


def generate_gemini_response(chat_history, files=None, model_name=None, location=None):
    """
    Generate a Gemini response using google-generativeai for text, images, code/text files, and zip files.
    Uses onboarding prompt only when files are uploaded for project context.
    files: list of dicts with keys 'bytes', 'type', and 'name'.
    model_name: str, optional, overrides the default model.
    location: str, optional, not used for google-generativeai.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "[GOOGLE_API_KEY not set in environment.]"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name or MODEL)
        
        # Only use onboarding prompt when files are uploaded
        if files and isinstance(files, list) and len(files) > 0:
            onboarding = get_onboarding_prompt()
            prompt = onboarding + "\n\n" + format_history_for_gemini(trim_history(chat_history))
        else:
            prompt = format_history_for_gemini(trim_history(chat_history))
            
        contents = [prompt]
        if files and isinstance(files, list):
            for file_info in files:
                file_bytes = file_info.get('bytes')
                file_type = file_info.get('type', '')
                file_name = file_info.get('name', 'uploaded_file')
                if not file_bytes:
                    continue  # skip empty files
                if file_type.startswith('image/'):
                    try:
                        image = Image.open(io.BytesIO(file_bytes))
                        contents.append(image)
                    except Exception:
                        contents.append(f"\n[File: {file_name}]: [Error reading image file]")
                elif file_type == 'application/zip' or file_name.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                            for zipinfo in zf.infolist():
                                if zipinfo.is_dir():
                                    continue
                                inner_name = zipinfo.filename
                                try:
                                    with zf.open(zipinfo) as inner_file:
                                        # Only include text-like files (not binaries)
                                        try:
                                            inner_bytes = inner_file.read()
                                            inner_text = inner_bytes.decode('utf-8')
                                        except Exception:
                                            try:
                                                inner_text = inner_bytes.decode('latin-1', errors='replace')
                                            except Exception:
                                                inner_text = '[Unreadable file content]'
                                        # Only include small files (e.g., <50KB)
                                        if len(inner_text) < 50000:
                                            contents.append(f"\n[Zip File: {file_name} | {inner_name}]:\n" + inner_text)
                                        else:
                                            contents.append(f"\n[Zip File: {file_name} | {inner_name}]: [File too large to display]")
                                except Exception:
                                    contents.append(f"\n[Zip File: {file_name} | {inner_name}]: [Error reading file]")
                    except Exception:
                        contents.append(f"\n[File: {file_name}]: [Error reading zip file]")
                elif (
                    file_type.startswith('text/') or
                    file_type == 'application/octet-stream' or
                    file_name.endswith('.py')
                ):
                    try:
                        code_text = file_bytes.decode('utf-8')
                    except Exception:
                        code_text = file_bytes.decode('latin-1', errors='replace')
                    contents.append(f"\n[File: {file_name}]:\n" + code_text)
                else:
                    contents.append(f"\n[File: {file_name}]: [Unsupported file type: {file_type}]")
        try:
            # Check total content size to avoid 500 errors
            total_chars = sum(len(str(content)) for content in contents)
            if total_chars > 1000000:  # 1M character limit (roughly 750K tokens)
                # Smart truncation that preserves critical prompt instructions
                if len(contents) > 1:
                    # Keep prompt but truncate file contents more aggressively
                    prompt_content = str(contents[0])
                    truncated_files = []
                    for content in contents[1:]:
                        content_str = str(content)
                        if len(content_str) > 30000:  # More aggressive truncation for files
                            truncated_files.append(content_str[:30000] + "\n\n[... content truncated due to size limits ...]")
                        else:
                            truncated_files.append(content)
                    contents = [prompt_content] + truncated_files
                else:
                    # For main prompt, preserve critical instructions at the beginning
                    prompt_str = str(contents[0])
                    if "🚀 CRITICAL DIRECTIVE" in prompt_str:
                        # Find the end of critical instructions
                        directive_end = prompt_str.find("**UPLOADED REQUIREMENTS:**") 
                        if directive_end == -1:
                            directive_end = prompt_str.find("**PROJECT REQUEST:**")
                        if directive_end == -1:
                            directive_end = 5000  # Fallback
                        
                        # Preserve critical instructions + reasonable amount of context
                        critical_part = prompt_str[:directive_end]
                        remaining_space = 750000 - len(critical_part)
                        context_part = prompt_str[directive_end:directive_end + remaining_space] if remaining_space > 0 else ""
                        contents[0] = critical_part + context_part + "\n\n[... prompt truncated but critical instructions preserved ...]"
                    else:
                        # Standard truncation for non-critical prompts
                        contents[0] = prompt_str[:800000] + "\n\n[... prompt truncated due to size limits ...]"
            
            response = model.generate_content(contents)
        except Exception as exc:
            # More specific error handling
            error_str = str(exc)
            if "500" in error_str or "internal error" in error_str.lower():
                return f"[Error from Gemini: 500 Internal Error - Request may be too large. Try with smaller files or shorter prompts. Original error: {exc}]"
            elif "quota" in error_str.lower() or "limit" in error_str.lower():
                return f"[Error from Gemini: API quota exceeded. Please check your usage limits. Original error: {exc}]"
            else:
                return f"[Error from Gemini: {exc}]"
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as exc:
        return f"[Unexpected error: {exc}]"


def get_onboarding_prompt():
    """
    Returns the onboarding prompt for Gemini to act as a highly experienced and technically skilled Project Manager, guiding new team members through the project structure and workflow.
    """
    return (
        "You are a highly experienced and technically skilled Project Manager with deep understanding of software architecture, cloud platforms, data engineering, and AI workflows. "
        "Your role is to onboard new team members by clearly and concisely explaining the structure, purpose, and flow of project files and code.\n\n"
        "For any project or codebase:\n"
        
        "– Start with a high-level overview of the project: its purpose, goals, and technologies used\n"
        "– Explain the folder and file structure, including the role of key files\n"
        "– Walk through the main logic or workflow in a simple, non-jargon-heavy way\n"
        "– Clarify any dependencies, configuration files, and environment setup\n"
        "– Highlight scope boundaries and current progress\n"
        "– Suggest possible areas of improvement or future extensions\n"
        "– Always assume the listener is joining the project mid-way and may not have seen the code before\n"
        "– Keep the tone clear, friendly, and supportive—like a mentor helping a new teammate get up to speed"
    )


def generate_chat_title(chat_history):
    """
    Generate a short, clear title for the chat using Gemini.
    Only the first 10 messages are used for efficiency.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "[GOOGLE_API_KEY not set in environment.]"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL)
    trimmed_history = trim_history(chat_history, max_messages=10)
    prompt = (
        get_onboarding_prompt() +
        "\n\nSummarize this conversation in a short, clear title (max 8 words):\n" +
        format_history_for_gemini(trimmed_history)
    )
    try:
        # Limit prompt size for title generation
        if len(prompt) > 10000:
            prompt = prompt[:10000] + "...[truncated for title generation]"
        
        response = model.generate_content(prompt)
        return response.text.strip().replace('\n', ' ')
    except Exception as exc:
        # Return a simple fallback title instead of error
        if chat_history and len(chat_history) > 0:
            first_user_msg = next((msg.get('content', '') for msg in chat_history if msg.get('role') == 'user'), '')
            if first_user_msg:
                return first_user_msg[:40] + ("..." if len(first_user_msg) > 40 else "")
        return "Chat Session"


def generate_gemini_image(text_description: str):
    """
    Generate an image using Gemini 2.0 Flash model based on text description.
    Returns the image as bytes that can be displayed in Streamlit.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None, "[GOOGLE_API_KEY not set in environment.]"
        
        genai.configure(api_key=api_key)
        
        # Use Gemini 2.0 Flash for image generation
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Create a prompt for diagram generation
        diagram_prompt = f"""
        Create a professional workflow diagram based on this description: {text_description}
        
        You are a highly skilled AI systems analyst and technical architect. You will be given detailed documentation of a software or data project. Based on this documentation, your task is to analyze the content, extract key components, and generate a professional and logical end-to-end workflow diagram of the entire project.

        The diagram should include:

        Key system components (e.g., input sources, processing layers, databases, APIs, front-ends)

        Data or control flow between components

        Technologies or tools used (if mentioned)

        Any conditional logic or branching in the process

        Clear labeling and logical structure

        Your output should only provide diagram in Markdown mermaid format.

        Assume your audience is a new technical team member who needs to quickly understand the architecture and flow of the project.
        """
        
        # Generate the image
        response = model.generate_content(diagram_prompt)
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # Return the image bytes
                        return part.inline_data.data, None
        
        return None, "No image generated"
        
    except Exception as exc:
        return None, f"[Error generating image: {exc}]" 