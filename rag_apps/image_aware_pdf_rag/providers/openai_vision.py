"""OpenAI vision implementation for page-level PDF image descriptions."""
from __future__ import annotations
import base64
import os
from typing import Any
from openai import OpenAI
from interfaces.vision import VisionResult, validate_vision_input

class OpenAIVisionModel:
    """VisionModel adapter for OpenAI vision models."""

    def __init__(self, model: str | None = None, client: Any | None = None,
                 max_completion_tokens: int = 600) -> None:
        """Initialize OpenAI client, model identifier, and token budget."""
        api_key = os.getenv("OPENAI_API_KEY")
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.client = client or OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
        self.max_completion_tokens = max_completion_tokens

    def describe_page(self, image_png: bytes, page_number: int) -> VisionResult:
        """Generate a factual textual description of a rendered PDF page image."""
        validate_vision_input(image_png, page_number)
        encoded = base64.b64encode(image_png).decode("ascii")
        prompt = (
            f"Analyze this image of PDF page {page_number}. In at most 120 words, "
            "describe useful visual evidence for document question answering. For charts, "
            "capture title, axes, units, legend labels, readable values, trends, and shaded "
            "uncertainty ranges. For tables, capture headers and key values. For diagrams, "
            "explain components and relationships. Do not guess unreadable values."
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{encoded}", "detail": "high"
                }},
            ]}],
            max_completion_tokens=self.max_completion_tokens,
        )
        if not response.choices:
            raise RuntimeError(f"OpenAI returned no vision choices for page {page_number}.")
        choice = response.choices[0]
        description = choice.message.content or ""
        if choice.finish_reason == "length":
            raise RuntimeError(f"OpenAI vision response for page {page_number} was truncated.")
        if not description.strip():
            raise RuntimeError(f"OpenAI returned an empty description for page {page_number}.")
        return VisionResult(page_number=page_number, description=description.strip())
