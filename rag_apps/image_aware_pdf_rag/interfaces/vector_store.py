
"""Provider-independent interface for vector storage and retrieval.

Potential adapters:
- FAISS (local)
- Chroma (local or server-backed)
- Other vector databases

The vector store accepts precomputed embeddings. Embedding generation
belongs to interfaces/embeddings.py and its provider adapters.
"""

from dataclasses import dataclass
import math
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class VectorDocument:
    """A document or visual description stored for retrieval."""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    """A retrieved document and its similarity/distance score."""

    id: str
    text: str
    metadata: dict[str, Any]
    score: float


@runtime_checkable
class VectorStore(Protocol):
    """Contract implemented by every vector-store adapter."""

    def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> None:
        """Insert or update documents by ID."""
        ...

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return the most relevant documents for a query vector.

        Results should be ordered from most relevant to least relevant.
        The meaning of score must be documented by each adapter.
        """
        ...

    def delete(self, ids: list[str]) -> None:
        """Delete documents by ID.

        Missing IDs should be handled consistently by each adapter.
        """
        ...


def validate_vector(vector: list[float]) -> None:
    """Validate a non-empty, finite numerical vector."""

    if not isinstance(vector, list) or not vector:
        raise ValueError("vector must be a non-empty list")

    for value in vector:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("vector values must be finite numbers")


def validate_document(document: VectorDocument) -> None:
    """Validate a document before inserting it."""

    if not isinstance(document.id, str) or not document.id.strip():
        raise ValueError("document ID must be a non-empty string")

    if not isinstance(document.text, str) or not document.text.strip():
        raise ValueError("document text must be a non-empty string")

    validate_vector(document.embedding)

    if not isinstance(document.metadata, dict):
        raise ValueError("document metadata must be a dictionary")

    page_number = document.metadata.get("page_number")

    if (
        page_number is not None
        and (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        )
    ):
        raise ValueError("page_number metadata must be a positive integer")


def validate_search_input(
    query_embedding: list[float],
    top_k: int,
) -> None:
    """Validate a vector-search request."""

    validate_vector(query_embedding)

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")
