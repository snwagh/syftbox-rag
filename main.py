import os
import requests
import json
from dotenv import load_dotenv
import webbrowser
import http.server
import socketserver
import urllib.parse
import threading
import time
import chromadb
import glob
import PyPDF2

# Load environment variables
load_dotenv()

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8000"
DOCUMENTS_FOLDER_ID = "3005497AC2A455DC!103"  # Your OneDrive Documents folder ID

# Ollama configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b" # "deepseek-r1:1.5b"

# Microsoft Graph API endpoints
AUTH_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.Read", "Files.ReadWrite", "offline_access"]

# Global variables
auth_code = None
server_closed = False

class CodeHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global auth_code, server_closed
        query = urllib.parse.urlparse(self.path).query
        query_components = urllib.parse.parse_qs(query)
        
        if 'code' in query_components:
            auth_code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><head><title>Authentication Successful</title></head>")
            self.wfile.write(b"<body><h1>Authentication Successful!</h1>")
            self.wfile.write(b"<p>You can close this window and return to the application.</p>")
            self.wfile.write(b"</body></html>")
            server_closed = True
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><head><title>Waiting for authentication</title></head>")
            self.wfile.write(b"<body><h1>Waiting for authentication...</h1></body></html>")

def run_server():
    with socketserver.TCPServer(("", 8000), CodeHandler) as httpd:
        print("Server started at http://localhost:8000")
        while not server_closed:
            httpd.handle_request()

def get_authorization_code():
    global auth_code, server_closed
    auth_code = None
    server_closed = False
    
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    auth_url = f"{AUTH_ENDPOINT}?client_id={CLIENT_ID}&response_type=code"
    auth_url += f"&redirect_uri={REDIRECT_URI}&scope={' '.join(SCOPES)}&response_mode=query"
    
    print("Opening browser for authentication...")
    webbrowser.open(auth_url)
    
    while not server_closed:
        time.sleep(1)
    
    return auth_code

def get_tokens(code):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': ' '.join(SCOPES),
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(TOKEN_ENDPOINT, data=data)
    return response.json() if response.status_code == 200 else None

def refresh_token(refresh_token):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': ' '.join(SCOPES),
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    
    response = requests.post(TOKEN_ENDPOINT, data=data)
    return response.json() if response.status_code == 200 else None

def list_onedrive_files(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    endpoint = f"{GRAPH_ENDPOINT}/me/drive/items/{DOCUMENTS_FOLDER_ID}/children"
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        files = response.json().get('value', [])
        print(f"\nFound {len(files)} files/folders:")
        for file in files:
            file_type = "📁 Folder" if 'folder' in file else "📄 File"
            print(f"{file_type}: {file['name']} (ID: {file['id']})")
        return files
    else:
        print(f"Error listing files: {response.status_code}")
        return []

def download_file(access_token, file_id, file_name):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(
        f"{GRAPH_ENDPOINT}/me/drive/items/{file_id}/content",
        headers=headers,
        stream=True
    )
    
    if response.status_code == 200:
        with open(file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {file_name} successfully!")
        return True
    else:
        print(f"Error downloading file: {response.status_code}")
        return False

def save_tokens(tokens):
    with open('.tokens.json', 'w') as f:
        json.dump(tokens, f)

def load_tokens():
    try:
        with open('.tokens.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def setup_rag():
    try:
        db_path = "syftbox_rag_dbs/onedrive_db"
        # Create the rag_databases directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize ChromaDB with the new path
        chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Try to get the existing collection, if it fails then create a new one
        try:
            collection = chroma_client.get_collection(name="documents")
            print("Using existing collection 'documents'")
        except Exception as e:
            if "Collection [documents] does not exists" in str(e):
                print("Creating new collection 'documents'")
                collection = chroma_client.create_collection(name="documents")
            else:
                raise
        
        return collection, chroma_client
    except Exception as e:
        print(f"Error setting up RAG system: {str(e)}")
        print("Please make sure ChromaDB is properly installed and the database path is accessible.")
        raise

def process_documents(collection):
    # Get all PDF files in the current directory
    pdf_files = glob.glob("*.pdf")
    
    for file_path in pdf_files:
        try:
            print(f"Processing {file_path}...")
            # Read PDF file
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            # Split content into chunks (you might want to implement a better chunking strategy)
            chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
            
            # Add chunks to collection
            for i, chunk in enumerate(chunks):
                if chunk.strip():  # Only add non-empty chunks
                    collection.add(
                        documents=[chunk],
                        metadatas=[{"source": file_path, "chunk": i}],
                        ids=[f"{file_path}_{i}"]
                    )
            
            print(f"Successfully processed {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    print(f"Processed {len(pdf_files)} documents into the RAG system")

def query_ollama(prompt):
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"Error querying Ollama: {str(e)}")
        return None

def query_rag(collection, query):
    try:
        # Search for relevant documents
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        # Prepare context and metadata
        context = []
        for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
            context.append(f"Document: {metadata['source']}\nContent: {doc}\n")
        
        # Create the prompt
        prompt = f"""Context:
{''.join(context)}

Question: {query}

Provide a concise answer to the question based on the provided context. If the answer cannot be found in the context, say so.
Also, specify which document (if any) was most relevant to your answer."""

        # Query Ollama
        response = query_ollama(prompt)
        if response:
            return response
        else:
            return "I'm sorry, I encountered an error while processing your question. Please try again."
    except Exception as e:
        print(f"Error in RAG query: {str(e)}")
        return "I'm sorry, I encountered an error while processing your question. Please try again."

def main():
    # Authentication
    tokens = load_tokens()
    
    if not tokens:
        print("No saved tokens found. Starting authentication flow...")
        code = get_authorization_code()
        if code:
            tokens = get_tokens(code)
            if tokens:
                save_tokens(tokens)
    else:
        print("Found saved tokens. Refreshing access token...")
        new_tokens = refresh_token(tokens.get('refresh_token'))
        if new_tokens:
            tokens = new_tokens
            save_tokens(tokens)
    
    if not tokens or 'access_token' not in tokens:
        print("Failed to get access token. Please try again.")
        return
    
    print("Successfully authenticated!")
    
    # List and download all files
    files = list_onedrive_files(tokens['access_token'])
    downloaded_files = []
    
    if files:
        print("\nDownloading all files...")
        for file in files:
            if 'folder' not in file:  # Only download files, not folders
                file_id = file['id']
                file_name = file['name']
                if download_file(tokens['access_token'], file_id, file_name):
                    downloaded_files.append(file_name)
                    print(f"Downloaded: {file_name}")
    
    try:
        # Setup RAG system
        print("\nSetting up RAG system...")
        collection, client = setup_rag()
        process_documents(collection)
    except Exception as e:
        print(f"Error setting up RAG system: {str(e)}")
        print("Please make sure Ollama is running and the model is available.")
        return
    
    # Delete downloaded files
    print("\nCleaning up downloaded files...")
    for file_name in downloaded_files:
        try:
            os.remove(file_name)
            print(f"Deleted: {file_name}")
        except Exception as e:
            print(f"Error deleting {file_name}: {e}")
    
    # Interactive querying
    print(f"\nRAG system is ready at {client._identifier}")

if __name__ == "__main__":
    main()
