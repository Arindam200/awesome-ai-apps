"""Pydantic models for RAG operations."""

from typing import List, Optional

from pydantic import BaseModel, Field

from ..core.types import QueryMode
class SourceNode(BaseModel):
    """Source node with file information and relevance."""

    file_name: str = Field(description="Name of the file")
    url: str = Field(description="GitHub URL of the file")
    score: float = Field(description="Relevance score")
    content: str = Field(description="Content excerpt")


class QueryRequest(BaseModel):
    """Query request model."""

    repository: str = Field(description="Repository name to query")
    query: str = Field(description="User's question")
    mode: QueryMode = Field(default=QueryMode.DEFAULT, description="Search mode")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")


class QueryResponse(BaseModel):
    """Query response model."""

    response: str = Field(description="AI-generated response")
    source_nodes: List[SourceNode] = Field(description="Source citations")
    repository: str = Field(description="Queried repository")
    mode: QueryMode = Field(description="Search mode used")
    processing_time: float = Field(description="Query processing time in seconds")


class IngestionProgress(BaseModel):
    """Ingestion progress tracking."""

    total_documents: int = Field(description="Total documents to process")
    processed_documents: int = Field(description="Documents processed so far")
    current_phase: str = Field(description="Current processing phase")
    elapsed_time: float = Field(description="Elapsed time in seconds")
    estimated_remaining: Optional[float] = Field(
        default=None, description="Estimated remaining time"
    )