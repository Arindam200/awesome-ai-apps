"""LinkedIn post image generation tool."""

import logging
from pathlib import Path
from typing import Any

from writing.app.dataset_loader import load_examples
from writing.app.image_handler import generate_post_image
from writing.app.profile_loader import load_profiles
from writing.config.constants import IMAGE_FILE, POST_FILE

logger = logging.getLogger(__name__)


async def generate_image_tool(working_dir: str) -> dict[str, Any]:
    """Generate a LinkedIn post image using Gemini image generation.

    Reads the existing post.md and generates a professional image
    following the branding and character profiles, using dataset media
    as style reference images.

    Args:
        working_dir: Path to the working directory with post.md.

    Returns:
        Dict with status, image path, and message.
    """

    working_path = Path(working_dir)

    post_path = working_path / POST_FILE
    if not post_path.exists():
        msg = f"{POST_FILE} not found in {working_dir}. Run generate_post first."
        raise FileNotFoundError(msg)

    post_content = post_path.read_text(encoding="utf-8")
    profiles = load_profiles()
    examples = load_examples()
    output_path = working_path / IMAGE_FILE

    # Collect reference image paths from media examples
    reference_images = [ex.media_path for ex in examples.media_examples]

    logger.info(
        f"Generating LinkedIn post image with {len(reference_images)} reference image(s)..."
    )
    await generate_post_image(post_content, profiles, output_path, reference_images)

    return {
        "status": "success",
        "image_path": str(output_path.resolve()),
        "message": f"Generated LinkedIn post image saved to {IMAGE_FILE}",
    }
