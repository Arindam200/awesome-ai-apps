"""
Clean Nebius AI client for both chat completions and embeddings
"""
from typing import List, Dict, Any
import os

from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

class NebiusClient:
    def __init__(self):
        # Single Nebius client for both chat and embeddings
        self.client = OpenAI(
            base_url="https://api.studio.nebius.com/v1/",
            api_key=os.getenv("NEBIUS_API_KEY")
        )

        # Model configurations
        self.chat_model = "openai/gpt-oss-120b"
        self.embedding_model = "Qwen/Qwen3-Embedding-8B"
        self.embedding_dimensions = 4096

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Nebius AI"""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            raise

    def chat_completion(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Generate chat completion using Nebius AI"""
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=60
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error in chat completion: {str(e)}")
            raise

    def batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            print(f"Error generating batch embeddings: {str(e)}")
            raise