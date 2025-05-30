#!/usr/bin/env python3
"""
RAG Document Search Application Launcher

This script starts the RAG document search system.
"""

import uvicorn
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.config import Config
from backend.main import app

def main():
    """Launch the RAG document search application"""
    print("🚀 Starting RAG Document Search System...")
    print(f"📂 Vector database: {Config.VECTOR_DB_PATH}")
    print(f"🤖 Embedding model: {Config.EMBEDDING_MODEL}")
    print(f"🌐 Server will be available at: http://{Config.HOST}:{Config.PORT}")
    print("\n" + "="*50)
    
    # Ensure directories exist
    Config.ensure_directories()
    
    # Start the server
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info",
        reload=False  # Set to True for development
    )

if __name__ == "__main__":
    main() 