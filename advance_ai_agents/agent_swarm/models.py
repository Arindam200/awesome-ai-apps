"""Model roster, Nebius Token Factory clients and live pricing for the swarm.

One expensive model thinks (plans, reviews, writes the final answer). Cheap
models do the work. Prices come from the live Token Factory catalog, so the
cost ledger matches what your account is billed; the table below is only a
fallback for when the catalog can't be reached.
"""

from __future__ import annotations

import os
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from langchain_nebius import ChatNebius

load_dotenv()

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "moonshotai/Kimi-K3.1-Pro")
WORKER_MODEL = os.getenv("WORKER_MODEL", "thinkingmachines/Inkling-2-Small")
FAST_WORKER_MODEL = os.getenv("FAST_WORKER_MODEL", "nvidia/Nemotron-3_5-Lightning")

# Kimi reasons before it answers. At "medium" a review of four or five worker
# outputs takes 16-40s; left unbounded one took over 2 minutes and 9k tokens.
ORCHESTRATOR_REASONING = os.getenv("ORCHESTRATOR_REASONING", "medium")
# Workers do focused, tool-backed subtasks and Kimi reviews them, so they think
# briefly. At the default effort Inkling once spent its whole 8k budget reasoning
# on a revision and returned nothing.
WORKER_REASONING = os.getenv("WORKER_REASONING", "low")

# Used if the key can't call the preferred orchestrator.
ORCHESTRATOR_FALLBACKS = ["moonshotai/Kimi-K3"]

# Workers: Inkling 2 Small or anything cheaper that supports tool calling.
WORKER_OPTIONS = [
    "thinkingmachines/Inkling-2-Small",
    "MiniMaxAI/MiniMax-M3.1-Flash",
    "openai/gpt-oss-120b",
    "zai-org/GLM-5.3-Flash",
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "nvidia/Nemotron-3_5-Lightning",
]

LABELS = {
    "moonshotai/Kimi-K3.1-Pro": "Kimi K3.1 Pro",
    "moonshotai/Kimi-K3": "Kimi K3",
    "thinkingmachines/Inkling-2-Small": "Inkling 2 Small",
    "MiniMaxAI/MiniMax-M3.1-Flash": "MiniMax M3.1 Flash",
    "openai/gpt-oss-120b": "GPT-OSS 120B",
    "zai-org/GLM-5.3-Flash": "GLM-5.3 Flash",
    "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen3 30B A3B",
    "nvidia/Nemotron-3_5-Lightning": "Nemotron 3.5 Lightning",
}

# USD per 1M tokens (input, output), Token Factory list prices on 2026-11-16.
FALLBACK_PRICES = {
    "moonshotai/Kimi-K3.1-Pro": (2.00, 10.00),
    "moonshotai/Kimi-K3": (3.00, 15.00),
    "thinkingmachines/Inkling-2-Small": (0.30, 1.00),
    "MiniMaxAI/MiniMax-M3.1-Flash": (0.15, 0.60),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "zai-org/GLM-5.3-Flash": (0.15, 0.50),
    "Qwen/Qwen3-30B-A3B-Instruct-2507": (0.10, 0.30),
    "nvidia/Nemotron-3_5-Lightning": (0.06, 0.24),
}


def label(model_id: str) -> str:
    return LABELS.get(model_id, model_id.split("/")[-1])


def api_key() -> str:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
    return key


def chat(
    model: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 8000,
    reasoning_effort: str | None = None,
) -> ChatNebius:
    """A LangChain chat model on Nebius Token Factory."""
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    return ChatNebius(
        model=model,
        api_key=api_key(),
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=300,
        max_retries=2,
        stream_usage=True,
        **extra,
    )


@lru_cache(maxsize=1)
def catalog() -> dict[str, tuple[float, float]]:
    """Live model IDs and prices (USD per 1M tokens). Empty if the catalog is unreachable."""
    try:
        r = httpx.get(
            NEBIUS_BASE_URL + "models",
            params={"verbose": "true"},
            headers={"Authorization": f"Bearer {api_key()}"},
            timeout=20,
        )
        r.raise_for_status()
    except Exception:
        return {}
    prices = {}
    for m in r.json().get("data", []):
        p = m.get("pricing") or {}
        prices[m["id"]] = (float(p.get("prompt") or 0) * 1e6, float(p.get("completion") or 0) * 1e6)
    return prices


def price(model: str) -> tuple[float, float]:
    return catalog().get(model) or FALLBACK_PRICES.get(model, (0.0, 0.0))


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = price(model)
    return (input_tokens * p_in + output_tokens * p_out) / 1e6


def available(models: list[str]) -> list[str]:
    """Models from the list that this key can see. Returns the list unchanged if the catalog is down."""
    live = catalog()
    return [m for m in models if m in live] if live else list(models)


def resolve_orchestrator(preferred: str = ORCHESTRATOR_MODEL) -> str:
    """Preferred orchestrator if the key can call it, otherwise the first available fallback."""
    live = catalog()
    if not live or preferred in live:
        return preferred
    return next((m for m in ORCHESTRATOR_FALLBACKS if m in live), preferred)
