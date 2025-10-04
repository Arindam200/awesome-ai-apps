"""Repository data management and statistics."""

from typing import Any, Dict, List, Optional
import logging

from datetime import datetime

from ..core.config import settings
from ..core.types import ProcessingStatus
from .mongodb import mongodb_client
logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manages repository metadata and statistics."""

    def __init__(self):
        self.repos_collection = mongodb_client.get_collection(
            settings.repos_collection_name
        )
        self.docs_collection = mongodb_client.get_collection(settings.collection_name)

    def get_available_repositories(self) -> List[str]:
        """Get list of available repositories."""
        try:
            # Use repo_name field to match existing data structure
            repos = self.repos_collection.distinct("repo_name")
            return sorted(repos) if repos else []
        except Exception as e:
            logger.error(f"Failed to get available repositories: {e}")
            return []

    def get_repository_details(self) -> List[Dict[str, Any]]:
        """Get detailed information about all repositories."""
        try:
            repos = []
            for repo_doc in self.repos_collection.find():
                # Count documents for this repo
                repo_name = repo_doc.get("repo_name", "Unknown")
                doc_count = self.docs_collection.count_documents(
                    {"metadata.repo": repo_name}
                )

                # Get file tracking info
                files_info = repo_doc.get("files", [])
                tracked_files = len(files_info)

                repos.append(
                    {
                        "name": repo_name,
                        "files": repo_doc.get("file_count", doc_count),
                        "tracked_files": tracked_files,
                        "branch": repo_doc.get("branch", "main"),
                        "last_updated": repo_doc.get("last_updated", "Unknown"),
                        "status": repo_doc.get("status", "complete"),
                    }
                )

            return sorted(repos, key=lambda x: x["name"])
        except Exception as e:
            logger.error(f"Failed to get repository details: {e}")
            return []

    def get_repository_stats(self) -> Dict[str, Any]:
        """Get overall repository statistics."""
        try:
            total_repos = self.repos_collection.count_documents({})
            total_docs = self.docs_collection.count_documents({})

            # Get total files across all repos
            total_files = 0
            total_tracked_files = 0
            repos = self.repos_collection.find({}, {"file_count": 1, "files": 1})
            for repo in repos:
                total_files += repo.get("file_count", 0)
                total_tracked_files += len(repo.get("files", []))

            # Get collection size estimates
            try:
                stats = mongodb_client.database.command(
                    "collStats", settings.collection_name
                )
                collection_size = stats.get("size", 0)
            except Exception:
                collection_size = 0

            return {
                "total_repositories": total_repos,
                "total_documents": total_docs,
                "total_files": total_files,
                "total_tracked_files": total_tracked_files,
                "collection_size_bytes": collection_size,
                "collection_size_mb": (
                    round(collection_size / (1024 * 1024), 2)
                    if collection_size > 0
                    else 0
                ),
                "database_name": settings.db_name,
                "last_updated": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}")
            return {"error": str(e)}

    def update_repository_info(
        self,
        repo_name: str,
        file_count: int = 0,
        branch: Optional[str] = "main",
        files_with_sha: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """Update repository information incrementally."""
        try:
            if files_with_sha is None:
                files_with_sha = []

            # Get existing repository data
            existing_repo = self.repos_collection.find_one({"_id": repo_name})

            if existing_repo:
                # INCREMENTAL UPDATE: Merge with existing files
                existing_files = existing_repo.get("files", [])
                existing_file_lookup = {f["path"]: f for f in existing_files}

                # Update/add new files
                for file_info in files_with_sha:
                    existing_file_lookup[file_info["path"]] = {
                        "path": file_info["path"],
                        "sha": file_info["sha"],
                        "last_ingested": datetime.now(),
                        "status": "ingested",
                    }

                # Convert back to list
                merged_files = list(existing_file_lookup.values())

                # Update only specific fields, don't replace entire document
                update_operation = {
                    "$set": {
                        "files": merged_files,
                        "file_count": len(merged_files),  # Use actual count
                        "last_updated": datetime.now(),
                        "status": ProcessingStatus.COMPLETE.value,
                        "branch": branch,
                        "tracking_enabled": True,
                    }
                }

                # Use update_one instead of replace_one
                self.repos_collection.update_one({"_id": repo_name}, update_operation)

                logger.info(
                    f"Incrementally updated repository info for: {repo_name} "
                    f"(added/updated {len(files_with_sha)} files, total: {len(merged_files)})"
                )
            else:
                # NEW REPOSITORY: Create fresh entry
                file_tracking_data = []
                for file_info in files_with_sha:
                    file_tracking_data.append(
                        {
                            "path": file_info["path"],
                            "sha": file_info["sha"],
                            "last_ingested": datetime.now(),
                            "status": "ingested",
                        }
                    )

                update_data = {
                    "_id": repo_name,
                    "repo_name": repo_name,
                    "branch": branch,
                    "file_count": len(file_tracking_data),
                    "files": file_tracking_data,
                    "last_updated": datetime.now(),
                    "status": ProcessingStatus.COMPLETE.value,
                    "tracking_enabled": True,
                }

                self.repos_collection.insert_one(update_data)
                logger.info(
                    f"Created new repository tracking for: {repo_name} "
                    f"with {len(file_tracking_data)} files"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to update repository info for {repo_name}: {e}")
            return False

    def get_repository_files(self, repo_name: str) -> List[Dict[str, Any]]:
        """Get tracked files for a repository."""
        try:
            repo_doc = self.repos_collection.find_one({"_id": repo_name})
            if repo_doc:
                return repo_doc.get("files", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get repository files for {repo_name}: {e}")
            return []

    def detect_file_changes(
        self, repo_name: str, current_files: List[Dict[str, str]]
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Detect changes in repository files by comparing SHAs.

        Args:
            repo_name: Repository name
            current_files: List of current files with path and sha

        Returns:
            Dictionary with 'new', 'modified', 'deleted', and 'unchanged' file lists
        """
        try:
            logger.info(f"=== DEBUGGING detect_file_changes for {repo_name} ===")

            # Get stored files from database
            stored_files = self.get_repository_files(repo_name)
            logger.info(f"Stored files in DB: {len(stored_files)}")

            # Create lookup for stored files
            stored_lookup = {}
            for file_entry in stored_files:
                path = file_entry.get("path", file_entry.get("file_path", ""))
                sha = file_entry.get("sha", "")
                stored_lookup[path] = sha

            logger.info(f"Stored lookup keys: {list(stored_lookup.keys())[:5]}...")

            # Check current files
            logger.info(f"Current files from GitHub: {len(current_files)}")
            if current_files:
                logger.info(f"Sample current file: {current_files[0]}")

            new_files = []
            modified_files = []
            unchanged_files = []

            for file_info in current_files:
                path = file_info["path"]
                current_sha = file_info["sha"]

                if path not in stored_lookup:
                    # Truly new file
                    new_files.append(file_info)
                    logger.debug(f"NEW: {path}")
                elif stored_lookup[path] != current_sha:
                    # Modified file (SHA changed)
                    modified_files.append(file_info)
                    logger.debug(
                        f"MODIFIED: {path} (stored: {stored_lookup[path][:8]}, current: {current_sha[:8]})"
                    )
                else:
                    # Unchanged file
                    unchanged_files.append(file_info)
                    logger.debug(f"UNCHANGED: {path}")

            # Check for deleted files
            current_paths = {f["path"] for f in current_files}
            deleted_files = []
            for stored_path, stored_sha in stored_lookup.items():
                if stored_path not in current_paths:
                    deleted_files.append({"path": stored_path, "sha": stored_sha})
                    logger.debug(f"DELETED: {stored_path}")

            result = {
                "new": new_files,
                "modified": modified_files,
                "deleted": deleted_files,
                "unchanged": unchanged_files,
            }

            logger.info(
                f"Change detection result: {len(new_files)} new, {len(modified_files)} modified, {len(deleted_files)} deleted, {len(unchanged_files)} unchanged"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to detect changes for {repo_name}: {e}")
            return {"new": [], "modified": [], "deleted": [], "unchanged": []}

    def delete_specific_files(
        self, repo_name: str, file_paths: List[str], branch: str = "main"
    ) -> int:
        """Delete specific files from the vector store."""
        try:
            # Create document IDs for the files to delete
            doc_ids = [
                f"{repo_name}:{branch}:{path}" for path in file_paths
            ]  # Adjust branch if needed

            # Delete from vector store
            deleted_count = 0
            for doc_id in doc_ids:
                result = self.docs_collection.delete_many({"metadata.doc_id": doc_id})
                deleted_count += result.deleted_count

            logger.info(
                f"Deleted {deleted_count} documents for {len(file_paths)} files from {repo_name}"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete files from {repo_name}: {e}")
            return 0

    def delete_repository_data(self, repo_name: str) -> Dict[str, Any]:
        """Delete all data for a repository."""
        try:
            # Delete from documents collection
            docs_result = self.docs_collection.delete_many({"metadata.repo": repo_name})

            # Delete from repositories collection using _id (to match existing structure)
            repos_result = self.repos_collection.delete_one({"_id": repo_name})

            logger.info(
                f"Deleted repository {repo_name}: {docs_result.deleted_count} docs, {repos_result.deleted_count} repo entries"
            )

            return {
                "success": True,
                "documents_deleted": docs_result.deleted_count,
                "repository_deleted": repos_result.deleted_count > 0,
                "message": f"Successfully deleted {docs_result.deleted_count} documents for repository '{repo_name}'",
            }
        except Exception as e:
            logger.error(f"Failed to delete repository {repo_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to delete repository '{repo_name}': {str(e)}",
            }


# Global repository manager instance
repository_manager = RepositoryManager()