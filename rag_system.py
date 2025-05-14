import os
import json
import sys
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Data Source Connectors
from llama_index.readers.file import PDFReader, DocxReader
from llama_index.readers.web import SimpleWebPageReader
from llama_index.core import Document

# LlamaIndex Core Components
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import VectorIndexRetriever

# Ollama
from llama_index.llms.ollama import Ollama

# Optional dependencies for specific connectors
try:
    from onedrivesdk import get_default_client, AuthProvider
except ImportError:
    pass

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    pass

class DataSourceConnector:
    """Base class for data source connectors."""
    
    def load_documents(self, source_path: str) -> List[Document]:
        """Load documents from the source."""
        raise NotImplementedError
    
class LocalFileConnector(DataSourceConnector):
    """Connector for local files."""
    
    def __init__(self):
        self.pdf_reader = PDFReader()
        self.docx_reader = DocxReader()
        self.num_source_files = 0
    
    def load_documents(self, source_path: str) -> List[Document]:
        """Load documents from local files."""
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {source_path}")
            
        documents = []
        self.num_source_files = 0
        
        if path.is_file():
            documents.extend(self._load_file(path))
            self.num_source_files = 1
        elif path.is_dir():
            for file_path in path.glob("**/*"):
                if file_path.is_file():
                    documents.extend(self._load_file(file_path))
                    self.num_source_files += 1
                    
        return documents
    
    def _load_file(self, file_path: Path) -> List[Document]:
        """Load a single file based on its extension."""
        documents = []
        if file_path.suffix.lower() == ".pdf":
            documents = self.pdf_reader.load_data(str(file_path))
        elif file_path.suffix.lower() == ".docx":
            documents = self.docx_reader.load_data(str(file_path))
        
        # Add source metadata to each document
        for doc in documents:
            doc.metadata = {"source": str(file_path)}
        
        return documents

class OneDriveConnector(DataSourceConnector):
    """Connector for OneDrive."""
    
    def __init__(self):
        """Initialize OneDrive connector."""
        self.client_id = os.getenv('MS_CLIENT_ID')
        self.client_secret = os.getenv('MS_CLIENT_SECRET')
        self.redirect_uri = "http://localhost:8000/callback"
        
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Missing required environment variables for OneDrive. Please set MS_CLIENT_ID and MS_CLIENT_SECRET in .env file")
            
        self.local_connector = LocalFileConnector()
        
    def load_documents(self, source_path: str, download_dir: str = "./temp_downloads") -> List[Document]:
        """
        Load documents from OneDrive.
        source_path: The path in OneDrive.
        download_dir: Directory to temporarily download files to.
        """
        try:
            # Ensure download directory exists
            os.makedirs(download_dir, exist_ok=True)
            
            # Create OneDrive client
            auth_provider = AuthProvider(
                http_provider=None,
                client_id=self.client_id,
                scopes=['wl.signin', 'wl.offline_access', 'onedrive.readwrite']
            )
            client = get_default_client(client_id=self.client_id, auth_provider=auth_provider)
            
            # Get authentication URL
            auth_url = client.auth_provider.get_auth_url(self.redirect_uri)
            print(f"Please go to this URL and authorize the app: {auth_url}")
            
            # Get the authentication code from user
            auth_code = input("Enter the authentication code: ")
            client.auth_provider.authenticate(auth_code, self.redirect_uri, self.client_secret)
            
            # Get items from the specified path
            items = client.item(path=source_path).children.get()
            
            documents = []
            
            # Download each file and process it
            for item in items:
                if not item.folder:  # It's a file
                    download_path = os.path.join(download_dir, item.name)
                    with open(download_path, 'wb') as file:
                        client.item(id=item.id).content.download(file)
                    
                    # Use the local connector to process the downloaded file
                    documents.extend(self.local_connector.load_documents(download_path))
                    
                    # Clean up the downloaded file
                    os.remove(download_path)
            
            return documents
            
        except Exception as e:
            print(f"Error connecting to OneDrive: {str(e)}")
            return []

class GoogleDriveConnector(DataSourceConnector):
    """Connector for Google Drive."""
    
    def __init__(self):
        """Initialize Google Drive connector."""
        self.credentials_path = os.getenv('GDRIVE_CREDENTIALS_PATH')
        
        if not self.credentials_path:
            raise ValueError("Missing required environment variable for Google Drive. Please set GDRIVE_CREDENTIALS_PATH in .env file")
            
        self.local_connector = LocalFileConnector()
        
    def load_documents(self, folder_id: str, download_dir: str = "./temp_downloads") -> List[Document]:
        """
        Load documents from Google Drive.
        folder_id: The ID of the Google Drive folder.
        download_dir: Directory to temporarily download files to.
        """
        try:
            # Ensure download directory exists
            os.makedirs(download_dir, exist_ok=True)
            
            # Load credentials
            creds = Credentials.from_authorized_user_info(
                info=json.load(open(self.credentials_path))
            )
            
            # Build the Drive API client
            drive_service = build('drive', 'v3', credentials=creds)
            
            # List files in the folder
            results = drive_service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            documents = []
            
            # Download each file and process it
            for item in items:
                if 'folder' not in item.get('mimeType', ''):  # Not a folder
                    download_path = os.path.join(download_dir, item['name'])
                    
                    # Download the file
                    request = drive_service.files().get_media(fileId=item['id'])
                    with open(download_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                    
                    # Use the local connector to process the downloaded file
                    documents.extend(self.local_connector.load_documents(download_path))
                    
                    # Clean up the downloaded file
                    os.remove(download_path)
            
            return documents
            
        except Exception as e:
            print(f"Error connecting to Google Drive: {str(e)}")
            return []

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
        self.local_connector = LocalFileConnector()
    
    def connect_to_onedrive(self):
        """Create a OneDrive connector."""
        return OneDriveConnector()
    
    def connect_to_google_drive(self):
        """Create a Google Drive connector."""
        return GoogleDriveConnector()
    
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