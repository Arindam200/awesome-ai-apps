
"""Retrieve page-aware evidence using embeddings and a vector store."""

from __future__ import annotations

from typing import Any, Protocol

from interfaces.embeddings import validate_query
from interfaces.vector_store import SearchResult
from pipeline import RetrievedEvidence


class EmbeddingModelLike(Protocol):
    def embed_query(self, text: str) -> list[float]:
        ...


class VectorStoreLike(Protocol):
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        ...


class PDFRetriever:
    """Connect query embeddings, vector search, and PDF evidence."""

    def __init__(
        self,
        embeddings: EmbeddingModelLike,
        vector_store: VectorStoreLike,
    ) -> None:
        self.embeddings = embeddings
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_id: str | None = None,
    ) -> list[RetrievedEvidence]:
        """Retrieve relevant evidence while preserving page numbers.

        Args:
            query: User's question.
            top_k: Maximum number of chunks to return.
            source_id: Optional PDF ID to search within one document.
        """

        validate_query(query)

        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")

        if source_id is not None and (
            not isinstance(source_id, str) or not source_id.strip()
        ):
            raise ValueError("source_id must be a non-empty string or None")

        query_embedding = self.embeddings.embed_query(query)

        filters = {"source_id": source_id} if source_id is not None else None

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )

        evidence: list[RetrievedEvidence] = []

        for result in results:
            metadata = result.metadata

            page_number = metadata.get("page_number")
            if (
                isinstance(page_number, bool)
                or not isinstance(page_number, int)
                or page_number < 1
            ):
                # A result without a valid page number cannot support
                # reliable page-level citations.
                continue

            if not result.text.strip():
                continue

            source = metadata.get(
                "source_name",
                metadata.get("source", "uploaded PDF"),
            )
            if not isinstance(source, str) or not source.strip():
                source = "uploaded PDF"

            content_type = metadata.get("content_type", "text")
            if not isinstance(content_type, str) or not content_type.strip():
                content_type = "text"

            evidence.append(
                RetrievedEvidence(
                    page_number=page_number,
                    text=result.text,
                    source=source,
                    content_type=content_type,
                )
            )

        return evidence
