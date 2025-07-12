"""
RAG System for MultiModel ChatBot
Provides vector embeddings, semantic search, and knowledge base functionality
for uploaded project files.
"""

import os
import hashlib
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss  # type: ignore
import pickle


@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    embedding: Optional[np.ndarray] = None


@dataclass
class SearchResult:
    chunk: DocumentChunk
    similarity_score: float
    rank: int


class ProjectFileProcessor:
    """Processes and chunks uploaded project files for RAG indexing."""

    def __init__(self):
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.md': 'markdown',
            '.txt': 'text',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.sh': 'shell',
            '.dockerfile': 'docker',
            '.gitignore': 'config',
            '.env': 'config'
        }

    def process_files(self, files_content: Dict[str, str], user_id: str,
                      project_id: str) -> List[DocumentChunk]:
        """Process uploaded files into searchable chunks."""
        chunks = []

        for filename, content in files_content.items():
            file_chunks = self._chunk_file(filename, content,
                                           user_id, project_id)
            chunks.extend(file_chunks)

        return chunks

    def _chunk_file(self, filename: str, content: str, user_id: str,
                    project_id: str) -> List[DocumentChunk]:
        """Chunk a single file into manageable pieces."""
        file_ext = os.path.splitext(filename)[1].lower()
        file_type = self.supported_extensions.get(file_ext, 'unknown')

        chunks = []

        if file_type == 'python':
            chunks = self._chunk_python_file(filename, content,
                                             user_id, project_id)
        elif file_type in ['javascript', 'typescript']:
            chunks = self._chunk_js_file(filename, content,
                                         user_id, project_id)
        elif file_type == 'markdown':
            chunks = self._chunk_markdown_file(filename, content,
                                               user_id, project_id)
        elif file_type == 'json':
            chunks = self._chunk_json_file(filename, content,
                                           user_id, project_id)
        else:
            chunks = self._chunk_generic_file(filename, content,
                                              user_id, project_id, file_type)

        return chunks

    def _chunk_python_file(self, filename: str, content: str, user_id: str,
                           project_id: str) -> List[DocumentChunk]:
        """Chunk Python files by functions, classes, and imports."""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_type = 'general'

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect imports
            if stripped.startswith(('import ', 'from ')):
                if current_chunk and current_type != 'imports':
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'imports'
                current_chunk.append(line)

            # Detect class definitions
            elif stripped.startswith('class '):
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'class'
                current_chunk.append(line)

            # Detect function definitions
            elif stripped.startswith('def '):
                if current_chunk and current_type != 'class':
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'function'
                current_chunk.append(line)

            else:
                current_chunk.append(line)

                # Create chunk if it gets too large
                if len(current_chunk) > 50:
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                    current_type = 'general'

        # Add remaining content
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n'.join(current_chunk), filename, user_id, project_id,
                {'type': current_type,
                 'start_line': len(lines) - len(current_chunk) + 1}
            ))

        return chunks

    def _chunk_js_file(self, filename: str, content: str, user_id: str,
                       project_id: str) -> List[DocumentChunk]:
        """Chunk JavaScript/TypeScript files by functions and imports."""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_type = 'general'

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect imports
            if (stripped.startswith(('import ', 'require(', 'const ',
                                     'let ', 'var ')) and
                    ('require(' in stripped or 'import' in stripped)):
                if current_chunk and current_type != 'imports':
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'imports'
                current_chunk.append(line)

            # Detect class definitions
            elif stripped.startswith('class ') or 'class ' in stripped:
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'class'
                current_chunk.append(line)

            # Detect function definitions
            elif (stripped.startswith(('function ', 'const ')) and
                  ('=' in stripped and '=>' in stripped or
                   'function' in stripped)):
                if current_chunk and current_type != 'class':
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                current_type = 'function'
                current_chunk.append(line)

            else:
                current_chunk.append(line)

                # Create chunk if it gets too large
                if len(current_chunk) > 50:
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk), filename,
                        user_id, project_id,
                        {'type': current_type,
                         'start_line': i - len(current_chunk) + 1}
                    ))
                    current_chunk = []
                    current_type = 'general'

        # Add remaining content
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n'.join(current_chunk), filename, user_id, project_id,
                {'type': current_type,
                 'start_line': len(lines) - len(current_chunk) + 1}
            ))

        return chunks

    def _chunk_markdown_file(self, filename: str, content: str, user_id: str,
                             project_id: str) -> List[DocumentChunk]:
        """Chunk Markdown files by sections."""
        chunks = []
        sections = content.split('\n#')

        for i, section in enumerate(sections):
            if i > 0:
                section = '#' + section

            if section.strip():
                chunks.append(self._create_chunk(
                    section.strip(), filename, user_id, project_id,
                    {'type': 'markdown_section', 'section_index': i}
                ))

        return chunks

    def _chunk_json_file(self, filename: str, content: str, user_id: str,
                         project_id: str) -> List[DocumentChunk]:
        """Chunk JSON files by top-level keys."""
        chunks = []
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for key, value in data.items():
                    chunk_content = f"Key: {key}\nValue: {json.dumps(value, indent=2)}"
                    chunks.append(self._create_chunk(
                        chunk_content, filename, user_id, project_id,
                        {'type': 'json_key', 'key': key}
                    ))
            else:
                chunks.append(self._create_chunk(
                    content, filename, user_id, project_id,
                    {'type': 'json_content'}
                ))
        except json.JSONDecodeError:
            chunks.append(self._create_chunk(
                content, filename, user_id, project_id,
                {'type': 'invalid_json'}
            ))

        return chunks

    def _chunk_generic_file(self, filename: str, content: str, user_id: str,
                            project_id: str, file_type: str) -> List[DocumentChunk]:
        """Generic chunking for other file types."""
        chunks = []
        lines = content.split('\n')
        chunk_size = 100  # lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunk_content = '\n'.join(chunk_lines)

            chunks.append(self._create_chunk(
                chunk_content, filename, user_id, project_id,
                {'type': file_type, 'start_line': i + 1, 'end_line': i + len(chunk_lines)}
            ))

        return chunks

    def _create_chunk(self, content: str, filename: str, user_id: str,
                      project_id: str, metadata: Dict) -> DocumentChunk:
        """Create a DocumentChunk with proper metadata."""
        chunk_id = hashlib.md5(f"{user_id}_{project_id}_{filename}_{content[:100]}".encode()).hexdigest()

        full_metadata = {
            'filename': filename,
            'user_id': user_id,
            'project_id': project_id,
            'created_at': datetime.now().isoformat(),
            'content_length': len(content),
            **metadata
        }

        return DocumentChunk(
            content=content,
            metadata=full_metadata,
            chunk_id=chunk_id
        )

