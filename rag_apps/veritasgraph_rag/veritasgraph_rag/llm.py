"""Thin LLM client that switches between OpenAI-compatible and Ollama backends."""

from __future__ import annotations

import json
from typing import Any

from .config import Settings, get_settings


def chat_json(prompt: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Run a single chat completion expected to return JSON. Returns parsed dict."""
    settings = settings or get_settings()
    raw = _chat(prompt, settings=settings, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to recover the first JSON object in the response.
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def chat(prompt: str, *, settings: Settings | None = None) -> str:
    """Run a single chat completion and return the raw assistant message."""
    return _chat(prompt, settings=settings or get_settings(), json_mode=False)


def _chat(prompt: str, *, settings: Settings, json_mode: bool) -> str:
    if settings.is_local:
        import ollama

        client = ollama.Client(host=settings.ollama_base_url)
        resp = client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format="json" if json_mode else "",
        )
        return resp["message"]["content"]

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_api_base)
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""
