"""Configuration for Developer Trend & DevRel Ideation Agent."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_MODEL = "zai-org/GLM-5.2"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_ENGRAM_USER_ID = "engineering-content-agent-user"


@dataclass(frozen=True)
class Settings:
    nebius_api_key: str
    nebius_model: str = DEFAULT_MODEL
    nebius_base_url: str = DEFAULT_BASE_URL
    engram_api_key: str | None = None
    engram_namespace: str = "default"
    engram_user_id: str = DEFAULT_ENGRAM_USER_ID
    engram_conversation_id: str | None = None
    dev_api_key: str | None = None
    log_level: str = "INFO"

    @property
    def has_persistent_memory(self) -> bool:
        return bool(self.engram_api_key)


def load_project_env() -> None:
    """Load .env from the app directory without overriding active session keys."""
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, override=False)


def get_settings(require_nebius: bool = True) -> Settings:
    load_project_env()
    api_key = os.getenv("NEBIUS_API_KEY", "").strip()
    if require_nebius and not api_key:
        raise RuntimeError("Missing NEBIUS_API_KEY. Add it in the sidebar or .env file.")

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    namespace = (
        os.getenv("ENGRAM_NAMESPACE")
        or os.getenv("ENGRAM_PROJECT_ID")
        or "default"
    )

    return Settings(
        nebius_api_key=api_key,
        nebius_model=os.getenv("NEBIUS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        nebius_base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL).strip()
        or DEFAULT_BASE_URL,
        engram_api_key=os.getenv("ENGRAM_API_KEY") or None,
        engram_namespace=namespace,
        engram_user_id=os.getenv("ENGRAM_USER_ID", DEFAULT_ENGRAM_USER_ID).strip()
        or DEFAULT_ENGRAM_USER_ID,
        engram_conversation_id=os.getenv("ENGRAM_CONVERSATION_ID") or None,
        dev_api_key=os.getenv("DEV_API_KEY") or None,
        log_level=log_level,
    )
