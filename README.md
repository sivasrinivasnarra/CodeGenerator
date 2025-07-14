# 🚀 Enhanced MultiModel ChatBot

A comprehensive AI-powered development environment that combines multi-model chat capabilities with advanced project analysis, code generation, and repository integration.

## ✨ Features

### 🤖 **Multi-Model AI Chat**
- **4 Major AI Providers**: Gemini, OpenAI GPT, Claude, DeepSeek
- **12+ Model Options**: From lightweight to flagship models
- **File Upload Support**: Images, PDFs, Word documents, audio, video, code files, zip archives
- **Chat Management**: Persistent conversations with search and organization
- **Export Capabilities**: Download conversations as Markdown

### 📊 **Intelligent Project Analysis**
- **Basic Analysis**: Works with Gemini for immediate insights
- **Advanced RAG System**: Semantic search across codebases (optional)
 - **AI Agent Orchestra**: 3 specialized agents
  - 🚀 Project Generator - Create complete projects from docs or prompts
  - 🔍 Project Analyzer - Architecture and structure analysis
  - 🛠️ Code Assistant - Extend existing projects with new features

### 🚀 **Full Project Generator** ⭐ NEW!
- **Complete Project Creation**: Generate entire projects from descriptions or documentation
- **Comprehensive Testing**: Automatic unit, integration, and E2E test generation
- **Code Validation**: Built-in syntax checking, linting, and security scanning
- **Auto-Fixing**: AI-powered issue resolution with multiple iterations
- **Production Ready**: Includes documentation, examples, configuration files
- **Multiple Tech Stacks**: Python (FastAPI, Flask), JavaScript (Node.js, React), and more
- **ZIP Download**: Get complete projects as downloadable archives

### 🛠️ **AI Code Generator**
- **Smart Code Generation**: Context-aware code creation
- **3 Generation Modes**:
  - 🆕 Generate New Features - Build from scratch
  - 📁 Enhance Existing Projects - Add features to uploaded projects
  - 💡 Project Suggestions - Get improvement recommendations
- **Multi-Language Support**: Python, JavaScript, Java, HTML/CSS, and more
- **Framework Integration**: Streamlit, Flask, React, Node.js, Django
- **Intelligent Analysis**: Understands existing code patterns and style

### 🔗 **Git Repository Integration**
- **Multi-Platform Support**: GitHub, Bitbucket, GitLab
- **One-Click Analysis**: Fetch and analyze any public repository
- **4 Analysis Types**:
  - 📊 Repository Overview - Structure and technology stack
  - 🔍 Code Analysis - Quality, architecture, and recommendations
  - 📋 Documentation Generation - Auto-generate README files
  - 🛡️ Security Check - Vulnerability and security assessment
- **Export Options**: Download analysis reports and repository files

### 🔄 **Intelligent Fallbacks**
- **Graceful Degradation**: Core features work even without advanced dependencies
- **Modular Architecture**: Install only what you need
- **Clear Feedback**: Shows available vs. missing features
- **Easy Upgrades**: Simple instructions to enable advanced features

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ (Python 3.11+ recommended)
- Conda environment (recommended to avoid dependency conflicts)
- Firebase project for authentication
- API keys for desired AI models

### 1. Clone and Setup
```bash
git clone <repository-url>
cd CodeGenerator
```

### 2. Install Dependencies

**🎯 Recommended: Use the Automatic Launcher (Prevents Environment Issues)**
```bash
# This launcher automatically checks dependencies and avoids PATH conflicts
python launch.py
```

**🔧 Manual Setup (If you prefer manual control)**
```bash
# Install all dependencies via conda (avoids environment conflicts)
conda install -c conda-forge streamlit sentence-transformers faiss-cpu scikit-learn numpy pandas python-docx docx2txt firebase-admin requests urllib3

# Install AI model APIs via pip (not available in conda)
pip install python-dotenv google-generativeai openai anthropic deepseek-python pyrebase4

# Run with conda python to avoid environment mixing
python -m streamlit run app_final.py
```

**⚠️ Avoid Environment Conflicts:**
- Always use `python -m streamlit run app_final.py` instead of `streamlit run app_final.py`
- Or use the provided launchers: `python launch.py` or `./run_app.sh`

### 3. Configure Environment Variables
Create a `.env` file:
```env
# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token

# AI Model API Keys
GOOGLE_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-claude-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key

# Optional: GitHub token for higher API limits
GITHUB_TOKEN=your-github-token
```

### 4. Set up Firebase
1. Create a Firebase project at https://console.firebase.google.com
2. Enable Authentication with Email/Password
3. Enable Firestore Database
4. Download service account JSON and extract credentials for `.env`

### 5. Run the Application
```bash
streamlit run app_final.py
```
### 6. Command-Line Workflow
Use `agent_pipeline.py` for quick experiments without the web UI.

Generate a project from docs:
```bash
python agent_pipeline.py generator --docs path/to/docs --project MyApp
```

Analyse an existing project:
```bash
python agent_pipeline.py analyzer path/to/project
```

Extend a project with new code:
```bash
python agent_pipeline.py coder path/to/project "add login feature"

```

## 📖 Usage Guide

### 🔐 **Authentication**
- Sign up or log in with email/password
- All conversations and analysis results are saved per user
- Secure Firebase authentication with session management

