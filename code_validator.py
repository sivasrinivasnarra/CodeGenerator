"""
Code Validator for MultiModel ChatBot
Validates generated code by checking syntax, running linters, executing tests, and automatically fixing issues.
"""

import os
import ast
import json
import re
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from model_adapter import ModelClient
from project_generator import ProjectStructure, ProjectFile
# from test_generator import TestSuite  # Commented out if not present

@dataclass
class ValidationIssue:
    """Represents a code validation issue."""
    severity: str  # error, warning, info
    issue_type: str  # syntax, style, logic, performance, security
    file_path: str
    line_number: int
    column_number: int = 0
    message: str = ""
    rule_name: str = ""
    suggested_fix: str = ""

@dataclass
class ValidationResult:
    """Represents the result of code validation."""
    is_valid: bool
    total_issues: int
    issues_by_severity: Dict[str, int]
    issues: List[ValidationIssue]
    test_results: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    security_score: float = 0.0

@dataclass
class FixResult:
    """Represents the result of an automated fix."""
    success: bool
    fixed_issues: List[ValidationIssue]
    remaining_issues: List[ValidationIssue]
    modified_files: List[str]
    fix_summary: str

class SyntaxValidator:
    """Validates syntax for different programming languages."""
    
    def __init__(self):
        self.validators = {
            'python': self._validate_python_syntax,
            'javascript': self._validate_javascript_syntax,
            'typescript': self._validate_typescript_syntax,
            'json': self._validate_json_syntax
        }
    
    def validate_file(self, file_path: str, content: str, file_type: str) -> List[ValidationIssue]:
        """Validate syntax of a file."""
        validator = self.validators.get(file_type, None)
        if validator:
            return validator(file_path, content)
        return []
    
    def _validate_python_syntax(self, file_path: str, content: str) -> List[ValidationIssue]:
        """Validate Python syntax."""
        issues = []
        
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                severity="error",
                issue_type="syntax",
                file_path=file_path,
                line_number=e.lineno or 0,
                column_number=e.offset or 0,
                message=f"Syntax error: {e.msg}",
                rule_name="syntax_error"
            ))
        except Exception as e:
            issues.append(ValidationIssue(
                severity="error",
                issue_type="syntax",
                file_path=file_path,
                line_number=0,
                column_number=0,
                message=f"Parse error: {str(e)}",
                rule_name="parse_error"
            ))
        
        return issues
    
    def _validate_javascript_syntax(self, file_path: str, content: str) -> List[ValidationIssue]:
        """Validate JavaScript syntax using Node.js."""
        issues = []
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        try:
            # Use Node.js to check syntax
            result = subprocess.run(
                ['node', '--check', temp_file], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode != 0:
                # Parse error message
                error_lines = result.stderr.strip().split('\n')
                for line in error_lines:
                    if 'SyntaxError' in line:
                        issues.append(ValidationIssue(
                            severity="error",
                            issue_type="syntax",
                            file_path=file_path,
                            line_number=0,
                            column_number=0,
                            message=line,
                            rule_name="syntax_error"
                        ))
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Node.js not available or timeout
            pass
        finally:
            os.unlink(temp_file)
        
        return issues
    
    def _validate_typescript_syntax(self, file_path: str, content: str) -> List[ValidationIssue]:
        """Validate TypeScript syntax."""
        # Similar to JavaScript but would use TypeScript compiler
        # For now, fall back to JavaScript validation
        return self._validate_javascript_syntax(file_path, content)
    
    def _validate_json_syntax(self, file_path: str, content: str) -> List[ValidationIssue]:
        """Validate JSON syntax."""
        issues = []
        
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            issues.append(ValidationIssue(
                severity="error",
                issue_type="syntax",
                file_path=file_path,
                line_number=e.lineno,
                column_number=e.colno,
                message=f"JSON syntax error: {e.msg}",
                rule_name="json_syntax_error"
            ))
        
        return issues

class LinterRunner:
    """Runs various linters on code."""
    
    def __init__(self):
        self.linters = {
            'python': ['flake8', 'pylint', 'black', 'isort'],
            'javascript': ['eslint', 'prettier'],
            'typescript': ['eslint', 'prettier']
        }
    
    def run_linters(self, project_path: str, file_type: str) -> List[ValidationIssue]:
        """Run appropriate linters for the file type."""
        issues = []
        linters = self.linters.get(file_type, [])
        
        for linter in linters:
            try:
                linter_issues = self._run_linter(linter, project_path, file_type)
                issues.extend(linter_issues)
            except Exception as e:
                # Linter not available or failed
                continue
        
        return issues
    
    def _run_linter(self, linter_name: str, project_path: str, file_type: str) -> List[ValidationIssue]:
        """Run a specific linter."""
        issues = []
        
        try:
            if linter_name == 'flake8':
                result = subprocess.run(
                    ['flake8', '--format=json', project_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.stdout:
                    flake8_output = json.loads(result.stdout)
                    for item in flake8_output:
                        issues.append(ValidationIssue(
                            severity="warning" if item['code'].startswith('W') else "error",
                            issue_type="style",
                            file_path=item['filename'],
                            line_number=item['line_number'],
                            column_number=item['column_number'],
                            message=item['text'],
                            rule_name=item['code']
                        ))
            
            elif linter_name == 'pylint':
                result = subprocess.run(
                    ['pylint', '--output-format=json', project_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.stdout:
                    pylint_output = json.loads(result.stdout)
                    for item in pylint_output:
                        severity_map = {'error': 'error', 'warning': 'warning', 'info': 'info'}
                        issues.append(ValidationIssue(
                            severity=severity_map.get(item['type'], 'warning'),
                            issue_type="style",
                            file_path=item['path'],
                            line_number=item['line'],
                            column_number=item['column'],
                            message=item['message'],
                            rule_name=item['message-id']
                        ))
            
            elif linter_name == 'eslint':
                result = subprocess.run(
                    ['eslint', '--format=json', project_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.stdout:
                    eslint_output = json.loads(result.stdout)
                    for file_result in eslint_output:
                        for message in file_result['messages']:
                            severity_map = {1: 'warning', 2: 'error'}
                            issues.append(ValidationIssue(
                                severity=severity_map.get(message['severity'], 'warning'),
                                issue_type="style",
                                file_path=file_result['filePath'],
                                line_number=message['line'],
                                column_number=message['column'],
                                message=message['message'],
                                rule_name=message['ruleId'] or ''
                            ))
        
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            # Linter not available, timeout, or invalid output
            pass
        
        return issues

class TestRunner:
    """Runs tests and analyzes results."""
    
    def __init__(self):
        self.test_commands = {
            'python': ['pytest', '--json-report', '--json-report-file=test_results.json'],
            'javascript': ['npm', 'test', '--', '--json'],
            'typescript': ['npm', 'test', '--', '--json']
        }
    
    def run_tests(self, project_path: str, tech_stack: List[str]) -> Dict[str, Any]:
        """Run tests for the project."""
        test_results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0,
            'coverage': 0.0,
            'duration': 0.0,
            'failures': [],
            'success': False
        }
        
        # Determine primary language
        primary_lang = self._determine_primary_language(tech_stack)
        
        if primary_lang in self.test_commands:
            try:
                result = self._run_test_command(project_path, primary_lang)
                test_results.update(result)
            except Exception as e:
                test_results['failures'].append(f"Test execution failed: {str(e)}")
        
        return test_results
    
    def _determine_primary_language(self, tech_stack: List[str]) -> str:
        """Determine the primary programming language."""
        if "Python" in tech_stack:
            return "python"
        elif any(tech in tech_stack for tech in ["Node.js", "JavaScript"]):
            return "javascript"
        elif "TypeScript" in tech_stack:
            return "typescript"
        else:
            return "unknown"
    
    def _run_test_command(self, project_path: str, language: str) -> Dict[str, Any]:
        """Run test command for specific language."""
        results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0,
            'coverage': 0.0,
            'duration': 0.0,
            'failures': [],
            'success': False
        }
        
        commands = self.test_commands[language]
        
        try:
            result = subprocess.run(
                commands,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if language == "python":
                results = self._parse_pytest_results(project_path, result)
            elif language in ["javascript", "typescript"]:
                results = self._parse_jest_results(result)
            
            results['success'] = result.returncode == 0
        
        except subprocess.TimeoutExpired:
            results['failures'].append("Test execution timed out")
        except FileNotFoundError:
            results['failures'].append("Test runner not found")
        
        return results
    
    def _parse_pytest_results(self, project_path: str, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse pytest JSON results."""
        results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0,
            'coverage': 0.0,
            'duration': 0.0,
            'failures': []
        }
        
        # Try to read JSON report
        json_file = os.path.join(project_path, 'test_results.json')
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                summary = data.get('summary', {})
                results['passed'] = summary.get('passed', 0)
                results['failed'] = summary.get('failed', 0)
                results['skipped'] = summary.get('skipped', 0)
                results['total'] = summary.get('total', 0)
                results['duration'] = summary.get('duration', 0.0)
                
                # Extract failures
                for test in data.get('tests', []):
                    if test.get('outcome') == 'failed':
                        results['failures'].append({
                            'test': test.get('nodeid', ''),
                            'message': test.get('call', {}).get('longrepr', '')
                        })
            
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        return results
    
    def _parse_jest_results(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse Jest JSON results."""
        results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0,
            'coverage': 0.0,
            'duration': 0.0,
            'failures': []
        }
        
        try:
            if result.stdout:
                data = json.loads(result.stdout)
                
                results['passed'] = data.get('numPassedTests', 0)
                results['failed'] = data.get('numFailedTests', 0)
                results['skipped'] = data.get('numPendingTests', 0)
                results['total'] = data.get('numTotalTests', 0)
                
                # Extract coverage if available
                coverage_data = data.get('coverageMap', {})
                if coverage_data:
                    # Calculate average coverage
                    total_lines = sum(file_data.get('s', {}).values() for file_data in coverage_data.values())
                    covered_lines = sum(1 for file_data in coverage_data.values() 
                                      for count in file_data.get('s', {}).values() if count > 0)
                    if total_lines > 0:
                        results['coverage'] = (covered_lines / total_lines) * 100
        
        except json.JSONDecodeError:
            pass
        
        return results

class SecurityScanner:
    """Scans code for security vulnerabilities."""
    
    def __init__(self):
        self.security_patterns = {
            'python': [
                (r'eval\s*\(', 'Use of eval() is dangerous'),
                (r'exec\s*\(', 'Use of exec() is dangerous'),
                (r'input\s*\(', 'Use input() with caution'),
                (r'shell=True', 'shell=True in subprocess is risky'),
                (r'pickle\.loads?', 'Pickle deserialization is unsafe'),
                (r'yaml\.load\s*\((?!.*Loader)', 'Use yaml.safe_load() instead'),
            ],
            'javascript': [
                (r'eval\s*\(', 'Use of eval() is dangerous'),
                (r'innerHTML\s*=', 'innerHTML assignment can lead to XSS'),
                (r'document\.write\s*\(', 'document.write() is vulnerable to XSS'),
                (r'setTimeout\s*\(\s*["\']', 'String in setTimeout can be dangerous'),
                (r'new Function\s*\(', 'Function constructor can be dangerous'),
            ]
        }
    
    def scan_project(self, project: ProjectStructure) -> List[ValidationIssue]:
        """Scan project for security issues."""
        issues = []
        
        for file in project.files:
            file_issues = self.scan_file(file)
            issues.extend(file_issues)
        
        return issues
    
    def scan_file(self, project_file: ProjectFile) -> List[ValidationIssue]:
        """Scan a single file for security issues."""
        issues = []
        patterns = self.security_patterns.get(project_file.file_type, [])
        
        lines = project_file.content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, message in patterns:
                if re.search(pattern, line):
                    issues.append(ValidationIssue(
                        severity="warning",
                        issue_type="security",
                        file_path=project_file.path,
                        line_number=line_num,
                        column_number=0,
                        message=message,
                        rule_name="security_scan"
                    ))
        
        return issues

class AutoFixer:
    """Automatically fixes common code issues."""
    
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
        self.fixable_rules = {
            'python': [
                'missing_import',
                'unused_import',
                'line_too_long',
                'trailing_whitespace',
                'missing_docstring',
                'syntax_error'
            ],
            'javascript': [
                'missing_semicolon',
                'unused_variable',
                'missing_declaration',
                'trailing_comma',
                'syntax_error'
            ]
        }
    
    def fix_issues(self, project: ProjectStructure, issues: List[ValidationIssue]) -> FixResult:
        """Automatically fix issues in the project."""
        fixed_issues = []
        remaining_issues = []
        modified_files = []
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue)
        
        # Fix issues file by file
        for file_path, file_issues in issues_by_file.items():
            # Find the corresponding project file
            project_file = next((f for f in project.files if f.path == file_path), None)
            if not project_file:
                remaining_issues.extend(file_issues)
                continue
            
            # Attempt to fix issues
            fix_result = self._fix_file_issues(project_file, file_issues)
            
            if fix_result['success']:
                project_file.content = fix_result['fixed_content']
                fixed_issues.extend(fix_result['fixed_issues'])
                remaining_issues.extend(fix_result['remaining_issues'])
                modified_files.append(file_path)
            else:
                remaining_issues.extend(file_issues)
        
        # Generate fix summary
        fix_summary = self._generate_fix_summary(fixed_issues, remaining_issues, modified_files)
        
        return FixResult(
            success=len(fixed_issues) > 0,
            fixed_issues=fixed_issues,
            remaining_issues=remaining_issues,
            modified_files=modified_files,
            fix_summary=fix_summary
        )
    
    def _fix_file_issues(self, project_file: ProjectFile, issues: List[ValidationIssue]) -> Dict[str, Any]:
        """Fix issues in a specific file."""
        fixable_issues = [issue for issue in issues if self._is_fixable(issue, project_file.file_type)]
        
        if not fixable_issues:
            return {
                'success': False,
                'fixed_content': project_file.content,
                'fixed_issues': [],
                'remaining_issues': issues
            }
        
        # Generate fix prompt
        fix_prompt = self._generate_fix_prompt(project_file, fixable_issues)
        
        try:
            # Get AI-generated fix
            fixed_content = self.model_client.generate_response(fix_prompt)
            
            # Validate the fix
            if self._validate_fix(project_file, fixed_content, fixable_issues):
                return {
                    'success': True,
                    'fixed_content': fixed_content,
                    'fixed_issues': fixable_issues,
                    'remaining_issues': [issue for issue in issues if issue not in fixable_issues]
                }
        
        except Exception as e:
            pass
        
        return {
            'success': False,
            'fixed_content': project_file.content,
            'fixed_issues': [],
            'remaining_issues': issues
        }
    
    def _is_fixable(self, issue: ValidationIssue, file_type: str) -> bool:
        """Check if an issue can be automatically fixed."""
        fixable_rules = self.fixable_rules.get(file_type, [])
        return issue.rule_name in fixable_rules or issue.severity == "error"
    
    def _generate_fix_prompt(self, project_file: ProjectFile, issues: List[ValidationIssue]) -> str:
        """Generate prompt for fixing issues."""
        issues_description = "\n".join([
            f"Line {issue.line_number}: {issue.message} ({issue.rule_name})"
            for issue in issues
        ])
        
        return f"""
Fix the following issues in this {project_file.file_type} code:

File: {project_file.path}

Issues to fix:
{issues_description}

Original code:
{project_file.content}

Please provide the corrected code that fixes all the issues above while maintaining the original functionality. Only return the corrected code, no explanations.
"""
    
    def _validate_fix(self, original_file: ProjectFile, fixed_content: str, issues: List[ValidationIssue]) -> bool:
        """Validate that the fix is correct."""
        # Basic validation - check if the content is significantly different
        if len(fixed_content) < len(original_file.content) * 0.5:
            return False
        
        # Check syntax if possible
        if original_file.file_type == "python":
            try:
                ast.parse(fixed_content)
                return True
            except SyntaxError:
                return False
        
        return True
    
    def _generate_fix_summary(self, fixed_issues: List[ValidationIssue], 
                            remaining_issues: List[ValidationIssue], 
                            modified_files: List[str]) -> str:
        """Generate a summary of the fix results."""
        summary = f"Automated Fix Summary:\n"
        summary += f"- Fixed {len(fixed_issues)} issues\n"
        summary += f"- {len(remaining_issues)} issues remain\n"
        summary += f"- Modified {len(modified_files)} files\n"
        
        if modified_files:
            summary += f"\nModified files:\n"
            for file_path in modified_files:
                summary += f"  - {file_path}\n"
        
        if remaining_issues:
            summary += f"\nRemaining issues by severity:\n"
            severity_counts = {}
            for issue in remaining_issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            
            for severity, count in severity_counts.items():
                summary += f"  - {severity}: {count}\n"
        
        return summary

class CodeValidator:
    """Main class for comprehensive code validation."""
    
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_client = ModelClient(model_name)
        self.syntax_validator = SyntaxValidator()
        self.linter_runner = LinterRunner()
        self.test_runner = TestRunner()
        self.security_scanner = SecurityScanner()
        self.auto_fixer = AutoFixer(self.model_client)
    
    def validate_project(self, project: ProjectStructure, 
                        test_suite: Optional[Any] = None,
                        run_tests: bool = True,
                        auto_fix: bool = True) -> ValidationResult:
        """Perform comprehensive validation of a project."""
        
        all_issues = []
        
        # 1. Syntax validation
        syntax_issues = self._validate_syntax(project)
        all_issues.extend(syntax_issues)
        
        # 2. Security scanning
        security_issues = self.security_scanner.scan_project(project)
        all_issues.extend(security_issues)
        
        # 3. Create temporary project directory for linting and testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write project files to temp directory
            self._write_project_to_disk(project, temp_dir)
            
            # 4. Linting
            linter_issues = self._run_linting(temp_dir, project)
            all_issues.extend(linter_issues)
            
            # 5. Testing
            test_results = {}
            if run_tests and test_suite:
                # Write test files
                self._write_test_suite_to_disk(test_suite, temp_dir)
                test_results = self.test_runner.run_tests(temp_dir, project.technology_stack)
        
        # 6. Auto-fix issues if requested
        fix_result = None
        if auto_fix and all_issues:
            fix_result = self.auto_fixer.fix_issues(project, all_issues)
            if fix_result.success:
                # Re-run validation on fixed code
                return self.validate_project(project, test_suite, run_tests, auto_fix=False)
        
        # 7. Calculate metrics
        issues_by_severity = self._group_issues_by_severity(all_issues)
        security_score = self._calculate_security_score(security_issues, len(project.files))
        
        # 8. Performance metrics (basic)
        performance_metrics = {
            'total_files': len(project.files),
            'total_lines': sum(file.content.count('\n') + 1 for file in project.files),
            'complexity_estimate': self._estimate_complexity(project)
        }
        
        return ValidationResult(
            is_valid=len([i for i in all_issues if i.severity == "error"]) == 0,
            total_issues=len(all_issues),
            issues_by_severity=issues_by_severity,
            issues=all_issues,
            test_results=test_results,
            performance_metrics=performance_metrics,
            security_score=security_score
        )
    
    def _validate_syntax(self, project: ProjectStructure) -> List[ValidationIssue]:
        """Validate syntax of all project files."""
        issues = []
        
        for file in project.files:
            file_issues = self.syntax_validator.validate_file(
                file.path, file.content, file.file_type
            )
            issues.extend(file_issues)
        
        return issues
    
    def _write_project_to_disk(self, project: ProjectStructure, base_path: str):
        """Write project files to disk for linting and testing."""
        for file in project.files:
            file_path = os.path.join(base_path, file.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file.content)
    
    def _write_test_suite_to_disk(self, test_suite: Any, base_path: str):
        """Write test files to disk."""
        for test_file in test_suite.test_files:
            file_path = os.path.join(base_path, test_file.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(test_file.content)
    
    def _run_linting(self, project_path: str, project: ProjectStructure) -> List[ValidationIssue]:
        """Run linting on the project."""
        issues = []
        
        # Determine file types present
        file_types = set(file.file_type for file in project.files)
        
        for file_type in file_types:
            if file_type in ['python', 'javascript', 'typescript']:
                linter_issues = self.linter_runner.run_linters(project_path, file_type)
                issues.extend(linter_issues)
        
        return issues
    
    def _group_issues_by_severity(self, issues: List[ValidationIssue]) -> Dict[str, int]:
        """Group issues by severity level."""
        severity_counts = {'error': 0, 'warning': 0, 'info': 0}
        
        for issue in issues:
            if issue.severity in severity_counts:
                severity_counts[issue.severity] += 1
        
        return severity_counts
    
    def _calculate_security_score(self, security_issues: List[ValidationIssue], total_files: int) -> float:
        """Calculate a security score for the project."""
        if total_files == 0:
            return 100.0
        
        # Base score
        base_score = 100.0
        
        # Deduct points for security issues
        for issue in security_issues:
            if issue.severity == "error":
                base_score -= 20.0
            elif issue.severity == "warning":
                base_score -= 10.0
            else:
                base_score -= 5.0
        
        return max(0.0, base_score)
    
    def _estimate_complexity(self, project: ProjectStructure) -> str:
        """Estimate project complexity."""
        total_lines = sum(file.content.count('\n') + 1 for file in project.files)
        file_count = len(project.files)
        
        if total_lines > 5000 or file_count > 20:
            return "high"
        elif total_lines > 1000 or file_count > 10:
            return "medium"
        else:
            return "low"
    
    def generate_validation_report(self, validation_result: ValidationResult) -> str:
        """Generate a comprehensive validation report."""
        report = f"""
# Code Validation Report

## Summary
- **Validation Status**: {'✅ PASSED' if validation_result.is_valid else '❌ FAILED'}
- **Total Issues**: {validation_result.total_issues}
- **Security Score**: {validation_result.security_score:.1f}/100

## Issues by Severity
- **Errors**: {validation_result.issues_by_severity.get('error', 0)}
- **Warnings**: {validation_result.issues_by_severity.get('warning', 0)}
- **Info**: {validation_result.issues_by_severity.get('info', 0)}

## Test Results
"""
        
        if validation_result.test_results:
            test_results = validation_result.test_results
            report += f"""
- **Tests Passed**: {test_results.get('passed', 0)}
- **Tests Failed**: {test_results.get('failed', 0)}
- **Tests Skipped**: {test_results.get('skipped', 0)}
- **Coverage**: {test_results.get('coverage', 0):.1f}%
- **Duration**: {test_results.get('duration', 0):.2f}s
"""
        else:
            report += "- No test results available\n"
        
        ## Performance Metrics
        perf = validation_result.performance_metrics
        report += f"""
## Performance Metrics
- **Total Files**: {perf.get('total_files', 0)}
- **Total Lines**: {perf.get('total_lines', 0)}
- **Complexity**: {perf.get('complexity_estimate', 'unknown').title()}

## Detailed Issues
"""
        
        if validation_result.issues:
            # Group issues by file
            issues_by_file = {}
            for issue in validation_result.issues:
                if issue.file_path not in issues_by_file:
                    issues_by_file[issue.file_path] = []
                issues_by_file[issue.file_path].append(issue)
            
            for file_path, file_issues in issues_by_file.items():
                report += f"\n### {file_path}\n"
                for issue in file_issues:
                    severity_icon = {'error': '🔴', 'warning': '🟡', 'info': '🔵'}.get(issue.severity, '⚪')
                    report += f"- {severity_icon} Line {issue.line_number}: {issue.message} ({issue.rule_name})\n"
        else:
            report += "No issues found! 🎉\n"
        
        return report 