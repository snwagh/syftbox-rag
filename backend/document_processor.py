## 2. Document Processor (document_processor.py)
from docling.document_converter import DocumentConverter
from typing import List, Dict
import hashlib
import os
from .config import Config

class DocumentProcessor:
    def __init__(self):
        self.converter = DocumentConverter()
        self.supported_formats = Config.SUPPORTED_FORMATS
    
    def is_supported(self, file_path: str) -> bool:
        """Check if file format is supported"""
        return os.path.splitext(file_path)[1].lower() in self.supported_formats
    
    def process_document(self, file_path: str) -> List[Dict]:
        """Process document and return chunks with metadata"""
        if not self.is_supported(file_path):
            return []
        
        try:
            # Convert document using docling
            result = self.converter.convert(file_path)
            
            # Extract text and structure
            chunks = self._chunk_document(result, file_path)
            return chunks
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return []
    
    def _chunk_document(self, doc_result, file_path: str) -> List[Dict]:
        """Chunk document into smaller pieces with metadata"""
        chunks = []
        
        # Get file metadata
        file_stats = os.stat(file_path)
        file_hash = self._get_file_hash(file_path)
        
        # Extract text content using docling's export_to_markdown method
        try:
            full_text = doc_result.document.export_to_markdown()
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return []
        
        # Validate extracted text
        if not full_text or not full_text.strip():
            print(f"No text content extracted from {file_path}")
            return []
        
        full_text = full_text.strip()
        
        # If the document is very short, create a single chunk
        if len(full_text) <= Config.CHUNK_SIZE:
            if len(full_text) >= Config.MIN_CHUNK_SIZE:
                chunk_id = f"{file_hash}_0"
                chunks.append({
                    'id': chunk_id,
                    'text': full_text,
                    'metadata': {
                        'filename': os.path.basename(file_path),
                        'filepath': file_path,
                        'file_hash': file_hash,
                        'chunk_id': chunk_id,
                        'chunk_index': 0,
                        'file_size': file_stats.st_size,
                        'modified_time': file_stats.st_mtime,
                        'page': 1,
                    }
                })
            return chunks
        
        # Simple text chunking for longer documents
        chunk_size = Config.CHUNK_SIZE
        overlap = Config.CHUNK_OVERLAP
        chunk_index = 0
        
        for i in range(0, len(full_text), chunk_size - overlap):
            chunk_text = full_text[i:i + chunk_size].strip()
            
            # Skip chunks that are too small
            if len(chunk_text) < Config.MIN_CHUNK_SIZE:
                continue
                
            chunk_id = f"{file_hash}_{chunk_index}"
            
            chunks.append({
                'id': chunk_id,
                'text': chunk_text,
                'metadata': {
                    'filename': os.path.basename(file_path),
                    'filepath': file_path,
                    'file_hash': file_hash,
                    'chunk_id': chunk_id,
                    'chunk_index': chunk_index,
                    'file_size': file_stats.st_size,
                    'modified_time': file_stats.st_mtime,
                    'page': chunk_index + 1,
                }
            })
            
            chunk_index += 1
        
        return chunks
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash for file to detect changes"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()