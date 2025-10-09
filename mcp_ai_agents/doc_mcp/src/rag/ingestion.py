"""Document ingestion pipeline for RAG system."""

from typing import Callable, List, Optional
import logging

from llama_index.core import (Document, Settings, StorageContext,
import time
                              VectorStoreIndex)
from llama_index.core.text_splitter import SentenceSplitter
from llama_index.embeddings.nebius import NebiusEmbedding
from llama_index.llms.nebius import NebiusLLM

from ..core.config import settings
from ..core.exceptions import IngestionError
from ..database.repository import repository_manager
from ..database.vector_store import get_vector_store
from .models import IngestionProgress

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Handles document ingestion with progress tracking."""

    def __init__(
        self, progress_callback: Optional[Callable[[IngestionProgress], None]] = None
    ):
        self.progress_callback = progress_callback
        self.text_splitter = SentenceSplitter(chunk_size=settings.chunk_size)

        # Configure LlamaIndex settings
        Settings.node_parser = self.text_splitter
        Settings.llm = NebiusLLM(
            api_key=settings.nebius_api_key,
            model="meta-llama/Llama-3.3-70B-Instruct-fast",
        )
        Settings.embed_model = NebiusEmbedding(
            api_key=settings.nebius_api_key,
            model_name="BAAI/bge-en-icl",
            embed_batch_size=25,
        )

    def _report_progress(self, progress: IngestionProgress):
        """Report progress to callback if available."""
        if self.progress_callback:
            self.progress_callback(progress)

    async def ingest_documents(
        self,
        documents: List[Document],
        repo_name: str,
        branch: Optional[str] = "main",
        files_with_sha: Optional[List[dict]] = None,
    ) -> bool:
        """
        Ingest documents into the vector store.

        Args:
            documents: List of documents to ingest
            repo_name: Repository name for metadata

        Returns:
            True if successful, False otherwise
        """
        if not documents:
            logger.warning("No documents to ingest")
            return False

        start_time = time.time()
        total_docs = len(documents)

        try:
            logger.info(f"Starting ingestion of {total_docs} documents for {repo_name}")

            # Get vector store
            vector_store = get_vector_store()
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # Create index and ingest documents
            VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                show_progress=True,  # We handle progress ourselves
            )

            # Report completion
            elapsed_time = time.time() - start_time

            # Update repository metadata with SHA tracking
            if files_with_sha is None:
                # Extract SHA info from documents if not provided
                files_with_sha = []
                for doc in documents:
                    file_path = doc.metadata.get("file_path", "")
                    file_sha = doc.metadata.get("sha", "")
                    if file_path and file_sha:
                        files_with_sha.append({"path": file_path, "sha": file_sha})
                    else:
                        logger.warning(f"Missing SHA info for document: {file_path}")

            # Update repository metadata
            repository_manager.update_repository_info(
                repo_name, len(documents), branch, files_with_sha
            )

            logger.info(
                f"Successfully ingested {total_docs} documents for {repo_name} in {elapsed_time:.2f}s"
            )
            return True

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Ingestion failed after {elapsed_time:.2f}s: {e}")

            # Report error
            self._report_progress(
                IngestionProgress(
                    total_documents=total_docs,
                    processed_documents=0,
                    current_phase=f"Error: {str(e)}",
                    elapsed_time=elapsed_time,
                )
            )

            raise IngestionError(f"Document ingestion failed: {e}") from e


async def ingest_documents_async(
    documents: List[Document],
    repo_name: str,
    progress_callback: Optional[Callable[[IngestionProgress], None]] = None,
    branch: Optional[str] = "main",
    files_with_sha: Optional[List[dict]] = None,
) -> bool:
    """
    Async wrapper for document ingestion.

    Args:
        documents: List of documents to ingest
        repo_name: Repository name for metadata
        progress_callback: Optional progress callback

    Returns:
        True if successful, False otherwise
    """
    pipeline = DocumentIngestionPipeline(progress_callback)
    return await pipeline.ingest_documents(documents, repo_name, branch, files_with_sha)


async def reingest_changed_files(
    repo_url: str,
    repo_name: str,
    changes: dict,
    branch: str = "main",
    progress_callback: Optional[Callable[[IngestionProgress], None]] = None,
) -> bool:
    """
    Reingest only changed files for efficient updates.

    Args:
        repo_url: GitHub repository URL
        repo_name: Repository name
        changes: Dictionary with file changes from detect_file_changes
        branch: Branch name
        progress_callback: Optional progress callback

    Returns:
        True if successful, False otherwise
    """
    from ..github.file_loader import load_files_from_github

    try:
        # Files that need to be reingested (new + modified)
        files_to_reingest = changes["new"] + changes["modified"]
        deleted_files = changes["deleted"]

        if not files_to_reingest and not deleted_files:
            logger.info("No changes detected, skipping reingestion")
            return True

        logger.info(
            f"Reingesting {len(files_to_reingest)} changed files, deleting {len(deleted_files)} files"
        )

        # Delete removed files from vector store
        if deleted_files:
            deleted_paths = [f["path"] for f in deleted_files]
            repository_manager.delete_specific_files(repo_name, deleted_paths)

        # Load and reingest changed files
        if files_to_reingest:
            file_paths = [f["path"] for f in files_to_reingest]
            documents, failed_files = await load_files_from_github(
                repo_url, file_paths, branch
            )

            if documents:
                success = await ingest_documents_async(
                    documents, repo_name, progress_callback, branch, files_to_reingest
                )

                if success:
                    logger.info(
                        f"Successfully reingested {len(documents)} changed documents"
                    )
                    return True
                else:
                    logger.error("Failed to reingest changed documents")
                    return False

        # Update repository info even if no files to reingest (for deletion tracking)
        if not files_to_reingest:
            # Get all current files for tracking
            all_current_files = changes["unchanged"]  # Only unchanged files remain
            repository_manager.update_repository_info(
                repo_name, len(all_current_files), branch, all_current_files
            )

        return True

    except Exception as e:
        logger.error(f"Failed to reingest changed files: {e}")
        return False