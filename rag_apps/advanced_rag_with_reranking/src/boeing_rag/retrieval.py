from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from boeing_rag.config import Settings
from boeing_rag.embeddings import EmbeddingProvider
from boeing_rag.orm import ChunkRecord, DocumentRecord
from boeing_rag.rerank import Reranker
from boeing_rag.schemas import QueryFilters, SourceCitation
from boeing_rag.sparse import SparseEmbeddingProvider
from boeing_rag.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievalResult:
    chunk: ChunkRecord
    score: float


class Retriever:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingProvider,
        sparse_embeddings: SparseEmbeddingProvider,
        vector_store: VectorStore,
        reranker: Reranker,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.sparse_embeddings = sparse_embeddings
        self.vector_store = vector_store
        self.reranker = reranker

    def retrieve(
        self,
        session: Session,
        question: str,
        filters: QueryFilters,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        limit = top_k or self.settings.rerank_top_k
        query_vector = self.embeddings.embed_query(question)
        sparse_query_vector = self.sparse_embeddings.embed_query(question)
        fused = self.vector_store.search(
            query_vector,
            sparse_query_vector,
            filters,
            max(self.settings.vector_top_k, self.settings.lexical_top_k),
        )
        fused_ids = [chunk_id for chunk_id, _score in fused]
        if not fused_ids:
            return []

        chunk_map = {
            chunk.id: chunk
            for chunk in session.scalars(select(ChunkRecord).where(ChunkRecord.id.in_(fused_ids))).all()
        }
        candidates = [
            chunk
            for chunk_id in fused_ids
            if (chunk := chunk_map.get(chunk_id)) is not None
            and self._passes_quality_gate(chunk, filters)
        ]
        reranked = self.reranker.rerank(question, candidates, limit)
        return [RetrievalResult(chunk=chunk, score=score) for chunk, score in reranked]

    def _passes_quality_gate(self, chunk: ChunkRecord, filters: QueryFilters) -> bool:
        if _is_noise_chunk(chunk):
            return False
        if chunk.content_type != "table":
            return True
        if filters.content_type == "table":
            return not _is_toc_table(chunk)
        return chunk.metadata_json.get("table_quality_status") != "fail"

    def _lexical_search(
        self,
        session: Session,
        question: str,
        filters: QueryFilters,
        limit: int,
    ) -> list[tuple[str, float]]:
        terms = _important_terms(question)
        if not terms:
            return []
        statement = self._filtered_chunk_query(filters).limit(4000)
        chunks = session.scalars(statement).all()
        scored: list[tuple[str, float]] = []
        for chunk in chunks:
            lower = chunk.text.lower()
            score = 0.0
            for term in terms:
                count = lower.count(term)
                if count:
                    score += 1.0 + math.log(count)
            if score:
                scored.append((chunk.id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def _filtered_chunk_query(self, filters: QueryFilters) -> Select[tuple[ChunkRecord]]:
        statement = select(ChunkRecord).join(DocumentRecord)
        if filters.document_id:
            statement = statement.where(ChunkRecord.document_id == filters.document_id)
        if filters.file_name:
            statement = statement.where(DocumentRecord.file_name == filters.file_name)
        if filters.report_type:
            statement = statement.where(DocumentRecord.report_type == filters.report_type)
        if filters.content_type:
            statement = statement.where(ChunkRecord.content_type == filters.content_type)
        if filters.report_year:
            statement = statement.where(DocumentRecord.report_year == filters.report_year)
        if filters.report_year_min is not None:
            statement = statement.where(DocumentRecord.report_year >= filters.report_year_min)
        if filters.report_year_max is not None:
            statement = statement.where(DocumentRecord.report_year <= filters.report_year_max)
        return statement

    def _rrf(
        self,
        vector_hits: list[tuple[str, float]],
        lexical_hits: list[tuple[str, float]],
        k: int = 60,
    ) -> list[str]:
        scores: dict[str, float] = {}
        for hits in [vector_hits, lexical_hits]:
            for rank, (chunk_id, _score) in enumerate(hits, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def citation_from_result(result: RetrievalResult) -> SourceCitation:
    chunk = result.chunk
    doc = chunk.document
    text = chunk.raw_text or chunk.text
    return SourceCitation(
        chunk_id=chunk.id,
        document_id=doc.id,
        file_name=doc.file_name,
        report_year=doc.report_year,
        report_type=doc.report_type,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        citation_label=chunk.citation_label,
        content_type=chunk.content_type,
        text=text[:4000],
        score=result.score,
        page_image_path=chunk.metadata_json.get("page_image_path"),
        section_path=chunk.section_path or [],
        pdf_url=f"/documents/{doc.id}/file",
        page_image_url=f"/chunks/{chunk.id}/page-image"
        if chunk.metadata_json.get("page_image_path")
        else None,
    )


_NOISE_PATTERNS = [
    re.compile(r"UNITED STATES SECURITIES AND EXCHANGE COMMISSION", re.I),
    re.compile(r"FORM 10-K", re.I),
    re.compile(r"ANNUAL REPORT PURSUANT TO SECTION", re.I),
    re.compile(r"originally incorporated in the State of", re.I),
    re.compile(r"No material portion of our business is considered to be seasonal", re.I),
    re.compile(r"Executive Officers of the Registrant", re.I),
]

_TOC_INDICATORS = re.compile(
    r"(?:"
    r"PART\s+[IVX]+\s*\|.*Page"
    r"|\.{5,}"
    r"|(?:Item\s+\d+[A-Z]?\.\s+.{10,60}\s+\d{1,3}\s*\n){3,}"
    r")",
    re.I | re.M,
)

_EXHIBIT_INDICATOR = re.compile(
    r"(?:Exhibit\s+\d+|(?:Exhibit|Form)\s+\d+[A-Za-z.\-]*\s*\|){2,}", re.I
)


def _is_noise_chunk(chunk: ChunkRecord) -> bool:
    text = chunk.text
    if len(text.strip()) < 60:
        return True
    for pattern in _NOISE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _is_toc_table(chunk: ChunkRecord) -> bool:
    text = chunk.text
    if _TOC_INDICATORS.search(text):
        return True
    if _EXHIBIT_INDICATOR.search(text):
        return True
    return False


def _important_terms(text: str) -> list[str]:
    stop = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "what",
        "where",
        "does",
        "did",
        "boeing",
        "report",
        "reports",
        "annual",
        "sustainability",
    }
    terms = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-&]+", text.lower())
    return [term for term in terms if len(term) > 2 and term not in stop]
