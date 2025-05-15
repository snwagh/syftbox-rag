from pathlib import Path
from typing import List
from llama_index.core import Document
from llama_index.readers.file import PDFReader, DocxReader
from .base_connector import BaseConnector

class LocalConnector(BaseConnector):
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