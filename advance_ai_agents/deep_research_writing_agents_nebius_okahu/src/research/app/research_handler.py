"""Exa-backed research logic."""

import logging

from research.config.prompts import PROMPT_RESEARCH
from research.models.schemas import ResearchResult, ResearchSource
from research.utils.llm import call_exa_search

logger = logging.getLogger(__name__)


async def run_grounded_search(query: str) -> ResearchResult:
    """Run Exa real-time research for a single query.

    Uses Exa answer search to get a comprehensive answer with source citations.

    Args:
        query: The research query to search for.

    Returns:
        A ResearchResult with the answer and extracted sources.
    """

    # Wrap the raw query in the research prompt template, which adds
    # instructions for Exa to provide a detailed, well-sourced answer.
    prompt = PROMPT_RESEARCH.format(query=query)

    # Call Exa for real-time search with citations.
    # Returns the answer text and a list of raw source dicts (url + title)
    # extracted from Exa citation metadata.
    answer_text, raw_sources = await call_exa_search(prompt)

    # Convert raw source dicts into typed Pydantic ResearchSource objects.
    sources = [
        ResearchSource(
            url=src["url"],
            title=src.get("title", ""),
            snippet=src.get("snippet", ""),
        )
        for src in raw_sources
    ]

    # Package everything into a structured ResearchResult model
    return ResearchResult(
        query=query,
        answer=answer_text,
        sources=sources,
    )
