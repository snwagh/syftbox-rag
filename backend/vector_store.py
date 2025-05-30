import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Set
import os
import json
from .config import Config

class VectorStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.VECTOR_DB_PATH
        os.makedirs(self.db_path, exist_ok=True)
        
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False
            )
        )
        
        # Get or create collection for documents
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        # Get or create collection for configuration (watched folders/files)
        self.config_collection = self.client.get_or_create_collection(
            name="system_config",
            metadata={"description": "System configuration including watched paths"}
        )
    
    def add_documents(self, chunks: List[Dict]):
        """Add document chunks to vector store"""
        if not chunks:
            return
        
        # Prepare data for Chroma
        embeddings = [chunk['embedding'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        ids = [chunk['id'] for chunk in chunks]
        
        # Add to collection
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def search(self, query_embedding: List[float], n_results: int = None, 
              include: List[str] = None):
        """Search for similar documents"""
        if n_results is None:
            n_results = Config.DEFAULT_SEARCH_LIMIT
        
        # Limit to max search limit
        n_results = min(n_results, Config.MAX_SEARCH_LIMIT)
        
        if include is None:
            include = ["documents", "metadatas", "distances"]
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=include
        )
        return results
    
    def delete_by_file(self, file_path: str):
        """Delete all chunks from a specific file"""
        # Get all documents with this filepath
        results = self.collection.get(
            where={"filepath": file_path},
            include=["documents"]
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
    
    def delete_by_file_prefix(self, folder_path: str):
        """Delete all chunks from files under a specific folder path"""
        # Get all documents in the collection to filter by prefix
        all_results = self.collection.get()
        
        if not all_results['ids']:
            return
        
        # Find IDs of documents that have filepaths starting with the folder path
        ids_to_delete = []
        for i, metadata in enumerate(all_results['metadatas']):
            if metadata and 'filepath' in metadata:
                if metadata['filepath'].startswith(folder_path):
                    ids_to_delete.append(all_results['ids'][i])
        
        # Delete matching documents
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
    
    def count(self) -> int:
        """Get total number of documents"""
        return self.collection.count()
    
    def file_exists(self, file_hash: str) -> bool:
        """Check if file already exists in database"""
        results = self.collection.get(
            where={"file_hash": file_hash},
            limit=1
        )
        return len(results['ids']) > 0
    
    # Configuration persistence methods
    def save_watched_folders(self, watched_folders: Set[str]):
        """Save watched folders configuration to persistent storage"""
        config_data = {
            "type": "watched_folders",
            "paths": list(watched_folders)
        }
        
        # Delete existing watched folders config
        existing = self.config_collection.get(
            where={"type": "watched_folders"}
        )
        if existing['ids']:
            self.config_collection.delete(ids=existing['ids'])
        
        # Add new config
        self.config_collection.add(
            ids=["watched_folders_config"],
            documents=[json.dumps(config_data)],
            metadatas=[{"type": "watched_folders", "version": "1.0"}]
        )
    
    def save_watched_files(self, watched_files: Set[str]):
        """Save watched files configuration to persistent storage"""
        config_data = {
            "type": "watched_files",
            "paths": list(watched_files)
        }
        
        # Delete existing watched files config
        existing = self.config_collection.get(
            where={"type": "watched_files"}
        )
        if existing['ids']:
            self.config_collection.delete(ids=existing['ids'])
        
        # Add new config
        self.config_collection.add(
            ids=["watched_files_config"],
            documents=[json.dumps(config_data)],
            metadatas=[{"type": "watched_files", "version": "1.0"}]
        )
    
    def load_watched_folders(self) -> Set[str]:
        """Load watched folders configuration from persistent storage"""
        try:
            results = self.config_collection.get(
                where={"type": "watched_folders"}
            )
            if results['documents']:
                config_data = json.loads(results['documents'][0])
                return set(config_data.get("paths", []))
        except Exception as e:
            print(f"Error loading watched folders config: {e}")
        return set()
    
    def load_watched_files(self) -> Set[str]:
        """Load watched files configuration from persistent storage"""
        try:
            results = self.config_collection.get(
                where={"type": "watched_files"}
            )
            if results['documents']:
                config_data = json.loads(results['documents'][0])
                return set(config_data.get("paths", []))
        except Exception as e:
            print(f"Error loading watched files config: {e}")
        return set()
    
    def save_indexing_status(self, status: Dict[str, Any]):
        """Save indexing status to persistent storage with optimized upsert"""
        try:
            # Try to update existing status first
            existing = self.config_collection.get(
                where={"type": "indexing_status"},
                limit=1
            )
            
            if existing['ids']:
                # Update existing document
                self.config_collection.update(
                    ids=existing['ids'],
                    documents=[json.dumps(status)],
                    metadatas=[{"type": "indexing_status", "version": "1.0"}]
                )
            else:
                # Add new document if none exists
                self.config_collection.add(
                    ids=["indexing_status_config"],
                    documents=[json.dumps(status)],
                    metadatas=[{"type": "indexing_status", "version": "1.0"}]
                )
        except Exception as e:
            # Fallback to delete+add if update fails
            try:
                existing = self.config_collection.get(
                    where={"type": "indexing_status"}
                )
                if existing['ids']:
                    self.config_collection.delete(ids=existing['ids'])
                
                self.config_collection.add(
                    ids=["indexing_status_config"],
                    documents=[json.dumps(status)],
                    metadatas=[{"type": "indexing_status", "version": "1.0"}]
                )
            except Exception as fallback_error:
                print(f"Error saving indexing status: {fallback_error}")
                # Don't raise to avoid blocking other operations
    
    def load_indexing_status(self) -> Dict[str, Any]:
        """Load indexing status from persistent storage"""
        try:
            results = self.config_collection.get(
                where={"type": "indexing_status"}
            )
            if results['documents']:
                return json.loads(results['documents'][0])
        except Exception as e:
            print(f"Error loading indexing status: {e}")
        
        # Return default status if not found
        return {
            "isRunning": False,
            "progress": 0,
            "totalFiles": 0,
            "processedFiles": 0,
            "totalSizeMB": 0,
            "processedSizeMB": 0,
            "totalChunks": 0,
            "processedChunks": 0,
            "logs": []
        }