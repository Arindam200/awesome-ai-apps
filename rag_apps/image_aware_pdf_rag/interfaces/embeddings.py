
"""Provider-independent interface for text embeddings.

Potential adapters:
- Local sentence-transformers models
- Hugging Face embedding models
- OpenAI embedding models
- Other compatible embedding providers

No provider-specific SDK dependencies belong in this module.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingModel(Protocol):
    """Contract for embedding text into numerical vectors."""

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed multiple document chunks.

        Returns one vector per input text, in the same order.
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a user query into the same vector space."""
        ...


def validate_texts(texts: list[str]) -> None:
    """Validate document texts before embedding."""
    if not isinstance(texts, list) or not texts:
        raise ValueError("texts must be a non-empty list")

    for index, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"texts[{index}] must be a non-empty string"
            )


def validate_query(text: str) -> None:
    """Validate a query before embedding."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("query must be a non-empty string")


def validate_embedding(
    vector: list[float],
) -> None:
    """Validate a single embedding vector."""
    if not isinstance(vector, list) or not vector:
        raise ValueError("embedding must be a non-empty list")

    for value in vector:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
        ):
            raise ValueError("embedding values must be numeric")

        # Reject NaN and infinity.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("embedding values must be finite")


def validate_embeddings(
    vectors: list[list[float]],
    expected_count: int,
) -> None:
    """Validate embedding count, dimensions, and values."""
    if not isinstance(vectors, list):
        raise ValueError("embeddings must be a list")

    if len(vectors) != expected_count:
        raise ValueError(
            f"Expected {expected_count} embeddings, got {len(vectors)}"
        )

    if expected_count == 0:
        return

    dimensions = None

    for vector in vectors:
        validate_embedding(vector)

        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise ValueError(
                "All embeddings must have the same dimensions"
            )
