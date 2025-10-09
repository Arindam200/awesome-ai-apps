"""Query interface tab implementation."""

from typing import Any, Dict, Tuple
import logging

import gradio as gr

from ...database.repository import repository_manager
from ...rag.query import create_query_retriever
from ..components.common import (create_query_interface,
                                 create_repository_dropdown)

logger = logging.getLogger(__name__)


class QueryTab:
    """Handles the query interface tab UI and logic."""

    def __init__(self):
        pass

    def create_tab(self) -> gr.TabItem:
        """Create the query tab interface."""
        with gr.TabItem("🤖 AI Documentation Assistant") as tab:
            gr.Markdown("### 💬 Intelligent Documentation Q&A")
            gr.Markdown(
                "Query your processed documentation using advanced semantic search. Get contextual answers with source citations."
            )

            with gr.Row():
                with gr.Column(scale=2):
                    # Repository selection
                    with gr.Row():
                        repo_dropdown = create_repository_dropdown(
                            choices=self._get_available_repos(),
                            label="📚 Select Documentation Repository",
                        )

                        selected_repo_textbox = gr.Textbox(
                            label="🎯 Selected Repository",
                            value="",
                            interactive=False,
                            visible=False,
                        )

                    refresh_repos_btn = gr.Button(
                        "🔄 Refresh Repository List", variant="secondary", size="sm"
                    )

                    (
                        query_input,
                        query_mode,
                        query_btn,
                        response_output,
                        sources_output,
                    ) = create_query_interface()

            # Event handlers
            repo_dropdown.change(
                fn=self._handle_repo_selection,
                inputs=[repo_dropdown],
                outputs=[repo_dropdown, selected_repo_textbox, query_btn],
                show_api=False,
            )

            refresh_repos_btn.click(
                fn=self._refresh_repositories,
                outputs=[repo_dropdown, selected_repo_textbox, query_btn],
                show_api=False,
            )

            query_btn.click(
                fn=self._execute_query,
                inputs=[selected_repo_textbox, query_mode, query_input],
                outputs=[response_output, sources_output],
                show_api=False,
            )

            query_input.submit(
                fn=self._execute_query,
                inputs=[selected_repo_textbox, query_mode, query_input],
                outputs=[response_output, sources_output],
                show_api=False,
            )

        return tab

    def _get_available_repos(self):
        """Get list of available repositories."""
        try:
            repos = repository_manager.get_available_repositories()
            return repos if repos else ["No repositories available"]
        except Exception as e:
            logger.error(f"Error getting repositories: {e}")
            return ["Error loading repositories"]

    def _handle_repo_selection(self, selected_repo: str):
        """Handle repository selection from dropdown."""
        if not selected_repo or selected_repo in [
            "No repositories available",
            "Error loading repositories",
            "",
        ]:
            return (
                gr.Dropdown(visible=True),
                gr.Textbox(visible=False, value=""),
                gr.Button(interactive=False),
            )
        else:
            return (
                gr.Dropdown(visible=False),
                gr.Textbox(visible=True, value=selected_repo),
                gr.Button(interactive=True),
            )

    def _refresh_repositories(self):
        """Refresh repository list."""
        try:
            repos = self._get_available_repos()
            return (
                gr.Dropdown(choices=repos, value=None, visible=True),
                gr.Textbox(visible=False, value=""),
                gr.Button(interactive=False),
            )
        except Exception as e:
            logger.error(f"Error refreshing repositories: {e}")
            return (
                gr.Dropdown(
                    choices=["Error loading repositories"], value=None, visible=True
                ),
                gr.Textbox(visible=False, value=""),
                gr.Button(interactive=False),
            )

    def _execute_query(
        self, repo: str, mode: str, query: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Execute query against repository."""
        if not query.strip():
            return "Please enter a query.", {"error": "Empty query"}

        if not repo or repo in [
            "No repositories available",
            "Error loading repositories",
            "",
        ]:
            return "Please select a valid repository.", {
                "error": "No repository selected"
            }

        try:
            # Create query retriever
            retriever = create_query_retriever(repo)

            # Execute query
            result = retriever.make_query(query, mode)

            if "error" in result:
                return f"Error: {result['error']}", {"error": result["error"]}

            response_text = result.get("response", "No response available")
            source_nodes = result.get("source_nodes", [])

            return response_text, {
                "sources": source_nodes,
                "repository": repo,
                "mode": mode,
                "processing_time": result.get("processing_time", 0),
                "total_sources": len(source_nodes),
            }

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            error_msg = f"Query failed: {str(e)}"
            return error_msg, {"error": str(e)}