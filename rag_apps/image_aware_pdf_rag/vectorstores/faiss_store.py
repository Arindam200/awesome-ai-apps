"""In-memory FAISS vector store with chunk metadata."""

from __future__ import annotations

import threading
from typing import Any, Iterable

import faiss
import numpy as np

from interfaces.vector_store import (
    SearchResult,
    VectorDocument,
    validate_document,
    validate_search_input,
)


class FAISSVectorStore:
    """FAISS-backed implementation of the VectorStore contract.

    Vectors use inner-product similarity. For cosine similarity,
    supply L2-normalized document and query embeddings.
    """

    def __init__(self, dimension: int | None = None) -> None:
        if dimension is not None and (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 1
        ):
            raise ValueError("dimension must be a positive integer")

        self.dimension = dimension
        self.index: Any = None
        self._next_faiss_id = 1

        # Stable application chunk ID -> FAISS integer ID.
        self._chunk_to_faiss: dict[str, int] = {}

        # FAISS integer ID -> stored document fields.
        self._documents: dict[int, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _create_index(self, dimension: int) -> None:
        """Create an index that supports explicit integer IDs."""
        self.dimension = dimension
        base_index = faiss.IndexFlatIP(dimension)
        self.index = faiss.IndexIDMap2(base_index)

    @staticmethod
    def _validate_embedding(
        embedding: Iterable[float],
        expected_dimension: int | None = None,
    ) -> np.ndarray:
        """Validate numeric type, 1D shape, and dimension conformance of an embedding."""
        try:
            vector = np.asarray(list(embedding), dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding must contain numeric values") from exc

        if vector.ndim != 1 or vector.size == 0:
            raise ValueError("Embedding must be a non-empty one-dimensional vector")

        if not np.isfinite(vector).all():
            raise ValueError("Embedding must contain only finite values")

        if expected_dimension is not None and vector.size != expected_dimension:
            raise ValueError(
                f"Embedding dimension is {vector.size}; "
                f"expected {expected_dimension}"
            )

        return vector

    def add_documents(self, documents: list[VectorDocument]) -> None:
        """Add documents, replacing any existing documents with the same IDs."""

        if not documents:
            return

        with self._lock:
            prepared: list[tuple[VectorDocument, np.ndarray]] = []
            seen_ids: set[str] = set()
            expected_dimension = self.dimension

            for document in documents:
                validate_document(document)

                if document.id in seen_ids:
                    raise ValueError(f"Duplicate document ID: {document.id}")

                seen_ids.add(document.id)

                vector = self._validate_embedding(
                    document.embedding,
                    expected_dimension,
                )

                if expected_dimension is None:
                    expected_dimension = int(vector.size)

                prepared.append((document, vector))

            # Validate the entire batch before modifying the existing index.
            if self.dimension is None:
                self._create_index(expected_dimension)
            elif self.index is None:
                self._create_index(self.dimension)

            existing_ids = [
                document.id
                for document, _ in prepared
                if document.id in self._chunk_to_faiss
            ]
            self._delete_unlocked(existing_ids)

            vectors = np.vstack([vector for _, vector in prepared]).astype(
                np.float32,
                copy=False,
            )
            faiss_ids = np.arange(
                self._next_faiss_id,
                self._next_faiss_id + len(prepared),
                dtype=np.int64,
            )
            self.index.add_with_ids(vectors, faiss_ids)

            for (document, _), faiss_id in zip(prepared, faiss_ids):
                integer_id = int(faiss_id)
                self._chunk_to_faiss[document.id] = integer_id
                self._documents[integer_id] = {
                    "id": document.id,
                    "text": document.text,
                    "metadata": dict(document.metadata),
                }

            self._next_faiss_id += len(prepared)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return the most similar matching documents."""

        validate_search_input(query_embedding, top_k)

        if filters is not None and not isinstance(filters, dict):
            raise ValueError("filters must be a dictionary or None")

        with self._lock:
            query = self._validate_embedding(
                query_embedding,
                self.dimension,
            ).reshape(1, -1)

            if self.index is None or self.index.ntotal == 0:
                return []

            candidate_count = int(self.index.ntotal)
            scores, ids = self.index.search(query, candidate_count)

            results: list[SearchResult] = []

            for score, faiss_id in zip(scores[0], ids[0]):
                integer_id = int(faiss_id)

                if integer_id == -1:
                    continue

                record = self._documents.get(integer_id)
                if record is None:
                    continue

                metadata = record["metadata"]

                if filters and any(
                    metadata.get(key) != value
                    for key, value in filters.items()
                ):
                    continue

                results.append(
                    SearchResult(
                        id=record["id"],
                        text=record["text"],
                        metadata=dict(metadata),
                        score=float(score),
                    )
                )

                if len(results) >= top_k:
                    break

            return results

    def delete(self, ids: list[str]) -> None:
        """Delete chunks by their stable application IDs."""
        if not ids:
            return
        with self._lock:
            self._delete_unlocked(ids)

    def _delete_unlocked(self, ids: list[str]) -> None:
        """Delete chunks by stable IDs while the lock is held."""
        integer_ids = [
            self._chunk_to_faiss[chunk_id]
            for chunk_id in set(ids)
            if chunk_id in self._chunk_to_faiss
        ]

        if not integer_ids:
            return

        self.index.remove_ids(np.asarray(integer_ids, dtype=np.int64))

        for integer_id in integer_ids:
            record = self._documents.pop(integer_id, None)
            if record:
                self._chunk_to_faiss.pop(record["id"], None)

    def delete_source(self, source_id: str) -> int:
        """Delete every chunk belonging to one PDF; return count removed."""

        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must be a non-empty string")

        with self._lock:
            chunk_ids = [
                record["id"]
                for record in self._documents.values()
                if record["metadata"].get("source_id") == source_id
            ]
            self._delete_unlocked(chunk_ids)
        return len(chunk_ids)
