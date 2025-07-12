#!/bin/bash

# MultiModel ChatBot Startup Script
# This ensures the app runs with the correct conda environment

echo "🚀 Starting MultiModel ChatBot..."
echo "📍 Using conda environment: $(conda info --envs | grep '*' | awk '{print $1}')"

# Ensure we're using conda python
PYTHON_PATH=$(which python)
echo "🐍 Python path: $PYTHON_PATH"

# Check if required packages are available
echo "🔍 Checking dependencies..."
python -c "
import streamlit
import firebase_admin
import sentence_transformers
import docx
print('✅ All critical dependencies found!')
print(f'📦 Streamlit version: {streamlit.__version__}')
"

if [ $? -eq 0 ]; then
    echo "🎯 All dependencies OK. Starting app..."
    echo "🌐 App will be available at: http://localhost:8501"
    echo "📱 Use Ctrl+C to stop the app"
    echo ""
    
    # Run streamlit through conda python to avoid PATH issues
    python -m streamlit run app_final.py
else
    echo "❌ Dependencies missing. Please run:"
    echo "   conda install -c conda-forge streamlit sentence-transformers faiss-cpu scikit-learn numpy pandas"
    echo "   conda install -c conda-forge python-docx docx2txt"
    exit 1
fi 