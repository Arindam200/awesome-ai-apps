
"""Provider-independent visual description processing for PDF pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from interfaces.vision import (
    VisionModel,
    VisionResult,
    validate_vision_input,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageVisualDescription:
    """A visual description associated with its original PDF page."""

    page_number: int
    description: str
    content_type: str = "visual_description"


@dataclass(frozen=True)
class PageVisualBatch:
    """Successful page descriptions and failures keyed by page number."""

    descriptions: list[PageVisualDescription]
    failures: dict[int, str]


def describe_pdf_pages(
    pages: Iterable[object],
    vision_model: VisionModel,
) -> PageVisualBatch:
    """Generate visual descriptions for rendered PDF pages.

    Each page is expected to expose:
      - page_number: one-based PDF page number
      - image_png: rendered PNG bytes

    Pages without a rendered image are skipped.
    """

    descriptions: list[PageVisualDescription] = []
    failures: dict[int, str] = {}

    for page in pages:
        page_number = getattr(page, "page_number", None)
        image_png = getattr(page, "image_png", None)

        if (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            raise ValueError(
                "Every page must have a valid one-based page_number"
            )

        # Some ingestion results may not have a usable rendered image.
        if not image_png:
            continue

        try:
            validate_vision_input(image_png, page_number)
            result: VisionResult = vision_model.describe_page(
                image_png=image_png,
                page_number=page_number,
            )
        except Exception as exc:
            failures[page_number] = str(exc)
            logger.exception(
                "Visual description failed for page %s",
                page_number,
            )
            continue

        if result.page_number != page_number:
            raise ValueError(
                "Vision model returned a different page number "
                f"({result.page_number}) than requested ({page_number})"
            )

        description = result.description.strip()

        if not description:
            continue

        descriptions.append(
            PageVisualDescription(
                page_number=page_number,
                description=description,
            )
        )

    return PageVisualBatch(descriptions=descriptions, failures=failures)
