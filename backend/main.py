# rabitz/
# ├── backend/
# │   ├── main.py              # FastAPI server
# │   ├── document_processor.py # Docling integration
# │   ├── embeddings.py        # Embedding generation
# │   ├── file_watcher.py      # File system monitoring
# │   ├── vector_store.py      # Chroma database interface
# │   └── config.py            # Configuration
# ├── frontend/
# │   ├── index.html           # Main interface
# │   ├── app.js               # Frontend logic
# │   └── style.css            # Styling
# ├── vector_db/               # Chroma database files
# ├── requirements.txt
# └── run.py                   # Application launcher


## 1. Main Application (main.py)
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import stat

from .document_processor import DocumentProcessor
from .embeddings import EmbeddingGenerator
from .vector_store import VectorStore
from .file_watcher import FileWatcher
from .config import Config

# Ensure directories exist
Config.ensure_directories()

app = FastAPI(title="RAG Document Search")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Initialize components
doc_processor = DocumentProcessor()
embedding_gen = EmbeddingGenerator()
vector_store = VectorStore()
file_watcher = FileWatcher(vector_store, doc_processor, embedding_gen)

def build_file_tree(path: str, expand_folders: bool = True, max_depth: int = 3, current_depth: int = 0) -> List[Dict[str, Any]]:
    """Build a tree structure of files and folders for the file browser"""
    if current_depth >= max_depth:
        return []
    
    items = []
    try:
        # Get directory contents
        for item_name in sorted(os.listdir(path)):
            # Skip hidden files and system files
            if item_name.startswith('.'):
                continue
                
            item_path = os.path.join(path, item_name)
            
            try:
                # Get file stats
                item_stat = os.stat(item_path)
                is_dir = stat.S_ISDIR(item_stat.st_mode)
                
                # Calculate size
                if is_dir:
                    # For directories, try to count items (but don't go too deep)
                    try:
                        item_count = len([f for f in os.listdir(item_path) if not f.startswith('.')])
                        size_info = f"{item_count} items"
                        size_bytes = 0
                    except (PermissionError, OSError):
                        size_info = "? items"
                        size_bytes = 0
                else:
                    size_bytes = item_stat.st_size
                    size_info = format_file_size(size_bytes)
                
                # Create item object
                item = {
                    "name": item_name,
                    "path": item_path,
                    "type": "folder" if is_dir else "file",
                    "size": size_info,
                    "size_bytes": size_bytes,
                    "modified": item_stat.st_mtime,
                    "children": []
                }
                
                # Add children for directories if expanding
                if is_dir and expand_folders and current_depth < max_depth - 1:
                    try:
                        item["children"] = build_file_tree(
                            item_path, 
                            expand_folders, 
                            max_depth, 
                            current_depth + 1
                        )
                    except (PermissionError, OSError):
                        # If we can't read the directory, mark it as inaccessible
                        item["children"] = []
                        item["accessible"] = False
                
                items.append(item)
                
            except (PermissionError, OSError):
                # Skip items we can't access
                continue
                
    except (PermissionError, OSError):
        # Return empty list if we can't read the directory
        return []
    
    return items

def format_file_size(bytes_size: int) -> str:
    """Format file size in human readable format"""
    if bytes_size == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(bytes_size)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

# Pydantic models
class FolderRequest(BaseModel):
    folder_path: str

class SearchRequest(BaseModel):
    query: str
    limit: int = Config.DEFAULT_SEARCH_LIMIT

class SearchPathsRequest(BaseModel):
    query: str
    limit: int = Config.DEFAULT_SEARCH_LIMIT

class FileStructureRequest(BaseModel):
    path: Optional[str] = None
    expand_folders: bool = True

class CheckboxUpdate(BaseModel):
    paths: List[str]
    checked: bool

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    try:
        with open("frontend/index.html") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend not found")

