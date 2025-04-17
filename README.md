# SyftBox RAG Project

This project demonstrates a RAG (Retrieval-Augmented Generation) implementation using SyftBox for secure data sharing and processing.

## Prerequisites

- [Just](https://github.com/casey/just) - A command runner
- [UV](https://github.com/astral-sh/uv) - Python package installer and resolver
- [Jupyter Lab](https://jupyter.org/) - For running the notebook
- [SyftBox](https://github.com/OpenMined/SyftBox) - For secure data sharing
- [Ollama](https://ollama.ai/) - For running local LLMs (must be running on the default port 11434)

## Setup

1. Clone this repository
2. Make sure you have all prerequisites installed
3. Start the Ollama server (if not already running)
4. The project uses `just` for command management. Run `just --list` to see all available commands

## Usage

To run the full demo:

1. Clean the environment:
   ```bash
   just c
   ```

2. Start the SyftBox server:
   ```bash
   just ss
   ```

3. Start Alice's client:
   ```bash
   just ca
   ```

4. Start Bob's client:
   ```bash
   just cb
   ```

5. Start Jupyter Lab and run the notebook:
   ```bash
   just jup
   ```

## Project Structure

- `RAG.ipynb` - Main notebook demonstrating the RAG implementation
- `rag_service.py` - RAG service implementation
- `syft_rpc_client.py` - Syft RPC client implementation
- `rag_databases/` - Directory containing RAG databases
- `pyproject.toml` - Project dependencies and configuration
- `justfile` - Command definitions for the project

## Notes

- The SyftBox server runs on `http://127.0.0.1:5001`
- Alice's client runs on port `8081`
- Bob's client runs on port `8082`
- Client sync folders are created at `~/Desktop/SyftBoxAlice` and `~/Desktop/SyftBoxBob` 