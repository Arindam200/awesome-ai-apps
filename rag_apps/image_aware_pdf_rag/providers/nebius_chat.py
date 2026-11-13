
"""Nebius Token Factory chat provider adapter (OpenAI-compatible)."""

from __future__ import annotations

import os
from typing import Any

from interfaces.chat import ChatMessage, validate_messages

NEBIUS_BASE_URL = os.getenv(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
)


class NebiusChatModel:
    """Generate text responses through the Nebius Token Factory chat API."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "NEBIUS_CHAT_MODEL",
            "openai/gpt-oss-120b",
        )

        if client is not None:
            # Client injection is useful for unit tests.
            self.client = client
            return

        key = api_key or os.getenv("NEBIUS_API_KEY")
        if not key:
            raise ValueError(
                "Missing Nebius API key. Set NEBIUS_API_KEY in your environment."
            )

        from openai import OpenAI

        self.client = OpenAI(api_key=key, base_url=NEBIUS_BASE_URL)

    def generate(self, messages: list[ChatMessage]) -> str:
        """Generate an answer from validated chat messages."""

        validate_messages(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        if not response.choices:
            raise RuntimeError("Nebius returned no completion choices")

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise RuntimeError("Nebius chat response was truncated at the completion-token limit")

        content = choice.message.content

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Nebius returned an empty or invalid response")

        return content.strip()
