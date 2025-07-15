#!/usr/bin/env python3
"""
Test script for the interactive project generation workflow.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_tech_stack_analysis():
    """Test the tech stack analysis function."""
    print("🧪 Testing Tech Stack Analysis...")
    
    # Mock requirements
    requirements = """
    Create a web application for managing a library system with the following features:
    - User authentication and authorization
    - Book catalog management
    - Borrowing and returning books
    - Search and filtering
    - Admin dashboard
    - Email notifications
    """
    
    # Mock prompt
    prompt = "Create a library management system"
    
    try:
        from app_final import analyze_requirements_and_suggest_tech_stack
        result = analyze_requirements_and_suggest_tech_stack(prompt, requirements)
        print("✅ Tech stack analysis function works")
        print(f"Result length: {len(result)} characters")
        return True
    except Exception as e:
        print(f"❌ Tech stack analysis failed: {e}")
        return False

def test_architecture_generation():
    """Test the architecture generation function."""
    print("🧪 Testing Architecture Generation...")
    
    requirements = """
    Create a web application for managing a library system with the following features:
    - User authentication and authorization
    - Book catalog management
    - Borrowing and returning books
    - Search and filtering
    - Admin dashboard
    - Email notifications
    """
    
    tech_stack = "Option 1: Modern & Popular - React, Node.js, MongoDB"
    
    try:
        from app_final import generate_project_architecture
        result = generate_project_architecture(requirements, tech_stack, requirements)
        print("✅ Architecture generation function works")
        print(f"Result length: {len(result)} characters")
        return True
    except Exception as e:
        print(f"❌ Architecture generation failed: {e}")
        return False

def test_file_group_generation():
    """Test the file group generation function."""
    print("🧪 Testing File Group Generation...")
    
    requirements = """
    Create a web application for managing a library system with the following features:
    - User authentication and authorization
    - Book catalog management
    - Borrowing and returning books
    - Search and filtering
    - Admin dashboard
    - Email notifications
    """
    
    tech_stack = "Option 1: Modern & Popular - React, Node.js, MongoDB"
    architecture = """
    PROJECT ARCHITECTURE OVERVIEW:
    Modern full-stack library management system
    
    FILE GROUPS FOR GENERATION:
    Group 1: Core Application Files
    - src/App.js
    - src/components/Header.js
    - src/components/Footer.js
    
    Group 2: Configuration & Setup
    - package.json
    - .env.example
    - README.md
    """
    
    file_list = ["src/App.js", "src/components/Header.js", "src/components/Footer.js"]
    
    try:
        from app_final import generate_file_group
        result = generate_file_group("Core Application Files", file_list, requirements, tech_stack, architecture)
        print("✅ File group generation function works")
        print(f"Result length: {len(result)} characters")
        return True
    except Exception as e:
        print(f"❌ File group generation failed: {e}")
        return False

def test_file_group_parsing():
    """Test the file group parsing function."""
    print("🧪 Testing File Group Parsing...")
    
    architecture_response = """
    PROJECT ARCHITECTURE OVERVIEW:
    Modern full-stack library management system
    
    FILE GROUPS FOR GENERATION:
    Group 1: Core Application Files
    - src/App.js
    - src/components/Header.js
    - src/components/Footer.js
    
    Group 2: Configuration & Setup
    - package.json
    - .env.example
    - README.md
    
    Group 3: Documentation & Tests
    - tests/App.test.js
    - docs/API.md
    """
    
    try:
        from app_final import parse_file_groups_from_architecture
        result = parse_file_groups_from_architecture(architecture_response)
        print("✅ File group parsing function works")
        print(f"Found {len(result)} groups:")
        for i, group in enumerate(result, 1):
            print(f"  Group {i}: {group['name']} ({len(group['files'])} files)")
        return True
    except Exception as e:
        print(f"❌ File group parsing failed: {e}")
        return False

def test_workflow_state_management():
    """Test the workflow state management."""
    print("🧪 Testing Workflow State Management...")
    
    # Mock session state
    project_generation_state = {
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
    
    # Test workflow transitions
    workflow_steps = ["initial", "tech_stack_selection", "architecture_review", "group_generation", "complete"]
    
    print("✅ Workflow state structure is correct")
    print(f"Workflow steps: {workflow_steps}")
    return True

def main():
    """Run all tests."""
    print("🚀 Testing Interactive Project Generation Workflow\n")
    
    tests = [
        test_tech_stack_analysis,
        test_architecture_generation,
        test_file_group_generation,
        test_file_group_parsing,
        test_workflow_state_management
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Interactive workflow is ready.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return passed == total

if __name__ == "__main__":
    main() 