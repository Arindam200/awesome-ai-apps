"""Server configuration settings."""

import logging
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings for the Research MCP Server."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    # Server settings
    server_name: str = Field(
        default="Deep Research MCP Server", description="The name of the server"
    )
    version: str = Field(default="0.1.0", description="The version of the server")
    log_level: int = Field(
        default=logging.INFO, alias="LOG_LEVEL", description="The log level"
    )

    # LLM Configuration
    llm_model: str = Field(
        default="meta-llama/Llama-3.3-70B-Instruct",
        alias="LLM_MODEL",
        description="Default Nebius-hosted model for general use",
    )
    youtube_transcription_model: str = Field(
        default="meta-llama/Llama-3.3-70B-Instruct",
        alias="YOUTUBE_TRANSCRIPTION_MODEL",
        description="Nebius-hosted model for YouTube transcript summarization",
    )
    nebius_base_url: str = Field(
        default="https://api.studio.nebius.com/v1/",
        alias="NEBIUS_BASE_URL",
        description="OpenAI-compatible Nebius API base URL",
    )

    # API Keys
    nebius_api_key: SecretStr = Field(
        alias="NEBIUS_API_KEY", description="The API key for Nebius AI Studio"
    )
    exa_api_key: SecretStr = Field(
        alias="EXA_API_KEY", description="The API key for Exa search"
    )

    # Okahu / Monocle Observability Configuration
    okahu_api_key: SecretStr | None = Field(
        default=None,
        alias="OKAHU_API_KEY",
        description="The API key to authenticate with Okahu Cloud",
    )
    monocle_exporter: str | None = Field(
        default="file",
        alias="MONOCLE_EXPORTER",
        description="Comma-separated Monocle exporters, e.g. file or file,okahu",
    )
    okahu_workflow_name: str = Field(
        default="research-agent",
        alias="OKAHU_WORKFLOW_RESEARCH",
        description="Okahu/Monocle workflow name for research traces",
    )


@lru_cache
def get_settings() -> Settings:
    """Get the singleton settings instance."""

    return Settings()
