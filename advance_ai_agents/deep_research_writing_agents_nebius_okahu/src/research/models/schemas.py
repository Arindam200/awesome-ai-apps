"""Pydantic models for research operations."""

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    """A single source from research results."""

    url: str = Field(description="The URL of the source")
    title: str = Field(default="", description="Title of the source")
    snippet: str = Field(default="", description="Relevant excerpt from the source")


class ResearchResult(BaseModel):
    """A single research result from a grounded search."""

    query: str = Field(description="The query that produced this result")
    answer: str = Field(description="The research answer")
    sources: list[ResearchSource] = Field(
        default_factory=list, description="Sources cited in the answer"
    )
