#!/usr/bin/env python3
import os
import argparse
import json
import sys
from pathlib import Path
from typing import List
from dotenv import load_dotenv

from rag_system import RAGSystem, DataSourceConnector, LocalFileConnector

# Load environment variables
load_dotenv()

def setup_argparse():
    """Set up command-line argument parsing."""
    parser = argparse.ArgumentParser(description="RAG System CLI")
    
    # Source configuration
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--local', type=str, help='Path to local files or directory')
    source_group.add_argument('--onedrive', type=str, help='Path in OneDrive')
    source_group.add_argument('--gdrive', type=str, help='Google Drive folder ID')
    
    # RAG configuration
    parser.add_argument('--vector-store', type=str, default='./rag_db', help='Path to store vector database')
    parser.add_argument('--embedding-model', type=str, default='BAAI/bge-small-en-v1.5', help='Embedding model to use')
    parser.add_argument('--chunk-size', type=int, default=512, help='Chunk size for splitting documents')
    parser.add_argument('--force-reindex', action='store_true', help='Force reindexing of documents')
    
    # Ollama configuration
    parser.add_argument('--ollama-model', type=str, default='llama3.2:latest', help='Ollama model to use')
    parser.add_argument('--ollama-url', type=str, default='http://localhost:11434', help='Ollama server URL')
    
    # Query mode
    parser.add_argument('--query', type=str, help='Query the RAG system')
    parser.add_argument('--top-k', type=int, default=3, help='Number of top results to retrieve')
    
    # Interactive mode
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    
    return parser

def validate_args(args):
    """Validate command-line arguments and environment variables."""
    if args.onedrive:
        if not all([os.getenv('MS_CLIENT_ID'), os.getenv('MS_CLIENT_SECRET')]):
            print("Error: OneDrive connection requires MS_CLIENT_ID and MS_CLIENT_SECRET environment variables")
            return False
    
    if args.gdrive and not os.getenv('GDRIVE_CREDENTIALS_PATH'):
        print("Error: Google Drive connection requires GDRIVE_CREDENTIALS_PATH environment variable")
        return False
    
    return True

def load_documents(args, rag_system):
    """Load documents based on the selected source."""
    if args.local:
        connector = rag_system.local_connector
        return connector.load_documents(args.local)
    
    elif args.onedrive:
        connector = rag_system.connect_to_onedrive()
        return connector.load_documents(args.onedrive)
    
    elif args.gdrive:
        connector = rag_system.connect_to_google_drive()
        return connector.load_documents(args.gdrive)
    
    return []

def interactive_mode(rag_system):
    """Run in interactive mode."""
    print("=== RAG System Interactive Mode ===")
    print("Type 'exit' or 'quit' to exit")
    
    while True:
        query = input("\nEnter your query: ")
        if query.lower() in ['exit', 'quit']:
            break
        
        try:
            answer = rag_system.query(query)
            print("\nAnswer:")
            print(answer)
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    """Main entry point for the RAG system CLI."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    if not validate_args(args):
        sys.exit(1)
    
    # Initialize the RAG system
    rag_system = RAGSystem(
        vector_store_path=args.vector_store,
        embedding_model=args.embedding_model,
        chunk_size=args.chunk_size,
        ollama_model=args.ollama_model,
        ollama_url=args.ollama_url
    )
    
    # Load and index documents if not in query-only mode
    if not args.query or args.force_reindex:
        print("Loading documents...")
        documents = load_documents(args, rag_system)
        
        if not documents:
            print("No documents loaded. Exiting.")
            sys.exit(1)
        
        num_source_files = rag_system.local_connector.num_source_files
        print(f"Loaded {len(documents)} chunks from {num_source_files} source files")
        
        print("Indexing documents...")
        num_chunks = rag_system.index_documents(documents, force_reindex=args.force_reindex)
        print("Indexing complete")
    
    # Handle query or interactive mode
    if args.query:
        answer = rag_system.query(args.query, similarity_top_k=args.top_k)
        print(answer)
    
    elif args.interactive:
        interactive_mode(rag_system)

if __name__ == "__main__":
    main()
