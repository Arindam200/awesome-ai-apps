"""Nebius, LangChain, and Gemini helpers for writing interactions."""

import asyncio
import io
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from PIL import Image
from pydantic import BaseModel

from writing.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_llm(model: str | None = None) -> ChatOpenAI:
    """Create and cache a LangChain chat model backed by Nebius."""

    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.writer_model,
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
        temperature=0,
    )


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
    """Call a Nebius-hosted model via LangChain."""

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


async def call_gemini_image(
    prompt: str,
    output_path: Path,
    reference_images: list[Path] | None = None,
) -> Path:
    """Generate an image with Gemini and save it to disk."""

    settings = get_settings()

    def _generate() -> bytes:
        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        contents: list[types.Part] = []

        if reference_images:
            for img_path in reference_images:
                if img_path.exists():
                    suffix = img_path.suffix.lower()
                    mime = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                    }.get(suffix, "image/png")
                    contents.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime,
                                data=img_path.read_bytes(),
                            )
                        )
                    )

        contents.append(types.Part(text=prompt))
        response = client.models.generate_content(
            model=settings.image_model,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            msg = "Gemini image response did not include content parts."
            raise RuntimeError(msg)

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data

        msg = "Gemini image response did not include image data."
        raise RuntimeError(msg)

    image_bytes = await asyncio.to_thread(_generate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_image = Image.open(io.BytesIO(image_bytes))
    pil_image.save(str(output_path))
    logger.info(f"Image saved to {output_path}")

    return output_path


# Backward-compatible names used by existing handlers.
call_gemini = call_llm
