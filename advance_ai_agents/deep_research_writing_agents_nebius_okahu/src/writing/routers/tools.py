"""MCP Tools registration for writing operations."""

from typing import Any

from fastmcp import FastMCP

from writing.tools.edit_post_tool import edit_post_tool
from writing.tools.generate_image_tool import generate_image_tool
from writing.tools.generate_post_tool import generate_post_tool
from writing.utils.okahu_utils import atrace_span


def register_mcp_tools(mcp: FastMCP) -> None:
    """Register all MCP tools with the server instance."""

    # ========================================================================
    # POST GENERATION (with evaluate-optimize loop)
    # ========================================================================

    @mcp.tool()
    async def generate_post(
        working_dir: str, delete_iterations: bool = False
    ) -> dict[str, Any]:
        """Generate a LinkedIn post with an evaluate-optimize loop.

        Reads guideline.md and research.md from the working directory, generates
        an initial post, then runs N rounds of review + edit to refine it.

        By default, all intermediate post versions (post_0.md, post_1.md, ...)
        and reviews are saved. Pass delete_iterations=True to keep only
        the final post.md.

        Args:
            working_dir: Path to the directory containing guideline.md and research.md.
            delete_iterations: If True, only save the final post.md.
        """

        async with atrace_span(
            "mcp.tool.generate_post",
            {
                "working_dir": working_dir,
                "delete_iterations": delete_iterations,
            },
        ):
            return await generate_post_tool(
                working_dir, delete_iterations=delete_iterations
            )

    # ========================================================================
    # POST EDITING (single review+edit pass with human feedback)
    # ========================================================================

    @mcp.tool()
    async def edit_post(
        working_dir: str, human_feedback: str, delete_iterations: bool = False
    ) -> dict[str, Any]:
        """Edit an existing LinkedIn post based on human feedback.

        Reads the existing post.md, runs a review pass with the human feedback
        as highest priority, then edits the post. The updated post.md is saved
        in place.

        By default, saves a versioned copy (post_N.md) and reviews. Pass
        delete_iterations=True to skip saving versioned files and reviews.

        Args:
            working_dir: Path to the directory containing post.md, guideline.md, research.md.
            human_feedback: The user's feedback on what to change in the post.
            delete_iterations: If True, only update post.md.
        """

        async with atrace_span(
            "mcp.tool.edit_post",
            {
                "working_dir": working_dir,
                "human_feedback": human_feedback,
                "delete_iterations": delete_iterations,
            },
        ):
            return await edit_post_tool(
                working_dir, human_feedback, delete_iterations=delete_iterations
            )

    # ========================================================================
    # IMAGE GENERATION
    # ========================================================================

    @mcp.tool()
    async def generate_image(working_dir: str) -> dict[str, Any]:
        """Generate a LinkedIn post image using Gemini image generation.

        Reads the existing post.md and generates a professional image
        following the branding and character profiles. Saved as post_image.png.

        Args:
            working_dir: Path to the directory containing post.md.
        """

        async with atrace_span(
            "mcp.tool.generate_image",
            {"working_dir": working_dir},
        ):
            return await generate_image_tool(working_dir)
