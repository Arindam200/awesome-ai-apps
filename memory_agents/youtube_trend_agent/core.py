"""
Core logic for the YouTube Trend Analysis Agent.

This module contains:
- Memori initialization helpers (using an OpenAI-compatible client, e.g. MiniMax).
- YouTube scraping utilities.
- Exa-based trend fetching.
- Channel ingestion into Memori.

It is imported by `app.py`, which focuses on the Streamlit UI.
"""

import json
import os

import streamlit as st
import yt_dlp
from dotenv import load_dotenv
from exa_py import Exa
from memori import Memori
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()


class _SilentLogger:
    """Minimal logger for yt-dlp that suppresses debug/warning output."""

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def init_memori_with_nebius() -> Memori | None:
    """
    Initialize Memori v3 + Nebius client (via the OpenAI SDK).

    This is used so Memori can automatically persist "memories" when we send
    documents through the registered OpenAI-compatible client.

    NOTE:
    - To use MiniMax, set:
        OPENAI_BASE_URL = "https://api.minimax.io/v1"
        OPENAI_API_KEY  = "<your-minimax-api-key>"
    """
    # MiniMax (or other OpenAI-compatible) configuration via standard OpenAI env vars
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.minimax.io/v1")
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        st.warning(
            "OPENAI_API_KEY is not set – Memori v3 ingestion will not be active."
        )
        return None

    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./memori.sqlite")
        database_url = f"sqlite:///{db_path}"
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

        # Optional DB connectivity check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        # Use the OpenAI-compatible registration API; the client itself points to MiniMax (or any compatible provider).
        mem = Memori(conn=SessionLocal).openai.register(client)
        # Attribution so Memori can attach memories to this process/entity.
        mem.attribution(entity_id="youtube-channel", process_id="youtube-trend-agent")
        mem.config.storage.build()

        st.session_state.memori = mem
        st.session_state.nebius_client = client
        return mem
    except Exception as e:
        st.warning(f"Memori v3 initialization note: {e}")
        return None


