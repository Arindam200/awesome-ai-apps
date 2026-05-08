"""Local dataset loading for LinkedIn post evaluation."""

import logging
from typing import Any

from writing.app.dataset_loader import DATASET_DIR, load_by_scope

logger = logging.getLogger(__name__)


def load_offline_eval_items(split: str) -> list[dict[str, Any]]:
    """Load pre-generated post evaluation items for a dataset split."""

    entries = load_by_scope(split)
    if not entries:
        msg = f"No entries found for split '{split}'"
        raise ValueError(msg)

    items: list[dict[str, Any]] = []
    for entry in entries:
        if entry.label is None or entry.critique is None:
            continue

        generated = entry.generated_content(DATASET_DIR)
        guideline = entry.guideline_content(DATASET_DIR)
        research = entry.research_content(DATASET_DIR)

        if not generated:
            logger.warning("Skipping %s: missing generated post", entry.slug)
            continue

        items.append(
            {
                "name": entry.slug,
                "slug": entry.slug,
                "guideline": guideline,
                "research": research,
                "generated_post": generated,
                "label": entry.label.value,
                "critique": entry.critique,
            }
        )

    return items


def load_online_eval_items(split: str) -> list[dict[str, Any]]:
    """Load guideline/research items for online generation + evaluation."""

    entries = load_by_scope(split)
    if not entries:
        msg = f"No entries found for split '{split}'"
        raise ValueError(msg)

    items: list[dict[str, Any]] = []
    for entry in entries:
        guideline = entry.guideline_content(DATASET_DIR)
        research = entry.research_content(DATASET_DIR)

        if not guideline:
            logger.warning("Skipping %s: missing guideline", entry.slug)
            continue

        item: dict[str, Any] = {
            "name": entry.slug,
            "slug": entry.slug,
            "guideline": guideline,
            "research": research,
        }
        if entry.label is not None:
            item["label"] = entry.label.value
        items.append(item)

    return items
