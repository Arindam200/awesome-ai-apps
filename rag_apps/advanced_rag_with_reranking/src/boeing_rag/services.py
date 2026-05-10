from functools import lru_cache

from boeing_rag.answering import AnswerGenerator
from boeing_rag.chunking import ChunkBuilder
from boeing_rag.config import get_settings
from boeing_rag.contextual import Contextualizer
from boeing_rag.embeddings import EmbeddingProvider
from boeing_rag.ingest import IngestionPipeline
from boeing_rag.parser import MarkItDownPdfParser
from boeing_rag.rerank import Reranker
from boeing_rag.retrieval import Retriever
from boeing_rag.sparse import SparseEmbeddingProvider
from boeing_rag.vector_store import VectorStore


@lru_cache
def embeddings() -> EmbeddingProvider:
    return EmbeddingProvider(get_settings())


@lru_cache
def sparse_embeddings() -> SparseEmbeddingProvider:
    return SparseEmbeddingProvider(get_settings())


@lru_cache
def contextualizer() -> Contextualizer:
    return Contextualizer(get_settings())


@lru_cache
def vector_store() -> VectorStore:
    return VectorStore(get_settings())


@lru_cache
def reranker() -> Reranker:
    return Reranker(get_settings())


@lru_cache
def retriever() -> Retriever:
    settings = get_settings()
    return Retriever(settings, embeddings(), sparse_embeddings(), vector_store(), reranker())


@lru_cache
def answer_generator() -> AnswerGenerator:
    return AnswerGenerator(get_settings())


def ingestion_pipeline() -> IngestionPipeline:
    settings = get_settings()
    return IngestionPipeline(
        settings=settings,
        parser=MarkItDownPdfParser(settings),
        chunk_builder=ChunkBuilder(settings),
        embeddings=embeddings(),
        sparse_embeddings=sparse_embeddings(),
        vector_store=vector_store(),
        contextualizer=contextualizer(),
        vision_parser=None,
    )
