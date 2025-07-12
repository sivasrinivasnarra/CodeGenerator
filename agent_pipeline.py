#!/usr/bin/env python3
"""Simple command-line interface for RAG powered project flows.

This utility lets you run the main workflows without the Streamlit UI:

- ``generator`` – create a full project from requirement documents or a text prompt.
- ``analyzer`` – summarise an existing project for onboarding.
- ``coder`` – generate new code for an existing project.
"""

import argparse
import json
import os
import zipfile
from typing import Dict

from rag_system import ProjectRAG
from project_orchestrator import create_project_orchestrator, GenerationOptions
from model_adapter import ModelClient


def load_files(path: str) -> Dict[str, str]:
    """Load text files from a directory or zip archive."""
    files: Dict[str, str] = {}
    if os.path.isdir(path):
        for root, _, filenames in os.walk(path):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        rel = os.path.relpath(fpath, path)
                        files[rel] = f.read()
                except Exception:
                    continue
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                try:
                    with zf.open(name) as f:
                        files[name] = f.read().decode("utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            files[os.path.basename(path)] = f.read()
    return files


def run_generator(docs: str | None, prompt: str | None, project: str) -> None:
    orchestrator = create_project_orchestrator()
    options = GenerationOptions()
    if docs:
        documents = load_files(docs)
        result = orchestrator.generate_project_from_documents(documents, project, options)
    else:
        result = orchestrator.generate_project_from_prompt(prompt or "", project, options)
    archive = orchestrator.export_project_as_zip(result)
    out = f"{project or 'generated_project'}.zip"
    with open(out, "wb") as f:
        f.write(archive)
    print(f"\n✅ Project archive saved to {out}")
    print(result.summary)


def run_analyzer(project_path: str) -> None:
    files = load_files(project_path)
    rag = ProjectRAG()
    rag.index_project_files(files)
    summary = rag.generate_project_summary("default", "current")
    prompt = (
        "You are a senior developer. Provide a concise onboarding document for "
        "the following project summary:\n" + json.dumps(summary, indent=2)
    )
    model = ModelClient()
    analysis = model.generate_response(prompt)
    print("\n=== Project Analysis ===\n")
    print(analysis)


def run_coder(project_path: str, prompt: str) -> None:
    files = load_files(project_path)
    rag = ProjectRAG()
    rag.index_project_files(files)
    context = rag.get_relevant_context("default", "current", prompt, max_chunks=3)
    context_text = "\n\n".join(c.chunk.content for c in context)
    full_prompt = (
        f"Existing project context:\n{context_text}\n\nGenerate code for: {prompt}"
    )
    model = ModelClient()
    response = model.generate_response(full_prompt)
    print("\n=== Generated Code ===\n")
    print(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG project flows")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generator", help="Generate a new project")
    gen.add_argument("--docs", help="Path to requirements docs or zip")
    gen.add_argument("--prompt", help="Text prompt for the project")
    gen.add_argument("--project", default="generated_project", help="Output project name")

    ana = sub.add_parser("analyzer", help="Analyse an existing project")
    ana.add_argument("project", help="Path to project directory or zip")

    cod = sub.add_parser("coder", help="Generate code for an existing project")
    cod.add_argument("project", help="Path to project directory or zip")
    cod.add_argument("prompt", help="Feature description")

    args = parser.parse_args()

    if args.command == "generator":
        run_generator(args.docs, args.prompt, args.project)
    elif args.command == "analyzer":
        run_analyzer(args.project)
    elif args.command == "coder":
        run_coder(args.project, args.prompt)


if __name__ == "__main__":
    main()
