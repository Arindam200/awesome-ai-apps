from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import OpenAI

from boeing_rag.chunking import ChunkPayload
from boeing_rag.config import Settings
from boeing_rag.parser import ParsedDocument
from boeing_rag.utils import clean_text, stable_id

log = logging.getLogger(__name__)


class Contextualizer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: OpenAI | None = None
        if settings.use_nebius_chat:
            self.client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)

    def contextualize(self, parsed: ParsedDocument, chunks: list[ChunkPayload]) -> list[ChunkPayload]:
        if not self.settings.contextual_retrieval:
            return chunks

        document_context = self._document_context(parsed)
        contextualized: list[ChunkPayload] = []
        for chunk in chunks:
            context = self._cached_or_generate(parsed, chunk, document_context)
            text = clean_text(f"{context}\n\n{chunk.raw_text}") if context else chunk.raw_text
            metadata = {
                **chunk.metadata,
                "contextual_context": context,
                "contextualization_model": self.settings.nebius_chat_model,
                "contextualization_prompt_version": self.settings.contextual_prompt_version,
            }
            contextualized.append(
                ChunkPayload(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    ordinal=chunk.ordinal,
                    text=chunk.raw_text,
                    raw_text=chunk.raw_text,
                    contextual_text=text,
                    content_type=chunk.content_type,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_path=chunk.section_path,
                    citation_label=chunk.citation_label,
                    extraction_method=chunk.extraction_method,
                    token_estimate=chunk.token_estimate,
                    metadata=metadata,
                )
            )
        return contextualized

    def _cached_or_generate(
        self,
        parsed: ParsedDocument,
        chunk: ChunkPayload,
        document_context: str,
    ) -> str:
        cache_path = self._cache_path(parsed, chunk)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                return clean_text(data.get("context") or "")
            except Exception:
                pass

        context = self._generate_context(parsed, chunk, document_context)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "document_id": parsed.document_id,
                    "chunk_id": chunk.id,
                    "prompt_version": self.settings.contextual_prompt_version,
                    "model": self.settings.nebius_chat_model,
                    "context": context,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return context

    def _generate_context(self, parsed: ParsedDocument, chunk: ChunkPayload, document_context: str) -> str:
        fallback = self._fallback_context(parsed, chunk)
        if not self.client:
            return fallback

        prompt = f"""<document>
{document_context}
</document>

<chunk>
{chunk.raw_text[: self.settings.contextual_chunk_chars]}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.settings.nebius_chat_model or "",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You create concise retrieval context for Boeing disclosure chunks. "
                            "Mention document, year, report type, page, section, and table topic when clear."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=self.settings.contextual_max_tokens,
                timeout=60,
            )
            context = clean_text(response.choices[0].message.content or "")
            return context or fallback
        except Exception:
            log.exception("Contextualization failed for %s", chunk.id)
            return fallback

    def _fallback_context(self, parsed: ParsedDocument, chunk: ChunkPayload) -> str:
        year = parsed.report_year or "unknown year"
        section = " > ".join(chunk.section_path or []) or "unlabeled section"
        pages = (
            f"page {chunk.page_start}"
            if chunk.page_start == chunk.page_end or chunk.page_end is None
            else f"pages {chunk.page_start}-{chunk.page_end}"
        )
        return clean_text(
            f"This chunk is from {parsed.file_name}, a {year} Boeing {parsed.report_type}, "
            f"{pages}, content type {chunk.content_type}, section {section}."
        )

    def _document_context(self, parsed: ParsedDocument) -> str:
        headings: list[str] = []
        for page in parsed.pages:
            for line in page.text.splitlines()[:12]:
                line = clean_text(line.strip("# "))
                if 4 <= len(line) <= 120 and line not in headings:
                    headings.append(f"p. {page.page_number}: {line}")
                    break
        outline = "\n".join(headings[:80])
        text = "\n\n".join(page.text for page in parsed.pages)
        return clean_text(
            f"Document: {parsed.file_name}\n"
            f"Report year: {parsed.report_year}\n"
            f"Report type: {parsed.report_type}\n"
            f"Title: {parsed.title or ''}\n\n"
            f"Document outline:\n{outline}\n\n"
            f"Document excerpt:\n{text[: self.settings.contextual_context_chars]}"
        )

    def _cache_path(self, parsed: ParsedDocument, chunk: ChunkPayload) -> Path:
        key = stable_id(
            f"{parsed.file_hash}:{chunk.id}:{stable_id(chunk.raw_text)}:"
            f"{self.settings.contextual_prompt_version}",
            32,
        )
        return self.settings.context_cache_dir / parsed.document_id / f"{key}.json"
