
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

MAX_BASE64_IMAGE_BYTES = 3 * 1024 * 1024


import logging

logger = logging.getLogger(__name__)

DEFAULT_VISION_MAX_COMPLETION_TOKENS = 1024
RETRY_VISION_MAX_COMPLETION_TOKENS = 1536


class GroqVisionModel:
    """Describe charts, diagrams, tables, and other page visuals."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
        max_completion_tokens: int | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "GROQ_VISION_MODEL",
            "qwen/qwen3.8-27b",
        )
        env_tokens = os.getenv("GROQ_VISION_MAX_COMPLETION_TOKENS")
        self.max_completion_tokens = (
            max_completion_tokens
            or (int(env_tokens) if env_tokens and env_tokens.isdigit() else None)
            or DEFAULT_VISION_MAX_COMPLETION_TOKENS
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

        # Standard focused visual prompt capturing exact chart identifiers, legends, line colors, and uncertainty bands
        standard_prompt = (
            f"Analyze page {page_number} of a PDF and thoroughly describe all visual evidence:\n"
            "- Charts & Graphs: identify exact titles and numbers (e.g., 'Chart 1.1', 'Figure 2'), axes labels, units, time ranges, "
            "exact legend entries, colored lines or bars (e.g. orange, blue, green) and what each line/color represents, "
            "and any shaded areas, fan charts, or confidence/uncertainty bands.\n"
            "- Tables: exact table titles/numbers, column and row headers, units, and principal values.\n"
            "- Diagrams & Architectures: titles, component names, arrows, relationships, and directional flows.\n"
            "- Key highlights: preserve exact numbers, labels, units, and dates. Do not invent unreadable details. "
            "If no visual content exists, state that briefly."
        )

        # Fallback ultra-concise prompt for retry if truncation occurs
        concise_fallback_prompt = (
            f"Provide a concise summary of visual elements on page {page_number}. "
            "Explicitly list all chart/table numbers (e.g., 'Chart 1.1'), exact line/bar colors and their legend labels (e.g., orange line label), "
            "axes, units, key data points, and any shaded fan/uncertainty bands."
        )

        description = self._call_vision_with_retry(
            image_url=image_url,
            page_number=page_number,
            initial_prompt=standard_prompt,
            fallback_prompt=concise_fallback_prompt,
        )

        return VisionResult(
            page_number=page_number,
            description=description,
        )

    def _call_vision_with_retry(
        self,
        image_url: str,
        page_number: int,
        initial_prompt: str,
        fallback_prompt: str,
    ) -> str:
        """Execute vision completion with diagnostic logging and bounded truncation retry."""
        attempts = [
            {"prompt": initial_prompt, "tokens": self.max_completion_tokens, "label": "primary"},
            {
                "prompt": fallback_prompt,
                "tokens": max(self.max_completion_tokens, RETRY_VISION_MAX_COMPLETION_TOKENS),
                "label": "shorter_prompt_retry",
            },
        ]

        last_truncation_text = ""

        for attempt_idx, attempt in enumerate(attempts):
            prompt = attempt["prompt"]
            tokens = attempt["tokens"]
            label = attempt["label"]

            logger.info(
                "Calling Groq vision API for page %d (attempt=%s, model=%s, max_tokens=%d)",
                page_number,
                label,
                self.model,
                tokens,
            )

            try:
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
                    max_completion_tokens=tokens,
                )
            except Exception as exc:
                err_type = type(exc).__name__
                status_code = getattr(exc, "status_code", getattr(exc, "code", None))
                logger.error(
                    "Groq vision request failed on page %d (model=%s, error_type=%s, status_code=%s): %s",
                    page_number,
                    self.model,
                    err_type,
                    status_code,
                    exc,
                )
                if status_code == 429 or "rate_limit" in str(exc).lower() or "429" in str(exc):
                    raise RuntimeError(
                        f"Groq rate limit exceeded (HTTP 429) while processing page {page_number}: {exc}"
                    ) from exc
                elif status_code == 401 or "invalid_api_key" in str(exc).lower():
                    raise RuntimeError(
                        f"Groq authentication failed (HTTP 401): {exc}"
                    ) from exc
                else:
                    raise RuntimeError(
                        f"Groq vision error on page {page_number} ({err_type}{f' {status_code}' if status_code else ''}): {exc}"
                    ) from exc

            if not response.choices:
                logger.error("Groq returned empty choices for page %d (model=%s)", page_number, self.model)
                raise RuntimeError(f"Groq returned no vision completion choices for page {page_number}")

            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)
            raw_content = choice.message.content if hasattr(choice, "message") and choice.message else None
            text = (raw_content or "").strip()

            logger.info(
                "Groq vision response received for page %d (model=%s, finish_reason=%s, chars=%d)",
                page_number,
                self.model,
                finish_reason,
                len(text),
            )

            if finish_reason == "length":
                logger.warning(
                    "Groq vision response truncated (finish_reason='length') on page %d (model=%s, tokens_requested=%d, attempt=%s).",
                    page_number,
                    self.model,
                    tokens,
                    label,
                )
                if text:
                    last_truncation_text = text

                # If this was our first attempt, try the bounded concise retry
                if attempt_idx == 0:
                    logger.info("Retrying page %d with concise prompt and expanded token budget...", page_number)
                    continue

                # If still truncated after retry, check if we have usable partial text
                if last_truncation_text and len(last_truncation_text) >= 40:
                    logger.warning(
                        "Retaining usable truncated description (%d chars) for page %d after bounded retry.",
                        len(last_truncation_text),
                        page_number,
                    )
                    return last_truncation_text + " [Note: Visual description was partially truncated by token limit]"
                else:
                    raise RuntimeError(
                        f"Groq returned an incomplete page description (completion token limit reached) on page {page_number}"
                    )

            if not text:
                logger.error(
                    "Groq returned an empty page description for page %d (model=%s, finish_reason=%s)",
                    page_number,
                    self.model,
                    finish_reason,
                )
                raise RuntimeError(f"Groq returned an empty page description for page {page_number}")

            return text

    @staticmethod
    def _prepare_image(image_png: bytes) -> tuple[bytes, str]:
        """Validate and downsample/compress large images to stay under provider byte limits."""
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
