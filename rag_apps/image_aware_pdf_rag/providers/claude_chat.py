"""Anthropic Claude implementation of the project's ChatModel interface."""
from __future__ import annotations
import os
from typing import Any
from anthropic import Anthropic

class ClaudeChatModel:
    def __init__(self, model: str | None = None, client: Any | None = None,
                 max_tokens: int = 1200) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if client is None and not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        self.client = client or Anthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-4-5")
        self.max_tokens = max_tokens

    def generate(self, messages: list[dict[str, str]]) -> str:
        if not messages:
            raise ValueError("messages must not be empty.")
        system_parts = [str(m.get("content", "")) for m in messages if m.get("role") == "system"]
        claude_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m.get("role") in {"user", "assistant"}
        ]
        if not claude_messages:
            raise ValueError("At least one user or assistant message is required.")
        kwargs: dict[str, Any] = {
            "model": self.model, "max_tokens": self.max_tokens, "messages": claude_messages
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        response = self.client.messages.create(**kwargs)
        text = "\n".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Claude response reached max_tokens and may be incomplete.")
        if not text:
            raise RuntimeError(f"Claude returned no text (stop_reason={response.stop_reason!r}).")
        return text
