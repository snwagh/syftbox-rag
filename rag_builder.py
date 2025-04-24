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

class RAGBuilder:
    def __init__(self, client_id=None, client_secret=None, redirect_uri="http://localhost:8000"):
        # Load environment variables
        load_dotenv()
        
        # Configuration
        self.client_id = client_id or os.getenv('CLIENT_ID')
        self.client_secret = client_secret or os.getenv('CLIENT_SECRET')
        self.redirect_uri = redirect_uri
        
        # Microsoft Graph API endpoints
        self.auth_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        self.token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        # Updated scopes to include more permissions
        self.scopes = [
            "Files.Read",
            "Files.ReadWrite",
            "Files.Read.All",
            "Files.ReadWrite.All",
            "offline_access",
            "User.Read"
        ]
        
        # Global variables for authentication
        self.auth_code = None
        self.server_closed = False
        self.tokens = None
        
        # RAG configuration
        self.db_path = "syftbox_rag_dbs/onedrive_db"
        self.collection = None
        self.chroma_client = None

    def _run_server(self):
        class CodeHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.urlparse(self.path).query
                query_components = urllib.parse.parse_qs(query)
                
                if 'code' in query_components:
                    self.server.auth_code = query_components['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><head><title>Authentication Successful</title></head>")
                    self.wfile.write(b"<body><h1>Authentication Successful!</h1>")
                    self.wfile.write(b"<p>You can close this window and return to the application.</p>")
                    self.wfile.write(b"</body></html>")
                    self.server.server_closed = True
                    self.server.shutdown()  # Shutdown the server after successful authentication
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><head><title>Waiting for authentication</title></head>")
                    self.wfile.write(b"<body><h1>Waiting for authentication...</h1></body></html>")

        with socketserver.TCPServer(("", 8000), CodeHandler) as httpd:
            httpd.server = self
            print("Server started at http://localhost:8000")
            try:
                while not self.server_closed:
                    httpd.handle_request()
            except Exception as e:
                print(f"Server error: {str(e)}")
            finally:
                httpd.server_close()
                print("Server closed.")

    def _validate_token(self, token):
        """Validate a token by making a test request to Microsoft Graph API."""
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(
                f"{self.graph_endpoint}/me",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                return True
            elif response.status_code == 403:
                print("Permission denied. Please make sure your app has the correct permissions.")
                print("Required permissions: Files.Read, Files.ReadWrite, Files.Read.All, Files.ReadWrite.All")
                return False
            else:
                print(f"Token validation failed with status code: {response.status_code}")
                return False
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            print(f"Token validation failed: {str(e)}")
            return False

    def authenticate(self, timeout=300):
        """Authenticate with OneDrive and get access token.
        
        Args:
            timeout (int): Maximum time in seconds to wait for authentication. Default is 5 minutes.
        """
        # First check if we have valid tokens
        self.tokens = self._load_tokens()
        if self.tokens and 'access_token' in self.tokens:
            # Verify if the token is still valid with a timeout
            if self._validate_token(self.tokens['access_token']):
                print("Using existing valid authentication token.")
                return True
            
            # If token is invalid, try to refresh it
            if 'refresh_token' in self.tokens:
                try:
                    if self._refresh_token():
                        # Verify the new token
                        if self._validate_token(self.tokens['access_token']):
                            print("Successfully refreshed and validated authentication token.")
                            return True
                except Exception as e:
                    print(f"Token refresh failed: {str(e)}")
        
        # If we get here, we need to authenticate
        print("Starting new authentication process...")
        self.auth_code = None
        self.server_closed = False
        
        # Create a new server instance
        server = socketserver.TCPServer(("", 8000), self._create_handler())
        server.server = self
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        try:
            auth_url = f"{self.auth_endpoint}?client_id={self.client_id}&response_type=code"
            auth_url += f"&redirect_uri={self.redirect_uri}&scope={' '.join(self.scopes)}&response_mode=query"
            
            print("Opening browser for authentication...")
            print("Please complete the authentication in your browser.")
            print("After authentication, you can close the browser window and return to Jupyter.")
            print("\nNote: Make sure to grant all requested permissions when prompted.")
            
            # Open browser in a separate thread to not block
            browser_thread = threading.Thread(target=lambda: webbrowser.open(auth_url))
            browser_thread.daemon = True
            browser_thread.start()
            
            # Wait for authentication with timeout
            start_time = time.time()
            while not self.server_closed:
                if time.time() - start_time > timeout:
                    print("Authentication timed out. Please try again.")
                    break
                time.sleep(0.1)  # Shorter sleep for more responsive checking
            
            if self.auth_code:
                try:
                    self.tokens = self._get_tokens(self.auth_code)
                    if self.tokens:
                        # Verify the new token
                        if self._validate_token(self.tokens['access_token']):
                            self._save_tokens(self.tokens)
                            print("Authentication successful! You can now continue with the RAG database building.")
                            return True
                except Exception as e:
                    print(f"Error getting tokens: {str(e)}")
            
            return False
            
        finally:
            # Clean up
            server.shutdown()
            server.server_close()
            print("Authentication server closed.")

    def _create_handler(self):
        """Create a request handler for the authentication server."""
        class AuthHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.urlparse(self.path).query
                query_components = urllib.parse.parse_qs(query)
                
                if 'code' in query_components:
                    self.server.server.auth_code = query_components['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><head><title>Authentication Successful</title></head>")
                    self.wfile.write(b"<body><h1>Authentication Successful!</h1>")
                    self.wfile.write(b"<p>You can close this window and return to the application.</p>")
                    self.wfile.write(b"</body></html>")
                    self.server.server.server_closed = True
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><head><title>Waiting for authentication</title></head>")
                    self.wfile.write(b"<body><h1>Waiting for authentication...</h1></body></html>")
        
        return AuthHandler

    def _get_tokens(self, code):
        """Get access and refresh tokens."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': ' '.join(self.scopes),
            'code': code,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(self.token_endpoint, data=data, timeout=5)  # 5 second timeout
            if response.status_code == 200:
                tokens = response.json()
                if 'access_token' in tokens:
                    return tokens
                else:
                    print("Token response did not contain access token")
            else:
                print(f"Getting tokens failed with status code: {response.status_code}")
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            print(f"Error getting tokens: {str(e)}")
        return None

    def _refresh_token(self):
        """Refresh the access token using refresh token."""
        if not self.tokens or 'refresh_token' not in self.tokens:
            return False
            
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': ' '.join(self.scopes),
            'refresh_token': self.tokens['refresh_token'],
            'grant_type': 'refresh_token'
        }
        
        try:
            response = requests.post(self.token_endpoint, data=data, timeout=5)  # 5 second timeout
            if response.status_code == 200:
                new_tokens = response.json()
                if 'access_token' in new_tokens:
                    self.tokens = new_tokens
                    self._save_tokens(self.tokens)
                    return True
                else:
                    print("Refresh response did not contain access token")
            else:
                print(f"Token refresh failed with status code: {response.status_code}")
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            print(f"Error refreshing token: {str(e)}")
        return False

    def _save_tokens(self, tokens):
        """Save tokens to file."""
        with open('.tokens.json', 'w') as f:
            json.dump(tokens, f)

    def _load_tokens(self):
        """Load tokens from file."""
        try:
            with open('.tokens.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def list_files(self, folder_id=None):
        """List all files in OneDrive."""
        if not self.tokens:
            self.tokens = self._load_tokens()
            if not self.tokens:
                raise Exception("Not authenticated. Please call authenticate() first.")

        headers = {
            'Authorization': f'Bearer {self.tokens["access_token"]}',
            'Content-Type': 'application/json'
        }
        
        all_files = []
        
        def list_folder_contents(folder_id, folder_name="root"):
            print(f"Scanning folder: {folder_name}")
            endpoint = f"{self.graph_endpoint}/me/drive/items/{folder_id}/children"
            try:
                response = requests.get(endpoint, headers=headers)
                response.raise_for_status()
                
                items = response.json().get('value', [])
                print(f"Found {len(items)} items in {folder_name}")
                
                for item in items:
                    if 'folder' in item:
                        list_folder_contents(item['id'], item['name'])
                    else:
                        all_files.append(item)
                        print(f"Added file: {item['name']}")
            except requests.exceptions.RequestException as e:
                print(f"Error accessing folder {folder_name}: {str(e)}")
                return
        
        if folder_id is None:
            folder_id = "root"
        
        print("Starting recursive file scan...")
        list_folder_contents(folder_id)
        print(f"\nTotal files found: {len(all_files)}")
        return all_files

    def select_files(self, files):
        """Let user select files for RAG database."""
        print("\nAvailable files:")
        for i, file in enumerate(files, 1):
            path = file.get('parentReference', {}).get('path', '')
            if path:
                path = path.replace('/drive/root:', '')
                full_path = f"{path}/{file['name']}"
            else:
                full_path = file['name']
            print(f"{i}. {full_path}")
        
        while True:
            try:
                selection = input("\nEnter the numbers of files you want to include in the RAG database (comma-separated, e.g., '1,3,5'): ")
                selected_indices = [int(idx.strip()) - 1 for idx in selection.split(',')]
                
                if all(0 <= idx < len(files) for idx in selected_indices):
                    selected_files = [files[idx] for idx in selected_indices]
                    print("\nSelected files:")
                    for file in selected_files:
                        path = file.get('parentReference', {}).get('path', '')
                        if path:
                            path = path.replace('/drive/root:', '')
                            full_path = f"{path}/{file['name']}"
                        else:
                            full_path = file['name']
                        print(f"- {full_path}")
                    return selected_files
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Invalid input. Please enter numbers separated by commas.")

    def download_file(self, file_id, file_name):
        """Download a file from OneDrive."""
        headers = {'Authorization': f'Bearer {self.tokens["access_token"]}'}
        response = requests.get(
            f"{self.graph_endpoint}/me/drive/items/{file_id}/content",
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

    def setup_rag(self):
        """Set up the RAG database."""
        try:
            os.makedirs(self.db_path, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(path=self.db_path)
            
            try:
                self.collection = self.chroma_client.get_collection(name="documents")
                print("Using existing collection 'documents'")
            except Exception as e:
                if "Collection [documents] does not exists" in str(e):
                    print("Creating new collection 'documents'")
                    self.collection = self.chroma_client.create_collection(name="documents")
                else:
                    raise
            
            return self.collection, self.chroma_client
        except Exception as e:
            print(f"Error setting up RAG system: {str(e)}")
            print("Please make sure ChromaDB is properly installed and the database path is accessible.")
            raise

    def process_documents(self):
        """Process downloaded documents and add them to the RAG database."""
        if not self.collection:
            raise Exception("RAG system not set up. Please call setup_rag() first.")

        pdf_files = glob.glob("*.pdf")
        
        for file_path in pdf_files:
            try:
                print(f"Processing {file_path}...")
                # Read PDF file
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                
                # Add to RAG database
                self.collection.add(
                    documents=[text],
                    metadatas=[{"source": file_path}],
                    ids=[file_path]
                )
                print(f"Added {file_path} to RAG database")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")

    def build_rag_database(self):
        """Main method to build the RAG database from OneDrive files."""
        # Authenticate
        if not self.authenticate():
            raise Exception("Authentication failed")

        # List files
        files = self.list_files()
        
        # Select files
        selected_files = self.select_files(files)
        
        # Download selected files
        downloaded_files = []
        for file in selected_files:
            if self.download_file(file['id'], file['name']):
                downloaded_files.append(file['name'])
        
        # Set up RAG
        self.setup_rag()
        
        # Process documents
        self.process_documents()
        
        # Clean up downloaded files
        for file_name in downloaded_files:
            try:
                os.remove(file_name)
                print(f"Cleaned up {file_name}")
            except Exception as e:
                print(f"Error removing {file_name}: {str(e)}")
        
        print("RAG database is ready to use!") 