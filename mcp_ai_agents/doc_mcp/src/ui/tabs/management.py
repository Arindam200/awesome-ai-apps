"""Repository management tab implementation."""

from typing import Any, Dict, List, Tuple
import logging

import gradio as gr

from ...core.config import settings
from ...database.repository import repository_manager
logger = logging.getLogger(__name__)


class ManagementTab:
    """Handles the repository management tab UI and logic."""

    def __init__(self, demo: gr.Blocks):
        """Initialize the management tab."""
        self.demo = demo

    def create_tab(self) -> gr.TabItem:
        """Create the management tab interface."""
        with gr.TabItem(
            "🗂️ Repository Management", visible=settings.enable_repo_management
        ) as tab:
            gr.Markdown("### 📊 Repository Management")
            gr.Markdown(
                "Manage your ingested repositories - view details and delete repositories when needed."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Repository Statistics")
                    stats_display = gr.JSON(
                        label="Database Statistics",
                        value={"message": "Click refresh to load statistics..."},
                    )
                    refresh_stats_btn = gr.Button(
                        "🔄 Refresh Statistics", variant="secondary"
                    )

                with gr.Column(scale=2):
                    gr.Markdown("### 📋 Repository Details")
                    repos_table = gr.Dataframe(
                        headers=["Repository", "Files", "Last Updated", "Status"],
                        datatype=["str", "number", "str", "str"],
                        label="Ingested Repositories",
                        interactive=False,
                        wrap=True,
                    )
                    refresh_repos_btn = gr.Button(
                        "🔄 Refresh Repository List", variant="secondary"
                    )

            # Deletion section
            gr.Markdown("### 🗑️ Delete Repository")
            gr.Markdown(
                "**⚠️ Warning:** This will permanently delete all documents and metadata for the selected repository."
            )

            with gr.Row():
                with gr.Column(scale=2):
                    # Initialize dropdown with current repositories
                    initial_table_data, initial_dropdown_choices = (
                        self._load_repository_details()
                    )

                    delete_repo_dropdown = gr.Dropdown(
                        choices=initial_dropdown_choices,
                        label="Select Repository to Delete",
                        value=None,
                        interactive=True,
                        allow_custom_value=False,
                    )

                    confirm_delete = gr.Checkbox(
                        label="I understand this action cannot be undone", value=False
                    )

                    delete_btn = gr.Button(
                        "🗑️ Delete Repository",
                        variant="stop",
                        size="lg",
                        interactive=False,
                    )

                with gr.Column(scale=1):
                    deletion_status = gr.Textbox(
                        label="Deletion Status",
                        value="Select a repository and confirm to enable deletion.",
                        interactive=False,
                        lines=6,
                    )

            # Set initial data for table
            repos_table.value = initial_table_data

            # Event handlers
            refresh_stats_btn.click(
                fn=self._load_repository_stats, outputs=[stats_display], show_api=False
            )

            refresh_repos_btn.click(
                fn=self._refresh_all_data,
                outputs=[repos_table, delete_repo_dropdown],
                show_api=False,
            )

            delete_repo_dropdown.change(
                fn=self._check_delete_button_state,
                inputs=[delete_repo_dropdown, confirm_delete],
                outputs=[delete_btn],
                show_api=False,
            )

            confirm_delete.change(
                fn=self._check_delete_button_state,
                inputs=[delete_repo_dropdown, confirm_delete],
                outputs=[delete_btn],
                show_api=False,
            )

            delete_btn.click(
                fn=self._delete_repository,
                inputs=[delete_repo_dropdown, confirm_delete],
                outputs=[
                    deletion_status,
                    delete_repo_dropdown,
                    confirm_delete,
                    repos_table,
                ],
                show_api=False,
            )

            # Load initial data when the demo loads
            self.demo.load(
                fn=self._load_repository_stats, outputs=[stats_display], show_api=False
            )
            self.demo.load(
                fn=self._refresh_all_data,
                outputs=[repos_table, delete_repo_dropdown],
                show_api=False,
            )

        return tab

    def _load_repository_stats(self) -> Dict[str, Any]:
        """Load repository statistics."""
        try:
            return repository_manager.get_repository_stats()
        except Exception as e:
            logger.error(f"Failed to load repository stats: {e}")
            return {"error": f"Failed to load statistics: {str(e)}"}

    def _load_repository_details(self) -> Tuple[List[List], List[str]]:
        """Load repository details for table and dropdown."""
        try:
            details = repository_manager.get_repository_details()

            if not details:
                return [["No repositories found", 0, "N/A", "N/A"]], []

            # Format for dataframe
            table_data = []
            dropdown_choices = []

            for repo in details:
                last_updated = repo.get("last_updated", "Unknown")
                if hasattr(last_updated, "strftime"):
                    last_updated = last_updated.strftime("%Y-%m-%d %H:%M")
                elif last_updated != "Unknown":
                    last_updated = str(last_updated)

                repo_name = repo.get("name", "Unknown")
                table_data.append(
                    [
                        repo_name,
                        repo.get("files", 0),
                        last_updated,
                        repo.get("status", "unknown"),
                    ]
                )

                # Add to dropdown choices
                if repo_name != "Unknown":
                    dropdown_choices.append(repo_name)

            return table_data, dropdown_choices

        except Exception as e:
            logger.error(f"Error loading repository details: {e}")
            return [["Error loading repositories", 0, str(e), "error"]], []

    def _refresh_all_data(self) -> Tuple[List[List], gr.Dropdown]:
        """Refresh both table and dropdown data."""
        try:
            table_data, dropdown_choices = self._load_repository_details()

            # Create new dropdown component with updated choices
            updated_dropdown = gr.Dropdown(
                choices=dropdown_choices,
                value=None,
                label="Select Repository to Delete",
                interactive=True,
                allow_custom_value=False,
            )

            logger.info(
                f"Refreshed data: {len(table_data)} table rows, {len(dropdown_choices)} dropdown choices"
            )
            return table_data, updated_dropdown

        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            return [["Error loading repositories", 0, str(e), "error"]], gr.Dropdown(
                choices=[],
                value=None,
                label="Select Repository to Delete",
                interactive=True,
                allow_custom_value=False,
            )

    def _check_delete_button_state(
        self, repo_selected: str, confirmation_checked: bool
    ):
        """Enable/disable delete button based on selection and confirmation."""
        if repo_selected and confirmation_checked and repo_selected != "":
            return gr.Button(interactive=True)
        else:
            return gr.Button(interactive=False)

    def _delete_repository(
        self, repo_name: str, confirmed: bool
    ) -> Tuple[str, gr.Dropdown, gr.Checkbox, List[List]]:
        """Delete the selected repository."""
        if not repo_name:
            table_data, dropdown_choices = self._load_repository_details()
            return (
                "❌ No repository selected.",
                gr.Dropdown(
                    choices=dropdown_choices,
                    value=None,
                    label="Select Repository to Delete",
                    interactive=True,
                    allow_custom_value=False,
                ),
                gr.Checkbox(value=False),
                table_data,
            )

        if not confirmed:
            table_data, dropdown_choices = self._load_repository_details()
            return (
                "❌ Please confirm deletion by checking the checkbox.",
                gr.Dropdown(
                    choices=dropdown_choices,
                    value=repo_name,
                    label="Select Repository to Delete",
                    interactive=True,
                    allow_custom_value=False,
                ),
                gr.Checkbox(value=False),
                table_data,
            )

        try:
            logger.info(f"Deleting repository: {repo_name}")
            result = repository_manager.delete_repository_data(repo_name)

            # Refresh data after deletion
            table_data, dropdown_choices = self._load_repository_details()

            # Create updated dropdown
            updated_dropdown = gr.Dropdown(
                choices=dropdown_choices,
                value=None,
                label="Select Repository to Delete",
                interactive=True,
                allow_custom_value=False,
            )

            if result["success"]:
                return (
                    f"✅ {result['message']}",
                    updated_dropdown,
                    gr.Checkbox(value=False),
                    table_data,
                )
            else:
                return (
                    f"❌ {result['message']}",
                    updated_dropdown,
                    gr.Checkbox(value=False),
                    table_data,
                )

        except Exception as e:
            logger.error(f"Repository deletion error: {e}")
            table_data, dropdown_choices = self._load_repository_details()
            return (
                f"❌ Deletion failed: {str(e)}",
                gr.Dropdown(
                    choices=dropdown_choices,
                    value=None,
                    label="Select Repository to Delete",
                    interactive=True,
                    allow_custom_value=False,
                ),
                gr.Checkbox(value=False),
                table_data,
            )