class VectorStore:
    """Vector storage and similarity search using FAISS."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        self.chunks: List[DocumentChunk] = []
        self.metadata_store: Dict[str, DocumentChunk] = {}

    def add_chunks(self, chunks: List[DocumentChunk]):
        """Add document chunks to the vector store."""
        if not chunks:
            return

        # Generate embeddings
        contents = [chunk.content for chunk in chunks]
        embeddings = self.model.encode(contents, normalize_embeddings=True)
        # Add to FAISS index
        embeddings_float32 = embeddings.astype('float32')
        self.index.add(embeddings_float32)

        # Store chunks and metadata 
        for chunk, embedding in zip(chunks, embeddings_float32):
            chunk.embedding = embedding
            self.chunks.append(chunk)
            self.metadata_store[chunk.chunk_id] = chunk

    def search(self, query: str, k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """Search for similar chunks using semantic similarity."""
        if self.index.ntotal == 0:
            return []
        # Generate query embedding
        query_embedding = self.model.encode([query], normalize_embeddings=True).astype('float32')
        # Ensure query_embedding has correct shape for FAISS
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        # Search in FAISS with proper parameters
        k_search = min(k, self.index.ntotal)  # Ensure k doesn't exceed available vectors
        scores, indices = self.index.search(query_embedding, k_search)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                # Apply filters if provided
                if filters and not self._matches_filters(chunk, filters):
                    continue
                results.append(SearchResult(
                    chunk=chunk,
                    similarity_score=float(score),
                    rank=len(results) + 1
                ))
                if len(results) >= k:
                    break
        return results

    def _matches_filters(self, chunk: DocumentChunk, filters: Dict[str, Any]) -> bool:
        """Check if chunk matches the provided filters."""
        for key, value in filters.items():
            if key not in chunk.metadata:
                return False
            if chunk.metadata[key] != value:
                return False
        return True

    def save(self, filepath: str):
        """Save the vector store to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, f"{filepath}.faiss")

        # Save chunks and metadata
        with open(f"{filepath}.pkl", 'wb') as f:
            pickle.dump({
                'chunks': self.chunks,
                'metadata_store': self.metadata_store,
                'dimension': self.dimension
            }, f)

    def load(self, filepath: str):
        """Load the vector store from disk."""
        if os.path.exists(f"{filepath}.faiss") and os.path.exists(f"{filepath}.pkl"):
            # Load FAISS index
            self.index = faiss.read_index(f"{filepath}.faiss")

            # Load chunks and metadata
            with open(f"{filepath}.pkl", 'rb') as f:
                data = pickle.load(f)
                self.chunks = data['chunks']
                self.metadata_store = data['metadata_store']
                self.dimension = data['dimension']

