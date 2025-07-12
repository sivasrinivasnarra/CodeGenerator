"""
Project Generator for MultiModel ChatBot
Generates complete project structures from documentation, architecture diagrams, or prompts.
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from model_adapter import ModelClient

@dataclass
class ProjectFile:
    """Represents a generated project file."""
    path: str
    content: str
    file_type: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class ProjectStructure:
    """Represents the complete project structure."""
    name: str
    description: str
    technology_stack: List[str] = field(default_factory=list)
    files: List[ProjectFile] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)  # package -> version
    setup_instructions: List[str] = field(default_factory=list)
    architecture_notes: str = ""
    estimated_complexity: str = "medium"  # low, medium, high

class DocumentParser:
    """Parses various document types to extract project requirements."""
    
    def __init__(self):
        self.requirement_patterns = [
            r"(?i)requirements?:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
            r"(?i)features?:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
            r"(?i)specifications?:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
            r"(?i)functionality:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
        ]
        
        self.tech_stack_patterns = [
            r"(?i)(?:tech|technology|stack|framework|language)s?:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
            r"(?i)using\s+(.*?)(?=\n|\.|,)",
            r"(?i)built\s+with\s+(.*?)(?=\n|\.|,)",
        ]
    
    def parse_document(self, content: str, filename: str = "") -> Dict[str, Any]:
        """Parse document content to extract project information."""
        doc_info = {
            "requirements": [],
            "tech_stack": [],
            "project_type": self._detect_project_type(content),
            "complexity": self._estimate_complexity(content),
            "architecture_style": self._detect_architecture(content),
            "raw_content": content,
            "filename": filename
        }
        
        # Extract requirements
        for pattern in self.requirement_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
            for match in matches:
                requirements = [req.strip() for req in match.split('\n') if req.strip()]
                doc_info["requirements"].extend(requirements)
        
        # Extract tech stack
        for pattern in self.tech_stack_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
            for match in matches:
                tech_items = [tech.strip() for tech in re.split(r'[,\n]', match) if tech.strip()]
                doc_info["tech_stack"].extend(tech_items)
        
        # Clean up duplicates
        doc_info["requirements"] = list(set(doc_info["requirements"]))
        doc_info["tech_stack"] = list(set(doc_info["tech_stack"]))
        
        return doc_info
    
    def _detect_project_type(self, content: str) -> str:
        """Detect the type of project from content."""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['web app', 'website', 'frontend', 'backend', 'api']):
            return "web_application"
        elif any(word in content_lower for word in ['mobile app', 'android', 'ios', 'react native']):
            return "mobile_application"
        elif any(word in content_lower for word in ['desktop app', 'gui', 'tkinter', 'qt']):
            return "desktop_application"
        elif any(word in content_lower for word in ['data analysis', 'machine learning', 'ai', 'ml']):
            return "data_science"
        elif any(word in content_lower for word in ['microservice', 'service', 'api only']):
            return "microservice"
        elif any(word in content_lower for word in ['cli', 'command line', 'script']):
            return "cli_tool"
        else:
            return "general"
    
    def _estimate_complexity(self, content: str) -> str:
        """Estimate project complexity based on content."""
        complexity_score = 0
        content_lower = content.lower()
        
        # Add points for various complexity indicators
        if any(word in content_lower for word in ['database', 'db', 'sql', 'mongodb']):
            complexity_score += 2
        if any(word in content_lower for word in ['authentication', 'auth', 'login', 'user']):
            complexity_score += 2
        if any(word in content_lower for word in ['api', 'rest', 'graphql']):
            complexity_score += 1
        if any(word in content_lower for word in ['microservice', 'distributed', 'scalable']):
            complexity_score += 3
        if any(word in content_lower for word in ['real-time', 'websocket', 'streaming']):
            complexity_score += 2
        if any(word in content_lower for word in ['machine learning', 'ai', 'neural network']):
            complexity_score += 3
        
        if complexity_score <= 2:
            return "low"
        elif complexity_score <= 5:
            return "medium"
        else:
            return "high"
    
    def _detect_architecture(self, content: str) -> str:
        """Detect architectural style from content."""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['microservice', 'microservices']):
            return "microservices"
        elif any(word in content_lower for word in ['mvc', 'model view controller']):
            return "mvc"
        elif any(word in content_lower for word in ['rest', 'restful']):
            return "rest_api"
        elif any(word in content_lower for word in ['spa', 'single page']):
            return "spa"
        elif any(word in content_lower for word in ['serverless', 'lambda']):
            return "serverless"
        else:
            return "traditional"

class ProjectGenerator:
    """Main class for generating complete projects from documentation."""
    
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_client = ModelClient(model_name)
        self.doc_parser = DocumentParser()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Load project templates for different types."""
        return {
            "web_application": {
                "structure": ["frontend/", "backend/", "database/", "tests/", "docs/"],
                "base_files": ["README.md", "requirements.txt", ".gitignore", "docker-compose.yml"],
                "tech_defaults": ["React", "Node.js", "Express", "PostgreSQL"]
            },
            "mobile_application": {
                "structure": ["src/", "assets/", "tests/", "docs/"],
                "base_files": ["README.md", "package.json", ".gitignore"],
                "tech_defaults": ["React Native", "TypeScript"]
            },
            "data_science": {
                "structure": ["data/", "notebooks/", "src/", "models/", "tests/", "docs/"],
                "base_files": ["README.md", "requirements.txt", ".gitignore", "setup.py"],
                "tech_defaults": ["Python", "Pandas", "NumPy", "Jupyter"]
            },
            "microservice": {
                "structure": ["src/", "api/", "tests/", "docker/", "docs/"],
                "base_files": ["README.md", "requirements.txt", "Dockerfile", ".gitignore"],
                "tech_defaults": ["FastAPI", "Python", "Docker", "PostgreSQL"]
            },
            "cli_tool": {
                "structure": ["src/", "tests/", "docs/"],
                "base_files": ["README.md", "requirements.txt", "setup.py", ".gitignore"],
                "tech_defaults": ["Python", "Click", "argparse"]
            }
        }
    def generate_project_from_docs(self, documents: Dict[str, str], 
                                 project_name: str = "generated_project") -> ProjectStructure:
        """Generate a complete project from uploaded documentation."""
        
        # Parse all documents
        parsed_docs = []
        for filename, content in documents.items():
            parsed_doc = self.doc_parser.parse_document(content, filename)
            parsed_docs.append(parsed_doc)
        
        # Combine requirements from all documents
        combined_requirements = []
        combined_tech_stack = []
        project_types = []
        
        for doc in parsed_docs:
            combined_requirements.extend(doc["requirements"] or [])
            combined_tech_stack.extend(doc["tech_stack"] or [])
            project_types.append(doc["project_type"] or "general")
        
        # Determine primary project type
        primary_type = max(set(project_types), key=project_types.count) if project_types else "general"
        
        # Generate project structure
        return self._generate_project_structure(
            requirements=combined_requirements or [],
            tech_stack=combined_tech_stack or [],
            project_type=primary_type or "general",
            project_name=project_name or "generated_project",
            source_docs=parsed_docs or []
        )
    def generate_project_from_prompt(self, prompt: str, 
                                   project_name: str) -> ProjectStructure:
        """Generate a complete project from a text prompt."""
        
        # Parse the prompt as a document
        parsed_prompt = self.doc_parser.parse_document(prompt)
        
        return self._generate_project_structure(
            requirements=parsed_prompt["requirements"] or [prompt],
            tech_stack=parsed_prompt["tech_stack"] or [],
            project_type=parsed_prompt["project_type"] or "general",
            project_name=project_name or "prompted_project",
            source_prompt=prompt or ""
        )
    
    def _generate_project_structure(self, requirements: List[str], 
                                  tech_stack: List[str], 
                                  project_type: str,
                                  project_name: str,
                                  source_docs: Optional[List[Dict]] = None,
                                  source_prompt: Optional[str] = None) -> ProjectStructure:
        """Generate the complete project structure."""
        
        # Get template for project type
        template = self.templates.get(project_type, self.templates["web_application"])
        
        # Enhance tech stack with defaults if needed
        final_tech_stack = list(set((tech_stack or []) + template["tech_defaults"]))
        
        # Generate project architecture using AI
        architecture_prompt = self._build_architecture_prompt(
            requirements or [], final_tech_stack, project_type or "general", project_name or "project"
        )
        
        architecture_response = self.model_client.generate_response(architecture_prompt)
        
        # Generate individual files
        files = self._generate_project_files(
            requirements or [], final_tech_stack, project_type or "general", 
            project_name or "project", architecture_response or ""
        )
        
        # Generate dependencies
        dependencies = self._generate_dependencies(final_tech_stack, project_type or "general")
        
        # Generate setup instructions
        setup_instructions = self._generate_setup_instructions(
            project_type or "general", final_tech_stack, dependencies
        )
        
        return ProjectStructure(
            name=project_name or "project",
            description=self._generate_project_description(requirements or []),
            technology_stack=final_tech_stack,
            files=files,
            dependencies=dependencies,
            setup_instructions=setup_instructions,
            architecture_notes=architecture_response or "",
            estimated_complexity=self._estimate_project_complexity(requirements or [], final_tech_stack)
        )
    
    def _build_architecture_prompt(self, requirements: List[str], 
                                 tech_stack: List[str], 
                                 project_type: str, 
                                 project_name: str) -> str:
        """Build prompt for generating project architecture."""
        return f"""
You are a senior software architect tasked with designing a {project_type} project.

Project Name: {project_name}
Technology Stack: {', '.join(tech_stack)}

Requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Please provide:
1. Detailed project architecture explanation
2. Folder structure with explanations
3. Key components and their interactions
4. Data flow and API design (if applicable)
5. Security considerations
6. Scalability considerations

Be thorough and provide a production-ready architecture design.
"""
    
    def _generate_project_files(self, requirements: List[str], 
                              tech_stack: List[str], 
                              project_type: str,
                              project_name: str, 
                              architecture: str) -> List[ProjectFile]:
        """Generate all project files with content."""
        files = []
        
        # Generate main application files
        if "Python" in tech_stack:
            files.extend(self._generate_python_files(requirements, tech_stack, project_type, architecture))
        elif "Node.js" in tech_stack or "JavaScript" in tech_stack:
            files.extend(self._generate_nodejs_files(requirements, tech_stack, project_type, architecture))
        elif "React" in tech_stack:
            files.extend(self._generate_react_files(requirements, tech_stack, project_type, architecture))
        
        # Generate configuration files
        files.extend(self._generate_config_files(tech_stack, project_type))
        
        # Generate documentation
        files.extend(self._generate_documentation_files(project_name, requirements, tech_stack, architecture))
        
        return files
    
    def _generate_python_files(self, requirements: List[str], 
                             tech_stack: List[str], 
                             project_type: str, 
                             architecture: str) -> List[ProjectFile]:
        """Generate Python project files."""
        files = []
        
        # Main application file
        main_app_prompt = f"""
Generate a main Python application file that implements these requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Technology Stack: {', '.join(tech_stack)}
Project Type: {project_type}

Architecture Context:
{architecture}

Provide complete, production-ready Python code with:
- Proper imports and dependencies
- Error handling
- Logging
- Configuration management
- Main entry point
- Clear documentation
"""
        
        main_content = self.model_client.generate_response(main_app_prompt)
        files.append(ProjectFile(
            path="src/main.py" if project_type != "cli_tool" else "src/cli.py",
            content=main_content,
            file_type="python",
            description="Main application entry point"
        ))
        
        # Generate additional Python modules based on requirements
        if any("api" in req.lower() for req in requirements):
            api_content = self._generate_api_module(requirements, tech_stack)
            files.append(ProjectFile(
                path="src/api.py",
                content=api_content,
                file_type="python",
                description="API routes and handlers"
            ))
        
        if any("database" in req.lower() or "db" in req.lower() for req in requirements):
            db_content = self._generate_database_module(requirements, tech_stack)
            files.append(ProjectFile(
                path="src/database.py",
                content=db_content,
                file_type="python", 
                description="Database models and connections"
            ))
        
        # Generate __init__.py files
        files.append(ProjectFile(
            path="src/__init__.py",
            content="# Main application package\n",
            file_type="python",
            description="Package initialization"
        ))
        
        return files
    
    def _generate_nodejs_files(self, requirements: List[str], 
                             tech_stack: List[str], 
                             project_type: str, 
                             architecture: str) -> List[ProjectFile]:
        """Generate Node.js project files."""
        files = []
        
        # Main server file
        server_prompt = f"""
Generate a main Node.js server file that implements these requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Technology Stack: {', '.join(tech_stack)}
Project Type: {project_type}

Architecture Context:
{architecture}

Provide complete, production-ready Node.js code with:
- Express.js setup (if web application)
- Proper middleware
- Error handling
- Environment configuration
- Route definitions
- Database connections (if needed)
- Security best practices
"""
        
        server_content = self.model_client.generate_response(server_prompt)
        files.append(ProjectFile(
            path="src/server.js",
            content=server_content,
            file_type="javascript",
            description="Main server file"
        ))
        
        # Generate package.json
        package_json = self._generate_package_json(requirements, tech_stack)
        files.append(ProjectFile(
            path="package.json",
            content=package_json,
            file_type="json",
            description="Node.js dependencies and scripts"
        ))
        
        return files
    
    def _generate_react_files(self, requirements: List[str], 
                            tech_stack: List[str], 
                            project_type: str, 
                            architecture: str) -> List[ProjectFile]:
        """Generate React project files."""
        files = []
        
        # Main App component
        app_prompt = f"""
Generate a main React App component that implements these requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Technology Stack: {', '.join(tech_stack)}

Architecture Context:
{architecture}

Provide complete, production-ready React code with:
- Modern React hooks
- Component structure
- State management
- Routing (if needed)
- API integration (if needed)
- Responsive design
- Error boundaries
"""
        
        app_content = self.model_client.generate_response(app_prompt)
        files.append(ProjectFile(
            path="src/App.js",
            content=app_content,
            file_type="javascript",
            description="Main React application component"
        ))
        
        # Generate index.js
        index_content = """
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""
        files.append(ProjectFile(
            path="src/index.js",
            content=index_content,
            file_type="javascript",
            description="React application entry point"
        ))
        
        return files
    
    def _generate_api_module(self, requirements: List[str], tech_stack: List[str]) -> str:
        """Generate API module content."""
        api_prompt = f"""
