email=$(jq -r '.email' ~/.syftbox/config.json)

# Find the docker image qdrant/qdrant and kill it, it should be on port 6333
docker kill $(docker ps -q --filter ancestor=qdrant/qdrant)

# Remove apps
rm -rf ~/SyftBox/apps/rag-router-demo
rm -rf ~/SyftBox/apps/rag-ingestor

# Remove app data
rm -rf ~/SyftBox/datasites/$email/app_data/
rm -rf ~/SyftBox/datasites/$email/embeddings/