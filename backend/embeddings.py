from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import warnings
from .config import Config

class EmbeddingGenerator:
    def __init__(self, model_name: str = None):
        """Initialize with a lightweight, fast model"""
        model_name = model_name or Config.EMBEDDING_MODEL
        
        # Suppress MPS warnings on Mac since we handle them gracefully
        warnings.filterwarnings("ignore", message=".*pin_memory.*")
        warnings.filterwarnings("ignore", message=".*MPS.*")
        
        try:
            # Initialize model with CPU fallback for compatibility
            self.model = SentenceTransformer(model_name, device='cpu')
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"Initialized embedding model: {model_name} on CPU (dimension: {self.dimension})")
        except Exception as e:
            print(f"Error initializing embedding model {model_name}: {e}")
            # Fallback to a known working model
            fallback_model = "all-MiniLM-L6-v2"
            self.model = SentenceTransformer(fallback_model, device='cpu')
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"Fallback to {fallback_model} on CPU")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        # Validate input text
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension
        
        # Ensure minimum text length
        text = text.strip()
        if len(text) < 3:
            # Pad very short text to avoid embedding issues
            text = text + " " * (3 - len(text))
        
        try:
            # Suppress numpy warnings during embedding generation
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
                
                # Validate embedding output
                if embedding is None or len(embedding) == 0:
                    print(f"Empty embedding generated for text")
                    return [0.0] * self.dimension
                    
                # Check for NaN or infinite values
                if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
                    print(f"Invalid embedding values (NaN/Inf) generated")
                    return [0.0] * self.dimension
                    
                return embedding.tolist()
                
        except Exception as e:
            print(f"Error generating embedding for text: {e}")
            # Return zero vector on error
            return [0.0] * self.dimension
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        # Filter and validate texts
        valid_texts = []
        for text in texts:
            if text and text.strip() and len(text.strip()) >= 3:
                valid_texts.append(text.strip())
            else:
                # Pad short or empty texts
                padded_text = (text.strip() if text else "") + " " * max(0, 3 - len(text.strip() if text else ""))
                valid_texts.append(padded_text)
        
        if not valid_texts:
            # Return zero vectors for empty batch
            return [[0.0] * self.dimension] * len(texts)
        
        try:
            # Suppress warnings during batch embedding generation
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                embeddings = self.model.encode(valid_texts, convert_to_numpy=True, show_progress_bar=False)
                
                # Validate batch embeddings
                if embeddings is None or len(embeddings) == 0:
                    print(f"Empty batch embeddings generated")
                    return [[0.0] * self.dimension] * len(texts)
                
                # Check for any invalid values in the batch
                if np.any(np.isnan(embeddings)) or np.any(np.isinf(embeddings)):
                    print(f"Invalid values in batch embeddings, cleaning...")
                    # Replace invalid embeddings with zero vectors
                    clean_embeddings = []
                    for emb in embeddings:
                        if np.any(np.isnan(emb)) or np.any(np.isinf(emb)):
                            clean_embeddings.append([0.0] * self.dimension)
                        else:
                            clean_embeddings.append(emb.tolist())
                    return clean_embeddings
                    
                return embeddings.tolist()
                
        except Exception as e:
            print(f"Error generating batch embeddings: {e}")
            # Return zero vectors for all texts on error
            return [[0.0] * self.dimension] * len(texts)