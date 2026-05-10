"""Manual end-to-end test of the Deep Research MCP server workflow.

Connects to the research MCP server as a client and runs the full
deep research workflow against a sample topic.

Usage:
    uv run python scripts/test_research_workflow.py [--working-dir PATH] [--iterations N]
"""

import asyncio
import json
import logging
from pathlib import Path

import click
from fastmcp import Client

from writing.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Number of separator chars for visual output
SEP_WIDTH = 70

# Sample queries to research
SAMPLE_QUERIES = [
    "What are AI agent architectures and design patterns in 2025?",
    "How do autonomous AI agents use tools and skills to complete tasks?",
    "What is the Model Context Protocol (MCP) and how does it work?",
]


def print_step(step: str, description: str) -> None:
    """Print a formatted workflow step header."""

    print(f"\n{'=' * SEP_WIDTH}")
    print(f"  STEP {step}: {description}")
    print(f"{'=' * SEP_WIDTH}\n")


def print_result(result: object) -> None:
    """Print the tool result in a readable format."""

    data = getattr(result, "data", result)
    if isinstance(data, dict):
        message = data.get("message", "")
        status = data.get("status", "unknown")
        print(f"  Status: {status}")
        if message:
            print(f"  Message: {message}")
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
            print(f"  {json.dumps(parsed, indent=2)}")
        except (json.JSONDecodeError, TypeError):
            print(f"  {data}")
    else:
        print(f"  {data}")


async def run_workflow(
    client: Client, working_dir: str, iterations: int, youtube_url: str | None
) -> None:
    """Execute the full deep research workflow via MCP tool calls."""

    # ------------------------------------------------------------------
    # Step 1: Deep research queries
    # ------------------------------------------------------------------
    for i, query in enumerate(SAMPLE_QUERIES[:iterations], 1):
        print_step(f"1.{i}", f"Deep research: {query[:50]}...")

        result = await client.call_tool(
            "deep_research",
            {"working_dir": working_dir, "query": query},
        )
        print_result(result)

    # ------------------------------------------------------------------
    # Step 2: Analyze YouTube video (if provided)
    # ------------------------------------------------------------------
    if youtube_url:
        print_step("2", f"Analyze YouTube video: {youtube_url}")

        result = await client.call_tool(
            "analyze_youtube_video",
            {"working_dir": working_dir, "youtube_url": youtube_url},
        )
        print_result(result)
    else:
        print_step("2", "Analyze YouTube video (SKIPPED — none provided)")

    # ------------------------------------------------------------------
    # Step 3: Compile research
    # ------------------------------------------------------------------
    print_step("3", "Compile final research.md")

    result = await client.call_tool(
        "compile_research",
        {"working_dir": working_dir},
    )
    print_result(result)

    print(f"\n{'=' * SEP_WIDTH}")
    print("  WORKFLOW COMPLETE")
    print(f"{'=' * SEP_WIDTH}")

    output_path = Path(working_dir) / "research.md"
    if output_path.exists():
        size = output_path.stat().st_size
        print(f"\n  Output: {output_path.resolve()} ({size:,} bytes)")
    else:
        print(f"\n  WARNING: {output_path} was not created.")


@click.command()
@click.option(
    "--working-dir",
    "-d",
    default="test_research",
    help="Working directory for output (default: test_research)",
)
@click.option(
    "--iterations",
    "-n",
    default=2,
    type=int,
    help="Number of research queries to run (default: 2, max: 3)",
)
@click.option(
    "--youtube-url",
    "-y",
    default=None,
    help="Optional YouTube URL to analyze",
)
def main(working_dir: str, iterations: int, youtube_url: str | None) -> None:
    """Run the full deep research workflow as an MCP client test."""

    setup_logging()

    # Resolve working directory
    working_path = Path(working_dir).resolve()
    working_path.mkdir(parents=True, exist_ok=True)

    print("Deep Research MCP Server — Workflow Test")
    print(f"Working directory: {working_path}")
    print(f"Research queries: {iterations}")

    # Connect to the server via stdio (launches it as a subprocess)
    server_path = str(Path(__file__).parent.parent / "src" / "research" / "server.py")
    client = Client(server_path)

    async def _run() -> None:
        async with client:
            # Verify connection by listing tools
            tools = await client.list_tools()
            print(f"\nConnected to server. Available tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}")
            print()

            await run_workflow(client, str(working_path), iterations, youtube_url)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
