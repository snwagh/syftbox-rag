#! /bin/sh

# Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker daemon is not running. Please start Docker and try again."
  exit 1
fi

if lsof -i :8002; then
    echo "Something is already running on 8002"
    exit 1
fi

# Read the data_dir and email value from the ~/.syftbox/config.json file
data_dir=$(jq -r '.data_dir' ~/.syftbox/config.json)
email=$(jq -r '.email' ~/.syftbox/config.json)

# git clone https://github.com/openmined/rag-ingestor.git $data_dir/rag-ingestor
# git clone https://github.com/openmined/rag-router-demo.git $data_dir/rag-router-demo
git clone git@github.com:OpenMined/rag-ingestor.git $data_dir/apps/rag-ingestor
git clone git@github.com:OpenMined/rag-router-demo.git $data_dir/apps/rag-router-demo

# Wait for 5 seconds for the folders to be created
echo "........................."
echo "Waiting for 10 seconds..."
echo "........................."
sleep 10

# Open the applications
open $data_dir/datasites/$email/embeddings/
