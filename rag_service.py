from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from loguru import logger
import chromadb
from langchain_community.llms import Ollama
from syft_event.types import Request

from syft_rpc_client import SyftRPCClient
from syft_core import Client


# ----------------- Request/Response Models -----------------

class RAGQueryRequest(BaseModel):
    """Request to query the RAG system."""
    prompt: str = Field(description="The query text to process")
    model: str = Field(description="Name of the Ollama model to use")
    n_results: int = Field(default=4, description="Number of documents to retrieve")
    temperature: float = Field(default=0.1, description="Model temperature")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum tokens to generate")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), 
                         description="Timestamp of the request")


class RAGQueryResponse(BaseModel):
    """Response from the RAG system."""
    answer: str = Field(description="Generated answer text")
    sources: List[Dict[str, Any]] = Field(description="Source documents used")
    error: Optional[str] = Field(default=None, description="Error message, if any")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), 
                         description="Timestamp of the response")


class ModelListRequest(BaseModel):
    """Request to list available models."""
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                        description="Timestamp of the request")


class ModelListResponse(BaseModel):
    """Response containing available models."""
    models: List[str] = Field(description="List of available model names")
    error: Optional[str] = Field(default=None, description="Error message, if any")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                        description="Timestamp of the response")


# ----------------- RAG Service Implementation -----------------

