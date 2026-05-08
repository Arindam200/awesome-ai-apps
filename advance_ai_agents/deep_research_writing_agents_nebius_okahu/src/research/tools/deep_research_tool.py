"""Exa-backed research tool implementation."""

import logging
from typing import Any

from research.app.exploration_budget import (
    BudgetExceededError,
    record_exploration_call,
)
from research.app.research_handler import run_grounded_search
from research.config.constants import (
    MAX_EXPLORATION_CALLS,
    MEMORY_FOLDER,
    RESEARCH_RESULTS_FILE,
)
from research.utils.file_utils import (
    ensure_memory_dir,
    load_json,
    save_json,
    validate_directory,
)

logger = logging.getLogger(__name__)


async def deep_research_tool(working_dir: str, query: str) -> dict[str, Any]:
    """Run Exa research for a single research query.

    Executes the query using Exa search and appends
    the result to .memory/research_results.json.

    Args:
        working_dir: Path to the working directory.
        query: The research query to execute.

    Returns:
        Dict with status, research result, and output file path.
    """

    # Step 1: Ensure the working directory is valid and .memory/ exists
    validate_directory(working_dir)
    memory_path = ensure_memory_dir(working_dir)

    # Step 2: Enforce the exploration call budget. If the agent has already
    # used MAX_EXPLORATION_CALLS calls, refuse and instruct it to compile.
    # The recorded state lives in .memory/exploration_state.json.
    try:
        call_index, calls_remaining = record_exploration_call(
            memory_path, tool="deep_research", query=query
        )
    except BudgetExceededError as exc:
        return {
            "status": "budget_exceeded",
            "query": query,
            "used_calls": exc.used_calls,
            "max_calls": exc.max_calls,
            "message": str(exc),
        }

    # Step 3: Build the path to the cumulative results JSON file
    results_path = memory_path / RESEARCH_RESULTS_FILE

    # Step 4: Load any previously saved results so we can append to them.
    # If this is the first query, starts with an empty list.
    existing_results = load_json(results_path, default=[])

    # Step 5: Send the query to Exa.
    # This performs a live web search and returns a structured ResearchResult
    # containing the answer text and cited sources.
    logger.info(f"Executing research query: {query}")
    result = await run_grounded_search(query)

    # Step 6: Append the new result (as a dict) and persist back to disk.
    # This accumulates results across multiple tool invocations so that
    # compile_research_tool can later merge them all into research.md.
    existing_results.append(result.model_dump())
    save_json(results_path, existing_results)

    # Step 7: Return a response dict to the MCP caller with the answer,
    # sources, and metadata about where results were saved. Budget info is
    # included so the agent can self-pace within the cap.
    return {
        "status": "success",
        "query": query,
        "answer": result.answer,
        "sources": [src.model_dump() for src in result.sources],
        "total_sources": len(result.sources),
        "output_path": str(results_path.resolve()),
        "call": call_index,
        "max_calls": MAX_EXPLORATION_CALLS,
        "calls_remaining": calls_remaining,
        "message": (
            f"Researched: '{query}'. "
            f"Found {len(result.sources)} sources. "
            f"Results saved to {MEMORY_FOLDER}/{RESEARCH_RESULTS_FILE}. "
            f"Call {call_index}/{MAX_EXPLORATION_CALLS} "
            f"({calls_remaining} remaining before compile_research is required)."
        ),
    }