Generate a Python API module with routes for these requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Technology Stack: {', '.join(tech_stack)}

Include:
- RESTful endpoints
- Request validation
- Error handling
- Authentication (if mentioned in requirements)
- Response formatting
- Documentation strings
"""
        return self.model_client.generate_response(api_prompt)
    
    def _generate_database_module(self, requirements: List[str], tech_stack: List[str]) -> str:
        """Generate database module content."""
        db_prompt = f"""
Generate a Python database module for these requirements:
{chr(10).join(f"- {req}" for req in requirements)}

Technology Stack: {', '.join(tech_stack)}

Include:
- Database models/schemas
- Connection management
- CRUD operations
- Migration support
- Error handling
- Connection pooling
"""
        return self.model_client.generate_response(db_prompt)
    
    def _generate_package_json(self, requirements: List[str], tech_stack: List[str]) -> str:
        """Generate package.json for Node.js projects."""
        dependencies = {
            "express": "^4.18.0",
            "cors": "^2.8.5",
            "helmet": "^6.0.0",
            "morgan": "^1.10.0"
        }
        
        if "MongoDB" in tech_stack or "mongoose" in tech_stack:
            dependencies["mongoose"] = "^6.8.0"
        if "PostgreSQL" in tech_stack:
            dependencies["pg"] = "^8.8.0"
        if "JWT" in tech_stack or any("auth" in req.lower() for req in requirements):
            dependencies["jsonwebtoken"] = "^9.0.0"
        
        package_data = {
            "name": "generated-project",
            "version": "1.0.0",
            "description": "Generated project",
            "main": "src/server.js",
            "scripts": {
                "start": "node src/server.js",
                "dev": "nodemon src/server.js",
                "test": "jest"
            },
            "dependencies": dependencies,
            "devDependencies": {
                "nodemon": "^2.0.20",
                "jest": "^29.3.0"
            }
        }
        
        return json.dumps(package_data, indent=2)
    
    def _generate_config_files(self, tech_stack: List[str], project_type: str) -> List[ProjectFile]:
        """Generate configuration files."""
        files = []
        
        # .gitignore
        gitignore_content = self._generate_gitignore(tech_stack)
        files.append(ProjectFile(
            path=".gitignore",
            content=gitignore_content,
            file_type="config",
            description="Git ignore file"
        ))
        
        # Environment file
        env_content = self._generate_env_file(tech_stack, project_type)
        files.append(ProjectFile(
            path=".env.example",
            content=env_content,
            file_type="config",
            description="Environment variables template"
        ))
        
        # Docker files if applicable
        if "Docker" in tech_stack:
            dockerfile_content = self._generate_dockerfile(tech_stack, project_type)
            files.append(ProjectFile(
                path="Dockerfile",
                content=dockerfile_content,
                file_type="docker",
                description="Docker container configuration"
            ))
        
        return files
    
    def _generate_documentation_files(self, project_name: str,
                                       requirements: List[str],
                                       tech_stack: List[str],
                                       architecture: str) -> List[ProjectFile]:
        """Generate documentation files."""
        files = []

        # README.md
        readme_prompt = f"""
