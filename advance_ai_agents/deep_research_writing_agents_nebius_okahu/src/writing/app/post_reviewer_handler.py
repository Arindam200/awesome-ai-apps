"""LinkedIn post evaluation logic."""

import logging

from writing.config.prompts import PROMPT_REVIEW_POST
from writing.config.settings import get_settings
from writing.models.schemas import Post, PostReviews, Profiles
from writing.utils.llm import call_llm

logger = logging.getLogger(__name__)


async def review_post(
    post: Post,
    guideline: str,
    profiles: Profiles,
    human_feedback: str | None = None,
    max_reviews: int = 5,
) -> PostReviews:
    """Evaluate a LinkedIn post against profiles and guideline.

    Uses Nebius through LangChain with structured output instructions.

    Args:
        post: The post to review.
        guideline: The post guideline content.
        profiles: The writing profiles to check against.
        human_feedback: Optional human feedback (takes highest priority).
        max_reviews: Maximum number of reviews to produce.

    Returns:
        A PostReviews object with the list of reviews.
    """

    settings = get_settings()

    human_feedback_section = ""
    if human_feedback:
        human_feedback_section = (
            f"**IMPORTANT — Human Feedback (highest priority):**\n"
            f"The user provided the following feedback. Address it before "
            f"checking profiles.\n\n<human_feedback>\n{human_feedback}\n</human_feedback>\n"
        )

    prompt = PROMPT_REVIEW_POST.format(
        post=post.content,
        guideline=guideline,
        structure_profile=profiles.structure.content,
        terminology_profile=profiles.terminology.content,
        character_profile=profiles.character.content,
        human_feedback_section=human_feedback_section,
        max_reviews=max_reviews,
    )

    response = await call_llm(
        prompt,
        model=settings.reviewer_model,
        response_schema=PostReviews,
    )

    return PostReviews.model_validate_json(response)
