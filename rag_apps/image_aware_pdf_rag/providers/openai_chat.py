"""OpenAI implementation of the project's ChatModel interface."""
from __future__ import annotations
import os
from typing import Any
from openai import OpenAI

class OpenAIChatModel:
    """ChatModel adapter for OpenAI chat completions models."""

    def __init__(self, model: str | None = None, client: Any | None = None,
                 max_completion_tokens: int = 1200) -> None:
        """Initialize OpenAI client, model identifier, and token budget."""
        api_key = os.getenv("OPENAI_API_KEY")
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.client = client or OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
        self.max_completion_tokens = max_completion_tokens

    def generate(self, messages: list[dict[str, str]]) -> str:
        """Send chat messages to OpenAI and return the generated answer."""
        if not messages:
            raise ValueError("messages must not be empty.")
        response = self.client.chat.completions.create(
            model=self.model, messages=messages,
            max_completion_tokens=self.max_completion_tokens,
        )
        if not response.choices:
            raise RuntimeError("OpenAI returned no completion choices.")
        choice = response.choices[0]
        content = choice.message.content or ""
        if choice.finish_reason == "length":
            raise RuntimeError("OpenAI response was truncated at the completion-token limit.")
        if not content.strip():
            raise RuntimeError(f"OpenAI returned empty content (finish_reason={choice.finish_reason!r}).")
        return content.strip()
