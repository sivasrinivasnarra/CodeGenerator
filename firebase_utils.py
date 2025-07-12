import os
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
from dotenv import load_dotenv
from datetime import datetime
import uuid
from gemini_utils import generate_chat_title as generate_gemini_title
from openai_utils import generate_chat_title as generate_openai_title

load_dotenv()

# Pyrebase config for Auth
firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL"),
}

firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

# Firebase Admin for Firestore
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_service_account.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Auth functions
def sign_in(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        return user
    except Exception as e:
        return None

def sign_up(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        return user
    except Exception as e:
        # Pyrebase returns error details in e.args[1] as a JSON string
        try:
            import json
            error_json = json.loads(e.args[1])
            error_message = error_json['error']['message']
            return {"error": error_message}
        except Exception:
            return {"error": str(e)}

def get_user_id(user):
    return user['localId']

# --- Multi-session chat functions ---
def list_user_chats(user_id, model_type="gemini"):
    """List all chat sessions for a user, showing only summarized chat titles."""
    try:
        chats_ref = db.collection('users').document(user_id).collection('chats')
        chats = chats_ref.order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        chat_list = []
        
        for chat in chats:
            chat_dict = chat.to_dict()
            chat_id = chat.id
            history = chat_dict.get('history', [])
            created_at = chat_dict.get('created_at', 'Unknown date')
            
            # Try to format the created_at timestamp
            try:
                if hasattr(created_at, 'strftime'):
                    created_at = created_at.strftime('%Y-%m-%d %H:%M')
                elif isinstance(created_at, str):
                    # Try to parse ISO format
                    from datetime import datetime
                    parsed_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = parsed_date.strftime('%Y-%m-%d %H:%M')
            except:
                created_at = 'Unknown date'
            
            # Get title from stored title or generate fallback
            title = chat_dict.get('title')
            if not title or title.startswith('New Chat'):
                # Generate fallback title from history
                if history:
                    for msg in history:
                        if msg.get('role') == 'user' and msg.get('content'):
                            content = msg['content'].strip()
                            if not content.startswith('[Uploaded file:'):
                                title = content[:40] + ("..." if len(content) > 40 else "")
                                break
                    if not title:
                        title = f"Chat Session - {created_at}"
                else:
                    title = f"Empty Chat - {created_at}"
            
            # Check if chat has project files
            has_project_files = chat_dict.get('has_project_files', False) or chat_dict.get('project_context', {}).get('indexed', False)
            
            chat_list.append({
                "chat_id": chat_id, 
                "title": title,
                "created_at": created_at,
                "has_project_files": has_project_files,
                "message_count": len(history)
            })
        
        return chat_list
    
    except Exception as e:
        print(f"Error loading chat history: {str(e)}")
        return []

def create_new_chat(user_id, title=None, model_type="gemini"):
    """Create a new chat session and return its chat_id. Optionally set a title."""
    chats_ref = db.collection('users').document(user_id).collection('chats')
    chat_id = str(uuid.uuid4())
    chat_doc = chats_ref.document(chat_id)
    
    # Generate a default title if none provided
    if not title:
        if model_type == "enhanced":
            title = "New Chat Session"
        else:
            title = f"New Chat ({model_type.capitalize()})"
    
    try:
        chat_doc.set({
            "created_at": datetime.utcnow().isoformat(),
            "history": [],
            "title": title,
            "model_type": model_type,
            "has_project_files": False
        })
        print(f"Created new chat: {chat_id} with title: {title}")
        return chat_id
    except Exception as e:
        print(f"Error creating chat: {str(e)}")
        return None

def get_chat_history(user_id, chat_id):
    try:
        chat_doc = db.collection('users').document(user_id).collection('chats').document(chat_id).get()
        if chat_doc.exists:
            history = chat_doc.to_dict().get('history', [])
            print(f"Loaded chat {chat_id}: {len(history)} messages")
            return history
        else:
            print(f"Chat {chat_id} not found")
            return []
    except Exception as e:
        print(f"Error loading chat history for {chat_id}: {str(e)}")
        return []

def summarize_title_from_history(history):
    """Generate a short title from the first user message or a summary of the chat."""
    for msg in history:
        if msg.get('role') == 'user' and msg.get('content'):
            content = msg['content'].strip()
            return content[:40] + ("..." if len(content) > 40 else "")
    return "Chat"

def add_message_to_chat(user_id, chat_id, message, model_type="gemini"):
    chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
    chat_doc = chat_ref.get()
    if chat_doc.exists:
        history = chat_doc.to_dict().get('history', [])
        current_title = chat_doc.to_dict().get('title', 'New Chat')
    else:
        history = []
        current_title = 'New Chat'
    history.append(message)
    # Update title logic
    new_title = current_title
    # If this is a file upload, use the file name as title
    if message.get('role') == 'user' and '[Uploaded file:' in message.get('content', ''):
        import re
        match = re.search(r'\[Uploaded file: ([^\(]+)', message['content'])
        if match:
            new_title = match.group(1).strip()
    # If we have enough messages (at least 2 user messages), generate a proper title
    if len([msg for msg in history if msg.get('role') == 'user']) >= 2:
        # Only generate title if current title is still the default
        if current_title.startswith('New Chat') or current_title == 'Chat':
            try:
                if model_type.startswith("gemini"):
                    new_title = generate_gemini_title(history)
                else:
                    # Default to OpenAI for all other models (including gpt models)
                    new_title = generate_openai_title(history)
            except Exception as e:
                # If title generation fails, keep current title
                new_title = current_title
    chat_ref.update({'history': history, 'title': new_title})

def set_chat_title(user_id, chat_id, title):
    chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
    chat_ref.update({'title': title})

def regenerate_chat_title(user_id, chat_id, model_type="gemini"):
    """Regenerate the title for a chat using AI."""
    chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
    chat_doc = chat_ref.get()
    
    if not chat_doc.exists:
        return False
    
    history = chat_doc.to_dict().get('history', [])
    if len(history) < 2:
        return False
    
    try:
        if model_type.startswith("gemini"):
            new_title = generate_gemini_title(history)
        else:
            # Default to OpenAI for all other models (including gpt models)
            new_title = generate_openai_title(history)
        
        chat_ref.update({'title': new_title})
        return True
    except Exception as e:
        return False

# --- Legacy single-chat fallback (for migration/compatibility) ---
def get_user_chats(user_id):
    """Legacy: get single chat history (for backward compatibility)."""
    doc_ref = db.collection('chats').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('history', [])
    return []

def add_message(user_id, message):
    doc_ref = db.collection('chats').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        history = doc.to_dict().get('history', [])
    else:
        history = []
    history.append(message)
    doc_ref.set({'history': history})

def clear_chat_history(user_id):
    doc_ref = db.collection('chats').document(user_id)
    doc_ref.set({'history': []}) 