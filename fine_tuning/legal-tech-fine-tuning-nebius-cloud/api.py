"""
FastAPI server for the fine-tuned Gemma legal LoRA model.

Proxies requests to a vLLM OpenAI-compatible backend and exposes
clean domain-specific endpoints for legal text analysis.

Start with:
    uvicorn api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8100/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "legal-lora")

LEGAL_SYSTEM_PROMPT = os.getenv(
    "LEGAL_SYSTEM_PROMPT",
    "You are a legal expert AI assistant specialised in UK legislation. "
    "Answer the user's question directly in clear prose or bullet points. "
    "Do not repeat, quote back, or paraphrase the question as your answer. "
    "Begin with substantive analysis. Cite sections or provisions when relevant.",
)

DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1024"))
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.3"))

# Optional extra user preamble. Leave empty for QA / RAG–style fine-tunes — a long prefix here
# is often echoed or causes repetition loops with vLLM.
USER_QUERY_PREFIX = os.getenv("USER_QUERY_PREFIX", "")

# Sampling: reduce degenerate repetition of the question (OpenAI-compatible params for vLLM).
FREQUENCY_PENALTY = float(os.getenv("FREQUENCY_PENALTY", "0.35"))
PRESENCE_PENALTY = float(os.getenv("PRESENCE_PENALTY", "0.15"))


def _strip_instruction_echo(text: str, prefix: str) -> str:
    if not prefix or not text:
        return text
    p = prefix.strip()
    t = text
    for _ in range(3):
        if t.startswith(p):
            t = t[len(p) :].lstrip()
        else:
            break
    return t


def _strip_leading_system_echo(text: str, system: str | None) -> str:
    """Gemma/vLLM sometimes prepends a verbatim copy of the system message before the answer."""
    if not text or not system:
        return text
    s = system.strip()
    if not s:
        return text
    t = text.lstrip()
    if t.startswith(s):
        rest = t[len(s) :]
        return rest.lstrip().lstrip("\n")
    return text


def _strip_repeated_question_paragraphs(text: str, query: str) -> str:
    """Drop paragraphs that are exactly the question (model stuck in a copy loop)."""
    q = query.strip()
    if not q:
        return text
    parts: list[str] = []
    for block in text.split("\n\n"):
        b = block.strip()
        if not b:
            continue
        if b == q:
            continue
        parts.append(block.strip())
    out = "\n\n".join(parts).strip()
    return out


def _strip_echoed_query(text: str, query: str) -> str:
    """Final guardrails after vLLM returns text."""
    if not text or not query:
        return text
    text = _strip_repeated_question_paragraphs(text, query)
    if not text.strip():
        return (
            "(Model only repeated the question. Try lower max_tokens, higher FREQUENCY_PENALTY, "
            "or temperature ~0.2.)"
        )
    if text.strip() == query.strip():
        return (
            "(Model returned no separate answer — it repeated the question. "
            "Try lowering temperature or adjusting sampling penalties.)"
        )
    if len(query) > 20 and text.startswith(query):
        rest = text[len(query) :].lstrip().lstrip("\n")
        return rest if rest else text
    return text

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

client: AsyncOpenAI | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global client
    client = AsyncOpenAI(
        base_url=VLLM_BASE_URL,
        api_key="unused",
    )
    yield
    await client.close()


app = FastAPI(
    title="Legal AI API",
    description="Fine-tuned Gemma model served via vLLM with LoRA adapters",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="Legal question or text to analyze")
    max_tokens: int = Field(DEFAULT_MAX_TOKENS, ge=1, le=4096)
    temperature: float = Field(DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    system_prompt: str | None = Field(
        None, description="Override the default legal system prompt"
    )
    stream: bool = Field(False, description="Stream the response via SSE")


class AnalyzeResponse(BaseModel):
    answer: str
    model: str
    usage: dict | None = None


class ChatMessage(BaseModel):
    role: str = Field(..., description="One of: system, user, assistant")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    max_tokens: int = Field(DEFAULT_MAX_TOKENS, ge=1, le=4096)
    temperature: float = Field(DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    stream: bool = Field(False, description="Stream the response via SSE")


class ChatResponse(BaseModel):
    message: ChatMessage
    model: str
    usage: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Check that the vLLM backend is reachable and healthy."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{VLLM_BASE_URL}/models")
            resp.raise_for_status()
        return {"status": "healthy", "vllm": "reachable", "model": MODEL_NAME}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"vLLM backend not reachable: {exc}",
        )


@app.post("/v1/legal/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """
    Analyze a legal query using the fine-tuned model.

    Wraps the query with a legal system prompt and returns a structured response.
    Supports optional SSE streaming when `stream=true`.
    """
    assert client is not None

    system = req.system_prompt or LEGAL_SYSTEM_PROMPT
    prefix = USER_QUERY_PREFIX
    user_body = f"{prefix}{req.query}" if prefix else req.query
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_body},
    ]

    if req.stream:
        return StreamingResponse(
            _stream_chat(messages, req.max_tokens, req.temperature),
            media_type="text/event-stream",
        )

    completion = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        frequency_penalty=FREQUENCY_PENALTY,
        presence_penalty=PRESENCE_PENALTY,
    )

    choice = completion.choices[0]
    raw = (choice.message.content or "").strip()
    raw = _strip_instruction_echo(raw, prefix)
    raw = _strip_leading_system_echo(raw, system)
    answer = _strip_echoed_query(raw, req.query.strip())
    return AnalyzeResponse(
        answer=answer,
        model=completion.model,
        usage=completion.usage.model_dump() if completion.usage else None,
    )


@app.post("/v1/legal/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Pass-through chat completions with the LoRA model pre-selected.

    Accepts an arbitrary message list (system/user/assistant turns).
    Supports optional SSE streaming when `stream=true`.
    """
    assert client is not None

    messages = [m.model_dump() for m in req.messages]

    if req.stream:
        return StreamingResponse(
            _stream_chat(messages, req.max_tokens, req.temperature),
            media_type="text/event-stream",
        )

    completion = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        frequency_penalty=FREQUENCY_PENALTY,
        presence_penalty=PRESENCE_PENALTY,
    )

    choice = completion.choices[0]
    content_raw = (choice.message.content or "").strip()
    sys_parts = [m.content for m in req.messages if m.role == "system"]
    sys_text = "\n\n".join(sys_parts) if sys_parts else None
    content_raw = _strip_leading_system_echo(content_raw, sys_text)
    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        "",
    )
    content = _strip_echoed_query(content_raw, last_user.strip()) if last_user else content_raw
    return ChatResponse(
        message=ChatMessage(
            role=choice.message.role,
            content=content,
        ),
        model=completion.model,
        usage=completion.usage.model_dump() if completion.usage else None,
    )


async def _stream_chat(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> AsyncIterator[str]:
    """Yield SSE-formatted chunks from the vLLM streaming response."""
    assert client is not None

    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        frequency_penalty=FREQUENCY_PENALTY,
        presence_penalty=PRESENCE_PENALTY,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            yield f"data: {token}\n\n"

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Run directly: python api.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8000")),
        log_level="info",
    )
