"""Anthropic Claude vision implementation for rendered PDF page images."""
from __future__ import annotations
import base64
import os
from typing import Any
from anthropic import Anthropic
from interfaces.vision import VisionResult, validate_vision_input

class ClaudeVisionModel:
    """VisionModel adapter for Anthropic Claude vision models."""

    def __init__(self, model: str | None = None, client: Any | None = None,
                 max_tokens: int = 700) -> None:
        """Initialize Claude client, model identifier, and generation budget."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if client is None and not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        self.client = client or Anthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-5")
        self.max_tokens = max_tokens

    def describe_page(self, image_png: bytes, page_number: int) -> VisionResult:
        """Generate a factual textual description of a rendered PDF page image."""
        validate_vision_input(image_png, page_number)
        encoded = base64.standard_b64encode(image_png).decode("ascii")
        prompt = (
            f"Analyze this image of PDF page {page_number}. In at most 140 words, "
            "describe useful evidence for document question answering. For charts, capture "
            "title, axes, units, legend labels, readable values, trends, and uncertainty bands. "
            "For tables, capture headers and key values. For diagrams, describe components "
            "and relationships. Do not guess unreadable text or numbers."
        )
        response = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": encoded
                }},
                {"type": "text", "text": prompt},
            ]}],
        )
        description = "\n".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"Claude vision response for page {page_number} reached max_tokens.")
        if not description:
            raise RuntimeError(f"Claude returned an empty vision description for page {page_number}.")
        return VisionResult(page_number=page_number, description=description)
