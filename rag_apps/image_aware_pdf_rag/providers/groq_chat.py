
"""Groq chat provider adapter."""

from __future__ import annotations

import os
from typing import Any

from interfaces.chat import ChatMessage, validate_messages


class GroqChatModel:
    """Generate text responses through Groq's chat completions API."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "GROQ_CHAT_MODEL",
            "openai/gpt-oss-20b",
        )

        if client is not None:
            # Client injection is useful for unit tests.
            self.client = client
            return

        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError(
                "Missing Groq API key. Set GROQ_API_KEY in your environment."
            )

        from groq import Groq

        self.client = Groq(api_key=key)

    def generate(self, messages: list[ChatMessage]) -> str:
        """Generate an answer from validated chat messages."""

        validate_messages(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        if not response.choices:
            raise RuntimeError("Groq returned no completion choices")

        content = response.choices[0].message.content

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Groq returned an empty or invalid response")

        return content.strip()
