from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    gradium_api_key: str
    nebius_api_key: str
    gradium_base_url: str = "https://eu.api.gradium.ai/api"
    gradium_voice_id: str = "m86j6D7UZpGzHsNu"
    nebius_model: str = "moonshotai/Kimi-K2.5"


def load_settings() -> Settings:
    load_dotenv()

    gradium_api_key = os.getenv("GRADIUM_API_KEY", "").strip()
    nebius_api_key = os.getenv("NEBIUS_API_KEY", "").strip()

    missing = []
    if not gradium_api_key:
        missing.append("GRADIUM_API_KEY")
    if not nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variable(s): {names}")

    return Settings(
        gradium_api_key=gradium_api_key,
        nebius_api_key=nebius_api_key,
        gradium_base_url=os.getenv("GRADIUM_BASE_URL", "https://eu.api.gradium.ai/api").strip(),
        gradium_voice_id=os.getenv("GRADIUM_VOICE_ID", "m86j6D7UZpGzHsNu").strip(),
        nebius_model=os.getenv("NEBIUS_MODEL", "moonshotai/Kimi-K2.5").strip(),
    )
