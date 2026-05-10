"""Gemini native multimodal embeddings via `gemini-embedding-2-preview`.

Embeds text and video clips into the same vector space using a single
`GEMINI_API_KEY`. No Vertex / GCP project required.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache

from google import genai
from google.genai import types

MODEL_NAME = "gemini-embedding-2-preview"


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def embed_text(text: str) -> list[float]:
    result = _client().models.embed_content(
        model=MODEL_NAME,
        contents=text,
    )
    return list(result.embeddings[0].values)


def _wait_active(file_obj, timeout: int = 300) -> None:
    client = _client()
    deadline = time.time() + timeout
    while getattr(file_obj, "state", None) and str(file_obj.state).endswith("PROCESSING"):
        if time.time() > deadline:
            raise TimeoutError(f"File {file_obj.name} did not become ACTIVE in {timeout}s")
        time.sleep(2)
        file_obj = client.files.get(name=file_obj.name)
    if str(getattr(file_obj, "state", "")).endswith("FAILED"):
        raise RuntimeError(f"File upload failed: {file_obj.name}")


def embed_video(video_path: str) -> list[float]:
    """Upload a video clip and embed it natively with the multimodal model."""
    client = _client()
    uploaded = client.files.upload(file=video_path)
    _wait_active(uploaded)
    try:
        result = client.models.embed_content(
            model=MODEL_NAME,
            contents=[types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)],
        )
        return list(result.embeddings[0].values)
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass
