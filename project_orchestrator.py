"""
Project Orchestrator for MultiModel ChatBot
Coordinates the full pipeline: project generation -> validation -> fixes
"""

import json
import zipfile
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from model_adapter import ModelClient
from project_generator import ProjectGenerator, ProjectStructure, ProjectFile
# Comment out unresolved import
# from test_generator import TestGenerator, TestSuite
from code_validator import CodeValidator, ValidationResult


@dataclass
class GenerationOptions:
    """Options for project generation."""
    auto_generate_tests: bool = True
    auto_validate_code: bool = True
    auto_fix_issues: bool = True
    run_tests: bool = True
    target_coverage: float = 80.0
    max_fix_iterations: int = 3
    include_documentation: bool = True
    include_examples: bool = True


@dataclass
class GenerationResult:
    """Result of the complete project generation process."""
    success: bool
    project: Optional[ProjectStructure]
    test_suite: Optional[Any]
    validation_result: Optional[ValidationResult]
    generated_files: List[ProjectFile] = field(default_factory=list)
    execution_time: float = 0.0
    iterations: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ProjectMetrics:
    """Metrics about the generated project."""
    total_files: int = 0
    total_lines: int = 0
    code_files: int = 0
    test_files: int = 0
    config_files: int = 0
    doc_files: int = 0
    test_coverage: float = 0.0
    security_score: float = 0.0
    complexity_score: str = ""
    technology_stack: List[str] = field(default_factory=list)


