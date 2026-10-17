
"""Groq vision provider adapter for rendered PDF pages."""

from __future__ import annotations

import base64
import os
from typing import Any

from interfaces.vision import (
    VisionResult,
    validate_vision_input,
)


class GroqVisionModel:
    """Describe charts, diagrams, tables, and other page visuals."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "GROQ_VISION_MODEL",
            "qwen/qwen3.8-27b",
        )

        if client is not None:
            self.client = client
            return

        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError(
                "Missing Groq API key. Set GROQ_API_KEY in your environment."
            )

        from groq import Groq

        self.client = Groq(api_key=key)

    def describe_page(
        self,
        image_png: bytes,
        page_number: int,
    ) -> VisionResult:
        """Generate a visual description for one PDF page."""

        validate_vision_input(image_png, page_number)

        encoded_image = base64.b64encode(image_png).decode("ascii")
        image_url = f"data:image/png;base64,{encoded_image}"

        prompt = (
            f"Analyze page {page_number} of a PDF. Describe its meaningful "
            "visual content, including charts, diagrams, tables, axes, "
            "labels, legends, relationships, and visible numerical values. "
            "Preserve numbers and units carefully. If there is no meaningful "
            "visual content, say so. Never guess unreadable information."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            max_completion_tokens=400,
        )

        if not response.choices:
            raise RuntimeError("Groq returned no vision completion choices")

        description = response.choices[0].message.content

        if not isinstance(description, str) or not description.strip():
            raise RuntimeError("Groq returned an empty page description")

        return VisionResult(
            page_number=page_number,
            description=description.strip(),
        )
