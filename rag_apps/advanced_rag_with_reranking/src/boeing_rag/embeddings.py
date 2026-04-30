from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable

import numpy as np
from openai import OpenAI

from boeing_rag.config import Settings


class EmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: OpenAI | None = None
        if settings.use_nebius_embeddings:
            self.client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.client:
            response = self.client.embeddings.create(
                model=self.settings.nebius_embed_model or "",
                input=texts,
            )
            return [item.embedding for item in response.data]
        return [self._local_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def fallback_dimension(self) -> int:
        return self.settings.local_embed_dim

    def _local_embedding(self, text: str) -> list[float]:
        dim = self.settings.local_embed_dim
        vector = np.zeros(dim, dtype=np.float32)
        tokens = self._tokens(text)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        for left, right in zip(tokens, tokens[1:]):
            digest = hashlib.blake2b(f"{left} {right}".encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % dim
            vector[bucket] += 0.5

        norm = float(np.linalg.norm(vector))
        if math.isclose(norm, 0.0):
            return vector.tolist()
        return (vector / norm).tolist()

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-&]+", text.lower())


def batched(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
