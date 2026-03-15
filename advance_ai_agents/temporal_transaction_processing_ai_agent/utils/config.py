"""Configuration management for the application."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Config:
    """Application configuration from environment variables."""
    
    # Couchbase Configuration
    COUCHBASE_CONNECTION_STRING: str = os.getenv("COUCHBASE_CONNECTION_STRING", "")
    COUCHBASE_USERNAME: str = os.getenv("COUCHBASE_USERNAME", "")
    COUCHBASE_PASSWORD: str = os.getenv("COUCHBASE_PASSWORD", "")
    COUCHBASE_BUCKET: str = os.getenv("COUCHBASE_BUCKET", "transactions")
    COUCHBASE_SCOPE: str = os.getenv("COUCHBASE_SCOPE", "_default")
    
    # Collection Names
    TRANSACTIONS_COLLECTION: str = os.getenv("TRANSACTIONS_COLLECTION", "transactions")
    DECISIONS_COLLECTION: str = os.getenv("DECISIONS_COLLECTION", "decisions")
    HUMAN_REVIEWS_COLLECTION: str = os.getenv("HUMAN_REVIEWS_COLLECTION", "human_reviews")
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Temporal Configuration
    TEMPORAL_HOST: str = os.getenv("TEMPORAL_HOST", "localhost:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    TEMPORAL_TASK_QUEUE: str = os.getenv("TEMPORAL_TASK_QUEUE", "transaction-processing")
    
    # API Configuration
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api")
    
    # Business Rules
    AUTO_APPROVAL_LIMIT: float = float(os.getenv("AUTO_APPROVAL_LIMIT", "50000"))
    CONFIDENCE_THRESHOLD_APPROVE: float = float(os.getenv("CONFIDENCE_THRESHOLD_APPROVE", "85"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
    
    # Legacy AWS/Bedrock fields (kept for backward compatibility, but not used)
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_MODEL_VERSION: str = os.getenv("BEDROCK_MODEL_VERSION", "N/A (using OpenAI)")
    GROQ_MODEL_ID: str = os.getenv("GROQ_MODEL_ID", "N/A (using OpenAI)")

# Global config instance
config = Config()

