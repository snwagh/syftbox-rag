#!/bin/sh

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if port is in use
check_port() {
    if lsof -i :8002; then
        echo "Something is already running on 8002"
        exit 1
    fi
}

# Function to get config values
get_config() {
    data_dir=$(jq -r '.data_dir' ~/.syftbox/config.json)
    email=$(jq -r '.email' ~/.syftbox/config.json)
}

# Function to install
install() {
    echo "Installing applications..."
    check_docker
    check_port
    get_config

    syftbox app install https://github.com/openmined/rag-ingestor.git
    syftbox app install https://github.com/openmined/rag-router-demo.git

    echo "........................."
    echo "Waiting for 10 seconds..."
    echo "........................."
    sleep 10

    open $data_dir/datasites/$email/embeddings/
    echo "Installation completed!"
}

# Function to test
test() {
    echo "Running tests..."
    get_config
    cd $data_dir/apps/rag-router-demo/
    uv run chat_test.py
}

# Function to clean
clean() {
    echo "Cleaning up..."
    get_config

    # Kill Qdrant container
    docker kill $(docker ps -q --filter ancestor=qdrant/qdrant)

    # Remove apps
    rm -rf ~/SyftBox/apps/rag-router-demo
    rm -rf ~/SyftBox/apps/rag-ingestor

    # Remove app data
    rm -rf ~/SyftBox/datasites/$email/app_data/
    rm -rf ~/SyftBox/datasites/$email/embeddings/
    
    echo "Cleanup completed!"
}

# Function to display menu
show_menu() {
    echo "Please choose an option:"
    echo "1) Install"
    echo "2) Test"
    echo "3) Clean"
    echo "4) Exit"
    echo
    echo -n "Enter your choice (1-4): "
}

# Main script
show_menu
read choice

case $choice in
    1)
        install
        ;;
    2)
        test
        ;;
    3)
        clean
        ;;
    4)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Please enter a number between 1 and 4."
        exit 1
        ;;
esac 