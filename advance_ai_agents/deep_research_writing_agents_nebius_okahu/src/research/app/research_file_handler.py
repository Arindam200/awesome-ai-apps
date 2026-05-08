"""Final research.md compilation logic."""

import logging
from pathlib import Path

from research.config.constants import (
    MEMORY_FOLDER,
    RESEARCH_RESULTS_FILE,
    TRANSCRIPTS_FOLDER,
)
from research.utils.file_utils import load_json, read_file
from research.utils.markdown_utils import (
    build_research_results_section,
    build_sources_section,
    combine_research_sections,
)

logger = logging.getLogger(__name__)


def compile_research_file(working_dir: str) -> str:
    """Compile all research data into a final markdown document.

    Reads all intermediate files from .memory/ and assembles them into a
    structured research.md with collapsible sections.

    Args:
        working_dir: Path to the working directory.

    Returns:
        The complete markdown document as a string.
    """

    # Step 1: Build path to the .memory/ folder where all intermediate data lives
    memory_path = Path(working_dir) / MEMORY_FOLDER

    # Step 2: Load the accumulated web search results from the JSON file.
    # Each entry is a dict with query, answer, and sources — populated by
    # deep_research_tool across multiple invocations.
    research_results = load_json(memory_path / RESEARCH_RESULTS_FILE, default=[])

    # Step 3: Load all YouTube transcript markdown files from .memory/transcripts/.
    # Each .md file was created by analyze_youtube_video_tool.
    # We collect them as (title, content) tuples where title = filename stem (video ID).
    transcripts_dir = memory_path / TRANSCRIPTS_FOLDER
    youtube_sources: list[tuple[str, str]] = []
    if transcripts_dir.exists():
        for md_file in sorted(transcripts_dir.glob("*.md")):
            content = read_file(md_file)
            if content:
                title = md_file.stem
                youtube_sources.append((title, content))

    # Step 4: Convert the raw data into formatted markdown sections.
    # build_research_results_section formats each search result with its
    # answer and source citations inside collapsible <details> blocks.
    research_results_section = build_research_results_section(research_results)

    # build_sources_section wraps each transcript in a collapsible <details> block
    # under a "YouTube Video Transcripts" heading.
    youtube_section = build_sources_section(
        "## YouTube Video Transcripts",
        youtube_sources,
        "No YouTube video transcripts found.",
    )

    # Step 5: Combine all sections into the final research.md document
    return combine_research_sections(
        research_results_section,
        youtube_section,
    )
