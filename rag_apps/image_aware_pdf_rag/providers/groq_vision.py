
"""Groq vision provider adapter for rendered PDF pages."""

from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Any

from PIL import Image

from interfaces.vision import (
    VisionImageTooLargeError,
    VisionResult,
    validate_vision_input,
)

MAX_BASE64_IMAGE_BYTES = 19 * 1024 * 1024


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

        image_data, media_type = self._prepare_image(image_png)
        encoded_image = base64.b64encode(image_data).decode("ascii")
        image_url = f"data:{media_type};base64,{encoded_image}"

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

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError(
                "Groq returned an incomplete page description "
                "(completion token limit reached)"
            )

        description = choice.message.content

        if not isinstance(description, str) or not description.strip():
            raise RuntimeError("Groq returned an empty page description")

        return VisionResult(
            page_number=page_number,
            description=description.strip(),
        )

    @staticmethod
    def _prepare_image(image_png: bytes) -> tuple[bytes, str]:
        max_image_bytes = (MAX_BASE64_IMAGE_BYTES // 4) * 3
        if len(image_png) <= max_image_bytes:
            return image_png, "image/png"

        with Image.open(BytesIO(image_png)) as image:
            image.load()
            if "A" in image.getbands():
                alpha = image.getchannel("A")
                background = Image.new("RGB", image.size, "white")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")

        width, height = image.size
        while True:
            for quality in (85, 70, 55):
                output = BytesIO()
                image.save(
                    output,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )
                image_jpeg = output.getvalue()
                if len(image_jpeg) <= max_image_bytes:
                    return image_jpeg, "image/jpeg"

            if width == 1 and height == 1:
                raise VisionImageTooLargeError(
                    "Page image cannot be reduced below Groq's request limit"
                )

            width = max(1, int(width * 0.75))
            height = max(1, int(height * 0.75))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
