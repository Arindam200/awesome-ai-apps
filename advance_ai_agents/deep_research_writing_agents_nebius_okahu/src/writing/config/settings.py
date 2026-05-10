"""Server configuration settings."""

import logging
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings for the LinkedIn Writer MCP Server."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    # Server settings
    server_name: str = Field(
        default="LinkedIn Writer MCP Server", description="The name of the server"
    )
    version: str = Field(default="0.1.0", description="The version of the server")
    log_level: int = Field(
        default=logging.INFO, alias="LOG_LEVEL", description="The log level"
    )

    # LLM Configuration
    writer_model: str = Field(
        default="meta-llama/Llama-3.3-70B-Instruct",
        alias="WRITER_MODEL",
        description="Model for post generation and editing",
    )
    reviewer_model: str = Field(
        default="meta-llama/Llama-3.3-70B-Instruct",
        alias="REVIEWER_MODEL",
        description="Model for post evaluation",
    )
    image_model: str = Field(
        default="gemini-2.5-flash-image",
        alias="IMAGE_MODEL",
        description="Gemini image generation model",
    )
    nebius_base_url: str = Field(
        default="https://api.studio.nebius.com/v1/",
        alias="NEBIUS_BASE_URL",
        description="OpenAI-compatible Nebius API base URL",
    )

    # Workflow Configuration
    num_reviews: int = Field(
        default=4, description="Number of review/edit iterations in generate_post"
    )

    # API Keys
    nebius_api_key: SecretStr = Field(
        alias="NEBIUS_API_KEY", description="The API key for Nebius AI Studio"
    )
    gemini_api_key: SecretStr = Field(
        alias="GEMINI_API_KEY", description="The API key for Gemini image generation"
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
        default="writing-workflow",
        alias="OKAHU_WORKFLOW_WRITING",
        description="Okahu/Monocle workflow name for writing traces",
    )


@lru_cache
def get_settings() -> Settings:
    """Get the singleton settings instance."""

    return Settings()
