#!/bin/bash

# Configuration
DATA_DIR="./data"
PID_FILE="$DATA_DIR/app.pid"
LOCK_FILE="$DATA_DIR/app.lock"
LOG_FILE="$DATA_DIR/app.log"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Function to check if process is running
is_process_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    
    if kill -0 "$pid" 2>/dev/null; then
        return 0  # Process is running
    else
        return 1  # Process is not running
    fi
}

# Function to cleanup stale files
cleanup_stale_files() {
    echo "Cleaning up stale files..."
    rm -f "$PID_FILE" "$LOCK_FILE"
}

# Function to start the application
start_application() {
    echo "Starting application..."
    
    # Create lock file
    echo "$(date): Application starting" > "$LOCK_FILE"
    
    # Start the application in background and capture PID
    (
        rm -rf .venv
        uv venv -p 3.12 .venv
        uv pip install -r requirements.txt
        SYFTBOX_ASSIGNED_PORT=${SYFTBOX_ASSIGNED_PORT:-9000}
        uv run uvicorn backend.main:app --host 0.0.0.0 --port $SYFTBOX_ASSIGNED_PORT --workers 1
    ) > "$LOG_FILE" 2>&1 &
    
    local app_pid=$!
    echo "$app_pid" > "$PID_FILE"
    
    echo "Application started with PID: $app_pid"
    echo "Logs available at: $LOG_FILE"
    echo "PID file: $PID_FILE"
}

# Main logic
echo "Checking for existing application instance..."

# Check if PID file exists
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null)
    echo "Found PID file with PID: $pid"
    
    # Check if process is actually running
    if is_process_running "$pid"; then
        echo "Application is already running with PID: $pid"
        echo "Skipping startup. Use './cleanup.sh' to stop the application."
        exit 0
    else
        echo "PID file exists but process is not running. Cleaning up stale files..."
        cleanup_stale_files
    fi
fi

# Check if lock file exists (additional safety check)
if [ -f "$LOCK_FILE" ]; then
    echo "Found lock file but no valid PID. Cleaning up..."
    cleanup_stale_files
fi

# Start the application
start_application 