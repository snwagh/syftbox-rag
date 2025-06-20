class RAGDocumentSearch {
    constructor() {
        this.currentTab = 'search';
        this.searchResults = [];
        this.stats = { total_documents: 0, watched_folders: 0 };
        this.watchedFolders = [];
        this.fileStructure = [];
        this.expandedFolders = new Set();
        this.selectedPaths = new Set();
        this.savedSelectedPaths = new Set();
        this.currentPath = '';
        this.indexingStatus = {
            isRunning: false,
            progress: 0,
            totalFiles: 0,
            completedFiles: 0,
            totalSizeMB: 0,
            processedSizeMB: 0,
            currentFile: null,
            currentFileProgress: 0,
            currentFileChunks: { processed: 0, total: 0 },
            logs: []
        };
        this.hasUnsavedChanges = false;
        this.fileTreeEventsBound = false; // Track if events are bound
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadStats();
        this.loadWatchedFolders();
        this.startStatusPolling();
        this.switchTab('search'); // Start with search tab
    }

    bindEvents() {
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Search functionality
        const searchBox = document.getElementById('searchBox');
        const searchBtn = document.getElementById('searchBtn');
        
        searchBox.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });
        
        searchBtn.addEventListener('click', () => {
            this.performSearch();
        });

        // Indexing status - clickable container
        const indexingStatusContainer = document.getElementById('indexingStatusContainer');
        const closeModalBtn = document.getElementById('closeModal');
        const modal = document.getElementById('indexingModal');
        
        indexingStatusContainer.addEventListener('click', () => {
            modal.style.display = 'flex';
        });
        
        closeModalBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Save changes functionality
        const saveChangesBtn = document.getElementById('saveChangesBtn');
        const discardChangesBtn = document.getElementById('discardChangesBtn');
        
        saveChangesBtn.addEventListener('click', () => {
            this.saveChanges();
        });
        
        discardChangesBtn.addEventListener('click', () => {
            this.discardChanges();
        });
        
        // Breadcrumb navigation
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('breadcrumb-item')) {
                const path = e.target.dataset.path;
                this.navigateToPath(path);
            }
        });
    }

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });
        
        // Load relevant data
        if (tabName === 'files') {
            this.loadFileStructure();
            this.loadWatchedFolders();
        }
    }

    async performSearch() {
        const query = document.getElementById('searchBox').value.trim();
        const limit = parseInt(document.getElementById('searchLimit').value) || 5;
        
        if (!query) {
            this.showMessage('Please enter a search query', 'error');
            return;
        }

        this.showLoading('searching');
        
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query, limit })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.searchResults = data.results;
            this.displaySearchResults(data);
            
        } catch (error) {
            console.error('Search error:', error);
            this.showMessage('Error performing search: ' + error.message, 'error');
        } finally {
            this.hideLoading('searching');
        }
    }

    displaySearchResults(data) {
        const resultsContainer = document.getElementById('searchResults');
        const statsContainer = document.getElementById('searchStats');
        
        // Update stats
        statsContainer.textContent = `Found ${data.results.length} results for "${data.query}"`;
        
        if (data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <h3>No results found</h3>
                    <p>Try a different search query or add more documents to your index.</p>
                </div>
            `;
            return;
        }
        
        // Display results
        resultsContainer.innerHTML = data.results.map((result, index) => `
            <div class="result-item">
                <div class="result-header">
                    <div class="result-filename">${this.escapeHtml(result.filename)}</div>
                    <div class="result-similarity">${(result.similarity * 100).toFixed(1)}%</div>
                </div>
                <div class="result-content" id="content-${index}">
                    ${this.highlightSearchTerms(this.escapeHtml(result.content), data.query)}
                </div>
                ${result.content.length > 200 ? `
                    <button class="expand-btn" onclick="ragApp.toggleExpand(${index})">
                        Show more
                    </button>
                ` : ''}
                <div class="result-meta">
                    <span>📄 Page ${result.page}</span>
                    <span>📁 ${this.escapeHtml(result.filepath)}</span>
                    <span>📏 ${this.formatFileSize(result.file_size)}</span>
                    <span>🕒 ${this.formatDate(result.modified_time)}</span>
                </div>
            </div>
        `).join('');
    }

    toggleExpand(index) {
        const contentEl = document.getElementById(`content-${index}`);
        const btnEl = contentEl.nextElementSibling;
        
        if (contentEl.classList.contains('expanded')) {
            contentEl.classList.remove('expanded');
            btnEl.textContent = 'Show more';
        } else {
            contentEl.classList.add('expanded');
            btnEl.textContent = 'Show less';
        }
    }

    async loadWatchedFolders() {
        try {
            const response = await fetch('/api/watched-folders');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.watchedFolders = data.folders;
            
            // Update saved selected paths to match watched folders
            this.savedSelectedPaths.clear();
            this.watchedFolders.forEach(folder => {
                this.savedSelectedPaths.add(folder);
            });
            
            // Reset selected paths to match saved state
            this.selectedPaths = new Set(this.savedSelectedPaths);
            this.hasUnsavedChanges = false;
            this.updateSaveSection();
            
        } catch (error) {
            console.error('Load folders error:', error);
            this.showMessage('Error loading watched folders: ' + error.message, 'error');
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.stats = data;
            this.displayStats();
            
        } catch (error) {
            console.error('Load stats error:', error);
            this.showMessage('Error loading statistics: ' + error.message, 'error');
        }
    }

    displayStats() {
        const totalDocsEl = document.getElementById('totalDocs');
        const watchedFoldersEl = document.getElementById('watchedFoldersCount');
        
        if (totalDocsEl) {
            totalDocsEl.textContent = this.stats.total_documents.toLocaleString();
        }
        
        if (watchedFoldersEl) {
            watchedFoldersEl.textContent = this.stats.watched_folders;
        }
    }

    showLoading(context) {
        if (context === 'saving') {
            const saveBtn = document.getElementById('saveChangesBtn');
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<span class="loading"></span> Saving...';
            }
        } else {
            const btn = document.getElementById('searchBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> Searching...';
            }
        }
    }

    hideLoading(context) {
        if (context === 'saving') {
            const saveBtn = document.getElementById('saveChangesBtn');
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = 'Save Changes';
            }
        } else {
            const btn = document.getElementById('searchBtn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Search';
            }
        }
    }

    showMessage(message, type = 'info') {
        // Create a temporary message element
        const messageEl = document.createElement('div');
        messageEl.className = `message message-${type}`;
        messageEl.textContent = message;
        messageEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'error' ? '#e74c3c' : type === 'success' ? '#27ae60' : '#3498db'};
            color: white;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(messageEl);
        
        // Remove after 3 seconds
        setTimeout(() => {
            messageEl.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.parentNode.removeChild(messageEl);
                }
            }, 300);
        }, 3000);
    }

    highlightSearchTerms(text, query) {
        if (!query) return text;
        
        const terms = query.toLowerCase().split(' ').filter(term => term.length > 2);
        let highlighted = text;
        
        terms.forEach(term => {
            const regex = new RegExp(`(${this.escapeRegex(term)})`, 'gi');
            highlighted = highlighted.replace(regex, '<mark>$1</mark>');
        });
        
        return highlighted;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatDate(timestamp) {
        if (!timestamp) return 'Unknown';
        return new Date(timestamp * 1000).toLocaleDateString();
    }

    async loadFileStructure(path = '') {
        const fileTree = document.getElementById('fileTree');
        
        // Show loading state
        fileTree.innerHTML = `
            <div class="loading-state">
                <div class="loading"></div>
                <span>Loading file structure...</span>
            </div>
        `;
        
        try {
            const endpoint = path ? '/api/file-structure' : '/api/file-structure/home';
            const requestData = path ? { path: path, expand_folders: false } : undefined;
            
            const response = await fetch(endpoint, {
                method: requestData ? 'POST' : 'GET',
                headers: requestData ? {
                    'Content-Type': 'application/json'
                } : {},
                body: requestData ? JSON.stringify(requestData) : undefined
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.fileStructure = data.structure;
            this.currentPath = data.path;
            
            this.updateBreadcrumb(data.path);
            this.renderFileTree();
            
        } catch (error) {
            console.error('Load file structure error:', error);
            fileTree.innerHTML = `
                <div class="error-state">
                    <span>Error loading file structure: ${error.message}</span>
                    <button class="retry-btn" onclick="ragApp.loadFileStructure('${path}')">Retry</button>
                </div>
            `;
        }
    }

    updateBreadcrumb(path) {
        const breadcrumb = document.getElementById('breadcrumb');
        const pathParts = path.split('/').filter(part => part);
        
        let breadcrumbHTML = '<span class="breadcrumb-item" data-path="">🏠 Home</span>';
        
        let currentPath = '';
        pathParts.forEach(part => {
            currentPath += '/' + part;
            breadcrumbHTML += `<span class="breadcrumb-item" data-path="${currentPath}">${part}</span>`;
        });
        
        breadcrumb.innerHTML = breadcrumbHTML;
    }

    renderFileTree() {
        const fileTree = document.getElementById('fileTree');
        
        // Preserve scroll position before re-rendering
        const scrollTop = fileTree.scrollTop;
        
        if (this.fileStructure.length === 0) {
            fileTree.innerHTML = `
                <div class="empty-state">
                    <h3>No items found</h3>
                    <p>This directory appears to be empty or inaccessible.</p>
                </div>
            `;
            return;
        }
        
        const treeHTML = this.buildFileTreeHTML(this.fileStructure);
        fileTree.innerHTML = treeHTML;
        
        // Restore scroll position after re-rendering
        // Use setTimeout to ensure DOM updates are complete
        setTimeout(() => {
            fileTree.scrollTop = scrollTop;
        }, 0);
        
        // Only bind event listeners once
        if (!this.fileTreeEventsBound) {
            this.bindFileTreeEvents();
            this.fileTreeEventsBound = true;
        }
    }

    buildFileTreeHTML(items, level = 0) {
        let html = '';
        
        items.forEach(item => {
            const isExpanded = this.expandedFolders.has(item.path);
            const hasChildren = item.children && item.children.length > 0;
            const indent = level > 0 ? `style="padding-left: ${level * 20 + 16}px;"` : '';
            
            // Determine checkbox state based on hierarchical logic
            let checkboxState = this.getCheckboxState(item);
            
            const icon = item.type === 'folder' ? '📁' : this.getFileIcon(item.name);
            
            html += `
                <div class="tree-item" data-path="${item.path}" data-type="${item.type}" ${indent}>
                    <div class="tree-expand ${hasChildren ? 'expandable' : ''} ${isExpanded ? 'expanded' : ''}"
                          data-path="${item.path}"></div>
                     
                    <div class="tree-checkbox ${checkboxState.partial ? 'partial' : ''}" data-path="${item.path}">
                        <input type="checkbox" 
                               ${checkboxState.checked ? 'checked' : ''}
                               data-path="${item.path}">
                        <div class="checkbox-custom"></div>
                    </div>
                     
                    <div class="tree-icon">${icon}</div>
                    <div class="tree-name" data-path="${item.path}" data-type="${item.type}">${item.name}</div>
                    <div class="tree-size">${item.size}</div>
                </div>
            `;
            
            // Add children if expanded
            if (isExpanded && hasChildren) {
                html += this.buildFileTreeHTML(item.children, level + 1);
            }
        });
        
        return html;
    }

    getCheckboxState(item) {
        // Check if this item is directly selected
        const isDirectlySelected = this.selectedPaths.has(item.path);
        
        // Check if this item is inherited from a selected parent
        const isInheritedSelected = this.isInheritedFromParent(item.path);
        
        if (item.type === 'file') {
            // Files can be directly selected or inherited from parent folder
            return { 
                checked: isDirectlySelected || isInheritedSelected, 
                partial: false 
            };
        }
        
        // For folders, check hierarchical state
        if (isDirectlySelected) {
            // Folder is directly selected (full selection)
            return { checked: true, partial: false };
        }
        
        if (isInheritedSelected) {
            // Folder is inherited from a parent selection
            return { checked: true, partial: false };
        }
        
        // Check if any children or descendants are selected
        const hasSelectedDescendants = this.hasSelectedDescendants(item.path);
        
        if (hasSelectedDescendants) {
            // Some descendants are selected (partial selection)
            return { checked: false, partial: true };
        }
        
        // Nothing selected
        return { checked: false, partial: false };
    }

    isInheritedFromParent(itemPath) {
        // Check if any parent folder is selected
        return Array.from(this.selectedPaths).some(selectedPath => {
            // Check if the selected path is a parent of this item
            return itemPath.startsWith(selectedPath + '/') && selectedPath !== itemPath;
        });
    }

    hasSelectedDescendants(folderPath) {
        // Check if any selected paths are descendants of this folder
        return Array.from(this.selectedPaths).some(selectedPath => {
            return selectedPath.startsWith(folderPath + '/');
        });
    }

    toggleSelection(path, checked) {
        if (checked) {
            // When checking a folder, remove all its descendants from selection
            // and add just the folder itself (represents selecting everything in it)
            if (this.isFolder(path)) {
                this.removeDescendantsFromSelection(path);
            }
            this.selectedPaths.add(path);
        } else {
            // When unchecking, remove the item and any descendants
            this.selectedPaths.delete(path);
            this.removeDescendantsFromSelection(path);
        }
        
        // Also remove any ancestors that are now redundant
        this.cleanupRedundantAncestors(path);
        
        // Check if changes have been made
        this.checkForUnsavedChanges();
        
        // Re-render to update checkbox states
        this.renderFileTree();
    }

    isFolder(path) {
        // Check if path is a folder by looking at current file structure
        const item = this.findItemByPath(this.fileStructure, path);
        return item && item.type === 'folder';
    }

    removeDescendantsFromSelection(folderPath) {
        // Remove any selected paths that are descendants of this folder
        const toRemove = Array.from(this.selectedPaths).filter(selectedPath => 
            selectedPath.startsWith(folderPath + '/')
        );
        toRemove.forEach(path => this.selectedPaths.delete(path));
    }

    cleanupRedundantAncestors(path) {
        // If we select a folder, remove any parent folders that contain this folder
        const pathParts = path.split('/');
        for (let i = pathParts.length - 1; i > 0; i--) {
            const ancestorPath = pathParts.slice(0, i).join('/');
            if (this.selectedPaths.has(ancestorPath)) {
                // If an ancestor is selected, this child selection is redundant
                this.selectedPaths.delete(ancestorPath);
            }
        }
    }

    findItemByPath(items, targetPath) {
        for (const item of items) {
            if (item.path === targetPath) {
                return item;
            }
            if (item.children && item.children.length > 0) {
                const found = this.findItemByPath(item.children, targetPath);
                if (found) return found;
            }
        }
        return null;
    }

    bindFileTreeEvents() {
        const fileTree = document.getElementById('fileTree');
        
        // Don't replace the entire element - this destroys scroll position
        // Instead, remove existing listeners more carefully
        
        // Use event delegation for all tree interactions
        fileTree.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // Handle checkbox container clicks (but not the checkbox itself)
            if (e.target.closest('.tree-checkbox') && e.target.type !== 'checkbox') {
                const checkbox = e.target.closest('.tree-checkbox').querySelector('input[type="checkbox"]');
                if (checkbox) {
                    // Trigger the checkbox
                    checkbox.click();
                }
                return;
            }
            
            // Handle expand/collapse clicks
            if (e.target.classList.contains('tree-expand') && e.target.classList.contains('expandable')) {
                const path = e.target.dataset.path;
                if (path) {
                    this.toggleFolder(path);
                }
                return;
            }
            
            // Handle folder navigation clicks
            if (e.target.classList.contains('tree-name')) {
                const path = e.target.dataset.path;
                const type = e.target.dataset.type;
                if (path && type === 'folder') {
                    this.navigateToPath(path);
                }
                return;
            }
        });
        
        // Handle checkbox change events - update local state only
        fileTree.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                e.stopPropagation();
                const path = e.target.dataset.path;
                if (path) {
                    this.toggleSelection(path, e.target.checked);
                }
            }
        });
    }

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const iconMap = {
            'pdf': '📄',
            'doc': '📝', 'docx': '📝',
            'txt': '📝', 'md': '📝',
            'html': '🌐', 'htm': '🌐',
            'pptx': '📊', 'ppt': '📊',
            'xlsx': '📈', 'xls': '📈',
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
            'mp4': '🎬', 'avi': '🎬', 'mov': '🎬',
            'mp3': '🎵', 'wav': '🎵',
            'zip': '📦', 'rar': '📦', '7z': '📦'
        };
        return iconMap[ext] || '📄';
    }

    toggleFolder(path) {
        // Preserve scroll position during folder toggle
        const fileTree = document.getElementById('fileTree');
        const scrollTop = fileTree.scrollTop;
        
        if (this.expandedFolders.has(path)) {
            this.expandedFolders.delete(path);
        } else {
            this.expandedFolders.add(path);
        }
        
        this.renderFileTree();
        
        // Restore scroll position after toggle
        // Use setTimeout to ensure DOM updates are complete
        setTimeout(() => {
            fileTree.scrollTop = scrollTop;
        }, 0);
    }

    navigateToPath(path) {
        this.loadFileStructure(path);
    }

    // Indexing status methods
    async startStatusPolling() {
        // Poll indexing status every 500ms for very responsive progress updates during chunking
        setInterval(async () => {
            await this.updateIndexingStatus();
        }, 500);
    }

    async updateIndexingStatus() {
        try {
            const response = await fetch('/api/indexing-status');
            if (response.ok) {
                const status = await response.json();
                this.indexingStatus = status;
                this.updateIndexingDisplay();
                
                // Auto-update stats during active indexing for real-time chunk count
                if (status.isRunning) {
                    await this.loadStats();
                }
            }
        } catch (error) {
            // Silent fail for status updates
        }
    }

    updateIndexingDisplay() {
        const statusEl = document.getElementById('indexingStatus');
        const statusProgress = document.getElementById('statusProgress');
        const statusProgressFill = document.getElementById('statusProgressFill');
        const statusProgressText = document.getElementById('statusProgressText');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const logsContainer = document.getElementById('logsContainer');

        // Get simplified progress data
        let progress = this.indexingStatus.progress || 0;
        let statusText = 'Idle';
        
        if (this.indexingStatus.isRunning) {
            const totalFiles = this.indexingStatus.totalFiles || 0;
            const completedFiles = this.indexingStatus.completedFiles || 0;
            const totalOps = this.indexingStatus.totalOperations || 0;
            const completedOps = this.indexingStatus.completedOperations || 0;
            const currentFile = this.indexingStatus.currentFile;
            const currentFileProgress = this.indexingStatus.currentFileProgress || 0;
            const currentFileChunks = this.indexingStatus.currentFileChunks || {processed: 0, total: 0};
            
            // Build status text based on current activity
            if (currentFile && currentFileChunks.total > 0) {
                statusText = `Processing ${currentFile} (${currentFileChunks.processed}/${currentFileChunks.total} chunks)`;
            } else if (currentFile && currentFileChunks.total === 0) {
                // File is being processed but chunks haven't been determined yet (parsing phase)
                statusText = `Parsing ${currentFile} (preparing for chunking...)`;
            } else if (completedFiles === 0 && totalFiles > 0) {
                statusText = `Starting indexing... (${totalFiles} files found)`;
            } else if (completedFiles < totalFiles) {
                if (totalOps > 1) {
                    statusText = `Processing (${completedOps}/${totalOps} operations, ${completedFiles}/${totalFiles} files)`;
                } else {
                    statusText = `Processing (${completedFiles}/${totalFiles} files)`;
                }
            } else {
                statusText = 'Finalizing...';
            }
        }

        // Update status text and inline progress
        if (this.indexingStatus.isRunning) {
            statusEl.textContent = statusText;
            statusEl.style.color = '#f39c12';
            
            // Show inline progress
            if (statusProgress) {
                statusProgress.style.display = 'flex';
                statusProgressFill.style.width = `${Math.min(progress, 100)}%`;
                statusProgressText.textContent = `${Math.round(Math.min(progress, 100))}%`;
            }
        } else {
            statusEl.textContent = 'Idle';
            statusEl.style.color = '#27ae60';
            
            // Hide inline progress
            if (statusProgress) {
                statusProgress.style.display = 'none';
            }
        }

        // Update modal progress bar
        if (progressFill) {
            progressFill.style.width = `${Math.min(progress, 100)}%`;
        }
        
        if (progressText) {
            const processedMB = this.indexingStatus.processedSizeMB || 0;
            const totalMB = this.indexingStatus.totalSizeMB || 0;
            const completedFiles = this.indexingStatus.completedFiles || 0;
            const totalFiles = this.indexingStatus.totalFiles || 0;
            const totalOps = this.indexingStatus.totalOperations || 0;
            const completedOps = this.indexingStatus.completedOperations || 0;
            const currentFile = this.indexingStatus.currentFile;
            const currentFileProgress = this.indexingStatus.currentFileProgress || 0;
            const currentFileChunks = this.indexingStatus.currentFileChunks || {processed: 0, total: 0};
            
            if (this.indexingStatus.isRunning) {
                let progressDetails = [];
                
                // Add operation info if multiple operations
                if (totalOps > 1) {
                    progressDetails.push(`${completedOps}/${totalOps} operations`);
                }
                
                // Add file progress
                if (totalFiles > 0) {
                    progressDetails.push(`${completedFiles}/${totalFiles} files`);
                }
                
                // Add current file chunk progress if processing
                if (currentFile && currentFileChunks.total > 0) {
                    progressDetails.push(`Current: ${currentFileChunks.processed}/${currentFileChunks.total} chunks`);
                } else if (currentFile && currentFileChunks.total === 0) {
                    progressDetails.push(`Parsing: ${currentFile}`);
                }
                
                // Add size progress
                if (totalMB > 0) {
                    progressDetails.push(`${processedMB.toFixed(1)}/${totalMB.toFixed(1)} MB`);
                }
                
                progressText.textContent = `${Math.round(Math.min(progress, 100))}% Complete (${progressDetails.join(', ')})`;
            } else {
                if (totalOps > 0 && completedOps === totalOps) {
                    progressText.textContent = `Completed ${totalOps} operation(s) - ${totalFiles} files, ${totalMB.toFixed(1)} MB`;
                } else {
                    progressText.textContent = 'No active indexing';
                }
            }
        }

        // Update logs
        if (logsContainer && this.indexingStatus.logs) {
            const logs = this.indexingStatus.logs.slice(-10).reverse(); // Last 10 logs, newest first
            logsContainer.innerHTML = logs.length > 0 
                ? logs.map(log => `<div class="log-entry ${log.type || ''}">${log.message}</div>`).join('')
                : '<div class="log-entry">No recent activity</div>';
        }
    }

    checkForUnsavedChanges() {
        // Compare current selection with saved selection
        const currentPaths = Array.from(this.selectedPaths).sort();
        const savedPaths = Array.from(this.savedSelectedPaths).sort();
        
        this.hasUnsavedChanges = JSON.stringify(currentPaths) !== JSON.stringify(savedPaths);
        this.updateSaveSection();
    }

    updateSaveSection() {
        const saveSection = document.getElementById('saveSection');
        if (saveSection) {
            if (this.hasUnsavedChanges) {
                saveSection.style.display = 'block';
            } else {
                saveSection.style.display = 'none';
            }
        }
    }

    async saveChanges() {
        try {
            this.showLoading('saving');
            
            // Calculate which paths to add and remove
            const pathsToAdd = Array.from(this.selectedPaths).filter(path => 
                !this.savedSelectedPaths.has(path));
            const pathsToRemove = Array.from(this.savedSelectedPaths).filter(path => 
                !this.selectedPaths.has(path));

            // Update saved state immediately (optimistic update)
            this.savedSelectedPaths = new Set(this.selectedPaths);
            this.hasUnsavedChanges = false;
            this.updateSaveSection();
            
            // Show success message immediately
            if (pathsToAdd.length > 0) {
                this.showMessage(`Changes saved! Indexing ${pathsToAdd.length} new path(s) in background...`, 'success');
            } else {
                this.showMessage('Changes saved successfully!', 'success');
            }
            
            // Perform the actual backend updates in the background (non-blocking)
            this.performBackgroundUpdates(pathsToAdd, pathsToRemove);
            
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showMessage('Error saving changes: ' + error.message, 'error');
            // Revert optimistic update on error
            this.loadWatchedFolders();
        } finally {
            this.hideLoading('saving');
        }
    }

    async performBackgroundUpdates(pathsToAdd, pathsToRemove) {
        try {
            // Update selections in background
            if (pathsToAdd.length > 0) {
                await this.updateFolderSelection(pathsToAdd, true);
            }
            if (pathsToRemove.length > 0) {
                await this.updateFolderSelection(pathsToRemove, false);
            }
            
            // Update stats without refreshing the file tree
            await this.loadStats();
            
        } catch (error) {
            console.error('Background update error:', error);
            this.showMessage('Warning: Some changes may not have been applied properly.', 'error');
            // Refresh the watched folders to sync state
            await this.loadWatchedFolders();
        }
    }

    discardChanges() {
        // Reset to saved state
        this.selectedPaths = new Set(this.savedSelectedPaths);
        this.hasUnsavedChanges = false;
        this.updateSaveSection();
        this.renderFileTree(); // Re-render to update checkboxes
        this.showMessage('Changes discarded', 'info');
    }

    async updateFolderSelection(paths, checked) {
        try {
            const response = await fetch('/api/folder-selection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    paths: paths,
                    checked: checked
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            throw error;
        }
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    mark {
        background: #f1c40f;
        padding: 1px 2px;
        border-radius: 2px;
    }
`;
document.head.appendChild(style);

// Initialize the app when DOM is loaded
let ragApp;
document.addEventListener('DOMContentLoaded', () => {
    ragApp = new RAGDocumentSearch();
}); 