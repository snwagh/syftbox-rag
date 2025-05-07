# Read the data_dir and email value from the ~/.syftbox/config.json file
data_dir=$(jq -r '.data_dir' ~/.syftbox/config.json)
email=$(jq -r '.email' ~/.syftbox/config.json)

# Open the applications
cd $data_dir/apps/rag-router-demo/

uv run chat_test.py