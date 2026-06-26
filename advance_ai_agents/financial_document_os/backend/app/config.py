from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
PAGES_DIR = DATA_DIR / "pages"
EDITED_DIR = DATA_DIR / "edited"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    unsiloed_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    nebius_api_key: str = ""
    resend_api_key: str = ""

    database_url: str = "postgresql+psycopg://findoc:findoc@localhost:5434/financial_document_os"
    database_readonly_url: str = ""
    app_url: str = "http://localhost:3006"

    unsiloed_base_url: str = "https://prod.visionapi.unsiloed.ai"
    unsiloed_edit_base_url: str = "https://platformbackend.unsiloed.ai"
    unsiloed_model: str = "beta"

    # LLM provider: auto (anthropic if key else openai) | openai | anthropic | nebius
    llm_provider: str = "auto"
    synthesis_model: str = "claude-opus-4-8"
    sentiment_model: str = "claude-haiku-4-5-20251001"
    openai_synthesis_model: str = "gpt-5"
    openai_sentiment_model: str = "gpt-5-mini"
    # Nebius Token Factory (OpenAI-compatible); used only when llm_provider=nebius
    nebius_base_url: str = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    nebius_synthesis_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    nebius_sentiment_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"

    # Feature flag — calibration passed 2026-06-13 (scripts/calibrate_edit.py),
    # edit bbox space = citation corners as-is
    editing_enabled: bool = True


settings = Settings()

for _d in (DOCS_DIR, PAGES_DIR, EDITED_DIR):
    _d.mkdir(parents=True, exist_ok=True)
