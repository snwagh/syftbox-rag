# SyftBox RAG

A RAG (Retrieval-Augmented Generation) application that combines document processing with AI capabilities. This project uses Streamlit for the user interface and various AI/ML libraries for document processing and question answering.

## Features

- Connecting to your OneDrive account via access tokens
- Document download, processing and indexing, and deletion
- UI or without UI
- Question answering capabilities
- Support for multiple document formats (PDF, DOCX, etc.)

## Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- [Ollama](https://ollama.ai/) - Local LLM server

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd syftbox-rag
```

2. Set up the virtual environment and install dependencies:
```bash
# Remove existing virtual environment (if any)
rm -rf .venv/

# Create new virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt
```

## Usage

### With Web Interface

To run the application with the Streamlit web interface:

```bash
uv run streamlit run app1.py
```

This will start a local web server and open the application in your default browser.

### Without Web Interface

To run the application in command-line mode:

```bash
uv run main.py
```

## Project Structure

- `app1.py`: Streamlit web application for creating
- `app2.py`: Additional application module for using the RAG
- `main.py`: Command-line interface (creating and using RAG)
- `requirements.txt`: Project dependencies
- `questions.txt`: Sample questions for testing
