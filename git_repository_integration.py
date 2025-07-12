"""
Git Repository Integration for MultiModel ChatBot
Fetches and analyzes projects from GitHub, Bitbucket, and other Git platforms
"""

import os
import re
import requests
import base64
import zipfile
import tempfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, quote
import json

@dataclass
class RepositoryInfo:
    owner: str
    name: str
    platform: str  # 'github', 'bitbucket', 'gitlab'
    branch: str
    url: str
    description: Optional[str] = None
    language: Optional[str] = None
    size: Optional[int] = None

@dataclass
class FileInfo:
    path: str
    content: str
    size: int
    type: str  # 'file', 'directory'
    language: Optional[str] = None

class GitRepositoryIntegration:
    """Handles fetching and analyzing Git repositories from various platforms."""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.max_file_size = 1024 * 1024  # 1MB limit per file
        self.max_files = 100  # Maximum files to fetch
        self.supported_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.md', 
            '.json', '.yaml', '.yml', '.txt', '.java', '.cpp', '.c', 
            '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt'
        }
    
    def parse_repository_url(self, url: str) -> Optional[RepositoryInfo]:
        """Parse repository URL to extract platform, owner, and repo name."""
        
        # Clean up URL
        url = url.strip().rstrip('/')
        
        # GitHub patterns
        github_patterns = [
            r'github\.com/([^/]+)/([^/]+)',
            r'raw\.githubusercontent\.com/([^/]+)/([^/]+)',
        ]
        
        # Bitbucket patterns
        bitbucket_patterns = [
            r'bitbucket\.org/([^/]+)/([^/]+)',
        ]
        
        # GitLab patterns
        gitlab_patterns = [
            r'gitlab\.com/([^/]+)/([^/]+)',
        ]
        
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc.lower()
        path = parsed_url.path.strip('/')
        
        # Determine platform and extract info
        if 'github.com' in hostname:
            for pattern in github_patterns:
                match = re.search(pattern, url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.replace('.git', '')  # Remove .git suffix
                    return RepositoryInfo(
                        owner=owner,
                        name=repo,
                        platform='github',
                        branch='main',  # Default, will be updated
                        url=url,
                    )
        
        elif 'bitbucket.org' in hostname:
            for pattern in bitbucket_patterns:
                match = re.search(pattern, url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.replace('.git', '')
                    return RepositoryInfo(
                        owner=owner,
                        name=repo,
                        platform='bitbucket',
                        branch='main',
                        url=url,
                    )
        
        elif 'gitlab.com' in hostname:
            for pattern in gitlab_patterns:
                match = re.search(pattern, url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.replace('.git', '')
                    return RepositoryInfo(
                        owner=owner,
                        name=repo,
                        platform='gitlab',
                        branch='main',
                        url=url,
                    )
        
        return None
    
    def fetch_repository(self, url: str, branch: Optional[str] = None) -> Tuple[RepositoryInfo, Dict[str, str]]:
        """Fetch repository files from URL."""
        
        repo_info = self.parse_repository_url(url)
        if not repo_info:
            raise ValueError("Unsupported repository URL format")
        
        if branch:
            repo_info.branch = branch
        
        if repo_info.platform == 'github':
            return self._fetch_github_repository(repo_info)
        elif repo_info.platform == 'bitbucket':
            return self._fetch_bitbucket_repository(repo_info)
        elif repo_info.platform == 'gitlab':
            return self._fetch_gitlab_repository(repo_info)
        else:
            raise ValueError(f"Unsupported platform: {repo_info.platform}")
    
    def _fetch_github_repository(self, repo_info: RepositoryInfo) -> Tuple[RepositoryInfo, Dict[str, str]]:
        """Fetch files from GitHub repository."""
        
        base_url = "https://api.github.com"
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        # Get repository info
        repo_url = f"{base_url}/repos/{repo_info.owner}/{repo_info.name}"
        try:
            repo_response = requests.get(repo_url, headers=headers)
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            
            repo_info.description = repo_data.get('description')
            repo_info.language = repo_data.get('language')
            repo_info.size = repo_data.get('size')
            repo_info.branch = repo_data.get('default_branch', 'main')
            
        except requests.RequestException as e:
            print(f"Warning: Could not fetch repository info: {e}")
        
        # Get file tree
        tree_url = f"{base_url}/repos/{repo_info.owner}/{repo_info.name}/git/trees/{repo_info.branch}?recursive=1"
        
        try:
            tree_response = requests.get(tree_url, headers=headers)
            tree_response.raise_for_status()
            tree_data = tree_response.json()
            
            files = {}
            file_count = 0
            
            for item in tree_data.get('tree', []):
                if file_count >= self.max_files:
                    break
                    
                if item['type'] == 'blob':  # It's a file
                    file_path = item['path']
                    file_size = item.get('size', 0)
                    
                    # Skip large files
                    if file_size > self.max_file_size:
                        continue
                    
                    # Skip unsupported file types
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext not in self.supported_extensions:
                        continue
                    
                    # Fetch file content
                    content = self._fetch_github_file_content(repo_info, file_path, headers)
                    if content:
                        files[file_path] = content
                        file_count += 1
            
            return repo_info, files
            
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch repository tree: {e}")
    
    def _fetch_github_file_content(self, repo_info: RepositoryInfo, file_path: str, headers: Dict) -> Optional[str]:
        """Fetch individual file content from GitHub."""
        
        base_url = "https://api.github.com"
        content_url = f"{base_url}/repos/{repo_info.owner}/{repo_info.name}/contents/{quote(file_path)}?ref={repo_info.branch}"
        
        try:
            response = requests.get(content_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get('encoding') == 'base64':
                content = base64.b64decode(data['content']).decode('utf-8', errors='ignore')
                return content
            
        except requests.RequestException:
            pass  # Skip files that can't be fetched
        except UnicodeDecodeError:
            pass  # Skip binary files
        
        return None
    
    def _fetch_bitbucket_repository(self, repo_info: RepositoryInfo) -> Tuple[RepositoryInfo, Dict[str, str]]:
        """Fetch files from Bitbucket repository."""
        
        base_url = "https://api.bitbucket.org/2.0"
        
        # Get repository info
        repo_url = f"{base_url}/repositories/{repo_info.owner}/{repo_info.name}"
        try:
            repo_response = requests.get(repo_url)
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            
            repo_info.description = repo_data.get('description')
            repo_info.language = repo_data.get('language')
            
            # Get main branch
            if 'mainbranch' in repo_data and repo_data['mainbranch']:
                repo_info.branch = repo_data['mainbranch']['name']
                
        except requests.RequestException as e:
            print(f"Warning: Could not fetch repository info: {e}")
        
        # Get file listing
        src_url = f"{base_url}/repositories/{repo_info.owner}/{repo_info.name}/src/{repo_info.branch}/"
        
        files = {}
        self._fetch_bitbucket_directory(repo_info, src_url, "", files)
        
        return repo_info, files
    
    def _fetch_bitbucket_directory(self, repo_info: RepositoryInfo, url: str, path_prefix: str, files: Dict[str, str]):
        """Recursively fetch Bitbucket directory contents."""
        
        if len(files) >= self.max_files:
            return
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('values', []):
                if len(files) >= self.max_files:
                    break
                    
                item_path = f"{path_prefix}{item['path']}" if path_prefix else item['path']
                
                if item['type'] == 'commit_file':
                    # It's a file
                    file_ext = os.path.splitext(item_path)[1].lower()
                    if file_ext in self.supported_extensions:
                        content = self._fetch_bitbucket_file_content(repo_info, item_path)
                        if content:
                            files[item_path] = content
                
                elif item['type'] == 'commit_directory':
                    # It's a directory, recurse
                    dir_url = f"https://api.bitbucket.org/2.0/repositories/{repo_info.owner}/{repo_info.name}/src/{repo_info.branch}/{quote(item_path)}"
                    self._fetch_bitbucket_directory(repo_info, dir_url, f"{item_path}/", files)
            
        except requests.RequestException:
            pass  # Skip directories that can't be fetched
    
    def _fetch_bitbucket_file_content(self, repo_info: RepositoryInfo, file_path: str) -> Optional[str]:
        """Fetch individual file content from Bitbucket."""
        
        raw_url = f"https://bitbucket.org/{repo_info.owner}/{repo_info.name}/raw/{repo_info.branch}/{quote(file_path)}"
        
        try:
            response = requests.get(raw_url)
            response.raise_for_status()
            return response.text
            
        except requests.RequestException:
            return None
        except UnicodeDecodeError:
            return None  # Skip binary files
    
    def _fetch_gitlab_repository(self, repo_info: RepositoryInfo) -> Tuple[RepositoryInfo, Dict[str, str]]:
        """Fetch files from GitLab repository."""
        
        base_url = "https://gitlab.com/api/v4"
        project_path = f"{repo_info.owner}/{repo_info.name}"
        encoded_path = quote(project_path, safe='')
        
        # Get repository info
        repo_url = f"{base_url}/projects/{encoded_path}"
        try:
            repo_response = requests.get(repo_url)
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            
            repo_info.description = repo_data.get('description')
            repo_info.branch = repo_data.get('default_branch', 'main')
            
        except requests.RequestException as e:
            print(f"Warning: Could not fetch repository info: {e}")
        
        # Get file tree
        tree_url = f"{base_url}/projects/{encoded_path}/repository/tree?recursive=true&ref={repo_info.branch}"
        
        try:
            tree_response = requests.get(tree_url)
            tree_response.raise_for_status()
            tree_data = tree_response.json()
            
            files = {}
            file_count = 0
            
            for item in tree_data:
                if file_count >= self.max_files:
                    break
                    
                if item['type'] == 'blob':  # It's a file
                    file_path = item['path']
                    
                    # Skip unsupported file types
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext not in self.supported_extensions:
                        continue
                    
                    # Fetch file content
                    content = self._fetch_gitlab_file_content(repo_info, file_path)
                    if content:
                        files[file_path] = content
                        file_count += 1
            
            return repo_info, files
            
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch repository tree: {e}")
    
    def _fetch_gitlab_file_content(self, repo_info: RepositoryInfo, file_path: str) -> Optional[str]:
        """Fetch individual file content from GitLab."""
        
        base_url = "https://gitlab.com/api/v4"
        project_path = f"{repo_info.owner}/{repo_info.name}"
        encoded_path = quote(project_path, safe='')
        encoded_file_path = quote(file_path, safe='')
        
        content_url = f"{base_url}/projects/{encoded_path}/repository/files/{encoded_file_path}/raw?ref={repo_info.branch}"
        
        try:
            response = requests.get(content_url)
            response.raise_for_status()
            return response.text
            
        except requests.RequestException:
            return None
        except UnicodeDecodeError:
            return None  # Skip binary files
    
    def analyze_repository_structure(self, files: Dict[str, str]) -> Dict[str, any]:
        """Analyze repository structure and provide insights."""
        
        analysis = {
            'total_files': len(files),
            'languages': {},
            'file_types': {},
            'directory_structure': {},
            'main_files': [],
            'config_files': [],
            'test_files': [],
            'documentation_files': [],
            'size_breakdown': {'small': 0, 'medium': 0, 'large': 0}
        }
        
        for file_path, content in files.items():
            # File extension analysis
            file_ext = os.path.splitext(file_path)[1].lower()
            analysis['file_types'][file_ext] = analysis['file_types'].get(file_ext, 0) + 1
            
            # Language detection
            language = self._detect_language(file_ext, content)
            if language:
                analysis['languages'][language] = analysis['languages'].get(language, 0) + 1
            
            # Directory structure
            directory = os.path.dirname(file_path) or 'root'
            analysis['directory_structure'][directory] = analysis['directory_structure'].get(directory, 0) + 1
            
            # Special file categories
            filename = os.path.basename(file_path).lower()
            
            if any(name in filename for name in ['main', 'index', 'app', '__init__']):
                analysis['main_files'].append(file_path)
            
            if any(name in filename for name in ['config', 'settings', 'env', 'package.json', 'requirements.txt', 'gemfile', 'dockerfile']):
                analysis['config_files'].append(file_path)
            
            if any(name in filename for name in ['test', 'spec', '__tests__']):
                analysis['test_files'].append(file_path)
            
            if any(name in filename for name in ['readme', 'doc', 'license', 'changelog']):
                analysis['documentation_files'].append(file_path)
            
            # Size analysis
            size = len(content)
            if size < 1000:
                analysis['size_breakdown']['small'] += 1
            elif size < 10000:
                analysis['size_breakdown']['medium'] += 1
            else:
                analysis['size_breakdown']['large'] += 1
        
        return analysis
    
    def _detect_language(self, file_ext: str, content: str) -> Optional[str]:
        """Detect programming language from file extension and content."""
        
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React JSX',
            '.tsx': 'React TSX',
            '.html': 'HTML',
            '.css': 'CSS',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.md': 'Markdown',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML'
        }
        
        return language_map.get(file_ext)
    
    def get_repository_summary(self, repo_info: RepositoryInfo, files: Dict[str, str], analysis: Dict[str, any]) -> str:
        """Generate a comprehensive repository summary."""
        
        summary = f"""
# Repository Analysis: {repo_info.name}

**Platform:** {repo_info.platform.title()}
**Owner:** {repo_info.owner}
**Branch:** {repo_info.branch}
**Description:** {repo_info.description or 'No description available'}

## Project Statistics
- **Total Files:** {analysis['total_files']}
- **Main Language:** {repo_info.language or 'Unknown'}
- **Languages Found:** {', '.join(analysis['languages'].keys())}

## File Distribution
"""
        
        for lang, count in analysis['languages'].items():
            percentage = (count / analysis['total_files']) * 100
            summary += f"- **{lang}:** {count} files ({percentage:.1f}%)\n"
        
        summary += f"""
## Directory Structure
- **Directories:** {len(analysis['directory_structure'])}
- **Main Files:** {len(analysis['main_files'])}
- **Configuration Files:** {len(analysis['config_files'])}
- **Test Files:** {len(analysis['test_files'])}
- **Documentation Files:** {len(analysis['documentation_files'])}

## Key Files Identified
"""
        
        if analysis['main_files']:
            summary += "**Main Application Files:**\n"
            for file in analysis['main_files'][:5]:  # Show top 5
                summary += f"- {file}\n"
        
        if analysis['config_files']:
            summary += "\n**Configuration Files:**\n"
            for file in analysis['config_files'][:5]:
                summary += f"- {file}\n"
        
        return summary 