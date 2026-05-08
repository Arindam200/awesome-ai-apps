"""Manual end-to-end test of the LinkedIn Writer MCP server workflow.

Connects to the writing MCP server as a client and runs the full
LinkedIn post writing workflow.

Usage:
    uv run python scripts/test_writing_workflow.py [--working-dir PATH]
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from fastmcp import Client

from writing.utils.logging import setup_logging

logger = logging.getLogger(__name__)

SEP_WIDTH = 70


def print_step(step: str, description: str) -> None:
    """Print a formatted workflow step header."""

    print(f"\n{'=' * SEP_WIDTH}")
    print(f"  STEP {step}: {description}")
    print(f"{'=' * SEP_WIDTH}\n")


def print_result(result: object) -> None:
    """Print the tool result in a readable format."""

    data = getattr(result, "data", result)
    if isinstance(data, dict):
        status = data.get("status", "unknown")
        message = data.get("message", "")
        print(f"  Status: {status}")
        if message:
            print(f"  Message: {message}")
        post = data.get("post", "")
        if post:
            print("\n  --- Post Content ---\n")
            for line in post.splitlines():
                print(f"  {line}")
            print("\n  --- End Post ---")
    else:
        print(f"  {data}")


async def run_workflow(
    client: Client, working_dir: str, delete_iterations: bool = False
) -> None:
    """Execute the full LinkedIn post writing workflow via MCP tool calls."""

    # ------------------------------------------------------------------
    # Step 1: Generate post (with evaluate-optimize loop)
    # ------------------------------------------------------------------
    print_step("1", "Generate LinkedIn post (with review/edit loop)")

    result = await client.call_tool(
        "generate_post",
        {"working_dir": working_dir, "delete_iterations": delete_iterations},
    )
    print_result(result)

    # ------------------------------------------------------------------
    # Step 2: Edit post with feedback
    # ------------------------------------------------------------------
    print_step("2", "Edit post with human feedback")

    result = await client.call_tool(
        "edit_post",
        {
            "working_dir": working_dir,
            "human_feedback": "Make the hook more provocative. Add a stronger call-to-action at the end.",
            "delete_iterations": delete_iterations,
        },
    )
    print_result(result)

    # ------------------------------------------------------------------
    # Step 3: Generate image
    # ------------------------------------------------------------------
    print_step("3", "Generate LinkedIn post image")

    try:
        result = await client.call_tool(
            "generate_image",
            {"working_dir": working_dir},
        )
        print_result(result)
    except Exception as e:
        print(f"  Image generation failed (may require Gemini image access): {e}")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    print(f"\n{'=' * SEP_WIDTH}")
    print("  WORKFLOW COMPLETE")
    print(f"{'=' * SEP_WIDTH}")

    post_path = Path(working_dir) / "post.md"
    if post_path.exists():
        size = post_path.stat().st_size
        print(f"\n  Output: {post_path.resolve()} ({size:,} bytes)")


def ensure_inputs(working_dir: str) -> None:
    """Check that required input files exist."""

    working_path = Path(working_dir)
    guideline = working_path / "guideline.md"
    research = working_path / "research.md"

    if not guideline.exists():
        print(f"ERROR: guideline.md not found in {working_dir}")
        sys.exit(1)
    if not research.exists():
        print(f"ERROR: research.md not found in {working_dir}")
        print("Run the research workflow first to generate research.md.")
        sys.exit(1)


@click.command()
@click.option(
    "--working-dir",
    "-d",
    default="test_writing",
    help="Working directory containing guideline.md and research.md (default: test_writing)",
)
@click.option(
    "--delete-iterations",
    is_flag=True,
    help="Delete intermediate post versions and reviews, keeping only the final post.md",
)
def main(working_dir: str, delete_iterations: bool) -> None:
    """Run the full LinkedIn post writing workflow as an MCP client test."""

    setup_logging()

    working_path = Path(working_dir).resolve()
    working_path.mkdir(parents=True, exist_ok=True)
    ensure_inputs(str(working_path))

    print("LinkedIn Writer MCP Server — Workflow Test")
    print(f"Working directory: {working_path}")

    server_path = str(Path(__file__).parent.parent / "src" / "writing" / "server.py")
    client = Client(server_path)

    async def _run() -> None:
        async with client:
            tools = await client.list_tools()
            print(f"\nConnected to server. Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}")
            print()

            await run_workflow(client, str(working_path), delete_iterations)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