class ProjectOrchestrator:
    """Main orchestrator for the complete project generation pipeline."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_client = ModelClient(model_name)
        self.project_generator = ProjectGenerator(model_name)
        self.code_validator = CodeValidator(model_name)
        self.model_name = model_name

    def generate_project_from_documents(self,
                                        documents: Dict[str, str],
                                        project_name: Optional[str] = None,
                                        options: Optional[GenerationOptions] = None
                                        ) -> GenerationResult:
        """Generate a complete project from uploaded documentation."""

        if options is None:
            options = GenerationOptions()

        start_time = datetime.now()
        errors = []
        warnings = []

        try:
            # Step 1: Generate project structure
            print("🏗️ Generating project structure from documents...")
            project = self.project_generator.generate_project_from_docs(
                documents, project_name or "generated_project"
            )

            if not project:
                return GenerationResult(
                    success=False,
                    project=None,
                    test_suite=None,
                    validation_result=None,
                    generated_files=[],
                    execution_time=0.0,
                    iterations=0,
                    errors=["Failed to generate project structure"],
                    warnings=[],
                    summary="Project generation failed"
                )

            # Step 2: Validate and fix code
            validation_result = None
            if options.auto_validate_code:
                print("🔍 Validating generated code...")
                validation_result = self._validate_and_fix_project(
                    project, None, options
                )
                iterations = validation_result.performance_metrics.get(
                    'fix_iterations', 0)

            # Step 4: Generate additional files if requested
            if options.include_examples:
                example_files = self._generate_example_files(project)
                project.files.extend(example_files)

            # Step 5: Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Step 6: Combine all generated files
            all_files = project.files[:]

            # Step 7: Generate summary
            summary = self._generate_project_summary(
                project, None, validation_result, execution_time
            )

            return GenerationResult(
                success=True,
                project=project,
                test_suite=None,
                validation_result=validation_result,
                generated_files=all_files,
                execution_time=execution_time,
                iterations=iterations,
                errors=errors,
                warnings=warnings,
                summary=summary
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return GenerationResult(
                success=False,
                project=None,
                test_suite=None,
                validation_result=None,
                generated_files=[],
                execution_time=execution_time,
                iterations=iterations,
                errors=[f"Unexpected error: {str(e)}"],
                warnings=warnings,
                summary="Project generation failed due to unexpected error"
            )
    
    def generate_project_from_prompt(self,
                                   prompt: str,
                                   project_name: Optional[str] = None,
                                   options: Optional[GenerationOptions] = None) -> GenerationResult:
        """Generate a complete project from a text prompt."""
        
        if options is None:
            options = GenerationOptions()
        
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            # Step 1: Generate project structure
            print("🏗️ Generating project structure from prompt...")
            project = self.project_generator.generate_project_from_prompt(
                prompt, project_name or "prompted_project"
            )
            
            if not project:
                return GenerationResult(
                    success=False,
                    project=None,
                    test_suite=None,
                    validation_result=None,
                    generated_files=[],
                    execution_time=0.0,
                    iterations=0,
                    errors=["Failed to generate project structure"],
                    warnings=[],
                    summary="Project generation failed"
                )
            
            # Continue with the same pipeline as document-based generation
            return self._complete_generation_pipeline(
                project, options, start_time, errors, warnings
            )
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return GenerationResult(
                success=False,
                project=None,
                test_suite=None,
                validation_result=None,
                generated_files=[],
                execution_time=execution_time,
                iterations=0,
                errors=[f"Unexpected error: {str(e)}"],
                warnings=warnings,
                summary="Project generation failed due to unexpected error"
            )
    
    def _complete_generation_pipeline(self,
                                    project: ProjectStructure,
                                    options: GenerationOptions,
                                    start_time: datetime,
                                    errors: List[str],
                                    warnings: List[str]) -> GenerationResult:
        """Complete the generation pipeline for a project."""
        
        iterations = 0
        
        # Step 2: Validate and fix code
        validation_result = None
        if options.auto_validate_code:
            print("🔍 Validating generated code...")
            validation_result = self._validate_and_fix_project(
                project, None, options
            )
            iterations = validation_result.performance_metrics.get('fix_iterations', 0)
        
        # Step 4: Generate additional files if requested
        if options.include_examples:
            example_files = self._generate_example_files(project)
            project.files.extend(example_files)
        
        # Step 5: Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Step 6: Combine all generated files
        all_files = project.files[:]
        
        # Step 7: Generate summary
        summary = self._generate_project_summary(
            project, None, validation_result, execution_time
        )
        
        return GenerationResult(
            success=True,
            project=project,
            test_suite=None,
            validation_result=validation_result,
            generated_files=all_files,
            execution_time=execution_time,
            iterations=iterations,
            errors=errors,
            warnings=warnings,
            summary=summary
        )
    
    def _validate_and_fix_project(self,
                                project: ProjectStructure,
                                test_suite: Optional[Any],
                                options: GenerationOptions) -> ValidationResult:
        """Validate and iteratively fix the project."""
        
        iteration = 0
        max_iterations = options.max_fix_iterations
        
        while iteration < max_iterations:
            iteration += 1
            print(f"🔧 Validation iteration {iteration}/{max_iterations}")
            
            # Run validation
            validation_result = self.code_validator.validate_project(
                project=project,
                test_suite=test_suite,
                run_tests=options.run_tests,
                auto_fix=options.auto_fix_issues
            )
            
            # Check if validation passed or if we should stop fixing
            critical_errors = [
                issue for issue in validation_result.issues 
                if issue.severity == "error"
            ]
            
            if not critical_errors or not options.auto_fix_issues:
                print(f"✅ Validation completed after {iteration} iterations")
                break
            
            print(f"⚠️ Found {len(critical_errors)} critical errors, attempting fixes...")
        
        # Add iteration count to performance metrics
        validation_result.performance_metrics['fix_iterations'] = iteration
        
        return validation_result
    
    def _generate_example_files(self, project: ProjectStructure) -> List[ProjectFile]:
        """Generate example files for the project."""
        example_files = []
        
        try:
            # Generate usage examples
            if "Python" in project.technology_stack:
                example_content = self._generate_python_examples(project)
                example_files.append(ProjectFile(
                    path="examples/usage_example.py",
                    content=example_content,
                    file_type="python",
                    description="Example usage of the application"
                ))
            
            elif "JavaScript" in project.technology_stack or "Node.js" in project.technology_stack:
                example_content = self._generate_javascript_examples(project)
                example_files.append(ProjectFile(
                    path="examples/usage_example.js",
                    content=example_content,
                    file_type="javascript",
                    description="Example usage of the application"
                ))
            
            # Generate sample configuration
            config_example = self._generate_config_example(project)
            if config_example:
                example_files.append(ProjectFile(
                    path="examples/sample_config.json",
                    content=config_example,
                    file_type="json",
                    description="Sample configuration file"
                ))
        
        except Exception as e:
            print(f"⚠️ Failed to generate example files: {str(e)}")
        
        return example_files
    
    def _generate_python_examples(self, project: ProjectStructure) -> str:
        """Generate Python usage examples."""
        prompt = f"""
