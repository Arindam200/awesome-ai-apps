"""Plain Video RAG: embed query → Weaviate search → Nebius chat with cited context."""

from __future__ import annotations

import os

from openai import OpenAI

from embeddings import embed_text
from weaviate_store import get_client, search

NEBIUS_BASE_URL = "https://api.studio.nebius.com/v1/"


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _nebius_client() -> OpenAI:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set")
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key)


def retrieve(query: str, video_id: str | None = None, top_k: int = 8) -> list[dict]:
    vec = embed_text(query)
    client = get_client()
    try:
        hits = search(client, query_vector=vec, top_k=top_k, video_id=video_id)
    finally:
        client.close()
    return [
        {
            "start": float(h.get("start_time", 0.0)),
            "end": float(h.get("end_time", 0.0)),
            "timestamp": _fmt_ts(h.get("start_time", 0.0)),
            "score": round(float(h.get("score", 0.0)), 4),
            "clip_path": h.get("clip_path", ""),
        }
        for h in hits
    ]


def answer(
    query: str,
    hits: list[dict],
    model_id: str = "Qwen/Qwen3-235B-A22B",
) -> str:
    context = "\n".join(
        f"- clip at [{h['timestamp']}] (start={h['start']:.1f}s, end={h['end']:.1f}s, score={h['score']})"
        for h in hits
    )
    system = (
        "You are a Video RAG assistant. You are given a list of video clips retrieved "
        "for the user's question. Answer ONLY from those clips. Cite every factual "
        "sentence with one or more timestamps in [mm:ss] format. If the clips are "
        "insufficient, say so explicitly. Do not invent facts."
    )
    user = f"Question: {query}\n\nRetrieved clips:\n{context}\n\nWrite a concise, cited answer."
    resp = _nebius_client().chat.completions.create(
        model=model_id,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
    )
    return (resp.choices[0].message.content or "").strip()


def ask(
    query: str,
    video_id: str | None = None,
    top_k: int = 8,
    model_id: str = "Qwen/Qwen3-235B-A22B",
) -> tuple[str, list[dict]]:
    hits = retrieve(query, video_id=video_id, top_k=top_k)
    return answer(query, hits, model_id=model_id), hits
