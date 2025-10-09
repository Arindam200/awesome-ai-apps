"""
Hybrid client for OpenRouter (Grok-4) and Together AI (embeddings)
"""
from typing import List, Dict, Any
import os

from dotenv import load_dotenv
from openai import OpenAI
from together import Together
load_dotenv()

class OpenRouterClient:
    def __init__(self):
        # OpenRouter client for chat completions (Grok-4)
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self.openrouter_client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=openrouter_api_key,
        )

        # Together AI client for embeddings
        together_api_key = os.getenv("TOGETHER_API_KEY")
        if not together_api_key:
            raise ValueError("TOGETHER_API_KEY is not set")
        self.together_client = Together(api_key=together_api_key)

        self.chat_model = os.getenv("GROK_MODEL", "x-ai/grok-4:online")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Together AI (BGE-Large)"""
        try:
            response = self.together_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            raise

    def chat_completion(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Generate chat completion using Grok-4 online via OpenRouter"""
        try:
            response = self.openrouter_client.chat.completions.create(
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
        """Generate embeddings for multiple texts using Together AI"""
        try:
            response = self.together_client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            print(f"Error generating batch embeddings: {str(e)}")
            raise