from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import asyncio
from typing import Set, List, Dict, Any
from datetime import datetime
from .config import Config
import uuid

class IndexingOperation:
    """Represents a single indexing operation (folder or file)"""
    def __init__(self, operation_id: str, operation_type: str, path: str, files: List[tuple]):
        self.id = operation_id
        self.type = operation_type  # 'folder' or 'file'
        self.path = path
        self.files = files  # List of (file_path, size_mb) tuples
        self.total_files = len(files)
        self.completed_files = 0
        self.total_size_mb = sum(size for _, size in files)
        self.processed_size_mb = 0
        self.status = "pending"  # pending, active, completed, error
        self.current_file = None
        self.current_file_progress = 0.0  # Progress of current file (0.0 to 1.0)
        self.current_file_chunks_total = 0
        self.current_file_chunks_processed = 0
        self.start_time = None
        self.end_time = None
        
    def get_overall_progress(self) -> float:
        """Get overall progress as percentage (0.0 to 1.0)"""
        if self.total_files == 0:
            return 1.0
        
        # Completed files contribute 1.0 each, current file contributes its partial progress
        total_progress = self.completed_files + self.current_file_progress
        return min(total_progress / self.total_files, 1.0)
    
    def update_current_file_progress(self, chunks_processed: int, total_chunks: int):
        """Update progress of the currently processing file"""
        self.current_file_chunks_processed = chunks_processed
        self.current_file_chunks_total = total_chunks
        if total_chunks > 0:
            self.current_file_progress = chunks_processed / total_chunks
        else:
            self.current_file_progress = 0.0
    
    def complete_current_file(self):
        """Mark the current file as completed"""
        self.completed_files += 1
        self.current_file_progress = 0.0
        self.current_file_chunks_total = 0
        self.current_file_chunks_processed = 0
        self.current_file = None

