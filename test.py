from llama_index.readers.microsoft_onedrive import OneDriveReader
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def fetch_onedrive_document(client_id, client_secret, document_path):
    """
    Fetch a document from OneDrive using client ID and client secret.
    
    Args:
        client_id (str): Microsoft application client ID
        client_secret (str): Microsoft application client secret
        document_path (str): Path to the document in OneDrive (e.g., "Documents/file.pdf")
    
    Returns:
        list: List of Document objects containing the loaded document data
    """
    try:
        # Initialize the OneDrive reader with your credentials
        onedrive_reader = OneDriveReader(
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Fetch the document from the specified path
        documents = onedrive_reader.load_data(
            file_paths=[document_path],  # Now expects a list of file paths
            recursive=False  # Set to True if you want to traverse subfolders
        )
        
        logger.info(f"Successfully fetched {document_path}")
        return documents
    except Exception as e:
        logger.error(f"Error fetching document: {str(e)}")
        raise

if __name__ == "__main__":
    # Replace these with your actual credentials
    CLIENT_ID = os.getenv('MS_CLIENT_ID')
    CLIENT_SECRET = os.getenv('MS_CLIENT_SECRET')
    
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Missing required environment variables: MS_CLIENT_ID and/or MS_CLIENT_SECRET")
        exit(1)
    
    # The path to the document you want to fetch
    DOCUMENT_PATH = "Documents/Bill_Cottrell.pdf"
    
    try:
        # Fetch the document
        documents = fetch_onedrive_document(CLIENT_ID, CLIENT_SECRET, DOCUMENT_PATH)
        
        # Print the content of the first document (if available)
        if documents:
            print(f"Content preview: {documents[0].text[:100]}...")
        else:
            logger.warning("No documents were fetched")
    except Exception as e:
        logger.error(f"Failed to process document: {str(e)}")
