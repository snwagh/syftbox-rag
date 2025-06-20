#!/bin/bash

# Example curl commands for the new /api/search-paths endpoint

echo "Example 1: Basic search for 'machine learning'"
echo "curl -X POST http://localhost:8000/api/search-paths \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"machine learning\", \"limit\": 5}'"
echo ""

echo "Example 2: Search for 'python programming' with custom limit"
echo "curl -X POST http://localhost:8000/api/search-paths \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"python programming\", \"limit\": 10}'"
echo ""

echo "Example 3: Search for 'data analysis' (using default limit)"
echo "curl -X POST http://localhost:8000/api/search-paths \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"data analysis\"}'"
echo ""

echo "Example 4: Pretty-printed JSON output"
echo "curl -X POST http://localhost:8000/api/search-paths \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"machine learning\", \"limit\": 5}' | python -m json.tool"
echo ""

echo "Example 5: Extract only file paths (using jq if available)"
echo "curl -X POST http://localhost:8000/api/search-paths \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"machine learning\"}' | jq -r '.file_paths[]'"
echo ""

echo "Note: Replace 'localhost:8000' with your actual server host and port if different." 