class GlobalIndexingManager:
    """Manages all indexing operations globally"""
    def __init__(self, vector_store, doc_processor, embedding_gen):
        self.vector_store = vector_store
        self.doc_processor = doc_processor
        self.embedding_gen = embedding_gen
        self.operations: Dict[str, IndexingOperation] = {}
        self.operation_queue = asyncio.Queue()
        self.is_processing = False
        self.global_status = {
            "isRunning": False,
            "operations": [],
            "totalOperations": 0,
            "completedOperations": 0,
            "totalFiles": 0,
            "processedFiles": 0,
            "totalSizeMB": 0,
            "processedSizeMB": 0,
            "estimatedTotalChunks": 0,
            "actualTotalChunks": 0,
            "processedChunks": 0,
            "estimatedChunks": True,
            "progress": 0,
            "logs": []
        }
        self._processor_task = None
        
    def add_operation(self, operation_type: str, path: str, files: List[tuple]) -> str:
        """Add a new indexing operation"""
        operation_id = str(uuid.uuid4())
        operation = IndexingOperation(operation_id, operation_type, path, files)
        self.operations[operation_id] = operation
        
        # Add to queue for processing
        asyncio.create_task(self.operation_queue.put(operation_id))
        
        # Update global status
        self._update_global_status()
        
        # Start processor if not running
        if not self.is_processing:
            self._start_processor()
            
        self._log_activity(f"Added {operation_type} for indexing: {path} ({len(files)} files)", "info")
        return operation_id
    
    def _start_processor(self):
        """Start the global operation processor"""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_operations())
    
    async def _process_operations(self):
        """Process operations from the queue"""
        self.is_processing = True
        self.global_status["isRunning"] = True
        self._update_global_status()
        
        try:
            while True:
                try:
                    # Wait for next operation with timeout
                    operation_id = await asyncio.wait_for(self.operation_queue.get(), timeout=1.0)
                    operation = self.operations[operation_id]
                    
                    # Process this operation
                    await self._process_single_operation(operation)
                    
                except asyncio.TimeoutError:
                    # Check if there are any active operations
                    active_ops = [op for op in self.operations.values() if op.status in ["pending", "active"]]
                    if not active_ops:
                        break  # No more work to do
                        
        except Exception as e:
            self._log_activity(f"Error in operation processor: {str(e)}", "error")
        
        finally:
            self.is_processing = False
            self.global_status["isRunning"] = False
            self._update_global_status()
            self._log_activity("Completed all indexing operations", "success")
    
    async def _process_single_operation(self, operation: IndexingOperation):
        """Process a single indexing operation"""
        operation.status = "active"
        operation.start_time = datetime.now()
        self._update_global_status()
        
        try:
            for i, (file_path, size_mb) in enumerate(operation.files):
                operation.current_file = os.path.basename(file_path)
                operation.update_current_file_progress(0, 0)  # Reset current file progress
                self._update_global_status()
                
                # Process this file
                await self._process_single_file(operation, file_path, size_mb, i + 1)
                
                # Complete this file and update progress
                operation.complete_current_file()
                operation.processed_size_mb += size_mb
                
                # Update global status after each file completion
                self._update_global_status()
                
                # Small delay to allow other tasks
                await asyncio.sleep(0.01)
            
            operation.status = "completed"
            operation.end_time = datetime.now()
            
        except Exception as e:
            operation.status = "error"
            operation.end_time = datetime.now()
            self._log_activity(f"Error processing {operation.path}: {str(e)}", "error")
        
        finally:
            operation.current_file = None
            self._update_global_status()
    
    async def _process_single_file(self, operation: IndexingOperation, file_path: str, size_mb: float, file_num: int) -> int:
        """Process a single file and return number of chunks"""
        try:
            # Show that we're starting to process this file
            operation.current_file = os.path.basename(file_path)
            operation.update_current_file_progress(0, 0)
            self._update_global_status()
            self._log_activity(f"Starting {os.path.basename(file_path)} ({file_num}/{operation.total_files}) - Computing file hash...", "processing")
            
            # Check if file already processed and unchanged
            file_hash = await asyncio.to_thread(self.doc_processor._get_file_hash, file_path)
            
            self._log_activity(f"Checking if {os.path.basename(file_path)} already exists in database...", "processing")
            if await asyncio.to_thread(self.vector_store.file_exists, file_hash):
                self._log_activity(f"Skipped (already indexed): {os.path.basename(file_path)}", "info")
                return 0
            
            # Remove old version if exists
            self._log_activity(f"Removing old version of {os.path.basename(file_path)} from database...", "processing")
            await asyncio.to_thread(self.vector_store.delete_by_file, file_path)
            
            # Process document - this is the major bottleneck
            self._log_activity(f"Parsing document {os.path.basename(file_path)} (this may take a while for large files)...", "processing")
            chunks = await asyncio.to_thread(self.doc_processor.process_document, file_path)
            
            if not chunks:
                self._log_activity(f"No content extracted from {os.path.basename(file_path)}", "warning")
                return 0
            
            # Initialize progress tracking for this file
            total_chunks = len(chunks)
            operation.update_current_file_progress(0, total_chunks)
            self._update_global_status()
            self._log_activity(f"Extracted {total_chunks} chunks from {os.path.basename(file_path)} - generating embeddings...", "processing")
            
            # Process chunks with live progress updates
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                # Generate embedding
                chunk['embedding'] = await asyncio.to_thread(self.embedding_gen.embed_text, chunk['text'])
                processed_chunks.append(chunk)
                
                # Update file progress (chunks processed so far)
                chunks_processed = i + 1
                operation.update_current_file_progress(chunks_processed, total_chunks)
                
                # Update global status every few chunks or on last chunk for responsiveness
                if (chunks_processed % 3) == 0 or chunks_processed == total_chunks:
                    self._update_global_status()
                    # Small delay for UI responsiveness
                    await asyncio.sleep(0.02)
            
            # Add all chunks to vector store
            self._log_activity(f"Storing {len(processed_chunks)} chunks in database...", "processing")
            await asyncio.to_thread(self.vector_store.add_documents, processed_chunks)
            
            self._log_activity(f"Indexed: {os.path.basename(file_path)} ({len(chunks)} chunks)", "success")
            return len(chunks)
            
        except Exception as e:
            self._log_activity(f"Error processing {os.path.basename(file_path)}: {str(e)}", "error")
            return 0
    
    def _update_global_status(self):
        """Update the global indexing status with file-based progress tracking"""
        # Count operations by status
        active_ops = [op for op in self.operations.values() if op.status == "active"]
        completed_ops = [op for op in self.operations.values() if op.status == "completed"]
        pending_ops = [op for op in self.operations.values() if op.status == "pending"]
        
        # Calculate totals across all operations
        total_files = sum(op.total_files for op in self.operations.values())
        completed_files = sum(op.completed_files for op in self.operations.values())
        total_size_mb = sum(op.total_size_mb for op in self.operations.values())
        processed_size_mb = sum(op.processed_size_mb for op in self.operations.values())
        
        # Calculate global progress based on file completion with live updates
        global_progress = 0.0
        if total_files > 0:
            # Sum up progress from all operations
            total_progress_sum = sum(op.get_overall_progress() * op.total_files for op in self.operations.values())
            global_progress = (total_progress_sum / total_files) * 100
        
        # Get current file info for display
        current_file = None
        current_file_progress = 0
        current_file_chunks = {"processed": 0, "total": 0}
        
        for op in active_ops:
            if op.current_file:
                current_file = op.current_file
                current_file_progress = op.current_file_progress * 100
                current_file_chunks = {
                    "processed": op.current_file_chunks_processed,
                    "total": op.current_file_chunks_total
                }
                break
        
        # Update global status
        self.global_status.update({
            "isRunning": len(active_ops) > 0 or len(pending_ops) > 0,
            "totalOperations": len(self.operations),
            "completedOperations": len(completed_ops),
            "totalFiles": total_files,
            "completedFiles": completed_files,
            "totalSizeMB": total_size_mb,
            "processedSizeMB": processed_size_mb,
            "progress": min(global_progress, 100),
            "currentFile": current_file,
            "currentFileProgress": current_file_progress,
            "currentFileChunks": current_file_chunks,
            "operations": [
                {
                    "id": op.id,
                    "type": op.type,
                    "path": op.path,
                    "status": op.status,
                    "currentFile": op.current_file,
                    "fileProgress": op.get_overall_progress() * 100,
                    "completedFiles": op.completed_files,
                    "totalFiles": op.total_files,
                    "currentFileChunks": {
                        "processed": op.current_file_chunks_processed,
                        "total": op.current_file_chunks_total
                    }
                }
                for op in self.operations.values()
            ]
        })
    
    def _log_activity(self, message: str, log_type: str = "info"):
        """Log activity to global status"""
        log_entry = {
            "message": message,
            "type": log_type,
            "timestamp": datetime.now().isoformat()
        }
        
        self.global_status["logs"].append(log_entry)
        
        # Keep only last 50 logs
        if len(self.global_status["logs"]) > 50:
            self.global_status["logs"] = self.global_status["logs"][-50:]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current global indexing status"""
        return self.global_status.copy()
    
    def cleanup_completed_operations(self, max_age_hours: int = 24):
        """Clean up old completed operations"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        to_remove = []
        
        for op_id, operation in self.operations.items():
            if (operation.status in ["completed", "error"] and 
                operation.end_time and 
                operation.end_time.timestamp() < cutoff_time):
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self.operations[op_id]
        
        if to_remove:
            self._update_global_status()