@app.post("/api/add-folder")
async def add_folder(request: FolderRequest):
    """Add a folder to be watched and indexed"""
    try:
        await file_watcher.add_watch_folder(request.folder_path)
        return {"status": "success", "message": f"Added {request.folder_path} to watch list"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/watched-folders")
async def get_watched_folders():
    """Get list of currently watched folders"""
    return {"folders": file_watcher.get_watched_folders()}

@app.post("/api/search")
async def search_documents(request: SearchRequest):
    """Search for similar documents"""
    try:
        # Generate query embedding
        query_embedding = embedding_gen.embed_text(request.query)
        
        # Search vector store
        results = vector_store.search(
            query_embedding=query_embedding,
            n_results=request.limit,
            include=["documents", "metadatas", "distances"]
        )
        
        return {
            "query": request.query,
            "results": format_search_results(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-paths")
async def search_document_paths(request: SearchPathsRequest):
    """Search for similar documents and return only file paths"""
    try:
        # Generate query embedding
        query_embedding = embedding_gen.embed_text(request.query)
        
        # Search vector store
        results = vector_store.search(
            query_embedding=query_embedding,
            n_results=request.limit,
            include=["metadatas", "distances"]
        )
        
        # Extract unique file paths from results
        file_paths = set()
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                if metadata and 'filepath' in metadata:
                    file_paths.add(metadata['filepath'])
        
        return {
            "query": request.query,
            "file_paths": list(file_paths),
            "total_files": len(file_paths)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Get database statistics"""
    return {
        "total_documents": vector_store.count(),
        "watched_folders": len(file_watcher.get_watched_folders())
    }

@app.get("/api/indexing-status")
async def get_indexing_status():
    """Get current indexing status and progress"""
    return file_watcher.get_indexing_status()

@app.delete("/api/watched-folders/{folder_path:path}")
async def remove_watched_folder(folder_path: str):
    """Remove a folder from the watch list"""
    try:
        # Use the FileWatcher's remove method which handles persistence
        file_watcher.remove_watch_path(folder_path)
        return {"status": "success", "message": f"Removed {folder_path} from watch list"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/file-structure")
async def get_file_structure(request: FileStructureRequest):
    """Get file structure for directory browsing with Dropbox-like interface"""
    try:
        base_path = request.path if request.path else os.path.expanduser("~")
        
        if not os.path.exists(base_path):
            raise HTTPException(status_code=404, detail="Path does not exist")
        
        if not os.path.isdir(base_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        structure = build_file_tree(base_path, request.expand_folders)
        return {
            "path": base_path,
            "structure": structure
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file-structure/home")
async def get_home_structure():
    """Get file structure starting from user's home directory"""
    try:
        home_path = os.path.expanduser("~")
        structure = build_file_tree(home_path, expand_folders=False, max_depth=2)
        return {
            "path": home_path,
            "structure": structure
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/folder-selection")
async def update_folder_selection(request: CheckboxUpdate):
    """Update folder selection state for watched folders"""
    try:
        # Validate paths and separate files from folders
        valid_paths = []
        for path in request.paths:
            if os.path.exists(path):
                valid_paths.append(path)
        
        if request.checked:
            # Add folders and files to watch list
            for path in valid_paths:
                if os.path.isdir(path):
                    await file_watcher.add_watch_folder(path)
                elif os.path.isfile(path) and doc_processor.is_supported(path):
                    await file_watcher.add_watch_file(path)
        else:
            # Remove folders and files from watch list (now async)
            for path in valid_paths:
                await file_watcher.remove_watch_path(path)
        
        return {
            "status": "success",
            "message": f"Updated selection for {len(valid_paths)} paths",
            "updated_paths": valid_paths
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def format_search_results(results):
    """Format search results for frontend"""
    formatted = []
    if not results['documents'] or not results['documents'][0]:
        return formatted
        
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0], 
        results['metadatas'][0], 
        results['distances'][0]
    )):
        formatted.append({
            "id": i,
            "content": doc,
            "filename": metadata.get('filename', 'Unknown'),
            "filepath": metadata.get('filepath', ''),
            "page": metadata.get('page', 0),
            "similarity": max(0, 1 - distance),  # Convert distance to similarity
            "chunk_id": metadata.get('chunk_id', ''),
            "file_size": metadata.get('file_size', 0),
            "modified_time": metadata.get('modified_time', 0)
        })
    return formatted

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    print(f"Starting RAG Document Search on {Config.HOST}:{Config.PORT}")
    
    # Log restored configuration
    watched_folders = file_watcher.watched_folders
    watched_files = file_watcher.watched_files
    
    if watched_folders or watched_files:
        print(f"Restored {len(watched_folders)} watched folders and {len(watched_files)} watched files from persistent storage")
        if watched_folders:
            print(f"Watched folders: {list(watched_folders)}")
        if watched_files:
            print(f"Watched files: {list(watched_files)}")
    else:
        print("No previously watched folders or files found")
    
    # Start the file watcher processing queue
    file_watcher.start_processing()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    file_watcher.stop()

if __name__ == "__main__":
    """Launch the RAG document search application"""
    print("🚀 Starting RAG Document Search System...")
    print(f"📂 Vector database: {Config.VECTOR_DB_PATH}")
    print(f"🤖 Embedding model: {Config.EMBEDDING_MODEL}")
    print(f"🌐 Server will be available at: http://{Config.HOST}:{Config.PORT}")
    print("\n" + "="*50)
    
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)