Generate a comprehensive README.md for a project with:
- Name: {project_name}
- Requirements: {', '.join(requirements)}
- Tech Stack: {', '.join(tech_stack)}

Include:
- Project description
- Features list
- Installation instructions
- Usage examples
- API documentation (if applicable)
- Contributing guidelines
- License information

Make it professional and comprehensive.
"""

        readme_content = self.model_client.generate_response(readme_prompt)
        files.append(ProjectFile(
            path="README.md",
            content=readme_content,
            file_type="markdown",
            description="Project documentation"
        ))

        return files

    def _generate_gitignore(self, tech_stack: List[str]) -> str:
        """Generate .gitignore file based on tech stack."""
        gitignore_lines = ["# Environment variables", ".env", ".env.local", ""]

        if "Python" in tech_stack:
            gitignore_lines.extend([
                "# Python",
                "__pycache__/",
                "*.pyc",
                "*.pyo",
                "*.pyd",
                ".Python",
                "build/",
                "develop-eggs/",
                "dist/",
                "downloads/",
                "eggs/",
                ".eggs/",
                "lib/",
                "lib64/",
                "parts/",
                "sdist/",
                "var/",
                "wheels/",
                "*.egg-info/",
                ".installed.cfg",
                "*.egg",
                ""
            ])

        if "Node.js" in tech_stack or "JavaScript" in tech_stack:
            gitignore_lines.extend([
                "# Node.js",
                "node_modules/",
                "npm-debug.log*",
                "yarn-debug.log*",
                "yarn-error.log*",
                ".pnpm-debug.log*",
                ""
            ])

        gitignore_lines.extend([
            "# IDE",
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "*~",
            "",
            "# OS",
            ".DS_Store",
            "Thumbs.db"
        ])

        return "\n".join(gitignore_lines)

    def _generate_env_file(self, tech_stack: List[str],
                          project_type: str) -> str:
        """Generate environment variables file."""
        env_vars = ["# Environment Configuration"]

        if project_type in ["web_application", "microservice"]:
            env_vars.extend([
                "PORT=3000",
                "NODE_ENV=development"
            ])

        if any("database" in stack.lower() for stack in tech_stack):
            env_vars.extend([
                "",
                "# Database Configuration",
                "DB_HOST=localhost",
                "DB_PORT=5432",
                "DB_NAME=your_database",
                "DB_USER=your_user",
                "DB_PASSWORD=your_password"
            ])

        if any("auth" in stack.lower() for stack in tech_stack):
            env_vars.extend([
                "",
                "# Authentication",
                "JWT_SECRET=your_jwt_secret_key_here",
                "SESSION_SECRET=your_session_secret_here"
            ])

        return "\n".join(env_vars)

    def _generate_dockerfile(self, tech_stack: List[str],
                            project_type: str) -> str:
        """Generate Dockerfile based on tech stack."""
        if "Python" in tech_stack:
            return """FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "src/main.py"]
