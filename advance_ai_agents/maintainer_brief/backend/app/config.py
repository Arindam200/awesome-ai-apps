from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
PAGES_DIR = DATA_DIR / "pages"
PROJECTS_DIR = REPO_DIR / "projects"


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
    github_token: str = ""
    resend_api_key: str = ""
    database_url: str = "postgresql+psycopg://brief:brief@localhost:5433/maintainer_brief"
    app_url: str = "http://localhost:3005"
    # Public URL of THIS backend — used for one-click 👍/👎 links in the email.
    api_public_url: str = "http://localhost:8000"
    # HMAC secret for signing feedback links (set a real random value in prod).
    feedback_secret: str = "dev-insecure-change-me"

    unsiloed_base_url: str = "https://prod.visionapi.unsiloed.ai"
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

    newsletter_from: str = "Maintainer Brief <onboarding@resend.dev>"


settings = Settings()

for _d in (DOCS_DIR, PAGES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
