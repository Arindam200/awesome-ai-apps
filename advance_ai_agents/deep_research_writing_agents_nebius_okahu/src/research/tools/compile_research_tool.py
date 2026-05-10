"""Research compilation tool implementation."""

import logging
from pathlib import Path
from typing import Any

from research.app.exploration_budget import reset_exploration_budget
from research.app.research_file_handler import compile_research_file
from research.config.constants import MEMORY_FOLDER, RESEARCH_MD_FILE
from research.utils.file_utils import validate_directory, write_file

logger = logging.getLogger(__name__)


def compile_research_tool(working_dir: str) -> dict[str, Any]:
    """Aggregate all collected research into a single markdown research brief.

    Combines all research data (search results and YouTube transcripts)
    from .memory/ into a structured research.md file.

    Args:
        working_dir: Path to the working directory containing .memory/ data.

    Returns:
        Dict with status, generated file path, and summary.
    """

    # Step 1: Ensure the working directory exists and is valid
    validate_directory(working_dir)

    # Step 2: Read all intermediate research data from .memory/ and compile
    # it into a single structured markdown string. This merges web search
    # results (from deep_research_tool) and YouTube transcripts (from
    # analyze_youtube_video_tool) into one document.
    final_md = compile_research_file(working_dir)

    # Step 3: Write the compiled markdown to research.md in the working directory.
    # This is the final output file that the Writing Workflow consumes
    # to generate LinkedIn posts.
    output_path = Path(working_dir) / RESEARCH_MD_FILE
    write_file(output_path, final_md)

    logger.info(f"Generated research file: {output_path.resolve()}")

    # Step 4: Clear the exploration round budget so any follow-up research
    # session in this working directory starts with a fresh cap.
    reset_exploration_budget(Path(working_dir) / MEMORY_FOLDER)

    # Step 5: Return a success response with the path to the generated file
    return {
        "status": "success",
        "output_path": str(output_path.resolve()),
        "message": f"Generated {RESEARCH_MD_FILE} at {output_path.resolve()}",
    }
