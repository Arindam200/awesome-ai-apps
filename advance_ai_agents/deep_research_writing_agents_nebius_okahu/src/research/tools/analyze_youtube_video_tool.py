"""YouTube video analysis tool implementation."""

import logging
from typing import Any

from research.app.exploration_budget import (
    BudgetExceededError,
    record_exploration_call,
)
from research.app.youtube_handler import analyze_youtube_video, get_video_id
from research.config.constants import (
    MAX_EXPLORATION_CALLS,
    MEMORY_FOLDER,
    TRANSCRIPTS_FOLDER,
)
from research.utils.file_utils import ensure_memory_dir, validate_directory

logger = logging.getLogger(__name__)


async def analyze_youtube_video_tool(
    working_dir: str, youtube_url: str
) -> dict[str, Any]:
    """Analyze a YouTube video using public captions plus Nebius.

    Takes a YouTube URL, fetches public captions, and returns a structured
    transcript with key insights.

    Args:
        working_dir: Path to the working directory.
        youtube_url: The YouTube video URL to analyze.

    Returns:
        Dict with status, transcript content, and output file path.
    """

    # Step 1: Validate working directory exists and create .memory/ if needed
    validate_directory(working_dir)
    memory_path = ensure_memory_dir(working_dir)

    # Step 2: Enforce the exploration call budget shared with deep_research.
    # If the cap is reached, refuse and instruct the agent to compile.
    try:
        call_index, calls_remaining = record_exploration_call(
            memory_path, tool="analyze_youtube_video", query=youtube_url
        )
    except BudgetExceededError as exc:
        return {
            "status": "budget_exceeded",
            "youtube_url": youtube_url,
            "used_calls": exc.used_calls,
            "max_calls": exc.max_calls,
            "message": str(exc),
        }

    # Step 3: Create the transcripts subfolder (.memory/transcripts/)
    dest_folder = memory_path / TRANSCRIPTS_FOLDER
    dest_folder.mkdir(parents=True, exist_ok=True)

    # Step 4: Extract the video ID from the URL to use as the filename.
    # Supports both youtube.com/watch?v=ID and youtu.be/ID formats.
    # Falls back to a sanitized URL string if parsing fails.
    video_id = get_video_id(youtube_url)
    if not video_id:
        sanitized = (
            youtube_url.replace("https://", "").replace("http://", "").replace("/", "_")
        )
        logger.warning(f"Could not extract video ID from URL: {youtube_url}")
        video_id = sanitized

    # Step 5: Build the output path (e.g. .memory/transcripts/dQw4w9WgXcQ.md)
    output_path = dest_folder / f"{video_id}.md"

    # Step 6: Fetch captions and summarize them with the Nebius LLM.
    logger.info(f"Analyzing YouTube video: {youtube_url}")
    transcript = await analyze_youtube_video(url=youtube_url, output_path=output_path)

    # Step 7: Return a response dict to the MCP caller with the transcript
    # content, metadata about where it was saved, and budget info so the
    # agent can self-pace within the cap.
    return {
        "status": "success",
        "youtube_url": youtube_url,
        "video_id": video_id,
        "transcript": transcript,
        "output_path": str(output_path.resolve()),
        "call": call_index,
        "max_calls": MAX_EXPLORATION_CALLS,
        "calls_remaining": calls_remaining,
        "message": (
            f"Analyzed video: {youtube_url}. "
            f"Transcript saved to {MEMORY_FOLDER}/{TRANSCRIPTS_FOLDER}/{video_id}.md. "
            f"Call {call_index}/{MAX_EXPLORATION_CALLS} "
            f"({calls_remaining} remaining before compile_research is required)."
        ),
    }
