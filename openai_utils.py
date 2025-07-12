"""
Utilities for interacting with OpenAI ChatGPT and other OpenAI models.
"""
import os
import io
from dotenv import load_dotenv
import openai
from PIL import Image
import zipfile
import base64

load_dotenv()

# OpenAI configuration
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


def format_history_for_openai(chat_history):
    """Format chat history for OpenAI API."""
    formatted_messages = []
    for msg in chat_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted_messages.append({"role": role, "content": content})
    return formatted_messages


def trim_history(chat_history, max_messages=20):
    """Trim chat history to the last max_messages."""
    if len(chat_history) > max_messages:
        return chat_history[-max_messages:]
    return chat_history


def encode_image_to_base64(image_bytes):
    """Encode image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode('utf-8')


def generate_openai_response(chat_history, files=None, model_name=None, location=None):
    """
    Generate an OpenAI response using OpenAI API for text, images, code/text files, and zip files.
    Always prepends the onboarding prompt to the chat context.
    files: list of dicts with keys 'bytes', 'type', and 'name'.
    model_name: str, optional, overrides the default model.
    location: str, optional, not used for OpenAI API.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "[OPENAI_API_KEY not set in environment.]"
        
        # Create OpenAI client with new API
        client = openai.OpenAI(api_key=api_key)
        model = model_name or DEFAULT_MODEL
        
        # Get onboarding prompt
        onboarding = get_onboarding_prompt()
        
        # Format messages for OpenAI
        messages = [{"role": "system", "content": onboarding}]
        
        # Add chat history
        formatted_history = format_history_for_openai(trim_history(chat_history))
        messages.extend(formatted_history)
        
        # Process files if any
        if files and isinstance(files, list):
            for file_info in files:
                file_bytes = file_info.get('bytes')
                file_type = file_info.get('type', '')
                file_name = file_info.get('name', 'uploaded_file')
                
                if not file_bytes:
                    continue
                
                if file_type.startswith('image/'):
                    try:
                        # For images, we need to add them as content with base64 encoding
                        base64_image = encode_image_to_base64(file_bytes)
                        image_content = {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{file_type};base64,{base64_image}"
                            }
                        }
                        # Add image as a separate user message
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Here is an image file: {file_name}"},
                                image_content
                            ]
                        })
                    except Exception as e:
                        messages.append({
                            "role": "user", 
                            "content": f"[File: {file_name}]: [Error reading image file: {e}]"
                        })
                
                elif file_type == 'application/zip' or file_name.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                            zip_content = []
                            for zipinfo in zf.infolist():
                                if zipinfo.is_dir():
                                    continue
                                inner_name = zipinfo.filename
                                try:
                                    with zf.open(zipinfo) as inner_file:
                                        inner_bytes = inner_file.read()
                                        try:
                                            inner_text = inner_bytes.decode('utf-8')
                                        except Exception:
                                            try:
                                                inner_text = inner_bytes.decode('latin-1', errors='replace')
                                            except Exception:
                                                inner_text = '[Unreadable file content]'
                                        
                                        if len(inner_text) < 50000:
                                            zip_content.append(f"[Zip File: {file_name} | {inner_name}]:\n{inner_text}")
                                        else:
                                            zip_content.append(f"[Zip File: {file_name} | {inner_name}]: [File too large to display]")
                                except Exception:
                                    zip_content.append(f"[Zip File: {file_name} | {inner_name}]: [Error reading file]")
                            
                            if zip_content:
                                messages.append({
                                    "role": "user",
                                    "content": f"Here are the contents of the zip file {file_name}:\n\n" + "\n\n".join(zip_content)
                                })
                    except Exception as e:
                        messages.append({
                            "role": "user",
                            "content": f"[File: {file_name}]: [Error reading zip file: {e}]"
                        })
                
                elif (
                    file_type.startswith('text/') or
                    file_type == 'application/octet-stream' or
                    file_name.endswith('.py')
                ):
                    try:
                        code_text = file_bytes.decode('utf-8')
                    except Exception:
                        code_text = file_bytes.decode('latin-1', errors='replace')
                    
                    messages.append({
                        "role": "user",
                        "content": f"Here is the content of file {file_name}:\n\n{code_text}"
                    })
                
                else:
                    messages.append({
                        "role": "user",
                        "content": f"[File: {file_name}]: [Unsupported file type: {file_type}]"
                    })
        
        # Make API call
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except openai.RateLimitError:
            return ("[OpenAI Rate Limited] You've exceeded the rate limit for OpenAI API. "
                   "Please wait a moment and try again, or consider upgrading your plan.")
        except openai.AuthenticationError:
            return ("[OpenAI Authentication Error] Your API key is invalid or expired. "
                   "Please check your OPENAI_API_KEY in the .env file.")
        except openai.PermissionDeniedError:
            return ("[OpenAI Access Forbidden] Your account doesn't have access to this model or feature. "
                   "Please check your OpenAI account permissions.")
        except openai.QuotaExceededError:
            return ("[OpenAI Quota Exceeded] You've reached your OpenAI API quota limit. "
                   "Please add payment information or upgrade your plan at https://platform.openai.com/.")
        except openai.APIError as exc:
            return f"[Error from OpenAI: {exc}]"
            
    except Exception as exc:
        return f"[Unexpected error: {exc}]"


