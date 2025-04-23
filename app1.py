import os
import streamlit as st
import requests
from dotenv import load_dotenv
from urllib.parse import quote, parse_qs, urlparse
import tempfile
import time
import msal
from langchain_community.document_loaders import TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb
import json
import shutil
import PyPDF2

# Load environment variables
load_dotenv()

# Check if credentials are available
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

if not client_id or not client_secret:
    st.error("CLIENT_ID or CLIENT_SECRET not found in .env file")
    st.stop()

# Microsoft Graph API endpoints
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPE = ["Files.Read", "Files.Read.All"]
REDIRECT_URI = "http://localhost:8501/"  # Streamlit default port
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

@st.cache_resource
def get_msal_app():
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=AUTHORITY
    )

def get_auth_url():
    msal_app = get_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI,
        state=str(time.time())
    )
    return auth_url

def get_token(auth_code):
    msal_app = get_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code=auth_code,
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )
    return result

def list_drive_items(access_token, folder_id=None):
    headers = {
        'Authorization': f"Bearer {access_token}"
    }
    
    if folder_id:
        # Get items from specific folder
        endpoint = f"{GRAPH_API_ENDPOINT}/me/drive/items/{folder_id}/children"
    else:
        # Get items from root folder
        endpoint = f"{GRAPH_API_ENDPOINT}/me/drive/root/children"
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        st.error(f"Error listing drive items: {response.status_code}")
        st.error(response.text)
        return []

def download_file(access_token, item_id, file_name):
    headers = {
        'Authorization': f"Bearer {access_token}"
    }
    
    # Get download URL
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        st.error(f"Error getting item details: {response.status_code}")
        st.error(response.text)
        return None
    
    download_url = response.json().get('@microsoft.graph.downloadUrl')
    
    if not download_url:
        st.error("Download URL not found")
        return None
    
    # Download the file
    file_response = requests.get(download_url)
    
    if file_response.status_code != 200:
        st.error(f"Error downloading file: {file_response.status_code}")
        return None
    
    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, file_name)
    
    with open(file_path, 'wb') as f:
        f.write(file_response.content)
    
    return file_path

