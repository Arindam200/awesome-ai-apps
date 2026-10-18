
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


import re

PAGE_REFERENCE_PATTERN = re.compile(r"\b(?:page|p\.?)\s*(\d+)\b", re.IGNORECASE)
CHART_OR_FIGURE_PATTERN = re.compile(
    r"\b(?:chart|figure|fig\.?|table|diagram)\s*([0-9]+(?:\.[0-9]+)*)\b",
    re.IGNORECASE,
)


class PDFRetriever:
    """Connect query embeddings, vector search, and PDF evidence with reference-aware ranking."""

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
        """Retrieve relevant evidence while preserving page numbers and prioritizing specific references.

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

        # Extract explicit structural references from the query (e.g., 'Chart 1.1', 'Page 1')
        page_matches = [int(m) for m in PAGE_REFERENCE_PATTERN.findall(query)]
        chart_matches = CHART_OR_FIGURE_PATTERN.findall(query)
        has_specific_ref = bool(page_matches or chart_matches)

        # Retrieve a broader pool of candidates to evaluate reference alignment
        fetch_limit = max(top_k * 4, 20) if has_specific_ref else top_k
        raw_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=fetch_limit,
            filters=filters,
        )

        valid_candidates = []

        for result in raw_results:
            metadata = result.metadata

            page_number = metadata.get("page_number")
            if (
                isinstance(page_number, bool)
                or not isinstance(page_number, int)
                or page_number < 1
            ):
                continue

            text = result.text.strip()
            if not text:
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

            score = getattr(result, "score", 0.0)

            # Compute reference alignment boost
            ref_boost = 0.0
            lower_text = text.lower()

            # Boost if query explicitly cited this page
            if page_number in page_matches:
                ref_boost += 2.0

            # Boost if query cited a specific chart/figure/table (e.g. Chart 1.1) and it appears in text
            for chart_id in chart_matches:
                pattern = (
                    rf"\b(?:chart|figure|fig\.?|table|diagram)\s*"
                    rf"{re.escape(chart_id)}(?!\.\d)\b"
                )
                if re.search(pattern, lower_text):
                    ref_boost += 3.0

            valid_candidates.append({
                "page_number": page_number,
                "text": text,
                "source": source,
                "content_type": content_type,
                "score": score,
                "composite_score": score + ref_boost,
            })

        # Re-sort candidates considering semantic similarity and explicit reference alignment
        if has_specific_ref:
            valid_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

        evidence: list[RetrievedEvidence] = []
        for item in valid_candidates[:top_k]:
            evidence.append(
                RetrievedEvidence(
                    page_number=item["page_number"],
                    text=item["text"],
                    source=item["source"],
                    content_type=item["content_type"],
                )
            )

        return evidence
