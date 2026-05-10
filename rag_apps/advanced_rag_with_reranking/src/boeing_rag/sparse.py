from __future__ import annotations

from fastembed import SparseTextEmbedding
from qdrant_client.http import models as qm

from boeing_rag.config import Settings


class SparseEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = SparseTextEmbedding(settings.sparse_model)

    def embed_texts(self, texts: list[str]) -> list[qm.SparseVector]:
        vectors: list[qm.SparseVector] = []
        for vector in self.model.embed(texts):
            vectors.append(
                qm.SparseVector(
                    indices=vector.indices.tolist(),
                    values=vector.values.tolist(),
                )
            )
        return vectors

    def embed_query(self, text: str) -> qm.SparseVector:
        return self.embed_texts([text])[0]
