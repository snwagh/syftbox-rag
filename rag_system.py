import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LlamaIndex Core Components
from llama_index.core import VectorStoreIndex, Settings, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import VectorIndexRetriever

# Ollama
from llama_index.llms.ollama import Ollama

# Import connectors
from connectors import LocalConnector, OneDriveConnector

class RAGSystem:
    """Main RAG system that integrates data sources, indexing, and generation."""
    
    def __init__(
        self, 
        vector_store_path: str = "./chroma_db",
        embedding_model: str = "BAAI/bge-small-en-v1.5", 
        chunk_size: int = 512,
        ollama_model: str = "llama3.2:latest",
        ollama_url: str = "http://localhost:11434"
    ):
        """Initialize the RAG system."""
        # Setup embedding model
        self.embedding_model = HuggingFaceEmbedding(model_name=embedding_model)
        
        # Setup LLM
        self.llm = Ollama(model=ollama_model, url=ollama_url)
        
        # Configure settings
        Settings.llm = self.llm
        Settings.embed_model = self.embedding_model
        Settings.node_parser = SentenceSplitter(chunk_size=chunk_size)
        
        # Setup vector store
        self.vector_store_path = vector_store_path
        self.vector_store = None
        self.index = None
        
        # Initialize connectors
        self.local_connector = LocalConnector()
        self.onedrive_connector = OneDriveConnector()
    
    def index_documents(self, documents: List[Document], force_reindex: bool = False) -> int:
        """Index documents into the vector store.
        Returns the number of chunks created."""
        import chromadb
        
        # Check if we need to reindex
        if os.path.exists(self.vector_store_path) and not force_reindex:
            # Load existing index
            chroma_client = chromadb.PersistentClient(path=self.vector_store_path)
            chroma_collection = chroma_client.get_or_create_collection("documents")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store
            )
            # Get the actual count from ChromaDB after index is loaded
            collection_data = chroma_collection.get()
            num_chunks = len(collection_data['ids']) if collection_data and 'ids' in collection_data else 0
            print(f"Loaded existing index from {self.vector_store_path} with {num_chunks} chunks")
            return num_chunks
        else:
            # Create a new index
            if os.path.exists(self.vector_store_path):
                import shutil
                shutil.rmtree(self.vector_store_path)
                
            chroma_client = chromadb.PersistentClient(path=self.vector_store_path)
            chroma_collection = chroma_client.get_or_create_collection("documents")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            
            # Create the index
            self.index = VectorStoreIndex.from_documents(
                documents=documents,
                vector_store=vector_store
            )
            
            # Get the actual count from ChromaDB after index is created
            collection_data = chroma_collection.get()
            if not collection_data or 'ids' not in collection_data:
                print("Warning: No data found in ChromaDB collection")
                return 0
                
            num_chunks = len(collection_data['ids'])
            print("Created new index")
            
            return num_chunks
    
    def query(self, query_text: str, similarity_top_k: int = 3) -> str:
        """Query the RAG system with a question."""
        if not self.index:
            raise ValueError("No index available. Please index documents first.")
        
        # Create retriever
        retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=similarity_top_k
        )
        
        # Retrieve relevant nodes
        nodes = retriever.retrieve(query_text)
        
        # Format context from retrieved nodes
        context_str = "\n\n".join([node.node.text for node in nodes])
        
        # Get source document information
        source_docs = []
        for node in nodes:
            if hasattr(node.node, 'metadata') and node.node.metadata and 'source' in node.node.metadata:
                source = node.node.metadata['source']
                if source not in source_docs:
                    source_docs.append(source)
        
        # Create the prompt for the LLM
        prompt = f"""
        You are a helpful assistant that answers questions based on the given context.
        
        Context:
        {context_str}
        
        Question: {query_text}
        
        Please provide a comprehensive answer based on the context provided.
        If the context doesn't contain relevant information to answer the question,
        please indicate that you don't have enough information to provide an answer.
        """
        
        # Get response from Ollama
        response = self.llm.complete(prompt)
        
        # Format the final response with source documents
        final_response = response.text
        if source_docs:
            final_response += "\n\nSource Documents:\n"
            for i, source in enumerate(source_docs, 1):
                final_response += f"{i}. {source}\n"
        
        return final_response

# Example usage
def main():
    """Example usage of the RAG system."""
    
    # Initialize the RAG system
    rag_system = RAGSystem(
        vector_store_path="./rag_db",
        ollama_model="llama3.2:latest"  # or whichever model you have in Ollama
    )
    
    # Connect to a local file source and load documents
    connector = rag_system.local_connector
    documents = connector.load_documents("./documents")
    
    # Build the index
    num_chunks = rag_system.index_documents(documents)
    
    # Query the system
    query = "What is the main topic of the documents?"
    answer = rag_system.query(query)
    print(f"Query: {query}")
    print(f"Answer: {answer}")

if __name__ == "__main__":
    main()