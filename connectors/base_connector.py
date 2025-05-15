from typing import List
from llama_index.core import Document

class BaseConnector:
    """Base class for data source connectors."""
    
    def load_documents(self, source_path: str) -> List[Document]:
        """Load documents from the source."""
        raise NotImplementedError 