def get_onboarding_prompt():
    """
    Returns the onboarding prompt for OpenAI to act as a highly experienced and technically skilled Project Manager, guiding new team members through the project structure and workflow.
    """
    return (
        "You are a highly experienced and technically skilled Project Manager with deep understanding of software architecture, cloud platforms, data engineering, and AI workflows. "
        "Your role is to onboard new team members by clearly and concisely explaining the structure, purpose, and flow of project files and code.\n\n"
        "For any project or codebase:\n"
        "– Create an animated workflow diagram in Mermaid syntax (suitable for copy-pasting into Mermaid live editors or compatible tools like Lucidchart, Atlassian, etc.), clearly showing what happens first and then so on\n"
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
    Generate a short, clear title for the chat using OpenAI.
    Only the first 10 messages are used for efficiency.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "[OPENAI_API_KEY not set in environment.]"
    
    # Create OpenAI client with new API
    client = openai.OpenAI(api_key=api_key)
    model = DEFAULT_MODEL
    
    trimmed_history = trim_history(chat_history, max_messages=10)
    messages = [
        {"role": "system", "content": get_onboarding_prompt()},
        {"role": "user", "content": f"Summarize this conversation in a short, clear title (max 8 words):\n{format_history_for_openai(trimmed_history)}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=50,
            temperature=0.3
        )
        return response.choices[0].message.content.strip().replace('\n', ' ')
    except openai.RateLimitError:
        return "OpenAI Chat (Rate Limited)"
    except openai.AuthenticationError:
        return "OpenAI Chat (Auth Error)"
    except openai.PermissionDeniedError:
        return "OpenAI Chat (Access Forbidden)"
    except openai.QuotaExceededError:
        return "OpenAI Chat (Quota Exceeded)"
    except openai.APIError as exc:
        return f"OpenAI Chat (Error: {exc})"


def generate_dalle_image(prompt: str):
    """
    Generate an image using OpenAI DALL·E 2 from a text prompt.
    Returns (image_url, error_message)
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "[OPENAI_API_KEY not set in environment.]"
        client = openai.OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        # Debug: print the response type and content
        print("DALL·E response:", response)
        if hasattr(response, 'data') and response.data:
            first = response.data[0]
            if isinstance(first, dict) and 'url' in first:
                return first['url'], None
            elif hasattr(first, 'url'):
                return first.url, None
        return None, "No image URL returned"
    except Exception as exc:
        return None, f"[Error generating image: {exc}]" 