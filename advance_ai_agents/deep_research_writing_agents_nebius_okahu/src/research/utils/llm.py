"""Nebius + LangChain helpers for research LLM interactions."""

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any

from exa_py import Exa
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from research.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_llm(model: str | None = None) -> ChatOpenAI:
    """Create and cache a LangChain chat model backed by Nebius."""

    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.llm_model,
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
        temperature=0,
    )


@lru_cache
def get_exa_client() -> Exa:
    """Create and cache the Exa search client."""

    settings = get_settings()
    return Exa(api_key=settings.exa_api_key.get_secret_value())


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def _extract_json(text: str) -> str:
    """Pull a JSON object out of model output that may include markdown fences."""

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


async def call_llm(
    prompt: str,
    model: str | None = None,
    response_schema: type[BaseModel] | None = None,
    system_instruction: str | None = None,
) -> str:
    """Call a Nebius-hosted model via LangChain.

    Structured output is requested with an explicit JSON-schema instruction so
    it works across OpenAI-compatible open-weight models.
    """

    llm = get_llm(model)
    messages: list[SystemMessage | HumanMessage] = []

    if system_instruction:
        messages.append(SystemMessage(content=system_instruction))

    user_prompt = prompt
    if response_schema is not None:
        schema = json.dumps(response_schema.model_json_schema(), indent=2)
        user_prompt = (
            f"{prompt}\n\n"
            "Return only valid JSON matching this JSON Schema. "
            "Do not wrap it in markdown fences.\n\n"
            f"{schema}"
        )

    messages.append(HumanMessage(content=user_prompt))
    response = await llm.ainvoke(messages)
    text = _message_text(response.content)

    if response_schema is not None:
        json_text = _extract_json(text)
        response_schema.model_validate_json(json_text)
        return json_text

    return text


async def call_exa_search(prompt: str) -> tuple[str, list[dict[str, str]]]:
    """Run Exa real-time research and return an answer plus source metadata."""

    def _answer() -> Any:
        return get_exa_client().answer(prompt, text=True)

    response = await asyncio.to_thread(_answer)
    answer_text = getattr(response, "answer", "") or ""
    citations = getattr(response, "citations", []) or []

    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for citation in citations:
        url = getattr(citation, "url", "") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(
            {
                "url": url,
                "title": getattr(citation, "title", "") or url,
                "snippet": (getattr(citation, "text", "") or "")[:500],
            }
        )

    return answer_text, sources


# Backward-compatible name used by existing handlers.
call_gemini = call_llm
