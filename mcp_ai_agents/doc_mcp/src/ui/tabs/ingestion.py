"""Documentation ingestion tab implementation."""

from typing import Any, Dict, List
import logging

import gradio as gr
import time

from ...core.types import ProcessingStatus
from ...github.file_loader import (discover_repository_files,
                                   load_files_from_github)
from ...rag.ingestion import ingest_documents_async
from ..components.common import (create_file_selector, create_progress_display,
                                 create_status_textbox,
                                 format_progress_display)

logger = logging.getLogger(__name__)


class IngestionTab:
    """Handles the documentation ingestion tab UI and logic."""

    def __init__(self):
        self.progress_state = {}

    def create_tab(self) -> gr.TabItem:
        """Create the ingestion tab interface."""
        with gr.TabItem("📥 Documentation Ingestion") as tab:
            gr.Markdown("### 🚀 Two-Step Documentation Processing Pipeline")
            gr.Markdown(
                "**Step 1:** Fetch markdown files from GitHub repository → **Step 2:** Generate vector embeddings and store in MongoDB Atlas"
            )

            # Repository input section
            with gr.Row(equal_height=True):
                with gr.Column(scale=2):
                    repo_input = gr.Textbox(
                        label="📂 GitHub Repository URL",
                        placeholder="Enter: owner/repo or https://github.com/owner/repo (e.g., gradio-app/gradio)",
                        value="",
                        info="Enter any GitHub repository containing markdown documentation",
                    )

                    branch_input = gr.Textbox(
                        label="🌿 Branch (optional)",
                        placeholder="Enter branch name (default: main)",
                        value="main",
                    )

                    load_btn = gr.Button(
                        "🔍 Discover Documentation Files", variant="secondary"
                    )

                with gr.Column(scale=1):
                    status_output = create_status_textbox(
                        label="Repository Discovery Status",
                        placeholder="Repository scanning results will appear here...",
                        lines=10,
                    )

            # File selection controls
            with gr.Row():
                select_all_btn = gr.Button(
                    "📋 Select All Documents", variant="secondary"
                )
                clear_all_btn = gr.Button("🗑️ Clear Selection", variant="secondary")

            # File selector
            with gr.Accordion("Available Documentation Files", open=False):
                file_selector = create_file_selector(
                    label="Select Markdown Files for RAG Processing"
                )

            # Processing controls
            gr.Markdown("### 🔄 RAG Pipeline Execution")

            with gr.Row():
                step1_btn = gr.Button(
                    "📥 Step 1: Load Files from GitHub",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )
                step2_btn = gr.Button(
                    "🧠 Step 2: Process & Store Embeddings",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

            with gr.Row():
                refresh_btn = gr.Button("🔄 Refresh Progress", variant="secondary")
                reset_btn = gr.Button("🗑️ Reset Progress", variant="secondary")

            # Progress display
            progress_display = create_progress_display(
                label="📊 Real-time Processing Progress",
                initial_value="🚀 Ready to start two-step processing...\n\n📋 Steps:\n1️⃣ Load files from GitHub repository\n2️⃣ Generate embeddings and store in vector database",
                lines=20,
            )

            # State management
            files_state = gr.State([])
            progress_state = gr.State({})
            branch_state = gr.State("main")

            # Event handlers
            load_btn.click(
                fn=self._discover_files,
                inputs=[repo_input, branch_input],
                outputs=[
                    file_selector,
                    status_output,
                    files_state,
                    step1_btn,
                    branch_state,
                ],
                show_api=False,
            )

            select_all_btn.click(
                fn=self._select_all_files,
                inputs=[files_state],
                outputs=[file_selector],
                show_api=False,
            )

            clear_all_btn.click(
                fn=self._clear_selection, outputs=[file_selector], show_api=False
            )

            # Use generator for real-time updates
            step1_btn.click(
                fn=self._start_file_loading_generator,
                inputs=[repo_input, file_selector, progress_state, branch_state],
                outputs=[progress_state, progress_display, step2_btn],
                show_api=False,
            )

            step2_btn.click(
                fn=self._start_vector_ingestion,
                inputs=[progress_state],
                outputs=[progress_state, progress_display],
                show_api=False,
            )

            refresh_btn.click(
                fn=self._refresh_progress,
                inputs=[progress_state],
                outputs=[progress_display],
                show_api=False,
            )

            reset_btn.click(
                fn=self._reset_progress,
                outputs=[progress_state, progress_display, step2_btn],
                show_api=False,
            )

        return tab

    def _discover_files(self, repo_url: str, branch: str = "main"):
        """Discover files in repository."""
        if not repo_url.strip():
            return (
                create_file_selector(visible=False),
                "Please enter a repository URL",
                [],
                gr.Button(interactive=False),
                "main",
            )

        # Use provided branch or default to main
        if not branch.strip():
            branch = "main"

        try:
            files_data, message = discover_repository_files(repo_url, branch=branch)

            if files_data:
                # Extract file paths for the selector (backward compatibility)
                if isinstance(files_data[0], dict):
                    # New format: list of {"path": "...", "sha": "..."}
                    file_paths = [file_info["path"] for file_info in files_data]
                else:
                    # Old format: list of file paths
                    file_paths = files_data

                return (
                    create_file_selector(
                        choices=file_paths,
                        label=f"Select Files from {repo_url}/{branch} ({len(file_paths)} files)",
                        visible=True,
                    ),
                    message,
                    files_data,  # Store the full data (with SHA) in state
                    gr.Button(interactive=True),
                    branch,
                )
            else:
                return (
                    create_file_selector(visible=False),
                    message,
                    [],
                    gr.Button(interactive=False),
                    branch,
                )
        except Exception as e:
            logger.error(f"File discovery error: {e}")
            return (
                create_file_selector(visible=False),
                f"Error: {str(e)}",
                [],
                gr.Button(interactive=False),
                branch,
            )

    def _select_all_files(self, available_files_data):
        """Select all available files."""
        if available_files_data:
            # Handle both old format (list of paths) and new format (list of dicts)
            if isinstance(available_files_data[0], dict):
                # New format: extract file paths from dictionaries
                file_paths = [file_info["path"] for file_info in available_files_data]
                return gr.CheckboxGroup(value=file_paths)
            else:
                # Old format: already a list of file paths
                return gr.CheckboxGroup(value=available_files_data)
        return gr.CheckboxGroup(value=[])

    def _clear_selection(self):
        """Clear file selection."""
        return gr.CheckboxGroup(value=[])

    async def _start_file_loading_generator(
        self,
        repo_url: str,
        selected_files: List[str],
        current_progress: Dict[str, Any],
        branch: str = "main",
    ):
        """Start file loading with real-time generator updates."""
        # Use provided branch or default to main
        if not branch.strip():
            branch = "main"

        logger.info(
            f"Starting file loading for {len(selected_files)} files from {repo_url}/{branch}"
        )

        if not selected_files:
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No files selected for loading",
                "progress": 0,
                "details": "Please select at least one file to proceed.",
                "step": "file_loading",
            }
            yield (
                error_progress,
                format_progress_display(error_progress),
                gr.Button(interactive=False),
            )
            return

        total_files = len(selected_files)
        start_time = time.time()

        # Parse repo name from URL
        if "github.com" in repo_url:
            repo_name = (
                repo_url.replace("https://github.com/", "")
                .replace("http://github.com/", "")
                .strip("/")
            )
            if "/" not in repo_name:
                error_progress = {
                    "status": ProcessingStatus.ERROR.value,
                    "message": "❌ Invalid repository URL format",
                    "progress": 0,
                    "details": "Expected format: owner/repo or https://github.com/owner/repo",
                    "step": "file_loading",
                }
                yield (
                    error_progress,
                    format_progress_display(error_progress),
                    gr.Button(interactive=False),
                )
                return
        else:
            repo_name = repo_url.strip()

        try:
            # Initial progress update
            initial_progress = {
                "status": ProcessingStatus.LOADING.value,
                "message": f"🚀 Starting file loading from {repo_name}/{branch}",
                "progress": 0,
                "total_files": total_files,
                "processed_files": 0,
                "successful_files": 0,
                "failed_files": 0,
                "phase": "File Loading",
                "details": f"Preparing to load {total_files} files from branch '{branch}'...",
                "step": "file_loading",
                "repo_name": repo_name,
                "branch": branch,
            }
            yield (
                initial_progress,
                format_progress_display(initial_progress),
                gr.Button(interactive=False),
            )

            # Use the existing load_files_from_github function with branch parameter
            documents, failed_files = await load_files_from_github(
                repo_url, selected_files, branch=branch, max_concurrent=10
            )

            loading_time = time.time() - start_time

            # Extract SHA information from loaded documents for tracking
            files_with_sha = []
            for doc in documents:
                file_path = doc.metadata.get("file_path", "")
                file_sha = doc.metadata.get("sha", "")
                if file_path and file_sha:
                    files_with_sha.append({"path": file_path, "sha": file_sha})

            # Final completion update
            completion_progress = {
                "status": ProcessingStatus.LOADED.value,
                "message": f"✅ File Loading Complete! Loaded {len(documents)} documents from {branch}",
                "progress": 100,
                "phase": "Files Loaded Successfully",
                "details": (
                    f"🎯 Final Results from branch '{branch}':\n✅ Successfully loaded: {len(documents)} documents\n❌ Failed files: {len(failed_files)}\n⏱️ Total time: {loading_time:.1f}s\n📊 Success rate: {(len(documents) / (len(documents) + len(failed_files)) * 100):.1f}%"
                    if (len(documents) + len(failed_files)) > 0
                    else "100%"
                ),
                "step": "file_loading_complete",
                "loaded_documents": documents,
                "failed_files": failed_files,
                "files_with_sha": files_with_sha,  # Add SHA tracking data
                "loading_time": loading_time,
                "repo_name": repo_name,
                "branch": branch,
                "total_files": total_files,
                "processed_files": total_files,
                "successful_files": len(documents),
            }
            yield (
                completion_progress,
                format_progress_display(completion_progress),
                gr.Button(interactive=True),  # Enable step 2 button
            )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"File loading error after {total_time:.1f}s: {e}")

            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": f"❌ File loading error after {total_time:.1f}s",
                "progress": 0,
                "phase": "Loading Failed",
                "details": f"Critical error during file loading from branch '{branch}':\n{str(e)}",
                "error": str(e),
                "step": "file_loading",
                "branch": branch,
            }
            yield (
                error_progress,
                format_progress_display(error_progress),
                gr.Button(interactive=False),
            )

    async def _start_vector_ingestion(self, current_progress: Dict[str, Any]):
        """Start vector ingestion process."""
        if current_progress.get("step") != "file_loading_complete":
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No documents to process",
                "progress": 0,
                "details": "Please load files first.",
            }
            return error_progress, format_progress_display(error_progress)

        documents = current_progress.get("loaded_documents", [])
        repo_name = current_progress.get("repo_name", "")
        branch = current_progress.get("branch", "main")
        files_with_sha = current_progress.get("files_with_sha", [])

        if not documents:
            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ No documents available",
                "progress": 0,
                "details": "No documents found to process.",
            }
            return error_progress, format_progress_display(error_progress)

        vector_start_time = time.time()

        try:
            logger.info(
                f"Starting vector ingestion for {len(documents)} documents from {repo_name}/{branch}"
            )

            # Run async ingestion without event loop issues
            success = await ingest_documents_async(
                documents, repo_name, branch=branch, files_with_sha=files_with_sha
            )

            vector_time = time.time() - vector_start_time
            loading_time = current_progress.get("loading_time", 0)
            total_time = loading_time + vector_time

            if success:
                # Get failed files data safely
                failed_files_data = current_progress.get("failed_files", [])
                failed_files_count = (
                    len(failed_files_data)
                    if isinstance(failed_files_data, list)
                    else (
                        failed_files_data if isinstance(failed_files_data, int) else 0
                    )
                )

                complete_progress = {
                    "status": ProcessingStatus.COMPLETE.value,
                    "message": f"🎉 Complete Processing Pipeline Finished for {repo_name}/{branch}!",
                    "progress": 100,
                    "phase": "Complete",
                    "details": f"Successfully processed {len(documents)} documents for {repo_name} from branch '{branch}' with SHA tracking enabled",
                    "step": "complete",
                    "total_time": total_time,
                    "documents_processed": len(documents),
                    "failed_files_count": failed_files_count,
                    "failed_files": failed_files_data,
                    "vector_time": vector_time,
                    "loading_time": loading_time,
                    "repo_name": repo_name,
                    "branch": branch,
                    "repository_updated": True,
                    "sha_tracking_enabled": True,  # Indicate SHA tracking is active
                }
            else:
                complete_progress = {
                    "status": ProcessingStatus.ERROR.value,
                    "message": "❌ Vector ingestion failed",
                    "progress": 0,
                    "details": "Document ingestion failed",
                }

            return complete_progress, format_progress_display(complete_progress)

        except Exception as e:
            vector_time = time.time() - vector_start_time
            logger.error(f"Vector ingestion error after {vector_time:.2f}s: {e}")

            # Get failed files data safely
            failed_files_data = current_progress.get("failed_files", [])
            failed_files_count = (
                len(failed_files_data)
                if isinstance(failed_files_data, list)
                else (failed_files_data if isinstance(failed_files_data, int) else 0)
            )

            error_progress = {
                "status": ProcessingStatus.ERROR.value,
                "message": "❌ Vector Store Ingestion Failed",
                "progress": 0,
                "phase": "Failed",
                "details": f"Error: {str(e)}",
                "error": str(e),
                "step": "vector_ingestion",
                "failed_files_count": failed_files_count,
                "failed_files": failed_files_data,
                "branch": branch,
            }
            return error_progress, format_progress_display(error_progress)

    def _refresh_progress(self, current_progress: Dict[str, Any]):
        """Refresh progress display."""
        return format_progress_display(current_progress)

    def _reset_progress(self):
        """Reset progress state."""
        return (
            {},
            "Ready to start two-step processing...",
            gr.Button(interactive=False),
        )