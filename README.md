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

## Setting up Azure Credentials
- Log into your azure account
- Go to App Registrations and register a new app
- Create the following API permissions for that app
<img width="1690" alt="Screenshot 2025-04-24 at 3 25 39 PM" src="https://github.com/user-attachments/assets/c69862e6-b899-4e63-a0b5-cc1622c7eb41" />

- Copy the Client ID from the overview page (for the `.env` file)
<img width="1123" alt="Screenshot 2025-04-24 at 3 39 54 PM" src="https://github.com/user-attachments/assets/54b3e80f-c394-4897-990c-8ee3f69bbf5b" />

- Create a client secret and copy the secret (for the `.env` file)
<img width="1119" alt="Screenshot 2025-04-24 at 3 40 23 PM" src="https://github.com/user-attachments/assets/e3e78f1a-bce5-4529-a377-23c502b83607" />


Create a .env file 
```
echo "CLIENT_ID=beb...
CLIENT_SECRET=YXW....
OLLAMA_BASE_URL=http://localhost:11434" > .env
```



## Usage

Make sure OLLAMA server is running and has at least one model. 

### With Jupyter Lab

To run the application with the Streamlit web interface:

```bash
uv run jupyter lab
```

And follow the `RAG.ipynb` notebook

### Without Web Interface

To run the application in command-line mode:

```bash
uv run main.py
```

## Project Structure

- `main.py`: Command-line interface for creating and using RAG
- `rag_builder/`: Core RAG implementation modules
- `RAG.ipynb`: Jupyter notebook with interactive examples and tutorials
- `requirements.txt`: Project dependencies
- `questions.txt`: Sample questions for testing
- `.env`: Environment variables for configuration

## Configuration

The application requires the following environment variables in `.env`:

- `CLIENT_ID`: Azure AD application client ID
- `CLIENT_SECRET`: Azure AD application client secret
- `OLLAMA_BASE_URL`: URL for the Ollama server (Keep it as http://localhost:11434)

## Development

To contribute to the project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Ollama](https://ollama.ai/) for providing the local LLM server
- [Streamlit](https://streamlit.io/) for the web interface
- [uv](https://github.com/astral-sh/uv) for Python package management
