"""Query processing and retrieval for RAG system."""

from typing import Any, Dict
import logging

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.vector_stores import (FilterOperator, MetadataFilter,
import time
                                            MetadataFilters)
from llama_index.embeddings.nebius import NebiusEmbedding
from llama_index.llms.nebius import NebiusLLM

from ..core.config import settings
from ..core.exceptions import QueryError
from ..database.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class QueryRetriever:
    """Handles document retrieval and query processing."""

    def __init__(self, repo_name: str):
        # Configure LlamaIndex settings
        Settings.llm = NebiusLLM(
            api_key=settings.nebius_api_key,
            model=settings.nebius_llm_model,
        )
        Settings.embed_model = NebiusEmbedding(
            api_key=settings.nebius_api_key,
            model_name=settings.nebius_embedding_model,
            embed_batch_size=25,
        )

        self.repo_name = repo_name
        self.vector_store_index = VectorStoreIndex.from_vector_store(get_vector_store())

        # Create repository filter (matching your working code exactly)
        self.filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="metadata.repo",
                    value=repo_name,
                    operator=FilterOperator.EQ,
                )
            ]
        )

    def make_query(
        self, query: str, mode: str = "default", top_k: int = None
    ) -> Dict[str, Any]:
        """
        Execute query against the repository documents.

        Args:
            query: User's question
            mode: Search mode (default, text_search, hybrid)
            top_k: Number of results to return

        Returns:
            Dictionary with response and source nodes
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not query.strip():
                raise QueryError("Empty query provided")

            if top_k is None:
                top_k = settings.similarity_top_k

            logger.info(f"Processing query for {self.repo_name}: '{query[:100]}...'")

            # Create query engine with repository filtering (matching working code)
            query_engine = self.vector_store_index.as_query_engine(
                similarity_top_k=top_k,
                vector_store_query_mode=mode,  # Use the mode directly as string
                filters=self.filters,
                response_mode="refine",
            )

            # Execute query
            response = query_engine.query(query)

            # Process source nodes (matching your working code exactly)
            source_nodes = []
            for node in response.source_nodes:
                try:
                    source_node = {
                        "file_name": node.metadata.get("file_name", "Unknown"),
                        "url": node.metadata.get("url", "#"),
                        "score": (
                            float(node.score) if node.score else 0.0
                        ),  # Convert to float
                        "content": node.get_content(),  # Use get_content() method
                    }
                    source_nodes.append(source_node)
                except Exception as e:
                    logger.error(f"Error formatting source node: {e}")
                    continue

            # Format response (matching working code structure)
            processing_time = time.time() - start_time
            result = {
                "response": str(
                    response.response
                ),  # Use response.response not str(response)
                "source_nodes": source_nodes,
                "repository": self.repo_name,
                "mode": mode,
                "processing_time": processing_time,
                "total_sources": len(source_nodes),
            }

            logger.info(
                f"Query completed in {processing_time:.2f}s with {len(source_nodes)} sources"
            )
            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Query failed after {processing_time:.2f}s: {e}")

            return {
                "error": str(e),
                "repository": self.repo_name,
                "mode": mode,
                "processing_time": processing_time,
            }


def create_query_retriever(repo_name: str) -> QueryRetriever:
    """Factory function to create query retriever."""
    return QueryRetriever(repo_name)