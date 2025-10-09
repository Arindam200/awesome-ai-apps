"""Configuration management for Doc-MCP application."""

from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings
load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""

    # API Keys
    github_api_key: Optional[str] = Field(default=None, env="GITHUB_API_KEY")

    # Nebius
    nebius_api_key: str = Field(..., env="NEBIUS_API_KEY")
    nebius_llm_model: Optional[str] = Field(default="meta-llama/Llama-3.3-70B-Instruct-fast", env="NEBIUS_LLM_MODEL")
    nebius_embedding_model: Optional[str] = Field(default="BAAI/bge-en-icl", env="NEBIUS_EMBEDDING_MODEL")

    # Database
    mongodb_uri: str = Field(..., env="MONGODB_URI")
    db_name: str = Field(default="docmcp", env="DB_NAME")
    collection_name: str = Field(default="doc_rag", env="COLLECTION_NAME")
    repos_collection_name: str = Field(
        default="ingested_repos", env="REPOS_COLLECTION_NAME"
    )

    # Vector Store
    vector_index_name: str = Field(default="vector_index", env="VECTOR_INDEX_NAME")
    fts_index_name: str = Field(default="fts_index", env="FTS_INDEX_NAME")
    embedding_dimensions: int = Field(default=4096, env="EMBEDDING_DIMENSIONS")

    # GitHub
    github_concurrent_requests: int = Field(
        default=10, env="GITHUB_CONCURRENT_REQUESTS"
    )
    github_timeout: int = Field(default=30, env="GITHUB_TIMEOUT")
    github_retries: int = Field(default=3, env="GITHUB_RETRIES")

    # Processing
    chunk_size: int = Field(default=3072, env="CHUNK_SIZE")
    similarity_top_k: int = Field(default=5, env="SIMILARITY_TOP_K")

    # UI
    enable_repo_management: bool = Field(default=True, env="ENABLE_REPO_MANAGEMENT")

    # Server
    server_host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    server_port: int = Field(default=7860, env="SERVER_PORT")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()