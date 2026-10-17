
"""Provider-independent interface for PDF page visual analysis.

Provider adapters may use:
- Hugging Face vision models
- Groq models that support image input
- OpenAI vision models
- Anthropic Claude vision models
- Local vision-language models

This module contains no provider-specific SDK dependencies.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class VisionImageTooLargeError(RuntimeError):
    """Raised when an image cannot be reduced to a provider's size limit."""


@dataclass(frozen=True)
class VisionResult:
    """Visual analysis result tied to its source PDF page."""

    page_number: int
    description: str

    def __post_init__(self):
        if (
            not isinstance(self.page_number, int)
            or isinstance(self.page_number, bool)
            or self.page_number < 1
        ):
            raise ValueError("page_number must be a one-based integer")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")


@runtime_checkable
class VisionModel(Protocol):
    """Contract that every vision provider adapter must implement."""

    def describe_page(
        self,
        image_png: bytes,
        page_number: int,
    ) -> VisionResult:
        """Analyze one rendered PDF page.

        Args:
            image_png: PNG image bytes from PDF ingestion.
            page_number: Original one-based PDF page number.

        Returns:
            A VisionResult containing a visual description and page number.

        Raises:
            ValueError: If the image or page number is invalid.
            RuntimeError: If the provider fails to analyze the image.
        """
        ...


def validate_vision_input(
    image_png: bytes,
    page_number: int,
) -> None:
    """Validate common inputs before calling a vision provider."""

    if not isinstance(image_png, bytes) or not image_png:
        raise ValueError("image_png must be non-empty bytes")

    if not image_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("image_png must contain PNG image data")

    if (
        not isinstance(page_number, int)
        or isinstance(page_number, bool)
        or page_number < 1
    ):
        raise ValueError("page_number must be a one-based integer")
