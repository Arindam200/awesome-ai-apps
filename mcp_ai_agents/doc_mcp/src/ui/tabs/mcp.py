"""Interface to implement MCP tab (Hidden)"""

from typing import Dict, List, Optional, Any, Union
import logging

import asyncio
import gradio as gr

from ...database.repository import repository_manager
from ...github.client import github_client
from ...github.file_loader import load_files_from_github
from ...rag.query import create_query_retriever
logger = logging.getLogger(__name__)


class MCPTab:
    """Hidden tab for MCP(Model context Protocol) functionality."""

    def __init__(self):
        # Initialize common input components
        self.repo_name_input = gr.Textbox(
            label="Repository Name", placeholder="Enter repo name"
        )

        self.branch_input = gr.Textbox(
            label="Branch",
            placeholder="Enter branch name (default: main)",
            value="main",
        )

        self.file_extensions_input = gr.CheckboxGroup(
            label="File Extensions",
            choices=[".md", ".mdx", ".txt", ".py"],
            value=[".md", ".mdx"],
        )

        self.single_file_path_input = gr.Textbox(
            label="File Path", placeholder="Enter file path"
        )

        self.multi_file_paths_input = gr.Textbox(
            label="File Paths (comma separated)",
            placeholder="Enter file paths, e.g. file1.md,file2.md",
        )

        self.query_input = gr.Textbox(label="Query", placeholder="Enter your question")

        self.search_mode_input = gr.Radio(
            label="Search Mode",
            choices=["default", "text_search", "hybrid"],
            value="default",
        )

        self.top_k_input = gr.Number(label="Top K Results", value=5, precision=0)

    def create_tab(self) -> gr.TabItem:
        """Create the MCP tab interface."""

        with gr.TabItem("MCP", visible=False) as tab:
            with gr.Column():
                # Buttons
                list_repo_btn = gr.Button("List Repositories")
                list_repo_file_btn = gr.Button("List Repository Files")
                get_file_content_btn = gr.Button("Get File Content")
                get_multi_file_content_btn = gr.Button("Get Multi File Content")
                query_btn = gr.Button("Query Repository")

                # Common inputs section
                with gr.Group():
                    gr.Markdown("### Repository Settings")
                    self.repo_name_input.render()
                    self.branch_input.render()

                # File-specific inputs
                with gr.Group():
                    gr.Markdown("### File Settings")
                    self.file_extensions_input.render()
                    self.single_file_path_input.render()
                    self.multi_file_paths_input.render()

                # Query-specific inputs
                with gr.Group():
                    gr.Markdown("### Query Settings")
                    self.query_input.render()
                    self.search_mode_input.render()
                    self.top_k_input.render()

                # Output
                output_block = gr.JSON(label="Output")

            # Define the actions for each button
            list_repo_btn.click(
                fn=self.list_available_repos_docs, inputs=[], outputs=output_block
            )

            list_repo_file_btn.click(
                fn=self.list_repository_files,
                inputs=[
                    self.repo_name_input,
                    self.file_extensions_input,
                    self.branch_input,
                ],
                outputs=output_block,
            )

            get_file_content_btn.click(
                fn=self.get_single_file_content_from_repo,
                inputs=[
                    self.repo_name_input,
                    self.single_file_path_input,
                    self.branch_input,
                ],
                outputs=output_block,
            )

            get_multi_file_content_btn.click(
                fn=self.get_multi_file_content_from_repo,
                inputs=[
                    self.repo_name_input,
                    self.multi_file_paths_input,
                    self.branch_input,
                ],
                outputs=output_block,
            )

            query_btn.click(
                fn=self.query_doc,
                inputs=[
                    self.repo_name_input,
                    self.query_input,
                    self.search_mode_input,
                    self.top_k_input,
                ],
                outputs=output_block,
            )

            return tab

    def list_available_repos_docs(self) -> List[Dict[str, str]]:
        """
        List of available ingested repositories docs.

        Returns:
            List[Dict[str, str]]: List of dictionaries containing repository names and branches.
        """
        try:
            repos = repository_manager.repos_collection.find(
                {}, {"repo_name": 1, "branch": 1, "_id": 0}
            )
            return list(repos)
        except Exception as e:
            logger.error(f"Error fetching repositories: {e}")
            return []

    def list_repository_files(
        self,
        repo_name: str,
        file_extensions: Optional[List[str]] = None,
        branch: Optional[str] = None,
    ) ->  Union[List[str], Dict[str, str]]:
        """
        List files in a repository with optional filtering by extensions and branch.
        Parameters:
            repo_name (str): Name of the repository.
            file_extensions (Optional[List[str]]): List of file extensions to filter by. Defaults to [".md", ".mdx"].
            branch (Optional[str]): Branch name to list files from. Defaults to main

        Returns:
            List[str]: List of file paths in the repository.
        """
        # Validation
        if not repo_name or not repo_name.strip():
            return {"error": "Repository name is required"}

        if not branch or not branch.strip():
            branch = "main"

        if not file_extensions:
            file_extensions = [".md", ".mdx"]

        filtered_files, _ = github_client.get_repository_tree(
            repo_url=repo_name, file_extensions=file_extensions, branch=branch
        )

        return filtered_files

    def get_single_file_content_from_repo(
        self, repo_name: str, file_path: str, branch: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get content of a single file in a repository.

        Parameters:
            repo_name (str): Name of the repository.
            file_path (str): Path to the file within the repository.
            branch (Optional[str]): Branch name to get the file from. Defaults to main.

        Returns:
            str: Content of the file.
        """
        # Validation
        if not repo_name or not repo_name.strip():
            return {"error": "Repository name is required"}

        if not file_path or not file_path.strip():
            return {"error": "File path is required"}

        if not branch or not branch.strip():
            branch = "main"

        file, _ = asyncio.run(
            load_files_from_github(
                repo_url=repo_name, file_paths=[file_path], branch=branch
            )
        )

        return (
            {"file_path": file_path, "content": file[0].get_content()}
            if file
            else {"message": "File not found or empty"}
        )

    def get_multi_file_content_from_repo(
        self, repo_name: str, file_paths: List[str], branch: Optional[str] = None
    ) ->  Union[List[str], Dict[str, str]]:
        """
        Get content of multiple files in a repository.

        Parameters:
            repo_name (str): Name of the repository.
            file_paths (List[str]): List of file paths within the repository.
            branch (Optional[str]): Branch name to get the files from. Defaults to main.

        Returns:
            List[str]: List of file contents.
        """
        # Validation
        if not repo_name or not repo_name.strip():
            return {"error": "Repository name is required"}

        if not file_paths:
            return {"error": "File paths are required"}

        if not branch or not branch.strip():
            branch = "main"

        if isinstance(file_paths, str):
            processed_file_paths = [
                file_path.strip() for file_path in file_paths.split(",")
            ]
            if not processed_file_paths or all(
                not path for path in processed_file_paths
            ):
                return {"error": "At least one valid file path is required"}
        else:
            processed_file_paths = file_paths

        files, _ = asyncio.run(
            load_files_from_github(
                repo_url=repo_name, file_paths=processed_file_paths, branch=branch
            )
        )

        return [
            {"path": file.metadata["file_path"], "content": file.get_content()}
            for file in files
        ]

    def query_doc(
        self,
        repo_name: str,
        query: str,
        mode: Optional[str] = "default",
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query against the repository documents.

        Args:
            repo_name (str): Name of the repository.
            query (str): User's question.
            mode Optional[str]: Search mode (default, text_search, hybrid). Optional and defaults to "default".
            top_k Optional[int]: Number of results to return. Optional and defaults to 5.

        Returns:
            Dict[str, any]: Dictionary with response and source nodes.
        """
        # Validation
        if not repo_name or not repo_name.strip():
            return {"error": "Repository name is required"}

        if not query or not query.strip():
            return {"error": "Query is required"}

        if mode not in ["default", "text_search", "hybrid"]:
            mode = "default"

        if top_k is None or top_k <= 0:
            top_k = 5

        if top_k > 100:
            top_k = 100

        return create_query_retriever(repo_name).make_query(query, mode, top_k)