class RAGService(SyftRPCClient):
    """Service for handling RAG queries using Ollama and ChromaDB."""
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 ollama_url: str = "http://localhost:11434",
                 rag_dir: str = "rag_databases"):
        """Initialize the RAG service.
        
        Args:
            config_path: Optional path to a custom config.json file
            ollama_url: URL of the local Ollama instance
            rag_dir: Directory containing RAG databases
        """
        # Initialize the client first to get the email
        self.client = Client.load(config_path)
        # user_email = self.client.email.split('@')[0]  # Get username part of email
        
        super().__init__(
            config_path=config_path,
            app_name="rag_service",  # Make app name unique per user
            endpoint="/query",
            request_model=RAGQueryRequest,
            response_model=RAGQueryResponse
        )
        
        self.ollama_url = ollama_url
        self.rag_dir = Path(rag_dir)
        
        # Load RAG database
        self.collection = None
        self.metadata = None
        self._load_rag_database()
    
    def _create_server(self):
        """Create and return the SyftEvents server."""
        box = super()._create_server()
        
        # Register model list endpoint
        @box.on_request("/models")
        def model_list_handler(request_data: dict, ctx: Request) -> dict:
            logger.info(f"🔔 RECEIVED: Model list request from {ctx.sender if hasattr(ctx, 'sender') else 'unknown'}")
            logger.info(f"Request data: {request_data}")
            request = ModelListRequest(**request_data)
            response = self._handle_model_list_request(request, ctx)
            return response.model_dump()
            
        return box
    
    def _load_rag_database(self):
        """Load the first available RAG database."""
        if not self.rag_dir.exists():
            logger.error(f"RAG database directory '{self.rag_dir}' not found")
            return
        
        # Find first valid database
        for db_dir in self.rag_dir.iterdir():
            if db_dir.is_dir() and (db_dir / "metadata.json").exists():
                try:
                    # Load metadata
                    with open(db_dir / "metadata.json", "r") as f:
                        self.metadata = json.load(f)
                    
                    # Initialize ChromaDB client
                    chroma_client = chromadb.PersistentClient(path=str(db_dir))
                    
                    # Get collection
                    collection_name = self.metadata.get("collection_name", "documents")
                    self.collection = chroma_client.get_collection(name=collection_name)
                    
                    logger.info(f"Loaded RAG database from {db_dir}")
                    return
                    
                except Exception as e:
                    logger.error(f"Error loading database {db_dir}: {e}")
    
    def _handle_model_list_request(self, request: ModelListRequest, ctx: Request) -> ModelListResponse:
        """Handle request to list available models."""
        try:
            logger.info(f"Querying Ollama at {self.ollama_url} for available models")
            
            # Query Ollama for available models
            client = httpx.Client(timeout=10.0)
            response = client.get(f"{self.ollama_url}/api/tags")
            
            if response.status_code == 200:
                models = [model["name"] for model in response.json().get("models", [])]
                logger.info(f"Found {len(models)} available models")
                return ModelListResponse(
                    models=models,
                    ts=datetime.now(timezone.utc)
                )
            else:
                error_msg = f"Failed to get models: HTTP {response.status_code}"
                logger.error(error_msg)
                return ModelListResponse(
                    models=[],
                    error=error_msg,
                    ts=datetime.now(timezone.utc)
                )
                
        except Exception as e:
            error_msg = f"Error getting models: {str(e)}"
            logger.error(error_msg)
            return ModelListResponse(
                models=[],
                error=error_msg,
                ts=datetime.now(timezone.utc)
            )
    
    def _handle_request(self, request: RAGQueryRequest, ctx: Request, box) -> RAGQueryResponse:
        """Handle an incoming RAG query request."""
        logger.info(f"🔔 RECEIVED: RAG query request for model '{request.model}'")
        
        try:
            if not self.collection:
                return RAGQueryResponse(
                    answer="",
                    sources=[],
                    error="No RAG database loaded",
                    ts=datetime.now(timezone.utc)
                )
            
            # Query the collection
            results = self.collection.query(
                query_texts=[request.prompt],
                n_results=request.n_results
            )
            
            # Extract results
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results else None
            ids = results["ids"][0]
            
            # Create context from documents
            context = "\n\n".join([f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents)])
            
            # Create prompt
            prompt = f"""Answer the following question based only on the provided context:

Question: {request.prompt}

Context:
{context}

Answer:"""
            
            # Initialize Ollama
            llm = Ollama(
                base_url=self.ollama_url,
                model=request.model,
                temperature=request.temperature
            )
            
            # Generate response
            answer = llm(prompt, max_tokens=request.max_tokens)
            
            # Prepare source information
            sources = []
            for i, (doc, meta, doc_id) in enumerate(zip(documents, metadatas, ids)):
                source = {
                    "content": doc,
                    "metadata": meta,
                    "id": doc_id
                }
                
                if distances:
                    source["relevance"] = 1 - (distances[i] / max(distances)) if max(distances) > 0 else 1
                    
                sources.append(source)
            
            return RAGQueryResponse(
                answer=answer,
                sources=sources,
                ts=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error processing RAG query: {e}")
            return RAGQueryResponse(
                answer="",
                sources=[],
                error=str(e),
                ts=datetime.now(timezone.utc)
            )
    
    def get_models(self, to_email: str) -> Optional[List[str]]:
        """Get list of available models from a remote datasite.
        
        Args:
            to_email: Email of the datasite to query
            
        Returns:
            List of model names if successful, None otherwise
        """
        logger.info(f"Requesting available models from {to_email}")
        
        # Verify the datasite is valid
        if not self._valid_datasite(to_email):
            logger.error(f"Invalid datasite: {to_email}")
            logger.info("Available datasites:")
            for d in self.list_datasites():
                logger.info(f"  - {d}")
            return None
        
        # Verify the server is available
        available_servers = self.list_available_servers()
        logger.info(f"Available servers: {available_servers}")
        if to_email not in available_servers:
            logger.error(f"Server not available for {to_email}")
            return None
        
        try:
            # Create request with current timestamp
            request = ModelListRequest(ts=datetime.now(timezone.utc))
            logger.info(f"Sending request: {request.model_dump()}")
            
            response = self.send_request(
                to_email=to_email,
                request_data=request,
                endpoint="/models",
                response_model=ModelListResponse
            )
            
            if response:
                if response.error:
                    logger.error(f"Error from {to_email}: {response.error}")
                    return None
                logger.info(f"Received {len(response.models)} models from {to_email}")
                return response.models
            else:
                logger.error(f"No response received from {to_email}")
                return None
                
        except Exception as e:
            logger.error(f"Error requesting models from {to_email}: {str(e)}")
            return None
    
    def query(self, 
              to_email: str,
              prompt: str,
              model: str,
              n_results: int = 4,
              temperature: float = 0.1,
              max_tokens: Optional[int] = 1000) -> Optional[RAGQueryResponse]:
        """Send a RAG query to a remote datasite.
        
        Args:
            to_email: Email of the datasite to query
            prompt: The query text
            model: Name of the model to use
            n_results: Number of documents to retrieve
            temperature: Model temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            RAGQueryResponse if successful, None otherwise
        """
        request = RAGQueryRequest(
            prompt=prompt,
            model=model,
            n_results=n_results,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return self.send_request(to_email, request)


# ----------------- Client API Functions -----------------

def client(config_path: Optional[str] = None,
           ollama_url: str = "http://localhost:11434",
           rag_dir: str = "rag_databases") -> RAGService:
    """Create and return a new RAG service client.
    
    Args:
        config_path: Optional path to a custom config.json file
        ollama_url: URL of the local Ollama instance
        rag_dir: Directory containing RAG databases
        
    Returns:
        A RAGService instance
    """
    return RAGService(config_path, ollama_url, rag_dir) 