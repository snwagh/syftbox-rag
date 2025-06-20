#!/bin/bash

# Configuration
DATA_DIR="./data"
PID_FILE="$DATA_DIR/app.pid"
LOCK_FILE="$DATA_DIR/app.lock"
LOG_FILE="$DATA_DIR/app.log"

echo "Stopping application..."

# Check if PID file exists
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null)
    echo "Found PID: $pid"
    
    # Check if process is running
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping process $pid..."
        
        # Try graceful shutdown first
        kill "$pid"
        
        # Wait a bit for graceful shutdown
        sleep 2
        
        # Check if process is still running
        if kill -0 "$pid" 2>/dev/null; then
            echo "Process still running, forcing shutdown..."
            kill -9 "$pid"
            sleep 1
        fi
        
        # Final check
        if kill -0 "$pid" 2>/dev/null; then
            echo "Warning: Could not stop process $pid"
        else
            echo "Process stopped successfully"
        fi
    else
        echo "Process $pid is not running"
    fi
else
    echo "No PID file found"
fi

# Clean up files
echo "Cleaning up files..."
rm -f "$PID_FILE" "$LOCK_FILE"
rm -rf "$DATA_DIR"
rm -rf "./vector_db"
rm -rf "./backend/__pycache__"

echo "Cleanup complete"