class ProjectRAG:
    """Main RAG system for project analysis."""

    def __init__(self, storage_dir: str = "./rag_storage"):
        self.storage_dir = storage_dir
        self.processor = ProjectFileProcessor()
        self.vector_stores: Dict[str, VectorStore] = {}  # project_id -> VectorStore
        os.makedirs(storage_dir, exist_ok=True)

    def index_project(self, user_id: str, project_id: str, files_content: Dict[str, str]):
        """Index a project's files for RAG search."""
        # Process files into chunks
        chunks = self.processor.process_files(files_content, user_id, project_id)

        # Create or load vector store for this project
        store_key = f"{user_id}_{project_id}"
        vector_store = VectorStore()

        # Load existing index if available
        store_path = os.path.join(self.storage_dir, store_key)
        if os.path.exists(f"{store_path}.faiss"):
            vector_store.load(store_path)

        # Add new chunks
        vector_store.add_chunks(chunks)

        # Save updated index
        vector_store.save(store_path)

        # Cache in memory
        self.vector_stores[store_key] = vector_store

        return len(chunks)

    def search_project(self, user_id: str, project_id: str, query: str,
                      k: int = 5, file_types: Optional[List[str]] = None) -> List[SearchResult]:
        """Search within a specific project."""
        store_key = f"{user_id}_{project_id}"

        # Load vector store if not in memory
        if store_key not in self.vector_stores:
            vector_store = VectorStore()
            store_path = os.path.join(self.storage_dir, store_key)
            if os.path.exists(f"{store_path}.faiss"):
                vector_store.load(store_path)
                self.vector_stores[store_key] = vector_store
            else:
                return []

        vector_store = self.vector_stores[store_key]

        # Apply filters if specified
        filters = {}
        if file_types is not None:
            filters['type'] = file_types

        return vector_store.search(query, k, filters)

    def get_relevant_context(self, user_id: str, project_id: str, query: str,
                           max_chunks: int = 3) -> str:
        """Get relevant context for answering a question about the project."""
        results = self.search_project(user_id, project_id, query, k=max_chunks)

        if not results:
            return ""

        context_parts = []
        for result in results:
            chunk = result.chunk
            context_part = f"""
File: {chunk.metadata['filename']}
Type: {chunk.metadata.get('type', 'unknown')}
Relevance Score: {result.similarity_score:.3f}

Content:
{chunk.content[:1000]}...
---
"""
            context_parts.append(context_part)

        return "\n".join(context_parts)

    def generate_project_summary(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Generate a summary of the indexed project."""
        store_key = f"{user_id}_{project_id}"

        if store_key not in self.vector_stores:
            return {"error": "Project not indexed"}

        vector_store = self.vector_stores[store_key]
        chunks = vector_store.chunks

        # Analyze project structure
        file_types = {}
        files = set()
        total_lines = 0

        for chunk in chunks:
            filename = chunk.metadata['filename']
            file_type = chunk.metadata.get('type', 'unknown')

            files.add(filename)
            file_types[file_type] = file_types.get(file_type, 0) + 1
            total_lines += chunk.content.count('\n') + 1

        return {
            "total_files": len(files),
            "total_chunks": len(chunks),
            "total_lines": total_lines,
            "file_types": file_types,
            "files": list(files),
            "indexed_at": datetime.now().isoformat()
        }

    def clear_project(self, user_id: str, project_id: str):
        """Clear the indexed data for a project."""
        store_key = f"{user_id}_{project_id}"

        # Remove from memory
        if store_key in self.vector_stores:
            del self.vector_stores[store_key]

        # Remove from disk
        store_path = os.path.join(self.storage_dir, store_key)
        for ext in ['.faiss', '.pkl']:
            filepath = f"{store_path}{ext}"
            if os.path.exists(filepath):
                os.remove(filepath)

    # Simplified interface methods for the app
    def index_project_files(self, files_content: Dict[str, str], user_id: str = "default", project_id: str = "current"):
        """Simplified method to index project files (wrapper for index_project)."""
        return self.index_project(user_id, project_id, files_content)

    def search_similar_code(self, query: str, top_k: int = 5, user_id: str = "default", project_id: str = "current"):
        """Simplified method to search for similar code (wrapper for search_project)."""
        results = self.search_project(user_id, project_id, query, k=top_k)

        # Convert to the format expected by the app
        formatted_results = []
        for result in results:
            formatted_results.append({
                'file': result.chunk.metadata['filename'],
                'content': result.chunk.content,
                'score': result.similarity_score,
                'type': result.chunk.metadata.get('type', 'unknown')
            })

        return formatted_results 