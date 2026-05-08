"""Image generation logic using Gemini image generation."""

import logging
from pathlib import Path

from writing.config.prompts import PROMPT_GENERATE_IMAGE, PROMPT_IMAGE_SCENE
from writing.models.schemas import Profiles
from writing.utils.llm import call_gemini_image, call_llm

logger = logging.getLogger(__name__)


async def _extract_visual_scene(post_content: str) -> str:
    """Use a text LLM to distill a post into a text-free visual scene description.

    This prevents the image model from reading the raw post and rendering
    its bullet points and labels as text in the image.
    """

    prompt = PROMPT_IMAGE_SCENE.format(post=post_content)
    scene = await call_llm(prompt)

    logger.info(f"Extracted visual scene: {scene}")

    return scene


async def generate_post_image(
    post_content: str,
    profiles: Profiles,
    output_path: Path,
    reference_images: list[Path] | None = None,
) -> Path:
    """Generate a LinkedIn post image using Gemini image generation.

    First extracts a text-free visual scene description from the post,
    then generates an image anchored to the branding profiles, with
    optional reference images as few-shot style examples.

    Args:
        post_content: The post text to base the image on.
        profiles: Writing profiles (uses character and branding).
        output_path: Path to save the generated image.
        reference_images: Optional list of image paths as style references.

    Returns:
        The path to the saved image.
    """

    scene = await _extract_visual_scene(post_content)

    prompt = PROMPT_GENERATE_IMAGE.format(
        branding_profile=profiles.branding.content,
        character_profile=profiles.character.content,
        scene=scene,
    )

    return await call_gemini_image(prompt, output_path, reference_images)
