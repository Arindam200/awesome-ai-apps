"""LinkedIn post editing tool with human feedback."""

import json
import logging
from pathlib import Path
from typing import Any

from writing.app.dataset_loader import load_examples
from writing.app.post_reviewer_handler import review_post
from writing.app.post_writer_handler import edit_post
from writing.app.profile_loader import load_profiles
from writing.config.constants import (
    GUIDELINE_FILE,
    MEMORY_FOLDER,
    POST_FILE,
    RESEARCH_FILE,
)
from writing.models.schemas import Post

logger = logging.getLogger(__name__)


async def edit_post_tool(
    working_dir: str,
    human_feedback: str,
    delete_iterations: bool = False,
) -> dict[str, Any]:
    """Edit an existing LinkedIn post with one review+edit pass guided by human feedback.

    Reads the existing post.md, runs a review pass with the human feedback
    as highest priority, then edits the post accordingly.

    By default, saves a versioned copy (post_N.md) and reviews to .memory/.
    Pass delete_iterations=True to skip saving versioned files and reviews.

    Args:
        working_dir: Path to the working directory with post.md, guideline.md, research.md.
        human_feedback: The user's feedback on what to change.
        delete_iterations: If True, only update post.md and discard
            versioned copies and reviews.

    Returns:
        Dict with status, reviews summary, and output file path.
    """

    working_path = Path(working_dir)

    # Validate inputs
    post_path = working_path / POST_FILE
    guideline_path = working_path / GUIDELINE_FILE
    research_path = working_path / RESEARCH_FILE

    if not post_path.exists():
        msg = f"{POST_FILE} not found in {working_dir}. Run generate_post first."
        raise FileNotFoundError(msg)
    if not guideline_path.exists():
        msg = f"{GUIDELINE_FILE} not found in {working_dir}"
        raise FileNotFoundError(msg)

    post_content = post_path.read_text(encoding="utf-8")
    guideline = guideline_path.read_text(encoding="utf-8")
    research = (
        research_path.read_text(encoding="utf-8") if research_path.exists() else ""
    )
    profiles = load_profiles()
    examples = load_examples()
    post_examples_text = examples.format_post_examples()
    post = Post(content=post_content)

    # Review with human feedback
    logger.info("Reviewing post with human feedback...")
    reviews_result = await review_post(
        post, guideline, profiles, human_feedback=human_feedback
    )
    reviews = reviews_result.reviews

    # Save reviews (unless delete_iterations is set)
    if not delete_iterations:
        memory_path = working_path / MEMORY_FOLDER
        memory_path.mkdir(parents=True, exist_ok=True)
        reviews_data = [r.model_dump() for r in reviews]
        (memory_path / "reviews_edit.json").write_text(
            json.dumps(reviews_data, indent=2), encoding="utf-8"
        )

    if not reviews:
        logger.info("No issues found. Post unchanged.")
        return {
            "status": "success",
            "reviews_count": 0,
            "output_path": str(post_path.resolve()),
            "message": "No issues found based on feedback. Post unchanged.",
            "post": post.content,
        }

    logger.info(f"Found {len(reviews)} review(s). Editing post...")

    # Edit
    edited_post = await edit_post(
        post, reviews, guideline, research, profiles, post_examples_text
    )

    # Save versioned copy (unless delete_iterations is set)
    if not delete_iterations:
        existing_versions = sorted(working_path.glob("post_*.md"))
        next_version = len(existing_versions)
        version_path = working_path / f"post_{next_version}.md"
        version_path.write_text(edited_post.content, encoding="utf-8")
        logger.info(f"Versioned post saved to {version_path.name}")

    # Update post.md
    post_path.write_text(edited_post.content, encoding="utf-8")
    logger.info(f"Updated {POST_FILE}")

    # Format reviews for display
    reviews_summary = "\n".join(
        f"- [{r.profile}] {r.location}: {r.comment}" for r in reviews
    )

    return {
        "status": "success",
        "reviews_count": len(reviews),
        "output_path": str(post_path.resolve()),
        "message": (
            f"Applied {len(reviews)} review(s) based on feedback. "
            f"Updated post saved to {POST_FILE}\n\nReviews addressed:\n{reviews_summary}"
        ),
        "post": edited_post.content,
    }
