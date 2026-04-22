"""Video ingestion: split into clips with ffmpeg, embed each clip natively with
Gemini `gemini-embedding-2-preview`, and upsert to Weaviate."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from embeddings import embed_video
from weaviate_store import ensure_schema, get_client, upsert_segments

DEFAULT_CLIP_SEC = 20.0


def probe_duration(video_path: str) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
    )
    return float(out.strip())


def split_clips(video_path: str, out_dir: str, clip_sec: float) -> list[tuple[float, float, str]]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    duration = probe_duration(video_path)
    clips: list[tuple[float, float, str]] = []
    i = 0
    start = 0.0
    while start < duration:
        end = min(start + clip_sec, duration)
        clip_path = os.path.join(out_dir, f"clip_{i:05d}.mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start}",
                "-i",
                video_path,
                "-t",
                f"{end - start}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-an",
                clip_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        clips.append((start, end, clip_path))
        start = end
        i += 1
    return clips


def ingest_video(
    video_path: str,
    clip_sec: float = DEFAULT_CLIP_SEC,
    video_id: str | None = None,
) -> dict:
    video_id = video_id or Path(video_path).stem + "_" + uuid.uuid4().hex[:6]
    clips_dir = os.path.join(os.path.dirname(video_path) or ".", f".clips_{video_id}")

    clips = split_clips(video_path, clips_dir, clip_sec)

    segments: list[dict] = []
    vectors: list[list[float]] = []
    for start, end, clip_path in clips:
        segments.append(
            {
                "video_id": video_id,
                "modality": "clip",
                "start_time": float(start),
                "end_time": float(end),
                "clip_path": clip_path,
            }
        )
        vectors.append(embed_video(clip_path))

    client = get_client()
    try:
        ensure_schema(client)
        inserted = upsert_segments(client, segments, vectors)
    finally:
        client.close()

    return {"video_id": video_id, "clips": len(clips), "inserted": inserted}
