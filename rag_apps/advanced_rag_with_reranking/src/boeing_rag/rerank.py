from __future__ import annotations

import re
from functools import lru_cache

from boeing_rag.config import Settings
from boeing_rag.orm import ChunkRecord

_BOILERPLATE_RE = re.compile(
    r"(?:"
    r"originally incorporated|Executive Officers of the Registrant"
    r"|No material portion.*seasonal"
    r"|FORM 10-K|SECURITIES AND EXCHANGE COMMISSION"
    r"|Exhibit\s+\d+\.\d+|PART\s+[IVX]+\s*\|.*Page"
    r"|\.{5,}"
    r")",
    re.I,
)


def _noise_penalty(chunk: ChunkRecord) -> float:
    text = chunk.text
    hits = len(_BOILERPLATE_RE.findall(text))
    if hits >= 3:
        return -2.0
    if hits >= 1:
        return -0.6
    alpha = sum(1 for c in text if c.isalpha())
    if len(text) > 100 and alpha / len(text) < 0.35:
        return -0.4
    return 0.0


class Reranker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cross_encoder = None
        if settings.reranker_provider == "sentence_transformers":
            self.cross_encoder = self._load_cross_encoder(settings.reranker_model)

    def rerank(self, question: str, chunks: list[ChunkRecord], limit: int) -> list[tuple[ChunkRecord, float]]:
        if not chunks:
            return []
        if self.cross_encoder:
            pairs = [(question, _rank_text(chunk)) for chunk in chunks]
            scores = self.cross_encoder.predict(pairs)
            ranked = sorted(zip(chunks, scores, strict=True), key=lambda item: float(item[1]), reverse=True)
            return [(chunk, float(score)) for chunk, score in ranked[:limit]]

        query_terms = set(_terms(question))
        query_phrases = _phrases(question)
        wants_table = any(term in question.lower() for term in ["table", "metric", "amount", "total", "progress"])
        ranked: list[tuple[ChunkRecord, float]] = []
        for chunk in chunks:
            text = _rank_text(chunk)
            terms = _terms(text)
            lower = text.lower()
            if not terms:
                score = 0.0
            else:
                term_set = set(terms)
                overlap = len(query_terms & term_set)
                exact_phrase_bonus = sum(1.5 for phrase in query_phrases if phrase in lower)
                term_frequency_bonus = sum(min(lower.count(term), 3) for term in query_terms) / 20
                score = overlap / max(len(query_terms), 1) + exact_phrase_bonus + term_frequency_bonus
                if chunk.content_type == "table" and not wants_table:
                    score -= 0.15
            score += _noise_penalty(chunk)
            ranked.append((chunk, float(score)))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:limit]

    @lru_cache(maxsize=1)
    def _load_cross_encoder(self, model_name: str):
        from sentence_transformers import CrossEncoder

        return CrossEncoder(model_name)


def _terms(text: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-&]+", text.lower()) if len(term) > 2]


def _phrases(text: str) -> list[str]:
    terms = _terms(text)
    phrases: list[str] = []
    for width in [4, 3, 2]:
        for index in range(0, max(len(terms) - width + 1, 0)):
            phrase = " ".join(terms[index : index + width])
            if len(phrase) > 8:
                phrases.append(phrase)
    return phrases


def _rank_text(chunk: ChunkRecord) -> str:
    return chunk.contextual_text or chunk.text
