import os
from pathlib import Path

class Config:
    # Database settings
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    
    # Embedding model settings: https://huggingface.co/spaces/mteb/leaderboard
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
    # Document processing settings
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "50"))
    
    # Supported file formats
    SUPPORTED_FORMATS = {'.pdf', '.docx', '.txt', '.md', '.html', '.xlsx'}
    
    # Server settings
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "9000"))
    
    # File watching settings
    PROCESSING_DELAY = float(os.getenv("PROCESSING_DELAY", "1.0"))  # seconds
    
    # Search settings
    DEFAULT_SEARCH_LIMIT = int(os.getenv("DEFAULT_SEARCH_LIMIT", "20"))
    MAX_SEARCH_LIMIT = int(os.getenv("MAX_SEARCH_LIMIT", "100"))
    
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist"""
        Path(cls.VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True) 