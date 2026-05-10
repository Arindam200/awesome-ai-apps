"""Run the LinkedIn writing workflow on every post in the dataset.

For each post in the dataset index, this script:
1. Creates a working directory under {output_dir}/{slug}/
2. Copies the guideline and seed files
3. Optionally runs the research MCP server to produce research.md (--run-research)
4. Runs the writing MCP server to generate the post (and optionally an image)
5. Results stay in the output directory

Usage:
    uv run python scripts/run_dataset_writing.py [--output-dir DIR] [--skip-image] [--run-research] [--slug SLUG]
"""

import asyncio
import logging
import shutil
from pathlib import Path

import click
import yaml
from fastmcp import Client

from writing.utils.logging import setup_logging

logger = logging.getLogger(__name__)

DATASET_DIR = Path(__file__).parent.parent / "datasets" / "linkedin_paul_iusztin"
WRITING_SERVER_PATH = str(
    Path(__file__).parent.parent / "src" / "writing" / "server.py"
)
RESEARCH_SERVER_PATH = str(
    Path(__file__).parent.parent / "src" / "research" / "server.py"
)

# Default research queries when no seed context is available
DEFAULT_QUERIES = [
    "What are the key concepts and best practices for this topic?",
    "What are the latest developments and trends in this area?",
]


async def run_research_workflow(working_dir: str, n_queries: int = 2) -> dict[str, str]:
    """Run the deep research workflow for a single post."""

    client = Client(RESEARCH_SERVER_PATH)
    results = {}

    async with client:
        # Read seed file for context
        seed_path = Path(working_dir) / "seed.md"
        seed_text = seed_path.read_text(encoding="utf-8") if seed_path.exists() else ""

        # Generate queries from seed content or use defaults
        queries = DEFAULT_QUERIES[:n_queries]
        if seed_text:
            # Use seed content as the basis for queries
            queries = [f"Research: {seed_text[:200]}"]

        # Run deep research for each query
        for query in queries:
            result = await client.call_tool(
                "deep_research",
                {"working_dir": working_dir, "query": query},
            )
            data = getattr(result, "data", {})
            if isinstance(data, dict) and data.get("status") != "success":
                logger.warning(f"Research query failed: {query[:50]}...")

        # Compile research file
        result = await client.call_tool(
            "compile_research", {"working_dir": working_dir}
        )
        data = getattr(result, "data", {})
        results["status"] = (
            data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        )

    return results


async def run_writing_workflow(
    working_dir: str,
    skip_image: bool = False,
    delete_iterations: bool = False,
) -> dict[str, str]:
    """Run the writing workflow for a single post."""

    client = Client(WRITING_SERVER_PATH)
    results = {}

    async with client:
        result = await client.call_tool(
            "generate_post",
            {"working_dir": working_dir, "delete_iterations": delete_iterations},
        )
        data = getattr(result, "data", {})
        results["status"] = (
            data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        )
        results["post"] = data.get("post", "") if isinstance(data, dict) else ""

        if not skip_image:
            try:
                result = await client.call_tool(
                    "generate_image", {"working_dir": working_dir}
                )
                data = getattr(result, "data", {})
                results["image"] = (
                    data.get("image_path", "") if isinstance(data, dict) else ""
                )
            except Exception as e:
                logger.warning(f"Image generation failed: {e}")
                results["image"] = "failed"

    return results


async def process_entry(
    entry_slug: str,
    output_path: Path,
    run_research: bool,
    skip_image: bool,
    semaphore: asyncio.Semaphore,
    delete_iterations: bool = False,
) -> bool:
    """Process a single dataset entry. Returns True on success."""

    async with semaphore:
        work_dir = output_path / entry_slug

        # Skip if already processed
        if (work_dir / "post.md").exists():
            logger.info(f"[{entry_slug}] Skipping (already exists)")
            return True

        # Check required files
        guideline_src = DATASET_DIR / f"{entry_slug}_guideline.md"
        seed_src = DATASET_DIR / f"{entry_slug}_seed.md"
        if not guideline_src.exists() or not seed_src.exists():
            logger.warning(f"[{entry_slug}] Missing guideline or seed, skipping")
            return False

        # Prepare working directory
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guideline_src, work_dir / "guideline.md")
        shutil.copy2(seed_src, work_dir / "seed.md")

        try:
            # Run research agent if requested
            if run_research:
                logger.info(f"[{entry_slug}] Running research workflow...")
                research_results = await run_research_workflow(str(work_dir))
                if research_results.get("status") != "success":
                    logger.warning(
                        f"[{entry_slug}] Research failed: {research_results}"
                    )
                    return False
                logger.info(f"[{entry_slug}] Research complete")

            # Fall back: if no research.md exists, skip this entry
            if not (work_dir / "research.md").exists():
                logger.warning(
                    f"[{entry_slug}] No research.md found "
                    "(use --run-research to generate it), skipping"
                )
                return False

            results = await run_writing_workflow(
                str(work_dir),
                skip_image=skip_image,
                delete_iterations=delete_iterations,
            )

            if results.get("status") != "success":
                logger.warning(f"[{entry_slug}] Failed: {results.get('status')}")
                return False

            logger.info(
                f"[{entry_slug}] Done: {work_dir / 'post.md'} "
                f"({len(results.get('post', ''))} chars)"
            )
            return True

        except Exception as e:
            logger.error(f"[{entry_slug}] Error: {e}")
            return False


async def run_all(
    output_dir: str,
    skip_image: bool,
    run_research: bool,
    slug: str | None,
    max_concurrent: int = 5,
    delete_iterations: bool = False,
) -> None:
    """Run the writing workflow on all dataset entries in parallel."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load index
    index_path = DATASET_DIR / "index.yaml"
    entries = yaml.safe_load(index_path.read_text(encoding="utf-8"))

    if slug:
        entries = [e for e in entries if e["slug"] == slug]
        if not entries:
            logger.error(f"Slug not found: {slug}")
            return

    logger.info(
        f"Processing {len(entries)} posts → {output_path} "
        f"(run_research={run_research}, skip_image={skip_image}, "
        f"max_concurrent={max_concurrent})"
    )

    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = [
        process_entry(
            entry["slug"],
            output_path,
            run_research,
            skip_image,
            semaphore,
            delete_iterations=delete_iterations,
        )
        for entry in entries
    ]
    results = await asyncio.gather(*tasks)

    succeeded = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    logger.info(
        f"\nResults: {succeeded} succeeded, {failed} failed out of {len(entries)}"
    )


@click.command()
@click.option(
    "--output-dir",
    "-o",
    default="test_all",
    help="Output directory for generated posts (default: test_all)",
)
@click.option("--skip-image", is_flag=True, help="Skip image generation")
@click.option(
    "--run-research",
    is_flag=True,
    help="Run the research agent to produce research.md",
)
@click.option("--slug", default=None, help="Process only this slug (default: all)")
@click.option(
    "--max-concurrent",
    default=5,
    help="Maximum number of posts to process in parallel (default: 5)",
)
@click.option(
    "--delete-iterations",
    is_flag=True,
    help="Delete intermediate post versions and reviews, keeping only the final post.md",
)
def main(
    output_dir: str,
    skip_image: bool,
    run_research: bool,
    slug: str | None,
    max_concurrent: int,
    delete_iterations: bool,
) -> None:
    """Run the writing workflow on the dataset."""

    setup_logging()

    asyncio.run(
        run_all(
            output_dir,
            skip_image,
            run_research,
            slug,
            max_concurrent,
            delete_iterations,
        )
    )


if __name__ == "__main__":
    main()