def fetch_channel_videos(channel_url: str) -> list[dict]:
    """
    Use yt-dlp to fetch recent YouTube videos for a given channel or playlist URL.

    Returns:
        A list of dicts:
        [
          {
            "title": "...",
            "url": "...",
            "published_at": "...",
            "views": "...",
            "topics": ["...", ...]
          },
          ...
        ]
    """
    ydl_opts = {
        # Don't download video files, we only want metadata
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Limit to most recent 20 videos
        "playlistend": 20,
        # Be forgiving if some videos fail
        "ignoreerrors": True,
        # Silence yt-dlp's own logging
        "logger": _SilentLogger(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    except Exception as e:
        st.error(f"Error fetching YouTube channel info: {e}")
        return []

    entries = info.get("entries") or []
    # Cache channel title for use in prompts
    if isinstance(info, dict):
        st.session_state["channel_title"] = info.get("title") or ""

    videos: list[dict] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = entry.get("id")
        url = entry.get("url")
        # Build full watch URL when possible
        full_url = url
        if video_id and (not url or "watch?" not in url):
            full_url = f"https://www.youtube.com/watch?v={video_id}"

        upload_date = entry.get("upload_date") or entry.get("release_date") or ""
        # Convert YYYYMMDD -> YYYY-MM-DD if present
        if (
            isinstance(upload_date, str)
            and len(upload_date) == 8
            and upload_date.isdigit()
        ):
            upload_date = f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

        description = entry.get("description") or ""
        duration = entry.get("duration")  # in seconds, if available

        videos.append(
            {
                "title": entry.get("title") or "Untitled video",
                "url": full_url or channel_url,
                "published_at": upload_date or "Unknown",
                "views": entry.get("view_count") or "Unknown",
                "topics": entry.get("tags") or [],
                "description": description,
                "duration_seconds": duration,
            }
        )

    return videos


def fetch_exa_trends(channel_name: str, videos: list[dict]) -> str:
    """
    Use Exa AI to fetch external web trends for the channel's niche.

    Returns:
        A formatted string of bullet points describing trending topics/articles.
    """
    api_key = os.getenv("EXA_API_KEY", "")
    if not api_key:
        return ""

    # Build a niche description from tags and titles
    tags: set[str] = set()
    for v in videos:
        for t in v.get("topics") or []:
            if isinstance(t, str):
                tags.add(t)

    base_niche = ", ".join(list(tags)[:10])
    if not base_niche:
        titles = [v.get("title") or "" for v in videos[:5]]
        base_niche = ", ".join(titles)

    if not base_niche:
        return ""

    query = (
        f"Current trending topics and YouTube-style video ideas for the niche: {base_niche}. "
        f"Focus on developer, programming, AI, and technology content if relevant."
    )

    try:
        client = Exa(api_key=api_key)
        # Keep the API call simple to avoid deprecated options like 'highlights'
        res = client.search_and_contents(
            query=query,
            num_results=5,
            type="auto",
        )
    except Exception as e:
        st.warning(f"Exa web search issue: {e}")
        return ""

    results = getattr(res, "results", []) or []
    if not results:
        return ""

    trend_lines: list[str] = []
    for doc in results[:5]:
        title = getattr(doc, "title", "") or "Untitled"
        url = getattr(doc, "url", "") or ""
        text = getattr(doc, "text", "") or ""
        snippet = " ".join(text.split())[:220]
        line = f"- {title} ({url}) — {snippet}"
        trend_lines.append(line)

    return "\n".join(trend_lines)


def ingest_channel_into_memori(channel_url: str) -> int:
    """
    Scrape a YouTube channel and ingest the results into Memori.

    Returns:
        Number of video documents ingested.
    """
    # Ensure Memori + Nebius client are initialized
    memori: Memori | None = st.session_state.get("memori")
    client: OpenAI | None = st.session_state.get("nebius_client")
    if memori is None or client is None:
        memori = init_memori_with_nebius()
        client = st.session_state.get("nebius_client")

    if memori is None or client is None:
        st.error("Memori/Nebius failed to initialize; cannot ingest channel.")
        return 0

    videos = fetch_channel_videos(channel_url)
    if not videos:
        st.warning("No videos were parsed from the YouTube channel response.")
        raw = st.session_state.get("yt_raw_response")
        if raw:
            st.caption("Raw YouTube agent output (truncated, for debugging):")
            st.code(str(raw)[:4000])
        return 0
    else:
        # Debug info to help understand what was parsed
        st.info(f"Parsed {len(videos)} video item(s) from the channel response.")
        st.caption("First parsed item (truncated):")
        try:
            st.code(json.dumps(videos[0], indent=2)[:2000])
        except Exception:
            # Fallback if item isn't JSON-serializable
            st.code(str(videos[0])[:2000])

    # Cache videos in session state so the chat agent can use them directly
    st.session_state["channel_videos"] = videos

    ingested = 0
    for video in videos:
        title = video.get("title") or "Untitled video"
        url = video.get("url") or channel_url
        published_at = video.get("published_at") or "Unknown"
        views = video.get("views") or "Unknown"
        topics = video.get("topics") or []
        description = video.get("description") or ""
        duration = video.get("duration_seconds") or "Unknown"

        topics_str = ", ".join(str(t) for t in topics) if topics else "N/A"
        # Truncate very long descriptions for ingestion
        desc_snippet = description[:1000]

        doc_text = f"""YouTube Video
Channel URL: {channel_url}
Title: {title}
Video URL: {url}
Published at: {published_at}
Views: {views}
Duration (seconds): {duration}
Topics: {topics_str}
Description:
{desc_snippet}
"""

        try:
            # Send this document through the registered Nebius client so that
            # Memori v3 can automatically capture it as a "memory".
            _ = client.chat.completions.create(
                model=os.getenv(
                    "YOUTUBE_TREND_INGEST_MODEL",
                    "MiniMax-M2.1",
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Store the following YouTube video metadata in memory "
                            "for future channel-trend analysis. Respond with a short "
                            "acknowledgement only.\n\n"
                            f"{doc_text}"
                        ),
                    }
                ],
            )
            ingested += 1
        except Exception as e:
            st.warning(f"Memori/Nebius issue ingesting video '{title}': {e}")

    # Flush writes if needed
    try:
        adapter = getattr(memori.config.storage, "adapter", None)
        if adapter is not None:
            adapter.commit()
    except Exception:
        # Non-fatal; Memori will still persist most data
        pass

    return ingested
