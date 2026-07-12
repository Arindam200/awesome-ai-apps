"""Provider-agnostic structured LLM call.

Provider is chosen by settings.llm_provider:
  - "auto" (default): Anthropic if its key is set, else OpenAI.
  - "openai" | "anthropic" | "nebius": forced.
Nebius Token Factory is OpenAI-compatible (custom base_url) — set LLM_PROVIDER=nebius
+ NEBIUS_API_KEY to use it. All paths return a validated Pydantic instance.
"""

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# tier -> {provider: model}
TIER_MODELS = {
    "synthesis": {
        "anthropic": settings.synthesis_model,
        "openai": settings.openai_synthesis_model,
        "nebius": settings.nebius_synthesis_model,
    },
    "sentiment": {
        "anthropic": settings.sentiment_model,
        "openai": settings.openai_sentiment_model,
        "nebius": settings.nebius_sentiment_model,
    },
}


def _resolve_provider() -> str:
    p = (settings.llm_provider or "auto").lower()
    if p in ("openai", "anthropic", "nebius"):
        return p
    return "anthropic" if settings.anthropic_api_key else "openai"


def _openai_compatible_parse(
    *, api_key: str, base_url: str | None, model: str,
    system: str, user_content: str, output_model: type[T], max_tokens: int,
) -> T | None:
    """Shared path for OpenAI and any OpenAI-compatible endpoint (Nebius).
    Tries native structured outputs; falls back to JSON-object mode + manual
    validation for endpoints/models that don't support json_schema."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    try:
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            response_format=output_model,
            max_tokens=max_tokens,  # cap latency — without this the primary path ignores the budget
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        logger.warning("structured parse unsupported on %s (%s); using json_object fallback", model, e)
        schema = json.dumps(output_model.model_json_schema())
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content":
                    f"{system}\n\nRespond with ONLY a JSON object matching this JSON Schema "
                    f"(no prose, no markdown fences):\n{schema}"},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        raw = (completion.choices[0].message.content or "").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return output_model.model_validate_json(raw)


def parse_structured(
    *,
    tier: str,
    system: str,
    user_content: str,
    output_model: type[T],
    max_tokens: int = 16000,
) -> T | None:
    provider = _resolve_provider()
    models = TIER_MODELS[tier]

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        kwargs = {"thinking": {"type": "adaptive"}} if tier == "synthesis" else {}
        response = client.messages.parse(
            model=models["anthropic"],
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            output_format=output_model,
            **kwargs,
        )
        return response.parsed_output

    if provider == "nebius":
        if not settings.nebius_api_key:
            raise RuntimeError("LLM_PROVIDER=nebius but NEBIUS_API_KEY is not set")
        return _openai_compatible_parse(
            api_key=settings.nebius_api_key, base_url=settings.nebius_base_url,
            model=models["nebius"], system=system, user_content=user_content,
            output_model=output_model, max_tokens=max_tokens,
        )

    # default: OpenAI
    if not settings.openai_api_key:
        raise RuntimeError("No LLM key configured — set OPENAI_API_KEY (or LLM_PROVIDER + its key)")
    return _openai_compatible_parse(
        api_key=settings.openai_api_key, base_url=None,
        model=models["openai"], system=system, user_content=user_content,
        output_model=output_model, max_tokens=max_tokens,
    )