class DocumentFileHandler(FileSystemEventHandler):
    def __init__(self, vector_store, doc_processor, embedding_gen):
        self.vector_store = vector_store
        self.doc_processor = doc_processor
        self.embedding_gen = embedding_gen
        self.processing_queue = asyncio.Queue()
        
    def on_modified(self, event):
        if not event.is_directory:
            asyncio.create_task(self._process_file_change(event.src_path, 'modified'))
    
    def on_created(self, event):
        if not event.is_directory:
            asyncio.create_task(self._process_file_change(event.src_path, 'created'))
    
    def on_deleted(self, event):
        if not event.is_directory:
            asyncio.create_task(self._process_file_change(event.src_path, 'deleted'))
    
    async def _process_file_change(self, file_path: str, change_type: str):
        """Process file changes asynchronously"""
        await self.processing_queue.put((file_path, change_type))

class FileWatcher:
    def __init__(self, vector_store, doc_processor, embedding_gen):
        self.vector_store = vector_store
        self.doc_processor = doc_processor
        self.embedding_gen = embedding_gen
        
        # Load persistent configuration from vector store
        self.watched_folders: Set[str] = self.vector_store.load_watched_folders()
        self.watched_files: Set[str] = self.vector_store.load_watched_files()
        self.watched_directories: Set[str] = set()  # Track directories being watched by observer
        
        self.observer = Observer()
        self.handler = DocumentFileHandler(vector_store, doc_processor, embedding_gen)
        self._queue_task = None
        
        # Initialize global indexing manager
        self.indexing_manager = GlobalIndexingManager(vector_store, doc_processor, embedding_gen)
        
        # Load initial logs from persistent storage (if any)
        persistent_status = self.vector_store.load_indexing_status()
        if persistent_status.get("logs"):
            self.indexing_manager.global_status["logs"] = persistent_status["logs"][-50:]  # Keep last 50
        
        # Restore watchers for existing folders and files
        self._restore_watchers()
        
    def _restore_watchers(self):
        """Restore file watchers for persistent folders and files"""
        try:
            # Restore folder watchers
            for folder_path in self.watched_folders.copy():
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    if folder_path not in self.watched_directories:
                        self.observer.schedule(self.handler, folder_path, recursive=True)
                        self.watched_directories.add(folder_path)
                else:
                    # Remove non-existent folders
                    self.watched_folders.discard(folder_path)
                    self._persist_watched_folders()
            
            # Restore file watchers
            for file_path in self.watched_files.copy():
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    parent_dir = os.path.dirname(file_path)
                    if parent_dir not in self.watched_directories:
                        self.observer.schedule(self.handler, parent_dir, recursive=False)
                        self.watched_directories.add(parent_dir)
                else:
                    # Remove non-existent files
                    self.watched_files.discard(file_path)
                    self._persist_watched_files()
            
            # Start observer if we have watched paths
            if self.watched_folders or self.watched_files:
                if not self.observer.is_alive():
                    self.observer.start()
                    
        except Exception as e:
            print(f"Error restoring watchers: {e}")
    
    def _persist_watched_folders(self):
        """Save watched folders to persistent storage (async scheduled)"""
        asyncio.create_task(self._persist_watched_folders_async())
    
    async def _persist_watched_folders_async(self):
        """Async persistence for watched folders"""
        try:
            await asyncio.to_thread(self.vector_store.save_watched_folders, self.watched_folders)
        except Exception as e:
            print(f"Error persisting watched folders: {e}")
    
    def _persist_watched_files(self):
        """Save watched files to persistent storage (async scheduled)"""
        asyncio.create_task(self._persist_watched_files_async())
    
    async def _persist_watched_files_async(self):
        """Async persistence for watched files"""
        try:
            await asyncio.to_thread(self.vector_store.save_watched_files, self.watched_files)
        except Exception as e:
            print(f"Error persisting watched files: {e}")
        
    def start_processing(self):
        """Start the queue processing task"""
        if self._queue_task is None:
            self._queue_task = asyncio.create_task(self._process_queue())
    
    async def add_watch_folder(self, folder_path: str):
        """Add folder to watch list and start background indexing"""
        if not os.path.exists(folder_path):
            raise ValueError(f"Folder does not exist: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        self.watched_folders.add(folder_path)
        self._persist_watched_folders()  # Persist immediately
        
        # Only add directory watch if not already watching
        if folder_path not in self.watched_directories:
            self.observer.schedule(self.handler, folder_path, recursive=True)
            self.watched_directories.add(folder_path)
        
        if not self.observer.is_alive():
            self.observer.start()
        
        # Start queue processing if not already started
        self.start_processing()
        
        # Scan folder and add to global indexing manager
        await self._add_folder_to_indexing(folder_path)
    
    async def add_watch_file(self, file_path: str):
        """Add individual file to watch list and start background indexing"""
        if not os.path.exists(file_path):
            raise ValueError(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a file: {file_path}")
        
        if not self.doc_processor.is_supported(file_path):
            raise ValueError(f"File type not supported: {file_path}")
        
        self.watched_files.add(file_path)
        self._persist_watched_files()  # Persist immediately
        
        # Watch the parent directory to catch file changes
        parent_dir = os.path.dirname(file_path)
        if parent_dir not in self.watched_directories:
            self.observer.schedule(self.handler, parent_dir, recursive=False)
            self.watched_directories.add(parent_dir)
        
        if not self.observer.is_alive():
            self.observer.start()
        
        # Start queue processing if not already started
        self.start_processing()
        
        # Add file to global indexing manager
        await self._add_file_to_indexing(file_path)
    
    async def _add_folder_to_indexing(self, folder_path: str):
        """Add folder contents to global indexing manager"""
        supported_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.doc_processor.is_supported(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        size_mb = file_size / (1024 * 1024)  # Convert to MB
                        supported_files.append((file_path, size_mb))
                    except OSError:
                        # Skip files we can't access
                        continue
        
        if supported_files:
            self.indexing_manager.add_operation("folder", folder_path, supported_files)
    
    async def _add_file_to_indexing(self, file_path: str):
        """Add single file to global indexing manager"""
        try:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            self.indexing_manager.add_operation("file", file_path, [(file_path, size_mb)])
        except OSError as e:
            raise ValueError(f"Cannot access file: {e}")
    
    async def remove_watch_path(self, path: str):
        """Remove a path (folder or file) from watch list"""
        if path in self.watched_folders:
            self.watched_folders.remove(path)
            self._persist_watched_folders()  # Persist immediately
            # Remove documents from this folder (async)
            await asyncio.to_thread(self.vector_store.delete_by_file_prefix, path)
            self.indexing_manager._log_activity(f"Removed folder from watch list: {path}", "success")
        
        if path in self.watched_files:
            self.watched_files.remove(path)
            self._persist_watched_files()  # Persist immediately
            # Remove this specific file (async)
            await asyncio.to_thread(self.vector_store.delete_by_file, path)
            self.indexing_manager._log_activity(f"Removed file from watch list: {path}", "success")
    
    async def _process_queue(self):
        """Process file change queue"""
        while True:
            try:
                file_path, change_type = await self.handler.processing_queue.get()
                
                # Only process files that are explicitly watched or in watched folders
                should_process = False
                
                if file_path in self.watched_files:
                    should_process = True
                else:
                    for folder in self.watched_folders:
                        if file_path.startswith(folder):
                            should_process = True
                            break
                
                if not should_process:
                    continue
                
                if change_type == 'deleted':
                    await asyncio.to_thread(self.vector_store.delete_by_file, file_path)
                    self.indexing_manager._log_activity(f"Removed from index: {os.path.basename(file_path)}", "success")
                else:
                    # Add delay to avoid processing partial writes
                    await asyncio.sleep(Config.PROCESSING_DELAY)
                    if os.path.exists(file_path) and self.doc_processor.is_supported(file_path):
                        await self._add_file_to_indexing(file_path)
                        
            except Exception as e:
                error_msg = f"Error in processing queue: {str(e)}"
                self.indexing_manager._log_activity(error_msg, "error")
                print(error_msg)
                await asyncio.sleep(1)
    
    def get_watched_folders(self) -> List[str]:
        """Get all watched paths (folders and files)"""
        return list(self.watched_folders) + list(self.watched_files)
    
    def get_indexing_status(self) -> Dict[str, Any]:
        """Get current global indexing status"""
        status = self.indexing_manager.get_status()
        
        # Persist logs periodically (every 10 logs)
        if len(status["logs"]) % 10 == 0:
            asyncio.create_task(self._persist_logs_async(status))
        
        return status
    
    async def _persist_logs_async(self, status: Dict[str, Any]):
        """Async persistence for logs"""
        try:
            # Create a minimal status object for persistence
            persistent_status = {"logs": status["logs"]}
            await asyncio.to_thread(self.vector_store.save_indexing_status, persistent_status)
        except Exception as e:
            print(f"Error persisting logs: {e}")
    
    def stop(self):
        """Stop the file watcher"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        
        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()
        
        # Clean up indexing manager
        self.indexing_manager.cleanup_completed_operations()