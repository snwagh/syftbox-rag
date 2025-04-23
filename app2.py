import os
import streamlit as st
from dotenv import load_dotenv
import glob
import json
import chromadb
from langchain_community.llms import Ollama

# Load environment variables
load_dotenv()

# Get Ollama base URL
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# App UI
st.title("RAG Query Application")

# Get available RAG databases
rag_dir = "rag_databases"
if not os.path.exists(rag_dir):
    st.error(f"RAG database directory '{rag_dir}' not found. Please run the RAG Builder app first.")
    st.stop()

# Find directories in rag_databases that contain ChromaDB databases
database_dirs = [d for d in os.listdir(rag_dir) 
                if os.path.isdir(os.path.join(rag_dir, d)) and 
                os.path.exists(os.path.join(rag_dir, d, "metadata.json"))]

if not database_dirs:
    st.error("No RAG databases found. Please run the RAG Builder app to create a database first.")
    st.stop()

# Display database selection options
selected_db = st.selectbox("Select RAG Database:", database_dirs)

# Get the full path of the selected database
selected_db_path = os.path.join(rag_dir, selected_db)

# Load the selected database
@st.cache_resource
def load_rag_database(db_path):
    """Load a RAG database using ChromaDB direct client"""
    try:
        # Load metadata
        metadata_path = os.path.join(db_path, "metadata.json")
        if not os.path.exists(metadata_path):
            st.error(f"Metadata file not found at {metadata_path}")
            return None, None
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        # Initialize ChromaDB client
        chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Get collection
        collection_name = metadata.get("collection_name", "documents")
        collection = chroma_client.get_collection(name=collection_name)
        
        return collection, metadata
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        return None, None

def query_database(collection, query_text, n_results=4):
    """Query the ChromaDB collection directly"""
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    
    return results

@st.cache_resource
def get_ollama_model(model_name):
    """Initialize the Ollama LLM"""
    return Ollama(
        base_url=ollama_base_url,
        model=model_name,
        temperature=0.1
    )

def generate_rag_response(llm, query, context_docs, max_new_tokens=1000):
    """Generate a response using RAG context and Ollama LLM"""
    # Create a prompt with the retrieved context
    prompt = f"""Answer the following question based only on the provided context:

Question: {query}

Context:
{context_docs}

Answer:"""

    # Generate response
    response = llm(prompt, max_tokens=max_new_tokens)
    return response

# Ollama model selection
available_models = st.text_input(
    "Available Ollama models (comma-separated):", 
    "gemma3:4b,llama3.2:latest,deepseek-r1:1.5b"
).split(',')

st.subheader("Model Selection")
generation_model = st.selectbox("Select model for answering:", available_models)

# Display information about the database
if st.button("Load Database"):
    with st.spinner("Loading database..."):
        collection, metadata = load_rag_database(selected_db_path)
        
        if collection and metadata:
            st.success(f"Database '{selected_db}' loaded successfully!")
            
            # Display metadata
            st.subheader("Database Information")
            st.write(f"Document count: {metadata.get('document_count', 'Unknown')}")
            st.write(f"Chunk count: {metadata.get('chunk_count', 'Unknown')}")
            st.write(f"Collection name: {metadata.get('collection_name', 'documents')}")
            st.write(f"Created at: {metadata.get('created_at', 'Unknown')}")
            
            # Store in session state
            st.session_state.collection = collection
            st.session_state.metadata = metadata
            st.session_state.llm = get_ollama_model(generation_model)
            
            st.info("Ready to answer questions!")

# Query interface
if 'collection' in st.session_state:
    st.subheader("Ask a Question")
    
    query = st.text_input("Enter your question:")
    n_results = st.slider("Number of documents to retrieve:", min_value=1, max_value=10, value=4)
    
    if query and st.button("Ask"):
        with st.spinner("Generating answer..."):
            try:
                # Query ChromaDB directly
                results = query_database(st.session_state.collection, query, n_results)
                
                # Extract documents and metadata
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0] if "distances" in results else None
                ids = results["ids"][0]
                
                # Join documents into context
                context = "\n\n".join([f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents)])
                
                # Generate answer using Ollama
                answer = generate_rag_response(st.session_state.llm, query, context)
                
                # Display answer
                st.subheader("Answer")
                st.write(answer)
                
                # Display sources
                st.subheader("Sources")
                for i, (doc, meta, doc_id) in enumerate(zip(documents, metadatas, ids)):
                    source_info = f"Source {i+1}"
                    if meta and "source" in meta:
                        source_info += f" - {os.path.basename(meta['source'])}"
                    
                    if distances:
                        relevance = 1 - (distances[i] / max(distances)) if max(distances) > 0 else 1
                        source_info += f" (Relevance: {relevance:.2f})"
                    
                    with st.expander(source_info):
                        st.write(doc)
                        if meta:
                            st.write("Metadata:", meta)
                
            except Exception as e:
                st.error(f"Error generating answer: {str(e)}")
                st.error("Please check if your Ollama server is running correctly.")