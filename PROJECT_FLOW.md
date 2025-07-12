# RAG-Driven Project Flow

This document outlines how to use the repository's tools to handle different project scenarios with Retrieval Augmented Generation (RAG) and specialized AI agents.

## 1. Generate a New Project
1. **Prepare Requirement Documents** – gather specs or write a prompt.
2. **Index with RAG** – upload the docs so the `ProjectRAG` system can create semantic embeddings.
3. **Run the Project Generator** – choose the `project generator` agent. It will read the RAG context and produce full source code, documentation and setup instructions.
4. **Download the Result** – the `ProjectOrchestrator` can export everything as a ZIP archive.

## 2. Analyse an Existing Project
1. **Upload Project Files or a Repository URL** – the files are indexed with RAG for contextual search.
2. **Select the `project analyzer` Agent** – it uses the indexed context to create onboarding documents describing architecture, technologies and setup steps.
3. **Share the Generated Report** – new team members can read the summary to understand the project quickly.

## 3. Extend an Existing Project
1. **Upload the Current Code Base** – index it with `ProjectRAG`.
2. **Select the `code assistant` Agent** – provide a prompt describing the new feature or modification.
3. **Receive Updated Source Code** – the agent generates new or modified files following the original project style.

These flows are also available via the Streamlit interface in `app_final.py` or through the CLI utility described below.