Generate a comprehensive Python usage example for this project:

Project: {project.name}
Description: {project.description}
Technology Stack: {', '.join(project.technology_stack)}

Create a practical example that demonstrates:
1. How to import and initialize the main components
2. Basic usage scenarios
3. Configuration and setup
4. Error handling
5. Common use cases

Provide complete, runnable Python code with comments.
"""
        return self.model_client.generate_response(prompt)
    
    def _generate_javascript_examples(self, project: ProjectStructure) -> str:
        """Generate JavaScript usage examples."""
        prompt = f"""
Generate a comprehensive JavaScript usage example for this project:

Project: {project.name}
Description: {project.description}
Technology Stack: {', '.join(project.technology_stack)}

Create a practical example that demonstrates:
1. How to import and initialize the main components
2. Basic usage scenarios
3. Configuration and setup
4. Error handling
5. Common use cases

Provide complete, runnable JavaScript code with comments.
"""
        return self.model_client.generate_response(prompt)
    
    def _generate_config_example(self, project: ProjectStructure) -> str:
        """Generate example configuration."""
        config = {
            "project_name": project.name,
            "description": project.description,
            "version": "1.0.0",
            "technology_stack": project.technology_stack,
            "environment": "development",
            "debug": True
        }
        
        # Add technology-specific configurations
        if "database" in project.description.lower():
            config["database"] = {
                "host": "localhost",
                "port": 5432,
                "name": "example_db",
                "user": "user",
                "password": "password"
            }
        
        if "api" in project.description.lower():
            config["api"] = {
                "host": "localhost",
                "port": 8000,
                "cors_enabled": True,
                "rate_limiting": {
                    "enabled": True,
                    "requests_per_minute": 100
                }
            }
        
        return json.dumps(config, indent=2)
    
    def _generate_project_summary(self,
                                project: ProjectStructure,
                                test_suite: Optional[Any],
                                validation_result: Optional[ValidationResult],
                                execution_time: float) -> str:
        """Generate a comprehensive project summary."""
        
        summary_lines = [
            f"🎉 Project '{project.name}' generated successfully!",
            "",
            "📊 **Project Overview:**",
            f"  - Technology Stack: {', '.join(project.technology_stack)}",
            f"  - Complexity: {project.estimated_complexity.title()}",
            f"  - Total Files: {len(project.files)}",
            f"  - Generation Time: {execution_time:.2f} seconds",
            ""
        ]
        
        if validation_result:
            summary_lines.extend([
                "✅ **Code Validation:**",
                f"  - Status: {'PASSED' if validation_result.is_valid else 'ISSUES FOUND'}",
                f"  - Total Issues: {validation_result.total_issues}",
                f"  - Security Score: {validation_result.security_score:.1f}/100",
                ""
            ])
            
            if validation_result.test_results:
                test_results = validation_result.test_results
                summary_lines.extend([
                    "🔬 **Test Results:**",
                    f"  - Tests Passed: {test_results.get('passed', 0)}",
                    f"  - Tests Failed: {test_results.get('failed', 0)}",
                    f"  - Coverage: {test_results.get('coverage', 0):.1f}%",
                    ""
                ])
        
        # Add setup instructions
        summary_lines.extend([
            "🚀 **Next Steps:**",
            "1. Extract the generated project files",
            "2. Follow the setup instructions in README.md",
            "3. Install dependencies as specified",
            "4. Start developing your application!"
        ])
        
        return "\n".join(summary_lines)
    
    def export_project_as_zip(self, result: GenerationResult, 
                            include_reports: bool = True) -> bytes:
        """Export the generated project as a ZIP file."""
        
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all project files
            for file in result.generated_files:
                zip_file.writestr(file.path, file.content)
            
            # Add reports if requested
            if include_reports and result.validation_result:
                # Add validation report
                validation_report = self.code_validator.generate_validation_report(
                    result.validation_result
                )
                zip_file.writestr("VALIDATION_REPORT.md", validation_report)
            
            # Add generation summary
            zip_file.writestr("GENERATION_SUMMARY.md", result.summary)
            
            # Add project metadata
            metadata = self._generate_project_metadata(result)
            zip_file.writestr("project_metadata.json", json.dumps(metadata, indent=2))
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    def _generate_project_metadata(self, result: GenerationResult) -> Dict[str, Any]:
        """Generate metadata about the project."""
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "generator_version": "1.0.0",
            "model_used": self.model_name,
            "generation_time": result.execution_time,
            "success": result.success,
            "iterations": result.iterations
        }
        
        if result.project:
            metadata["project"] = {
                "name": result.project.name,
                "description": result.project.description,
                "technology_stack": result.project.technology_stack,
                "complexity": result.project.estimated_complexity,
                "file_count": len(result.project.files),
                "dependencies": result.project.dependencies
            }
        
        if result.validation_result:
            metadata["validation"] = {
                "is_valid": result.validation_result.is_valid,
                "total_issues": result.validation_result.total_issues,
                "issues_by_severity": result.validation_result.issues_by_severity,
                "security_score": result.validation_result.security_score
            }
        
        return metadata
    
    def get_project_metrics(self, result: GenerationResult) -> ProjectMetrics:
        """Calculate comprehensive metrics for the generated project."""
        
        if not result.project:
            return ProjectMetrics(
                total_files=0, total_lines=0, code_files=0, test_files=0,
                config_files=0, doc_files=0, test_coverage=0.0,
                security_score=0.0, complexity_score="unknown",
                technology_stack=[]
            )
        
        # Count different file types
        code_files = 0
        test_files = 0
        config_files = 0
        doc_files = 0
        total_lines = 0
        
        for file in result.generated_files:
            total_lines += file.content.count('\n') + 1
            
            if file.file_type in ['python', 'javascript', 'typescript', 'java', 'cpp']:
                code_files += 1
            elif 'test' in file.path.lower():
                test_files += 1
            elif file.file_type in ['json', 'yaml', 'config']:
                config_files += 1
            elif file.file_type in ['markdown', 'text']:
                doc_files += 1
        
        # Get metrics from validation result
        test_coverage = 0.0
        security_score = 0.0
        
        if result.validation_result:
            test_coverage = result.validation_result.test_results.get('coverage', 0.0)
            security_score = result.validation_result.security_score
        
        return ProjectMetrics(
            total_files=len(result.generated_files),
            total_lines=total_lines,
            code_files=code_files,
            test_files=test_files,
            config_files=config_files,
            doc_files=doc_files,
            test_coverage=test_coverage,
            security_score=security_score,
            complexity_score=result.project.estimated_complexity,
            technology_stack=result.project.technology_stack
        )

# Convenience functions for integration with Streamlit
def create_project_orchestrator(model_name: str = "gemini-2.5-pro") -> ProjectOrchestrator:
    """Factory function to create a project orchestrator."""
    return ProjectOrchestrator(model_name)

def generate_project_from_upload(uploaded_files: Dict[str, str],
                                project_name: str = "",
                                model_name: str = "gemini-2.5-pro", 
                                options: Optional[GenerationOptions] = None) -> GenerationResult:
    opts = options if options is not None else GenerationOptions()
    return create_project_orchestrator(model_name).generate_project_from_documents(
        uploaded_files,
        project_name,
        opts
    )

def generate_project_from_description(description: str,
                                    project_name: str = "",
                                    model_name: str = "gemini-2.5-pro",
                                    options: Optional[GenerationOptions] = None) -> GenerationResult:
    opts = options if options is not None else GenerationOptions()
    return create_project_orchestrator(model_name).generate_project_from_prompt(
        description or "",
        project_name or "",
        opts
    ) 