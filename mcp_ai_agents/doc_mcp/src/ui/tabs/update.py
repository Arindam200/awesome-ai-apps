"""Repository update tab implementation for incremental ingestion."""

from typing import Dict, List, Tuple
import logging

import gradio as gr
import time

from ...core.types import ProcessingStatus
from ...database.repository import repository_manager
from ...github.file_loader import (discover_repository_files_with_changes,
                                   load_files_from_github)
from ...rag.ingestion import ingest_documents_async
from ..components.common import (create_file_selector, create_progress_display,
                                 create_repository_dropdown,
                                 create_status_textbox,
                                 format_progress_display)

logger = logging.getLogger(__name__)


class UpdateTab:
    """Handles the repository update tab UI and logic."""

    def __init__(self, demo: gr.Blocks):
        self.progress_state = {}
        self.demo = demo

    def create_tab(self) -> gr.TabItem:
        """Create the update tab interface."""
        with gr.TabItem("🔄 Repository Updates") as tab:
            gr.Markdown("### 🔄 Incremental Repository Updates")
            gr.Markdown(
                "**Smart Updates:** Detect and process only changed files for efficient repository maintenance. "
                "Also discover and ingest new files that haven't been processed yet."
            )

            # Repository selection section
            with gr.Row():
                with gr.Column(scale=2):
                    repo_dropdown = create_repository_dropdown(
                        choices=self._get_available_repos(),
                        label="📚 Select Repository to Update",
                        allow_custom=False,
                    )

                    refresh_dropdown_btn = gr.Button(
                        "🔄 Refresh Repository List", variant="secondary", size="sm"
                    )

                    branch_input = gr.Textbox(
                        label="🌿 Branch",
                        placeholder="Branch name (default: main)",
                        value="main",
                    )

                    detect_changes_btn = gr.Button(
                        "🔍 Detect Changes & Available Files", variant="secondary"
                    )

                with gr.Column(scale=1):
                    status_output = create_status_textbox(
                        label="Change Detection Status",
                        placeholder="Change detection results will appear here...",
                        lines=10,
                    )

            # Change summary section
            with gr.Row():
                with gr.Column():
                    change_summary_display = gr.JSON(
                        label="📊 Change Summary",
                        value={"message": "Run change detection to see summary..."},
                    )

            # File selection section
            with gr.Accordion("📁 Changed Files", open=False):
                with gr.Tabs():
                    with gr.TabItem("🆕 New Files"):
                        new_files_selector = create_file_selector(
                            label="New files to ingest"
                        )
                        with gr.Row():
                            select_all_new_btn = gr.Button(
                                "✅ Select All New", variant="secondary", size="sm"
                            )
                            clear_new_btn = gr.Button(
                                "❌ Clear New", variant="secondary", size="sm"
                            )

                    with gr.TabItem("✏️ Modified Files"):
                        modified_files_selector = create_file_selector(
                            label="Modified files to re-ingest"
                        )
                        with gr.Row():
                            select_all_modified_btn = gr.Button(
                                "✅ Select All Modified", variant="secondary", size="sm"
                            )
                            clear_modified_btn = gr.Button(
                                "❌ Clear Modified", variant="secondary", size="sm"
                            )

                    with gr.TabItem("🗑️ Deleted Files"):
                        deleted_files_display = gr.Dataframe(
                            headers=["File Path", "Last SHA"],
                            datatype=["str", "str"],
                            label="Files deleted from repository",
                            interactive=False,
                        )

                    with gr.TabItem("📄 Available Files"):
                        available_files_selector = create_file_selector(
                            label="Files available but not ingested"
                        )
                        with gr.Row():
                            select_all_available_btn = gr.Button(
                                "✅ Select All Available",
                                variant="secondary",
                                size="sm",
                            )
                            clear_available_btn = gr.Button(
                                "❌ Clear Available", variant="secondary", size="sm"
                            )

            # Update controls
            gr.Markdown("### 🚀 Update Execution")

            with gr.Row():
                update_changed_btn = gr.Button(
                    "🔄 Process Changed Files",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )
                ingest_available_btn = gr.Button(
                    "📥 Ingest Available Files",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

            with gr.Row():
                delete_removed_btn = gr.Button(
                    "🗑️ Remove Deleted Files", variant="stop", interactive=False
                )
                refresh_btn = gr.Button("🔄 Refresh Progress", variant="secondary")

            # Progress display
            progress_display = create_progress_display(
                label="📊 Update Progress",
                initial_value="🚀 Ready to detect changes and process updates...",
                lines=15,
            )

            # State management
            changes_state = gr.State({})
            available_files_state = gr.State([])
            progress_state = gr.State({})

            # Event handlers
            detect_changes_btn.click(
                fn=self._detect_changes_and_available,
                inputs=[repo_dropdown, branch_input],
                outputs=[
                    changes_state,
                    available_files_state,
                    status_output,
                    change_summary_display,
                    new_files_selector,
                    modified_files_selector,
                    deleted_files_display,
                    available_files_selector,
                    update_changed_btn,
                    ingest_available_btn,
                    delete_removed_btn,
                ],
                show_api=False,
            )

            # Selection helpers
            select_all_new_btn.click(
                fn=lambda changes: self._select_files_by_type(changes, "new"),
                inputs=[changes_state],
                outputs=[new_files_selector],
                show_api=False,
            )

            select_all_modified_btn.click(
                fn=lambda changes: self._select_files_by_type(changes, "modified"),
                inputs=[changes_state],
                outputs=[modified_files_selector],
                show_api=False,
            )

            select_all_available_btn.click(
                fn=self._select_all_available,
                inputs=[available_files_state],
                outputs=[available_files_selector],
                show_api=False,
            )

            clear_new_btn.click(
                fn=lambda: gr.CheckboxGroup(value=[]),
                outputs=[new_files_selector],
                show_api=False,
            )
            clear_modified_btn.click(
                fn=lambda: gr.CheckboxGroup(value=[]),
                outputs=[modified_files_selector],
                show_api=False,
            )
            clear_available_btn.click(
                fn=lambda: gr.CheckboxGroup(value=[]),
                outputs=[available_files_selector],
                show_api=False,
            )

            refresh_dropdown_btn.click(
                fn=self._refresh_repositories,
                outputs=[repo_dropdown],
                show_api=False,
            )

            # Update operations
            update_changed_btn.click(
                fn=self._process_changed_files,
                inputs=[
                    repo_dropdown,
                    branch_input,
                    new_files_selector,
                    modified_files_selector,
                    changes_state,
                ],
                outputs=[progress_state, progress_display],
                show_api=False,
            )

            ingest_available_btn.click(
                fn=self._ingest_available_files,
                inputs=[repo_dropdown, branch_input, available_files_selector],
                outputs=[progress_state, progress_display],
                show_api=False,
            )

            delete_removed_btn.click(
                fn=self._delete_removed_files,
                inputs=[repo_dropdown, changes_state],
                outputs=[progress_state, progress_display],
                show_api=False,
            )

            refresh_btn.click(
                fn=self._refresh_progress,
                inputs=[progress_state],
                outputs=[progress_display],
                show_api=False,
            )

            self.demo.load(fn=self._get_available_repos, outputs=[repo_dropdown], show_api=False)

        return tab

    def _refresh_repositories(self) -> gr.Dropdown:
        """Refresh repository list."""
        try:
            repos = self._get_available_repos()
            logger.info(f"Refreshed repository list: {len(repos)} repositories found")
            return gr.Dropdown(choices=repos, value=None)
        except Exception as e:
            logger.error(f"Error refreshing repositories: {e}")
            return gr.Dropdown(choices=["Error loading repositories"], value=None)

    def _get_available_repos(self) -> List[str]:
        """Get list of available repositories."""
        try:
            repos = repository_manager.get_available_repositories()
            logger.info(f"Available repositories: {repos}")
            return repos if repos else ["No repositories available"]
        except Exception as e:
            logger.error(f"Error getting repositories: {e}")
            return ["Error loading repositories"]

    def _detect_changes_and_available(
        self, repo_name: str, branch: str = "main"
    ) -> Tuple[
        Dict,
        List,
        str,
        Dict,
        gr.CheckboxGroup,
        gr.CheckboxGroup,
        gr.Dataframe,
        gr.CheckboxGroup,
        gr.Button,
        gr.Button,
        gr.Button,
    ]:
        """Detect changes and find available files for the repository."""
        if not repo_name or repo_name in [
            "No repositories available",
            "Error loading repositories",
        ]:
            empty_changes = {"new": [], "modified": [], "deleted": [], "unchanged": []}
            return (
                empty_changes,
                [],
                "Please select a valid repository.",
                {"error": "No repository selected"},
                create_file_selector(visible=False),
                create_file_selector(visible=False),
                gr.Dataframe(value=[]),
                create_file_selector(visible=False),
                gr.Button(interactive=False),
                gr.Button(interactive=False),
                gr.Button(interactive=False),
            )

        if not branch.strip():
            branch = "main"

        try:
            logger.info(f"Detecting changes for {repo_name} on branch {branch}")

            # Get changes and available files
            result = discover_repository_files_with_changes(
                repo_name, repo_name, branch
            )

            changes = result["changes"]
            has_changes = result["has_changes"]
            message = result["message"]

            logger.info(
                f"Change detection result: {len(changes['new'])} new, {len(changes['modified'])} modified, {len(changes['deleted'])} deleted, {len(changes['unchanged'])} unchanged"
            )

            # Calculate available files (files in repo but not ingested)
            all_current_files = (
                changes["new"] + changes["modified"] + changes["unchanged"]
            )
            ingested_files = repository_manager.get_repository_files(repo_name)
            ingested_paths = {f["path"] for f in ingested_files}

            available_files = []
            for file_info in all_current_files:
                file_path = (
                    file_info["path"] if isinstance(file_info, dict) else file_info
                )
                if file_path not in ingested_paths:
                    available_files.append(file_path)

            logger.info(f"Available files not ingested: {len(available_files)}")

            # Create change summary
            change_summary = {
                "repository": repo_name,
                "branch": branch,
                "has_changes": has_changes,
                "new_files": len(changes["new"]),
                "modified_files": len(changes["modified"]),
                "deleted_files": len(changes["deleted"]),
                "unchanged_files": len(changes["unchanged"]),
                "available_files": len(available_files),
                "total_current_files": len(all_current_files),
                "ingested_files": len(ingested_paths),
            }

            # Prepare file selectors
            new_file_paths = [f["path"] for f in changes["new"]]
            modified_file_paths = [f["path"] for f in changes["modified"]]

            new_files_selector = create_file_selector(
                choices=new_file_paths,
                label=f"New files ({len(new_file_paths)})",
                visible=len(new_file_paths) > 0,
            )

            modified_files_selector = create_file_selector(
                choices=modified_file_paths,
                label=f"Modified files ({len(modified_file_paths)})",
                visible=len(modified_file_paths) > 0,
            )

            available_files_selector = create_file_selector(
                choices=available_files,
                label=f"Available files ({len(available_files)})",
                visible=len(available_files) > 0,
            )

            # Deleted files display
            deleted_data = []
            for deleted_file in changes["deleted"]:
                deleted_data.append([deleted_file["path"], deleted_file["sha"]])

            deleted_files_display = gr.Dataframe(
                value=deleted_data,
                headers=["File Path", "Last SHA"],
                datatype=["str", "str"],
                label=f"Deleted files ({len(deleted_data)})",
                interactive=False,
            )

            # Enable buttons based on available actions
            has_new_or_modified = (
                len(changes["new"]) > 0 or len(changes["modified"]) > 0
            )
            has_available = len(available_files) > 0
            has_deleted = len(changes["deleted"]) > 0

            return (
                changes,
                available_files,
                message,
                change_summary,
                new_files_selector,
                modified_files_selector,
                deleted_files_display,
                available_files_selector,
                gr.Button(interactive=has_new_or_modified),
                gr.Button(interactive=has_available),
                gr.Button(interactive=has_deleted),
            )

        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
            empty_changes = {"new": [], "modified": [], "deleted": [], "unchanged": []}
            return (
                empty_changes,
                [],
                f"Error: {str(e)}",
                {"error": str(e)},
                create_file_selector(visible=False),
                create_file_selector(visible=False),
                gr.Dataframe(value=[]),
                create_file_selector(visible=False),
                gr.Button(interactive=False),
                gr.Button(interactive=False),
                gr.Button(interactive=False),
            )

    def _select_files_by_type(self, changes: Dict, file_type: str) -> gr.CheckboxGroup:
        """Select all files of a specific type."""
        if not changes or file_type not in changes:
            return gr.CheckboxGroup(value=[])

        file_paths = [f["path"] for f in changes[file_type]]
        return gr.CheckboxGroup(value=file_paths)

    def _select_all_available(self, available_files: List[str]) -> gr.CheckboxGroup:
        """Select all available files."""
        return gr.CheckboxGroup(value=available_files)

    async def _process_changed_files(
        self,
        repo_name: str,
        branch: str,
        selected_new: List[str],
        selected_modified: List[str],
        changes: Dict,
    ):
        """Process changed files (new and modified) using incremental updates."""
        if not repo_name or repo_name in [
            "No repositories available",
            "Error loading repositories",
        ]:
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No repository selected",
                "progress": 0,
            }
            yield error_progress, format_progress_display(error_progress)
            return

        all_selected = selected_new + selected_modified
        if not all_selected:
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No files selected for processing",
                "progress": 0,
            }
            yield error_progress, format_progress_display(error_progress)
            return

        try:
            start_time = time.time()

            # Initial progress
            initial_progress = {
                "status": ProcessingStatus.LOADING.value,
                "message": f"🔄 Processing {len(all_selected)} changed files incrementally",
                "progress": 0,
                "phase": "Starting Incremental Update",
                "details": f"Repository: {repo_name}\nBranch: {branch}\nFiles: {len(all_selected)}\nMode: Incremental (preserves existing files)",
                "step": "update_processing",
            }

            yield initial_progress, format_progress_display(initial_progress)

            # Step 1: Delete old versions of modified files first
            if selected_modified:
                logger.info(
                    f"Removing old versions of {len(selected_modified)} modified files"
                )
                removed_count = repository_manager.delete_specific_files(
                    repo_name, selected_modified
                )
                logger.info(f"Removed {removed_count} old file versions")

            # Step 2: Load selected files
            documents, failed_files = await load_files_from_github(
                repo_name, all_selected, branch
            )

            if not documents:
                error_progress = {
                    "status": ProcessingStatus.ERROR.value,
                    "message": "❌ No documents could be loaded",
                    "progress": 0,
                    "details": f"All {len(all_selected)} files failed to load",
                }
                yield error_progress, format_progress_display(error_progress)
                return

            # Update progress
            loading_progress = {
                "status": ProcessingStatus.LOADED.value,
                "message": f"✅ Loaded {len(documents)} documents for incremental update",
                "progress": 50,
                "phase": "Files Loaded - Ready for Incremental Processing",
                "details": f"Successfully loaded: {len(documents)}\nFailed: {len(failed_files)}\nProcessing mode: Incremental",
                "step": "update_processing",
            }

            yield loading_progress, format_progress_display(loading_progress)

            # Step 3: Create file info with SHA for tracking
            files_with_sha = []
            new_file_shas = {f["path"]: f["sha"] for f in changes.get("new", [])}
            modified_file_shas = {
                f["path"]: f["sha"] for f in changes.get("modified", [])
            }
            all_file_shas = {**new_file_shas, **modified_file_shas}

            for file_path in all_selected:
                if file_path in all_file_shas:
                    files_with_sha.append(
                        {"path": file_path, "sha": all_file_shas[file_path]}
                    )

            logger.info(f"Processing {len(documents)} documents with SHA tracking")

            # Step 4: Ingest documents incrementally
            success = await ingest_documents_async(
                documents, repo_name, branch=branch, files_with_sha=files_with_sha
            )

            processing_time = time.time() - start_time

            if success:
                # Get current repository stats
                current_stats = repository_manager.get_repository_stats()
                total_docs = current_stats.get("total_documents", "unknown")

                completion_progress = {
                    "status": ProcessingStatus.COMPLETE.value,
                    "message": f"🎉 Successfully updated {len(documents)} files incrementally",
                    "progress": 100,
                    "phase": "Incremental Update Complete",
                    "details": f"Repository: {repo_name}\nIncremental update completed:\n• New files: {len(selected_new)}\n• Modified files: {len(selected_modified)}\n• Total repository documents: {total_docs}\nTime: {processing_time:.1f}s",
                    "step": "update_complete",
                    "processing_time": processing_time,
                    "documents_processed": len(documents),
                    "total_time": processing_time,
                    "update_mode": "incremental",
                }
            else:
                completion_progress = {
                    "status": ProcessingStatus.ERROR.value,
                    "message": "❌ Incremental update processing failed",
                    "progress": 0,
                    "details": "Vector ingestion failed during incremental update",
                }

            yield completion_progress, format_progress_display(completion_progress)

        except Exception as e:
            logger.error(f"Error processing changed files: {e}")
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": f"❌ Incremental update failed: {str(e)}",
                "progress": 0,
                "error": str(e),
                "details": f"Incremental update error: {str(e)}",
            }
            yield error_progress, format_progress_display(error_progress)

    def _ingest_available_files(
        self, repo_name: str, branch: str, selected_files: List[str]
    ) -> Tuple[Dict, str]:
        """Ingest available files that haven't been processed yet."""
        if not selected_files:
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No files selected for ingestion",
                "progress": 0,
            }
            return error_progress, format_progress_display(error_progress)

        try:
            start_time = time.time()

            # This needs to be async, so let's create an async wrapper
            import asyncio

            async def _async_ingest():
                # Load and process files
                documents, failed_files = await load_files_from_github(
                    repo_name, selected_files, branch
                )

                if documents:
                    # Extract SHA info from documents for tracking
                    files_with_sha = []
                    for doc in documents:
                        file_path = doc.metadata.get("file_path", "")
                        file_sha = doc.metadata.get("sha", "")
                        if file_path and file_sha:
                            files_with_sha.append({"path": file_path, "sha": file_sha})

                    success = await ingest_documents_async(
                        documents,
                        repo_name,
                        branch=branch,
                        files_with_sha=files_with_sha,
                    )
                    processing_time = time.time() - start_time

                    if success:
                        completion_progress = {
                            "status": ProcessingStatus.COMPLETE.value,
                            "message": f"🎉 Successfully ingested {len(documents)} new files",
                            "progress": 100,
                            "processing_time": processing_time,
                            "documents_processed": len(documents),
                            "total_time": processing_time,
                        }
                    else:
                        completion_progress = {
                            "status": ProcessingStatus.ERROR.value,
                            "message": "❌ Ingestion failed",
                            "progress": 0,
                        }
                else:
                    completion_progress = {
                        "status": ProcessingStatus.ERROR.value,
                        "message": "❌ No documents could be loaded",
                        "progress": 0,
                    }

                return completion_progress, format_progress_display(completion_progress)

            # Run the async function
            return asyncio.run(_async_ingest())

        except Exception as e:
            logger.error(f"Error ingesting available files: {e}")
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": f"❌ Ingestion failed: {str(e)}",
                "progress": 0,
            }
            return error_progress, format_progress_display(error_progress)

    def _delete_removed_files(self, repo_name: str, changes: Dict) -> Tuple[Dict, str]:
        """Delete files that have been removed from the repository."""
        deleted_files = changes.get("deleted", [])
        if not deleted_files:
            info_progress = {
                "status": ProcessingStatus.COMPLETE.value,
                "message": "ℹ️ No deleted files to remove",
                "progress": 100,
            }
            return info_progress, format_progress_display(info_progress)

        try:
            deleted_paths = [f["path"] for f in deleted_files]
            deleted_count = repository_manager.delete_specific_files(
                repo_name, deleted_paths
            )

            completion_progress = {
                "status": ProcessingStatus.COMPLETE.value,
                "message": f"🗑️ Removed {deleted_count} deleted files from vector store",
                "progress": 100,
                "details": f"Deleted files: {len(deleted_files)}\nVector entries removed: {deleted_count}",
            }

            return completion_progress, format_progress_display(completion_progress)

        except Exception as e:
            logger.error(f"Error deleting removed files: {e}")
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": f"❌ Failed to delete files: {str(e)}",
                "progress": 0,
            }
            return error_progress, format_progress_display(error_progress)

    def _refresh_progress(self, progress_state: Dict) -> str:
        """Refresh progress display."""
        return format_progress_display(progress_state)