def load_document(file_path):
    """Load a document based on its file extension using direct methods"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    documents = []
    
    if file_extension == '.pdf':
        try:
            # Use PyPDF2 directly as in your example
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():  # Only add non-empty pages
                        documents.append({
                            "page_content": text,
                            "metadata": {
                                "source": file_path,
                                "page": i + 1,
                                "total_pages": len(pdf_reader.pages)
                            }
                        })
        except Exception as e:
            st.error(f"Error processing PDF {file_path}: {str(e)}")
    
    elif file_extension == '.docx':
        try:
            loader = Docx2txtLoader(file_path)
            for doc in loader.load():
                documents.append({
                    "page_content": doc.page_content,
                    "metadata": {"source": file_path, **doc.metadata}
                })
        except Exception as e:
            st.error(f"Error processing DOCX {file_path}: {str(e)}")
    
    elif file_extension in ['.txt', '.md', '.html']:
        try:
            loader = TextLoader(file_path)
            for doc in loader.load():
                documents.append({
                    "page_content": doc.page_content,
                    "metadata": {"source": file_path, **doc.metadata}
                })
        except Exception as e:
            st.error(f"Error processing text file {file_path}: {str(e)}")
    
    else:
        st.error(f"Unsupported file type: {file_extension}")
        return []
    
    return documents

def build_rag_database(documents, output_dir, collection_name="documents"):
    """Build a RAG database from documents using direct ChromaDB API"""
    # Ensure the output directory exists
    if os.path.exists(output_dir):
        # Remove existing directory to start fresh
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path=output_dir)
    
    # Create collection
    collection = chroma_client.create_collection(
        name=collection_name,
        metadata={"description": "Document collection for RAG"}
    )
    
    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    total_chunks = 0
    document_metadata = {}
    
    # Process each document
    for i, doc in enumerate(documents):
        # Get content and metadata
        content = doc["page_content"]
        source_file = doc["metadata"].get("source", f"document_{i}")
        
        # Track document metadata
        if source_file not in document_metadata:
            document_metadata[source_file] = {
                "chunks": 0,
                "pages": set()
            }
        
        # Add page info if available
        if "page" in doc["metadata"]:
            document_metadata[source_file]["pages"].add(doc["metadata"]["page"])
        
        # Split into chunks
        chunks = text_splitter.split_text(content)
        
        # Add chunks to the collection
        for j, chunk in enumerate(chunks):
            if chunk.strip():  # Only add non-empty chunks
                chunk_id = f"{os.path.basename(source_file)}_{i}_{j}"
                
                # Prepare metadata for this chunk
                chunk_metadata = {
                    "source": source_file,
                    "chunk_id": j,
                    "document_id": i
                }
                
                # Add page number if available
                if "page" in doc["metadata"]:
                    chunk_metadata["page"] = doc["metadata"]["page"]
                
                # Add to collection
                collection.add(
                    documents=[chunk],
                    metadatas=[chunk_metadata],
                    ids=[chunk_id]
                )
                
                # Update counts
                total_chunks += 1
                document_metadata[source_file]["chunks"] += 1
    
    # Convert sets to lists for JSON serialization
    for doc_id in document_metadata:
        if "pages" in document_metadata[doc_id]:
            document_metadata[doc_id]["pages"] = list(document_metadata[doc_id]["pages"])
    
    # Save metadata about the database
    metadata = {
        "collection_name": collection_name,
        "document_count": len(documents),
        "chunk_count": total_chunks,
        "documents": document_metadata,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Save metadata to file
    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return total_chunks

# App UI
st.title("RAG Builder from OneDrive Files")

# Session state for storing authentication and selection
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'current_folder_id' not in st.session_state:
    st.session_state.current_folder_id = None
if 'current_folder_name' not in st.session_state:
    st.session_state.current_folder_name = "Root"
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'folder_history' not in st.session_state:
    st.session_state.folder_history = []
if 'downloaded_files' not in st.session_state:
    st.session_state.downloaded_files = {}

# Handle query parameters for authentication
query_params = st.experimental_get_query_params()
code = query_params.get("code", [""])[0]

if code and not st.session_state.access_token:
    token_result = get_token(code)
    if "access_token" in token_result:
        st.session_state.access_token = token_result["access_token"]
        st.experimental_set_query_params()
        st.rerun()
    else:
        st.error(f"Error obtaining access token: {token_result.get('error_description')}")

# Display authentication button if not authenticated
if not st.session_state.access_token:
    st.write("Please authenticate with Microsoft OneDrive to proceed.")
    auth_url = get_auth_url()
    st.link_button("Sign in with Microsoft", auth_url)

else:
    # File navigation and selection interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("OneDrive File Browser")
        
        # Back button for navigation
        if st.session_state.folder_history:
            if st.button("⬅️ Back"):
                st.session_state.current_folder_id = st.session_state.folder_history.pop()
                # Update current folder name
                if not st.session_state.current_folder_id:
                    st.session_state.current_folder_name = "Root"
                st.rerun()
        
        st.write(f"Current location: {st.session_state.current_folder_name}")
        
        # List files and folders
        items = list_drive_items(st.session_state.access_token, st.session_state.current_folder_id)
        
        # Separate folders and files
        folders = [item for item in items if item.get('folder')]
        files = [item for item in items if not item.get('folder')]
        
        # Display folders
        if folders:
            st.subheader("Folders")
            for folder in folders:
                if st.button(f"📁 {folder['name']}", key=f"folder_{folder['id']}"):
                    st.session_state.folder_history.append(st.session_state.current_folder_id)
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    st.rerun()
        
        # Display files
        if files:
            st.subheader("Files")
            for file in files:
                # Filter for supported document types
                file_extension = os.path.splitext(file['name'])[1].lower()
                if file_extension in ['.pdf', '.docx', '.txt', '.md', '.html']:
                    file_id = file['id']
                    file_name = file['name']
                    
                    # Check if already selected
                    is_selected = any(selected['id'] == file_id for selected in st.session_state.selected_files)
                    
                    col_file, col_select = st.columns([3, 1])
                    with col_file:
                        st.write(f"📄 {file_name}")
                    with col_select:
                        if is_selected:
                            if st.button("✓ Selected", key=f"remove_{file_id}"):
                                st.session_state.selected_files = [f for f in st.session_state.selected_files if f['id'] != file_id]
                                if file_id in st.session_state.downloaded_files:
                                    del st.session_state.downloaded_files[file_id]
                                st.rerun()
                        else:
                            if st.button("Select", key=f"add_{file_id}"):
                                st.session_state.selected_files.append({
                                    'id': file_id,
                                    'name': file_name
                                })
                                st.rerun()
    
    with col2:
        st.subheader("Selected Files")
        if not st.session_state.selected_files:
            st.write("No files selected")
        else:
            for selected in st.session_state.selected_files:
                st.write(f"📄 {selected['name']}")
            
            # RAG database creation
            st.subheader("RAG Database Creation")
            rag_name = st.text_input("Enter RAG database name:", "my_rag_database")
            collection_name = st.text_input("Collection name:", "documents")
            
            if st.button("Build RAG Database"):
                with st.spinner("Downloading files and building RAG database..."):
                    # Download selected files if not already downloaded
                    for selected in st.session_state.selected_files:
                        if selected['id'] not in st.session_state.downloaded_files:
                            file_path = download_file(
                                st.session_state.access_token, 
                                selected['id'], 
                                selected['name']
                            )
                            if file_path:
                                st.session_state.downloaded_files[selected['id']] = file_path
                    
                    # Load and process documents
                    all_documents = []
                    for file_id, file_path in st.session_state.downloaded_files.items():
                        docs = load_document(file_path)
                        if docs:
                            all_documents.extend(docs)
                    
                    if all_documents:
                        # Create output directory
                        rag_dir = os.path.join("rag_databases", rag_name)
                        os.makedirs("rag_databases", exist_ok=True)
                        
                        # Build and save the RAG database
                        chunk_count = build_rag_database(all_documents, rag_dir, collection_name)
                        
                        st.success(f"RAG database created successfully with {chunk_count} chunks!")
                        st.info(f"Database stored in: {rag_dir}")
                        
                        # Show database information
                        metadata_path = os.path.join(rag_dir, "metadata.json")
                        if os.path.exists(metadata_path):
                            with open(metadata_path, "r") as f:
                                metadata = json.load(f)
                            
                            st.subheader("Database Information")
                            st.write(f"Document count: {metadata.get('document_count', 'Unknown')}")
                            st.write(f"Total chunks: {metadata.get('chunk_count', 'Unknown')}")
                            st.write(f"Collection name: {metadata.get('collection_name', 'documents')}")
                    else:
                        st.error("No documents could be processed. Please check selected files.")