### 💬 **Multi-Model Chat**
1. Select your preferred AI provider and model
2. Start a new chat or continue existing conversations
3. Upload files for analysis (images, documents, code, zip files)
4. Export conversations as Markdown files

### 📊 **Project Analysis**
1. Upload project files, Word documents, or zip archives
2. Choose analysis type (Overview, Code Review, Security, Documentation)
3. View comprehensive analysis results
4. Download reports and suggestions

### 🚀 **Full Project Generation** ⭐ NEW!
1. Select "🚀 Full Project Generator" agent
2. **Input Options**:
   - Describe your project in natural language
   - Upload documentation/requirements files
   - Provide Git repository URL for analysis
3. Configure generation options (tests, validation, examples)
4. Click "Generate Complete Project" and wait 1-3 minutes
5. Download complete project as ZIP file with all components

### 🛠️ **Code Generation**
1. **New Feature**: Describe what you want to build
2. **Enhance Project**: Upload existing code and describe new features
3. **Suggestions**: Get improvement recommendations for uploaded projects
4. Download generated code and integration instructions

### 🔗 **Git Integration**
1. Paste any public repository URL (GitHub, Bitbucket, GitLab)
2. Select analysis type and optional branch
3. Fetch and analyze repository automatically
4. Generate documentation, security reports, or code analysis
5. Download results as Markdown or zip files

## 🏗️ Architecture

### Core Components
- **`app_final.py`** - Main Streamlit application with all features
- **`project_orchestrator.py`** - Coordinates complete project generation pipeline
- **`project_generator.py`** - Creates complete project structures from requirements
- **`test_generator.py`** - Generates comprehensive test suites
- **`code_validator.py`** - Validates, lints, and auto-fixes generated code
- **`rag_system.py`** - Retrieval-Augmented Generation for semantic search
- **`model_adapter.py`** - Unified interface for all AI models
- **`git_repository_integration.py`** - Multi-platform repository fetching

### Model Utilities
- **`gemini_utils.py`** - Google Gemini integration
- **`openai_utils.py`** - OpenAI GPT integration
- **`anthropic_utils.py`** - Claude integration
- **`deepseek_utils.py`** - DeepSeek integration
- **`firebase_utils.py`** - Authentication and data storage

## 🎯 Use Cases

### For Developers
- **Code Review**: Get AI-powered feedback on code quality and best practices
- **Documentation**: Auto-generate comprehensive README files and API docs
- **Security Audit**: Identify vulnerabilities and security issues
- **Architecture Analysis**: Understand and improve project structure
- **Feature Development**: Generate new features that fit existing codebase

### For Project Managers
- **Project Overview**: Quick understanding of unfamiliar codebases
- **Technology Assessment**: Analyze tech stack and dependencies
- **Risk Assessment**: Security and maintenance risk evaluation
- **Documentation**: Generate project documentation for stakeholders

### For Students and Learners
- **Code Analysis**: Learn from real-world projects and best practices
- **Pattern Recognition**: Understand common coding patterns and architectures
- **Security Education**: Learn about common vulnerabilities and fixes
- **Technology Exploration**: Analyze projects using different frameworks

### For Open Source Contributors
- **Repository Analysis**: Understand new projects before contributing
- **Documentation**: Help improve project documentation
- **Code Quality**: Suggest improvements to maintainers
- **Security**: Help identify and report security issues

## 🔧 Advanced Configuration

### Firebase Setup Details
1. **Authentication**: Enable Email/Password and optionally Google OAuth
2. **Firestore Rules**: Configure for user-specific data access
3. **Security**: Set up proper security rules and API key restrictions

### API Key Management
- **Gemini**: Get free API key from Google AI Studio
- **OpenAI**: Requires paid account for GPT-4 models
- **Claude**: Anthropic API with free tier available
- **DeepSeek**: Free tier available for testing

### Performance Optimization
- **RAG System**: Adjust chunk sizes and embedding models for your needs
- **File Limits**: Configure maximum file sizes in the code
- **Caching**: Implement Redis for production deployments

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Install development dependencies
3. Set up pre-commit hooks for code quality
4. Run tests before submitting PRs

### Adding New Features
- **New AI Models**: Add to model utilities and update model_adapter.py
 - **New Agents**: Customize `generate_agent_response` in `app_final.py` to add new specialized agents
- **New Platforms**: Add to git_repository_integration.py

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Streamlit** for the amazing web framework
- **Firebase** for authentication and data storage
- **Google Gemini**, **OpenAI**, **Anthropic**, and **DeepSeek** for AI model APIs
- **Sentence Transformers** and **FAISS** for RAG capabilities
- **LangChain** for AI framework components

## 🆘 Support

### Troubleshooting
- **Import Errors**: Check if optional dependencies are installed
- **API Errors**: Verify API keys in .env file
- **Firebase Errors**: Check Firebase configuration and permissions
- **Memory Issues**: Reduce file upload sizes or adjust RAG settings

### Getting Help
- Check the GitHub Issues for common problems
- Create a new issue with detailed error information
- Include Python version, OS, and installed package versions

---

**Built with ❤️ for the developer community**

Transform your development workflow with AI-powered analysis, generation, and collaboration tools. 