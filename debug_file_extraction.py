#!/usr/bin/env python3
"""
Debug script for file extraction function
"""

import re

def debug_file_extraction():
    """Debug the file extraction function step by step"""
    
    # Sample AI response with project files
    sample_response = """
    I'll create a complete Python web application for you.
    
    📄 **src/main.py**
    ```python
    from flask import Flask, jsonify
    import os
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return jsonify({"message": "Hello World!"})
    
    if __name__ == '__main__':
        app.run(debug=True)
    ```
    
    📄 **requirements.txt**
    ```txt
    Flask==2.3.3
    python-dotenv==1.0.0
    ```
    
    📄 **README.md**
    ```markdown
    # My Web Application
    
    A simple Flask web application.
    
    ## Setup
    1. Install dependencies: `pip install -r requirements.txt`
    2. Run: `python src/main.py`
    ```
    
    📄 **.env.example**
    ```env
    FLASK_ENV=development
    FLASK_DEBUG=1
    ```
    """
    
    print("🔍 Debugging file extraction...")
    print("=" * 50)
    
    # Test Pattern 1: 📄 **filename.ext** ... ``` ... ```
    print("\n1️⃣ Testing Pattern 1: 📄 **filename.ext** ... ``` ... ```")
    explicit_pattern = r'📄\s*\*\*([^:]+):\*\*\s*\n```\n(.*?)```'
    explicit_matches = re.findall(explicit_pattern, sample_response, re.DOTALL)
    print(f"Found {len(explicit_matches)} matches:")
    for i, (file_path, content) in enumerate(explicit_matches):
        print(f"  Match {i+1}: {file_path} (content length: {len(content)})")
    
    # Test Pattern 2: **filename.ext** ... ``` ... ```
    print("\n2️⃣ Testing Pattern 2: **filename.ext** ... ``` ... ```")
    alt_pattern = r'\*\*([^:]+\.\w+)\*\*\s*\n```\n(.*?)```'
    alt_matches = re.findall(alt_pattern, sample_response, re.DOTALL)
    print(f"Found {len(alt_matches)} matches:")
    for i, (file_path, content) in enumerate(alt_matches):
        print(f"  Match {i+1}: {file_path} (content length: {len(content)})")
    
    # Test Pattern 3: File: filename.ext ... ``` ... ```
    print("\n3️⃣ Testing Pattern 3: File: filename.ext ... ``` ... ```")
    file_declaration_pattern = r'File:\s*([^\n]+\.\w+)\s*\n```\n(.*?)```'
    file_declaration_matches = re.findall(file_declaration_pattern, sample_response, re.DOTALL)
    print(f"Found {len(file_declaration_matches)} matches:")
    for i, (file_path, content) in enumerate(file_declaration_matches):
        print(f"  Match {i+1}: {file_path} (content length: {len(content)})")
    
    # Test Pattern 4: filename.ext ... ``` ... ``` (without explicit markers)
    print("\n4️⃣ Testing Pattern 4: filename.ext ... ``` ... ```")
    simple_pattern = r'([a-zA-Z0-9_\-/\\]+\.(?:py|js|ts|jsx|tsx|html|css|json|yaml|yml|md|txt|env|gitignore|dockerfile|sh|bat|xml|sql|java|cpp|c|h|go|rb|php|rs|kt|swift|dart|vue|svelte|astro|config|ini|toml|lock|log|sqlite|db|sql|sh|ps1|cmd|bat|exe|dll|so|dylib|a|o|class|jar|war|ear|rpm|deb|pkg|msi|app|ipa|apk|zip|tar|gz|bz2|7z|rar))\s*\n```\n(.*?)```'
    simple_matches = re.findall(simple_pattern, sample_response, re.DOTALL)
    print(f"Found {len(simple_matches)} matches:")
    for i, (file_path, content) in enumerate(simple_matches):
        print(f"  Match {i+1}: {file_path} (content length: {len(content)})")
    
    # Test Pattern 5: ```filename.ext ... ``` or ```path/to/filename.ext ... ```
    print("\n5️⃣ Testing Pattern 5: ```filename.ext ... ```")
    file_pattern1 = r'```(?:(\w+[/\\]\w+\.\w+)|(\w+\.\w+))\s*\n(.*?)```'
    matches1 = re.findall(file_pattern1, sample_response, re.DOTALL)
    print(f"Found {len(matches1)} matches:")
    for i, match in enumerate(matches1):
        file_path = match[0] if match[0] else match[1]
        content = match[2].strip()
        print(f"  Match {i+1}: {file_path} (content length: {len(content)})")
    
    # Now test the actual function
    print("\n" + "=" * 50)
    print("🧪 Testing actual function...")
    
    try:
        from app_final import extract_project_files_from_response
        files = extract_project_files_from_response(sample_response)
        print(f"✅ Function extracted {len(files)} files:")
        for file_path in files.keys():
            print(f"  - {file_path}")
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Function error: {e}")

if __name__ == "__main__":
    debug_file_extraction() 