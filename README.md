# 🔍 RAG Document Search

A lightweight, local RAG (Retrieval-Augmented Generation) system for indexing and searching your documents. Built with FastAPI, Docling, and ChromaDB for high-performance semantic search across your local files.

## ✨ Features

- **🚀 Lightweight & Fast**: Optimized for performance with millions of document chunks
- **🌐 Beautiful Web Interface**: Modern, responsive UI for easy document management and search
- **📁 Auto File Watching**: Automatically indexes new/modified files in watched folders
- **🔍 Semantic Search**: Uses advanced embeddings for intelligent document retrieval
- **📊 Real-time Stats**: Monitor your document index and search performance
- **🗂️ File Browser**: Dropbox-like interface for browsing and selecting files/folders
- **⚡ Smart Indexing**: Avoids re-indexing unchanged files using content hashing
- **📈 Progress Tracking**: Real-time indexing progress with detailed status updates
- **💾 Persistent Configuration**: Automatically saves and restores watched folders
- **🔧 Configurable**: Easy configuration via environment variables
- **🔐 OAuth Support**: Integration with Microsoft OneDrive/SharePoint (via .tokens.json)

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API    │    │  Vector Store   │
│  (HTML/JS)      │◄──►│   (FastAPI)      │◄──►│   (Chroma)      │
│                 │    │                  │    │                 │
│ • File selector │    │ • File watcher   │    │ • Embeddings    │
│ • Search UI     │    │ • Doc processing │    │ • Metadata      │
│ • Results view  │    │ • Embedding gen  │    │ • Fast search   │
│ • Progress view │    │ • Hash checking  │    │ • Deduplication │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌──────────────────┐
                       │  File System     │
                       │   Watcher        │
                       │  (watchdog)      │
                       └──────────────────┘
```

## 📋 Supported File Formats

- **PDF** documents
- **Microsoft Word** (.docx)
- **Text files** (.txt, .md)
- **HTML** files
- **PowerPoint** (.pptx)
- **Excel** (.xlsx)

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd syftbox-rag
   ```

