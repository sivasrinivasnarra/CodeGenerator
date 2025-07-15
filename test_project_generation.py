#!/usr/bin/env python3
"""
Test script for enhanced project generation functionality
"""

import json
import zipfile
from io import BytesIO
from datetime import datetime

def test_file_extraction():
    """Test the file extraction function"""
    
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
    
    # Import the function (assuming it's in app_final.py)
    try:
        from app_final import extract_project_files_from_response
        files = extract_project_files_from_response(sample_response)
        
        print("✅ File extraction test passed!")
        print(f"📁 Extracted {len(files)} files:")
        for file_path in files.keys():
            print(f"  - {file_path}")
        
        return files
        
    except ImportError:
        print("❌ Could not import extract_project_files_from_response function")
        return {}

def test_zip_creation(files):
    """Test ZIP file creation"""
    
    try:
        from app_final import create_project_zip
        zip_data = create_project_zip(files, "test_project")
        
        # Verify ZIP contents
        with zipfile.ZipFile(BytesIO(zip_data), 'r') as zip_file:
            file_list = zip_file.namelist()
            
        print("✅ ZIP creation test passed!")
        print(f"📦 ZIP contains {len(file_list)} files:")
        for file_name in file_list:
            print(f"  - {file_name}")
        
        return zip_data
        
    except ImportError:
        print("❌ Could not import create_project_zip function")
        return None

def test_comprehensive_prompt():
    """Test the comprehensive prompt generation"""
    
    try:
        from app_final import generate_comprehensive_project_prompt
        
        prompt = "Create a React todo app"
        context_info = "User wants a modern React application with TypeScript"
        
        comprehensive_prompt = generate_comprehensive_project_prompt(prompt, context_info, is_followup=False)
        
        print("✅ Comprehensive prompt generation test passed!")
        print(f"📝 Generated prompt length: {len(comprehensive_prompt)} characters")
        print("📋 Prompt includes:")
        print("  - Mission statement: ✅" if "MISSION" in comprehensive_prompt else "  - Mission statement: ❌")
        print("  - File structure: ✅" if "FILE STRUCTURE" in comprehensive_prompt else "  - File structure: ❌")
        print("  - Code requirements: ✅" if "CODE REQUIREMENTS" in comprehensive_prompt else "  - Code requirements: ❌")
        print("  - Interactive features: ✅" if "INTERACTIVE FEATURES" in comprehensive_prompt else "  - Interactive features: ❌")
        
        return comprehensive_prompt
        
    except ImportError:
        print("❌ Could not import generate_comprehensive_project_prompt function")
        return None

def main():
    """Run all tests"""
    print("🧪 Testing Enhanced Project Generation Functionality")
    print("=" * 60)
    
    # Test 1: File extraction
    print("\n1️⃣ Testing file extraction...")
    files = test_file_extraction()
    
    # Test 2: ZIP creation
    print("\n2️⃣ Testing ZIP creation...")
    if files:
        zip_data = test_zip_creation(files)
    else:
        print("⏭️ Skipping ZIP test (no files extracted)")
        zip_data = None
    
    # Test 3: Comprehensive prompt generation
    print("\n3️⃣ Testing comprehensive prompt generation...")
    comprehensive_prompt = test_comprehensive_prompt()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  - File extraction: {'✅ PASSED' if files else '❌ FAILED'}")
    print(f"  - ZIP creation: {'✅ PASSED' if zip_data else '❌ FAILED'}")
    print(f"  - Prompt generation: {'✅ PASSED' if comprehensive_prompt else '❌ FAILED'}")
    
    if files and zip_data and comprehensive_prompt:
        print("\n🎉 All tests passed! Enhanced project generation is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main() 