#!/usr/bin/env python3
"""
MultiModel ChatBot Launcher
Usage: python launch.py
This script ensures proper environment setup and launches the app safely.
"""

import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check if all required dependencies are available."""
    required_packages = {
        'streamlit': 'streamlit',
        'firebase_admin': 'firebase-admin', 
        'sentence_transformers': 'sentence-transformers',
        'docx': 'python-docx',
        'docx2txt': 'docx2txt',
        'numpy': 'numpy',
        'faiss': 'faiss-cpu'
    }
    
    missing_packages = []
    
    for package, conda_name in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (install with: conda install -c conda-forge {conda_name})")
            missing_packages.append(conda_name)
    
    return missing_packages

def main():
    print("🚀 MultiModel ChatBot Launcher")
    print("=" * 50)
    
    # Check Python version
    print(f"🐍 Python version: {sys.version}")
    print(f"📍 Python path: {sys.executable}")
    
    # Check if we're in conda environment
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', 'No conda environment detected')
    print(f"🏠 Conda environment: {conda_env}")
    
    if conda_env == 'No conda environment detected':
        print("\n⚠️ You are not in a conda environment. This script requires a conda environment.")
        print("Please activate a conda environment before running this script.")
        return 1

    print("\n🔍 Checking dependencies...")
    missing = check_dependencies()
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("\n🔧 To install missing packages, run:")
        print(f"conda install -c conda-forge {' '.join(missing)}")
        return 1
    
    print("\n✅ All dependencies satisfied!")
    
    # Check if app_final.py exists
    app_path = Path("app_final.py")
    if not app_path.exists():
        print("❌ app_final.py not found in current directory!")
        return 1
    
    print("\n🎯 Starting MultiModel ChatBot...")
    print("🌐 App will be available at: http://localhost:8501")
    print("📱 Press Ctrl+C to stop the app")
    print("=" * 50)
    
    try:
        # Launch streamlit using current Python interpreter
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app_final.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 App stopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting app: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 