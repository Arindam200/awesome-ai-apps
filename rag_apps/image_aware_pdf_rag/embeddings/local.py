
"""Local text embeddings using Sentence Transformers."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from interfaces.embeddings import (
    validate_query,
    validate_texts,
)


class LocalEmbeddingModel:
    """Generate text embeddings locally, without an embedding API.

    The model is downloaded on first use and then cached locally.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")

        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings
        self.model = SentenceTransformer(
            model_name,
            device=device,
        )
        self.dimension = self.model.get_sentence_embedding_dimension()

        if not self.dimension:
            raise RuntimeError("Could not determine embedding dimension")

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed multiple document chunks."""

        validate_texts(texts)

        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )

        vectors = np.asarray(vectors, dtype=np.float32)

        if vectors.ndim != 2 or vectors.shape != (
            len(texts),
            self.dimension,
        ):
            raise RuntimeError("Embedding model returned an unexpected shape")

        if not np.isfinite(vectors).all():
            raise RuntimeError("Embedding model returned non-finite values")

        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a user question for semantic retrieval."""

        validate_query(text)

        vector = self.model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )

        vector = np.asarray(vector, dtype=np.float32)

        if vector.shape != (1, self.dimension):
            raise RuntimeError("Embedding model returned an unexpected shape")

        if not np.isfinite(vector).all():
            raise RuntimeError("Embedding model returned non-finite values")

        return vector[0].tolist()
