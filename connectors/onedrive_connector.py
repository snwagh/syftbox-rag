import os
from typing import List
from llama_index.core import Document
from llama_index.readers.microsoft_onedrive import OneDriveReader
from .base_connector import BaseConnector

class OneDriveConnector(BaseConnector):
    """Connector for OneDrive using llama_index's OneDriveReader."""
    
    def __init__(self):
        """Initialize OneDrive connector."""
        self.client_id = os.getenv('MS_CLIENT_ID')
        self.client_secret = os.getenv('MS_CLIENT_SECRET')
        self.user_email = os.getenv('MS_USER_EMAIL')  # Add user email from environment
        
        if not all([self.client_id, self.client_secret, self.user_email]):
            raise ValueError(
                "Missing required environment variables for OneDrive. "
                "Please set MS_CLIENT_ID, MS_CLIENT_SECRET, and MS_USER_EMAIL in .env file"
            )
            
        self.reader = OneDriveReader(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_principal_name=self.user_email  # Add user email to reader
        )
    
    def load_documents(self, source_path: str) -> List[Document]:
        """
        Load documents from OneDrive.
        source_path: The path in OneDrive (e.g., "Documents/file.pdf")
        """
        try:
            # Fetch the document from the specified path
            documents = self.reader.load_data(
                file_paths=[source_path],
                recursive=False  # Set to True if you want to traverse subfolders
            )
            
            # Add source metadata to each document
            for doc in documents:
                doc.metadata = {"source": f"onedrive://{source_path}"}
            
            return documents
            
        except Exception as e:
            print(f"Error connecting to OneDrive: {str(e)}")
            return [] 