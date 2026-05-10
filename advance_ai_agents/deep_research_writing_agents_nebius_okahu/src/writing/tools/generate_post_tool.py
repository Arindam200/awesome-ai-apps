"""LinkedIn post generation tool with evaluate-optimize loop."""

import json
import logging
from pathlib import Path
from typing import Any

from writing.app.generate_post import generate_post
from writing.config.constants import (
    GUIDELINE_FILE,
    MEMORY_FOLDER,
    POST_FILE,
    RESEARCH_FILE,
)
from writing.config.settings import get_settings

logger = logging.getLogger(__name__)


async def generate_post_tool(
    working_dir: str,
    delete_iterations: bool = False,
) -> dict[str, Any]:
    """Generate a LinkedIn post with an evaluate-optimize loop.

    Reads guideline.md and research.md, then delegates to the shared
    generate_post() function for the full write -> [review -> edit] x N loop.

    By default, all intermediate post versions and reviews are saved.
    Pass delete_iterations=True to keep only the final post.

    Args:
        working_dir: Path to the working directory with guideline.md and research.md.
        delete_iterations: If True, only save the final post.md and discard
            intermediate versions and reviews.

    Returns:
        Dict with status, message, and output file path.
    """

    settings = get_settings()
    working_path = Path(working_dir)

    # Validate inputs
    guideline_path = working_path / GUIDELINE_FILE
    research_path = working_path / RESEARCH_FILE
    if not guideline_path.exists():
        msg = f"{GUIDELINE_FILE} not found in {working_dir}"
        raise FileNotFoundError(msg)
    if not research_path.exists():
        msg = f"{RESEARCH_FILE} not found in {working_dir}"
        raise FileNotFoundError(msg)

    guideline = guideline_path.read_text(encoding="utf-8")
    research = research_path.read_text(encoding="utf-8")

    # Use the shared generate_post function (same logic as evals)
    result = await generate_post(guideline, research)

    # Save intermediate versions and reviews (unless delete_iterations is set)
    if not delete_iterations:
        # Save all post versions
        for idx, version in enumerate(result.versions):
            version_path = working_path / f"post_{idx}.md"
            version_path.write_text(version.content, encoding="utf-8")
            logger.info(f"Saved version {idx} to {version_path.name}")

        # Save reviews to .memory/
        if result.reviews:
            memory_path = working_path / MEMORY_FOLDER
            memory_path.mkdir(parents=True, exist_ok=True)
            for idx, reviews_result in enumerate(result.reviews):
                reviews_data = [r.model_dump() for r in reviews_result.reviews]
                reviews_path = memory_path / f"reviews_{idx + 1}.json"
                reviews_path.write_text(
                    json.dumps(reviews_data, indent=2), encoding="utf-8"
                )
                logger.info(f"Saved reviews to {reviews_path.name}")

    # Save final version
    output_path = working_path / POST_FILE
    output_path.write_text(result.post.content, encoding="utf-8")
    logger.info(f"Final post saved to {output_path}")

    return {
        "status": "success",
        "review_iterations": settings.num_reviews,
        "output_path": str(output_path.resolve()),
        "message": (
            f"Generated LinkedIn post with {settings.num_reviews} review/edit iterations. "
            f"Final post saved to {POST_FILE}"
        ),
        "post": result.post.content,
    }