"""
        elif "Node.js" in tech_stack:
            return """FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
"""
        else:
            return "# Dockerfile template - customize for your tech stack"

    def _generate_dependencies(self, tech_stack: List[str],
                              project_type: str) -> Dict[str, str]:
        """Generate project dependencies."""
        deps = {}

        if "Python" in tech_stack:
            if project_type == "microservice":
                deps["fastapi"] = "^0.68.0"
            elif project_type == "web_application":
                deps["flask"] = "^2.0.0"
            
            deps.update({
                "requests": "^2.26.0",
                "python-dotenv": "^0.19.0",
                "pytest": "^6.2.5"
            })

            if "PostgreSQL" in tech_stack:
                deps["psycopg2-binary"] = "^2.9.0"
            if "MongoDB" in tech_stack:
                deps["pymongo"] = "^3.12.0"

        return deps

    def _generate_setup_instructions(self, project_type: str,
                                    tech_stack: List[str],
                                    dependencies: Dict[str, str]) -> List[str]:
        """Generate setup instructions."""
        instructions = []
        if "Python" in tech_stack:
            instructions.extend([
                "1. Create a virtual environment: `python -m venv venv`",
                ("2. Activate virtual environment: `source venv/bin/activate` "
                 "(Linux/Mac) or `venv\\Scripts\\activate` (Windows)"),
                "3. Install dependencies: `pip install -r requirements.txt`"
            ])
        elif "Node.js" in tech_stack:
            instructions.extend([
                "1. Install Node.js dependencies: `npm install`",
                "2. Copy environment file: `cp .env.example .env`",
                "3. Configure environment variables in .env file"
            ])
        if any("database" in stack.lower() for stack in tech_stack):
            instructions.append(
                "4. Set up database and configure connection in .env file")
        instructions.append(
            f"{len(instructions) + 1}. Run the application: "
            "Follow instructions in README.md")
        instructions.append(
            f"{len(instructions) + 2}. Run tests: "
            "Follow testing instructions in README.md")
        return instructions

    def _generate_project_description(self, requirements: List[str]) -> str:
        """Generate project description from requirements."""
        if not requirements:
            return ("A generated project with no specific requirements "
                   "provided.")
        return (f"A project that implements: "
                f"{', '.join(requirements[:3])}"
                f"{'...' if len(requirements) > 3 else ''}")

    def _estimate_project_complexity(self, requirements: List[str],
                                    tech_stack: List[str]) -> str:
        """Estimate overall project complexity."""
        complexity_score = len(requirements) + len(tech_stack)
        if complexity_score <= 5:
            return "low"
        elif complexity_score <= 10:
            return "medium"
        else:
            return "high"