2. **Install dependencies**:
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   ./run.sh
   ```

4. **Open your browser** and go to:
   ```
   http://localhost:9000
   ```

## 🎯 Usage

### Adding Documents

1. Go to the **"Manage Files"** tab
2. Use the **file browser** to navigate to your desired folder
3. **Select folders or individual files** using checkboxes
4. Click **"Add Selected"** to start indexing
5. Monitor progress in real-time with the **indexing status indicator**

### File Browser Features

- **📂 Navigate** through your file system like Dropbox
- **☑️ Select** multiple files and folders with checkboxes
- **📊 View** file sizes and modification dates
- **🔍 Quick** folder expansion/collapse
- **🏠 Home** directory quick access

### Searching Documents

1. Go to the **"Search Documents"** tab
2. Enter your search query in natural language
3. Adjust the results limit if needed (default: 20)
4. Click **"Search"** or press Enter
5. View results with similarity scores and metadata

### Search Examples

- `"machine learning algorithms"`
- `"project timeline and deadlines"`
- `"financial reports Q3"`
- `"meeting notes from last week"`

## ⚙️ Configuration

You can customize the system behavior using environment variables:

### Database Settings
```bash
export VECTOR_DB_PATH="./my_vector_db"  # Vector database location
```

### Embedding Model
```bash
export EMBEDDING_MODEL="all-MiniLM-L6-v2"  # Sentence transformer model
```

### Document Processing
```bash
export CHUNK_SIZE="500"           # Document chunk size (characters)
export CHUNK_OVERLAP="50"         # Overlap between chunks
export MIN_CHUNK_SIZE="50"        # Minimum chunk size to index
```

### Server Settings
```bash
export HOST="0.0.0.0"            # Server host
export PORT="8080"               # Server port
```

### Performance Tuning
```bash
export PROCESSING_DELAY="1.0"         # File processing delay (seconds)
export DEFAULT_SEARCH_LIMIT="20"      # Default search results
export MAX_SEARCH_LIMIT="100"         # Maximum search results
```

## 🏃‍♂️ Running the System

### Method 1: Using the run script (Recommended)
```bash
./run.sh
```

### Method 2: Direct FastAPI
```bash
uv run uvicorn backend.main:app --host 127.0.0.1 --port 9000
```

### Method 3: Development mode (with auto-reload)
```bash
uv run uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload
```

### Stopping the Application
```bash
./cleanup.sh
```

## 📁 Project Structure

```
syftbox-rag/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI server with API endpoints
│   ├── config.py            # Configuration settings
│   ├── document_processor.py # Docling integration for parsing
│   ├── embeddings.py        # Sentence transformer embeddings
│   ├── file_watcher.py      # File system monitoring & processing
│   └── vector_store.py      # ChromaDB interface
├── frontend/
│   ├── index.html           # Main interface with tabs
│   ├── app.js               # Frontend logic & file browser
│   └── style.css            # Modern responsive styling
├── data/                    # Application data (logs, PID files)
├── vector_db/               # ChromaDB storage (auto-created)
├── .tokens.json             # OAuth tokens (optional)
├── requirements.txt         # Python dependencies
├── run.sh                   # Application launcher script
├── cleanup.sh               # Application cleanup script
└── README.md                # This file
```

## 🔧 API Endpoints

The system provides a comprehensive REST API:

- **GET** `/` - Main web interface
- **POST** `/api/add-folder` - Add folder to watch list
- **GET** `/api/watched-folders` - Get watched folders
- **DELETE** `/api/watched-folders/{path}` - Remove watched folder
- **POST** `/api/search` - Search documents
- **GET** `/api/stats` - Get database statistics
- **GET** `/api/indexing-status` - Get real-time indexing progress
- **POST** `/api/file-structure` - Browse file system
- **GET** `/api/file-structure/home` - Get home directory structure
- **POST** `/api/folder-selection` - Batch add/remove files and folders

## 🎯 Advanced Features

### Smart Indexing
- **File hashing** prevents re-indexing unchanged documents
- **Chunked processing** handles large files efficiently
- **Background processing** doesn't block the UI
- **Error recovery** handles corrupted or inaccessible files

### Real-time Progress Tracking
- **Operation queue** with detailed progress information
- **File-level progress** with chunk counting
- **Size estimation** and processing speed metrics
- **Activity logs** for debugging and monitoring

### Persistent State Management
- **Watched folders** automatically restored on restart
- **Database integrity** maintained across sessions
- **Configuration persistence** via environment variables

## 🔧 Development

### Adding Dependencies
```bash
uv add package-name
```

### Running Tests
```bash
# Add test files to test the system
uv run python -m pytest tests/
```

### Code Formatting
```bash
uv run black backend/
uv run isort backend/
```

## 🎯 Performance Considerations

- **Vector Database**: ChromaDB provides excellent performance for millions of document chunks
- **Embedding Model**: The default `all-MiniLM-L6-v2` model balances speed and accuracy
- **Chunking Strategy**: 500-character chunks with 50-character overlap work well for most documents
- **File Watching**: Files are processed asynchronously to avoid blocking the UI
- **Search Speed**: Typical search times are under 1 second for large document collections
- **Smart Caching**: File hashing prevents unnecessary re-processing
- **Memory Management**: Efficient streaming processing for large documents

## 🛠️ Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   export SYFTBOX_ASSIGNED_PORT="8080"  # Use a different port
   ./run.sh
   ```

2. **Permission errors when adding folders**:
   - Ensure the folder path exists and is readable
   - Check file permissions on the target directory

3. **Slow indexing**:
   - Reduce `CHUNK_SIZE` for faster processing
   - Increase `PROCESSING_DELAY` to reduce system load
   - Monitor progress in the indexing status panel

4. **Out of memory**:
   - Use a smaller embedding model
   - Process fewer files at once
   - Increase system memory

5. **Files not being indexed**:
   - Check if file format is supported
   - Verify file permissions and accessibility
   - Monitor activity logs for error messages

6. **Application won't start**:
   ```bash
   # Clean up any stale processes and files
   ./cleanup.sh
   # Then try starting again
   ./run.sh
   ```

### Logs and Debugging

The application logs are stored in `./data/app.log`. For more detailed logging:

```bash
export LOG_LEVEL="DEBUG"
./run.sh
```

You can also check the application status:
```bash
# Check if application is running
ps aux | grep uvicorn

# View recent logs
tail -f ./data/app.log
```

### OAuth Configuration

If using Microsoft OneDrive/SharePoint integration:
1. Place your OAuth tokens in `.tokens.json`
2. Ensure proper permissions for Files.Read, Files.ReadWrite, etc.
3. Monitor token expiration and refresh as needed

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Docling](https://github.com/DS4SD/docling) for document processing
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [Sentence Transformers](https://www.sbert.net/) for embeddings
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Watchdog](https://python-watchdog.readthedocs.io/) for file system monitoring

## 🚀 Next Steps

- Add support for more file formats (CSV, JSON, XML)
- Implement document preview functionality
- Add user authentication and multi-user support
- Create Docker containerization
- Add automated testing suite
- Implement document versioning
- Add advanced search filters and faceting
