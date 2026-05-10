"""YouTube transcript analysis using public captions plus Nebius."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

from research.config.prompts import PROMPT_YOUTUBE_TRANSCRIPTION
from research.config.settings import get_settings
from research.utils.llm import call_llm

logger = logging.getLogger(__name__)


async def analyze_youtube_video(
    url: str,
    output_path: Path,
    timestamp: int = 30,
) -> str:
    """Analyze a YouTube video from its available transcript/captions.

    This replaces Gemini native video understanding with a provider-neutral flow:
    fetch the public transcript, then ask the Nebius LLM to format and summarize it.
    """

    video_id = get_video_id(url)
    if not video_id:
        msg = f"Could not extract a YouTube video ID from {url}."
        output_path.write_text(msg, encoding="utf-8")
        return msg

    logger.info(f"Fetching YouTube transcript for: {url}")
    transcript_text = await asyncio.to_thread(_fetch_transcript_text, video_id)
    if not transcript_text:
        msg = f"Could not fetch transcript for {url}."
        output_path.write_text(msg, encoding="utf-8")
        return msg

    settings = get_settings()
    prompt = (
        PROMPT_YOUTUBE_TRANSCRIPTION.format(timestamp=timestamp)
        + "\n\nUse only the transcript below. If visual details are missing, say so "
        "instead of inventing them.\n\n"
        f"<transcript>\n{transcript_text}\n</transcript>"
    )

    transcript = await call_llm(prompt, model=settings.youtube_transcription_model)
    output_path.write_text(transcript, encoding="utf-8")
    logger.info(f"Transcript saved to {output_path}")

    return transcript


def _fetch_transcript_text(video_id: str) -> str:
    transcript = YouTubeTranscriptApi().fetch(video_id)
    lines: list[str] = []

    for snippet in transcript:
        start = float(getattr(snippet, "start", 0.0))
        minutes = int(start // 60)
        seconds = int(start % 60)
        text = getattr(snippet, "text", "")
        lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")

    return "\n".join(lines)


def get_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from various URL formats."""

    parsed_url = urlparse(url)
    if "youtube.com" in parsed_url.netloc:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    if "youtu.be" in parsed_url.netloc:
        return parsed_url.path.lstrip("/")

    return None
