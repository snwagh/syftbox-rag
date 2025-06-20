#!/usr/bin/env python3
"""
Example script to demonstrate how to use the /api/search-paths endpoint
from the command line.
"""

import requests
import json
import sys

def search_document_paths(query, limit=10, host="localhost", port=8000):
    """
    Search for document paths using the new endpoint
    
    Args:
        query (str): The search query
        limit (int): Maximum number of results to return
        host (str): Server hostname
        port (int): Server port
    
    Returns:
        dict: Response from the API
    """
    url = f"http://{host}:{port}/api/search-paths"
    
    payload = {
        "query": query,
        "limit": limit
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python search_paths_example.py <query> [limit] [host] [port]")
        print("Example: python search_paths_example.py 'machine learning' 5 localhost 8000")
        sys.exit(1)
    
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    host = sys.argv[3] if len(sys.argv) > 3 else "localhost"
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 8000
    
    print(f"Searching for: '{query}'")
    print(f"Limit: {limit}")
    print(f"Server: {host}:{port}")
    print("-" * 50)
    
    result = search_document_paths(query, limit, host, port)
    
    if result:
        print(f"Query: {result['query']}")
        print(f"Total files found: {result['total_files']}")
        print("\nFile paths:")
        for i, file_path in enumerate(result['file_paths'], 1):
            print(f"{i}. {file_path}")
    else:
        print("Failed to get results")

if __name__ == "__main__":
    main() 