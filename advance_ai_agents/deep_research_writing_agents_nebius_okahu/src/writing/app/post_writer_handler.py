"""LinkedIn post generation and editing logic."""

import logging

from writing.config.prompts import PROMPT_EDIT_POST, PROMPT_WRITE_POST
from writing.models.schemas import Post, Profiles, Review
from writing.utils.llm import call_llm

logger = logging.getLogger(__name__)


async def write_post(
    guideline: str,
    research: str,
    profiles: Profiles,
    post_examples: str = "<none>",
) -> Post:
    """Generate a LinkedIn post from guideline, research, profiles, and examples.

    Args:
        guideline: The post guideline content.
        research: The research material content.
        profiles: The writing profiles to follow.
        post_examples: Formatted few-shot post examples.

    Returns:
        A Post with the generated content.
    """

    prompt = PROMPT_WRITE_POST.format(
        guideline=guideline,
        research=research,
        structure_profile=profiles.structure.content,
        terminology_profile=profiles.terminology.content,
        character_profile=profiles.character.content,
        post_examples=post_examples,
    )

    response = await call_llm(prompt)

    return Post(content=response)


def _format_reviews(reviews: list[Review]) -> str:
    """Format reviews into a readable text block for the edit prompt."""

    lines: list[str] = []
    for i, review in enumerate(reviews, 1):
        lines.append(f"{i}. [{review.profile}] @ {review.location}")
        lines.append(f"   {review.comment}")
        lines.append("")

    return "\n".join(lines)


async def edit_post(
    post: Post,
    reviews: list[Review],
    guideline: str,
    research: str,
    profiles: Profiles,
    post_examples: str = "<none>",
) -> Post:
    """Edit a LinkedIn post based on reviewer feedback.

    Args:
        post: The current post to edit.
        reviews: List of reviews to address.
        guideline: The post guideline content.
        research: The research material content.
        profiles: The writing profiles to follow.
        post_examples: Formatted few-shot post examples.

    Returns:
        A Post with the edited content.
    """

    reviews_text = _format_reviews(reviews)

    prompt = PROMPT_EDIT_POST.format(
        guideline=guideline,
        research=research,
        structure_profile=profiles.structure.content,
        terminology_profile=profiles.terminology.content,
        character_profile=profiles.character.content,
        post=post.content,
        reviews=reviews_text,
        post_examples=post_examples,
    )

    response = await call_llm(prompt)

    return Post(content=response)
