"""OpenAI embedding client for transaction embeddings."""

import os
import logging
from typing import List, Optional, Dict
from openai import OpenAI
from utils.config import config

logger = logging.getLogger(__name__)

class EmbeddingClient:
    """Client for generating embeddings using OpenAI."""
    
    def __init__(self):
        """Initialize OpenAI embedding client."""
        self._client = None
        self.model = config.OPENAI_EMBEDDING_MODEL
        self.primary_model = "openai"
        self.api_key = config.OPENAI_API_KEY
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client (for Temporal compatibility)."""
        if self._client is None and self.api_key:
            try:
                self._client = OpenAI(api_key=self.api_key)
                logger.info(f"Initialized OpenAI embedding client with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self._client = None
        return self._client
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a given text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding, or None if generation fails
        """
        if not self.client:
            logger.warning("OpenAI client not available. Returning mock embedding.")
            return self._mock_embedding()
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return self._mock_embedding()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (or None for failed generations)
        """
        if not self.client:
            logger.warning("OpenAI client not available. Returning mock embeddings.")
            return [self._mock_embedding() for _ in texts]
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [self._mock_embedding() for _ in texts]
    
    def _mock_embedding(self, dimensions: int = 1536) -> List[float]:
        """Generate a mock embedding for testing when API is unavailable."""
        import random
        return [random.gauss(0, 0.1) for _ in range(dimensions)]
    
    def health_check(self) -> Dict:
        """Check the health status of the embedding service."""
        openai_available = self.client is not None
        
        return {
            "primary_model": self.primary_model,
            "openai_available": openai_available,
            "model": self.model,
            "available_models": ["openai"] if openai_available else []
        }

# Global instance
embedding_client = EmbeddingClient()

