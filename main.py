import yaml
import argparse
from typing import List
from dotenv import load_dotenv
from rag_system import RAGSystem

# Load environment variables
load_dotenv()

def load_yaml_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_documents_from_config(config: dict, rag_system: RAGSystem) -> List:
    """Load documents based on the configuration."""
    all_documents = []
    
    # Process local files
    if 'data' in config and 'local' in config['data']:
        for path in config['data']['local']:
            documents = rag_system.local_connector.load_documents(path)
            all_documents.extend(documents)
            print(f"Loaded {len(documents)} documents from local path: {path}")
    
    # Process OneDrive files
    # if 'data' in config and 'onedrive' in config['data']:
    #     for path in config['data']['onedrive']:
    #         documents = rag_system.onedrive_connector.load_documents(path)
    #         all_documents.extend(documents)
    #         print(f"Loaded {len(documents)} documents from OneDrive path: {path}")
    
    return all_documents

def interactive_mode(rag_system: RAGSystem):
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
    """Main entry point for the RAG system."""
    parser = argparse.ArgumentParser(description="RAG System")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to YAML configuration file')
    parser.add_argument('--force-reindex', action='store_true', help='Force reindexing of documents')
    parser.add_argument('--query', type=str, help='Query the RAG system')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_yaml_config(args.config)
    
    # Get settings from config
    settings = config.get('settings', {})
    
    # Initialize the RAG system
    rag_system = RAGSystem(
        vector_store_path=settings.get('vector_store', './rag_db'),
        embedding_model=settings.get('embedding_model', 'BAAI/bge-small-en-v1.5'),
        chunk_size=settings.get('chunk_size', 512),
        ollama_model=settings.get('ollama_model', 'llama3.2:latest'),
        ollama_url=settings.get('ollama_url', 'http://localhost:11434')
    )
    
    # Load and index documents if not in query-only mode
    if not args.query or args.force_reindex:
        print("Loading documents...")
        documents = load_documents_from_config(config, rag_system)
        
        if not documents:
            print("No documents loaded. Exiting.")
            return
        
        print(f"Loaded {len(documents)} total documents")
        
        print("Indexing documents...")
        num_chunks = rag_system.index_documents(documents, force_reindex=args.force_reindex)
        print(f"Indexing complete. Created {num_chunks} chunks")
    
    # Handle query or interactive mode
    if args.query:
        answer = rag_system.query(args.query, similarity_top_k=settings.get('top_k', 3))
        print(answer)
    
    elif args.interactive:
        interactive_mode(rag_system)

if __name__ == "__main__":
    main() 