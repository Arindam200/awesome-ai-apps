"""Vector store operations and management."""

import logging

from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
from pymongo.operations import SearchIndexModel

from ..core.config import settings
from ..core.exceptions import VectorStoreError
from .mongodb import mongodb_client
logger = logging.getLogger(__name__)


def create_search_indexes() -> tuple[SearchIndexModel, SearchIndexModel]:
    """Create search index models for vector and full-text search."""

    vs_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": settings.embedding_dimensions,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "metadata.repo"},
            ]
        },
        name=settings.vector_index_name,
        type="vectorSearch",
    )

    fts_model = SearchIndexModel(
        definition={
            "mappings": {"dynamic": False, "fields": {"text": {"type": "string"}}}
        },
        name=settings.fts_index_name,
        type="search",
    )

    return vs_model, fts_model


def get_vector_store() -> MongoDBAtlasVectorSearch:
    """Get configured vector store instance."""
    try:
        collection = mongodb_client.get_collection(settings.collection_name)

        vector_store = MongoDBAtlasVectorSearch(
            mongodb_client=mongodb_client.client,
            db_name=settings.db_name,
            collection_name=settings.collection_name,
            vector_index_name=settings.vector_index_name,
            fulltext_index_name=settings.fts_index_name,
            embedding_key="embedding",
            text_key="text",
        )

        # Create search indexes if they don't exist
        vs_model, fts_model = create_search_indexes()
        try:
            collection.create_search_indexes(models=[vs_model, fts_model])
            logger.info("Search indexes created successfully")
        except Exception as e:
            # Indexes might already exist
            logger.info(f"Search indexes might already exist: {e}")

        return vector_store

    except Exception as e:
        logger.error(f"Failed to get vector store: {e}")
        raise VectorStoreError(f"Failed to get vector store: {e}")


def delete_vector_data(repo_name: str) -> bool:
    """Delete all vector data for a repository."""
    try:
        collection = mongodb_client.get_collection(settings.collection_name)
        result = collection.delete_many({"metadata.repo": repo_name})
        logger.info(f"Deleted {result.deleted_count} documents for repo: {repo_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete vector data for {repo_name}: {e}")
        return False