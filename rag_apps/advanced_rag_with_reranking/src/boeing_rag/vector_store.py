from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from boeing_rag.config import Settings
from boeing_rag.orm import ChunkRecord, DocumentRecord
from boeing_rag.schemas import QueryFilters


class VectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self.collection = settings.qdrant_collection

    def ensure_collection(self, vector_size: int) -> None:
        existing = {collection.name for collection in self.client.get_collections().collections}
        if self.collection not in existing:
            self._create_collection(vector_size)
            self._create_payload_indexes()
            return

        info = self.client.get_collection(self.collection)
        vectors = info.config.params.vectors
        current = vectors.get(self.settings.dense_vector_name) if isinstance(vectors, dict) else None
        if current is None or current.size != vector_size:
            self.client.delete_collection(collection_name=self.collection)
            self._create_collection(vector_size)
            self._create_payload_indexes()

    def _create_collection(self, vector_size: int) -> None:
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                self.settings.dense_vector_name: qm.VectorParams(
                    size=vector_size,
                    distance=qm.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self.settings.sparse_vector_name: qm.SparseVectorParams(
                    modifier=qm.Modifier.IDF,
                )
            },
        )

    def delete_collection(self) -> None:
        existing = {collection.name for collection in self.client.get_collections().collections}
        if self.collection in existing:
            self.client.delete_collection(collection_name=self.collection)

    def delete_document(self, document_id: str) -> None:
        existing = {collection.name for collection in self.client.get_collections().collections}
        if self.collection not in existing:
            return
        self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def upsert_chunks(
        self,
        chunks: list[ChunkRecord],
        documents_by_id: dict[str, DocumentRecord],
        dense_vectors: list[list[float]],
        sparse_vectors: list[qm.SparseVector],
    ) -> None:
        points: list[qm.PointStruct] = []
        for chunk, dense_vector, sparse_vector in zip(chunks, dense_vectors, sparse_vectors, strict=True):
            doc = documents_by_id[chunk.document_id]
            payload = {
                "chunk_id": chunk.id,
                "raw_chunk_id": chunk.id,
                "document_id": doc.id,
                "file_name": doc.file_name,
                "report_year": doc.report_year,
                "report_type": doc.report_type,
                "content_type": chunk.content_type,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "citation_label": chunk.citation_label,
                "section_path": chunk.section_path,
                "table_quality_status": chunk.metadata_json.get("table_quality_status"),
                "contextualization_model": chunk.metadata_json.get("contextualization_model"),
                "contextualization_prompt_version": chunk.metadata_json.get(
                    "contextualization_prompt_version"
                ),
            }
            if not chunk.vector_id:
                raise ValueError(f"Chunk {chunk.id} is missing a Qdrant vector_id")
            points.append(
                qm.PointStruct(
                    id=chunk.vector_id,
                    vector={
                        self.settings.dense_vector_name: dense_vector,
                        self.settings.sparse_vector_name: sparse_vector,
                    },
                    payload=payload,
                )
            )

        for index in range(0, len(points), 128):
            self.client.upsert(
                collection_name=self.collection,
                points=points[index : index + 128],
                wait=True,
            )

    def search(
        self,
        query_vector: list[float],
        sparse_query_vector: qm.SparseVector,
        filters: QueryFilters,
        limit: int,
    ) -> list[tuple[str, float]]:
        query_filter = self._build_filter(filters)
        try:
            response = self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    qm.Prefetch(
                        query=query_vector,
                        using=self.settings.dense_vector_name,
                        filter=query_filter,
                        limit=limit,
                    ),
                    qm.Prefetch(
                        query=sparse_query_vector,
                        using=self.settings.sparse_vector_name,
                        filter=query_filter,
                        limit=limit,
                    ),
                ],
                query=qm.FusionQuery(fusion=qm.Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        except Exception:
            return self._fallback_hybrid_search(query_vector, sparse_query_vector, query_filter, limit)
        hits: list[tuple[str, float]] = []
        for point in response.points:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id")
            if chunk_id:
                hits.append((str(chunk_id), float(point.score)))
        return hits

    def _fallback_hybrid_search(
        self,
        query_vector: list[float],
        sparse_query_vector: qm.SparseVector,
        query_filter: qm.Filter | None,
        limit: int,
    ) -> list[tuple[str, float]]:
        branches: list[list[tuple[str, float]]] = []
        for vector, using in [
            (query_vector, self.settings.dense_vector_name),
            (sparse_query_vector, self.settings.sparse_vector_name),
        ]:
            response = self.client.query_points(
                collection_name=self.collection,
                query=vector,
                using=using,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            hits: list[tuple[str, float]] = []
            for point in response.points:
                payload = point.payload or {}
                chunk_id = payload.get("chunk_id")
                if chunk_id:
                    hits.append((str(chunk_id), float(point.score)))
            branches.append(hits)
        return self._rrf(branches)[:limit]

    def _rrf(self, branches: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for hits in branches:
            for rank, (chunk_id, _score) in enumerate(hits, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)

    def _build_filter(self, filters: QueryFilters) -> qm.Filter | None:
        must: list[qm.FieldCondition] = []
        if filters.document_id:
            must.append(qm.FieldCondition(key="document_id", match=qm.MatchValue(value=filters.document_id)))
        if filters.file_name:
            must.append(qm.FieldCondition(key="file_name", match=qm.MatchValue(value=filters.file_name)))
        if filters.report_type:
            must.append(qm.FieldCondition(key="report_type", match=qm.MatchValue(value=filters.report_type)))
        if filters.content_type:
            must.append(qm.FieldCondition(key="content_type", match=qm.MatchValue(value=filters.content_type)))
        if filters.report_year:
            must.append(qm.FieldCondition(key="report_year", match=qm.MatchValue(value=filters.report_year)))
        if filters.report_year_min is not None or filters.report_year_max is not None:
            must.append(
                qm.FieldCondition(
                    key="report_year",
                    range=qm.Range(gte=filters.report_year_min, lte=filters.report_year_max),
                )
            )
        return qm.Filter(must=must) if must else None

    def _create_payload_indexes(self) -> None:
        for field, schema in [
            ("document_id", qm.PayloadSchemaType.KEYWORD),
            ("file_name", qm.PayloadSchemaType.KEYWORD),
            ("report_type", qm.PayloadSchemaType.KEYWORD),
            ("content_type", qm.PayloadSchemaType.KEYWORD),
            ("report_year", qm.PayloadSchemaType.INTEGER),
            ("page_start", qm.PayloadSchemaType.INTEGER),
        ]:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=schema,
            )
