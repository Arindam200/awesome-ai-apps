"""Configuration loader for the VeritasGraph showcase.

Reads ``.env`` and exposes a single :func:`get_settings` returning a typed
:class:`Settings` dataclass. Switches between cloud and local (Ollama) modes
via the ``VERITAS_MODE`` env var.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

Mode = Literal["cloud", "local"]


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the environment."""

    mode: Mode
    # Cloud
    openai_api_key: str | None
    openai_api_base: str
    openai_model: str
    openai_embedding_model: str
    # Local
    ollama_base_url: str
    ollama_model: str
    ollama_embedding_model: str
    # Paths
    input_dir: Path
    output_dir: Path
    lancedb_uri: str

    @property
    def is_local(self) -> bool:
        return self.mode == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from ``.env`` + process environment."""
    load_dotenv()

    mode = os.getenv("VERITAS_MODE", "cloud").lower()
    if mode not in ("cloud", "local"):
        raise ValueError(f"VERITAS_MODE must be 'cloud' or 'local', got {mode!r}")

    input_dir = Path(os.getenv("INPUT_DIR", "./input")).resolve()
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output")).resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        mode=mode,  # type: ignore[arg-type]
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        input_dir=input_dir,
        output_dir=output_dir,
        lancedb_uri=os.getenv("LANCEDB_URI", str(output_dir / "lancedb")),
    )
