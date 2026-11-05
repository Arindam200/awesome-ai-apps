"""Thin Kimi client on Nebius Token Factory.

Kimi K3.1 Pro is preferred. If the API key doesn't have access to it yet, the
app falls back to Kimi K3 (same family, vision + 1M context) and says so in the
UI instead of failing.
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from typing import Callable

from openai import AuthenticationError, BadRequestError, NotFoundError, OpenAI, PermissionDeniedError
from PIL import Image

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

PREFERRED_MODEL = os.getenv("KIMI_MODEL", "moonshotai/Kimi-K3.1-Pro")
FALLBACK_MODELS = ["moonshotai/Kimi-K3", "moonshotai/Kimi-K2.6"]

MODEL_LABELS = {
    "moonshotai/Kimi-K3.1-Pro": "Kimi K3.1 Pro",
    "moonshotai/Kimi-K3": "Kimi K3",
    "moonshotai/Kimi-K2.6": "Kimi K2.6",
}


def get_client() -> OpenAI:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
    # A float timeout applies per network read. Streams send tokens continuously,
    # so 3 minutes without a byte means the connection has stalled.
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key, timeout=180.0, max_retries=2)


def available_kimi_models(client: OpenAI) -> list[str]:
    """Kimi models this key can call, preferred model first."""
    try:
        ids = {m.id for m in client.models.list().data}
    except Exception:
        # Listing failed (network, permissions); let the call itself decide.
        return [PREFERRED_MODEL, *FALLBACK_MODELS]
    ordered = [PREFERRED_MODEL, *FALLBACK_MODELS]
    found = [m for m in ordered if m in ids]
    found += sorted(i for i in ids if "kimi" in i.lower() and i not in found)
    return found or ordered


def label(model_id: str) -> str:
    return MODEL_LABELS.get(model_id, model_id.split("/")[-1])


def image_part(img: Image.Image | bytes, max_side: int = 1600) -> dict:
    """Encode an image as an OpenAI-style base64 content part."""
    if isinstance(img, (bytes, bytearray)):
        img = Image.open(io.BytesIO(img))
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}


@dataclass
class ChatResult:
    content: str = ""
    reasoning: str = ""
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)


def stream_chat(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    reasoning_effort: str = "high",
    max_tokens: int = 32000,
    on_delta: Callable[[str, str], None] | None = None,
) -> ChatResult:
    """Stream a chat completion, reporting reasoning and answer deltas as they arrive.

    on_delta(kind, text) is called with kind "reasoning" or "content".
    If the stream drops mid-way, the answer is resumed: whatever arrived is kept
    and Kimi is asked to continue exactly from there (up to 2 resumes).
    """
    out = ChatResult()
    msgs = messages
    for attempt in range(3):
        try:
            _stream_once(client, model, msgs, reasoning_effort, max_tokens, on_delta, out)
            return out
        except (AuthenticationError, BadRequestError, NotFoundError, PermissionDeniedError):
            raise  # retrying won't help
        except Exception:
            if attempt == 2:
                raise
            if out.content:
                msgs = messages + [
                    {"role": "assistant", "content": out.content},
                    {"role": "user", "content": "Your previous answer was cut off by a network error. "
                     "Continue exactly where it stopped. Don't repeat anything and don't add a preamble."},
                ]
    raise AssertionError("unreachable")


def _stream_once(client, model, messages, reasoning_effort, max_tokens, on_delta, out: ChatResult) -> None:
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"reasoning_effort": reasoning_effort},
    )
    base = dict(out.usage)  # usage from earlier attempts, if this call is a resume
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage.model_dump()
            # Usage can repeat on several chunks: add earlier attempts once, never per chunk.
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage[k] = (base.get(k) or 0) + (usage.get(k) or 0)
            out.usage = usage
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        r = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if r:
            out.reasoning += r
            if on_delta:
                on_delta("reasoning", r)
        if delta.content:
            out.content += delta.content
            if on_delta:
                on_delta("content", delta.content)
        if choice.finish_reason:
            out.finish_reason = choice.finish_reason
