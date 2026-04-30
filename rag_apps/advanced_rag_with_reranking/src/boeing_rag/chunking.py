from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from boeing_rag.config import Settings
from boeing_rag.parser import ParsedDocument
from boeing_rag.utils import clean_text, estimate_tokens, split_text, stable_id


@dataclass(frozen=True)
class ChunkPayload:
    id: str
    document_id: str
    ordinal: int
    text: str
    raw_text: str
    contextual_text: str
    content_type: str
    page_start: int | None
    page_end: int | None
    section_path: list[str]
    citation_label: str
    extraction_method: str
    token_estimate: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, parsed: ParsedDocument) -> list[ChunkPayload]:
        chunks: list[ChunkPayload] = []
        ordinal = 0
        current_section: list[str] = []

        for page in parsed.pages:
            section_hint = self._section_hint(page.text)
            if section_hint:
                current_section = [section_hint]
            for part in split_text(
                page.text,
                target_chars=self.settings.chunk_target_chars,
                overlap_chars=self.settings.chunk_overlap_chars,
            ):
                ordinal += 1
                chunk_id = self._chunk_id(parsed.document_id, ordinal, part)
                citation = f"{parsed.file_name}, p. {page.page_number}"
                chunks.append(
                    ChunkPayload(
                        id=chunk_id,
                        document_id=parsed.document_id,
                        ordinal=ordinal,
                        text=part,
                        raw_text=part,
                        contextual_text=part,
                        content_type="text",
                        page_start=page.page_number,
                        page_end=page.page_number,
                        section_path=current_section,
                        citation_label=citation,
                        extraction_method=page.extraction_method,
                        token_estimate=estimate_tokens(part),
                        metadata={
                            "page_image_path": page.image_path,
                            "page_image_count": page.image_count,
                        },
                    )
                )

        for table in parsed.tables:
            ordinal += 1
            page = table.page_number
            page_label = f", p. {page}" if page else ""
            text = f"Table {table.ordinal}\n\n{table.markdown}"
            chunks.append(
                ChunkPayload(
                    id=self._chunk_id(parsed.document_id, ordinal, text),
                    document_id=parsed.document_id,
                    ordinal=ordinal,
                    text=text,
                    raw_text=text,
                    contextual_text=text,
                    content_type="table",
                    page_start=page,
                    page_end=page,
                    section_path=[],
                    citation_label=f"{parsed.file_name}{page_label}, table {table.ordinal}",
                    extraction_method="docling_table",
                    token_estimate=estimate_tokens(text),
                    metadata={
                        "table_ordinal": table.ordinal,
                        "table_rows": table.rows,
                        "table_cols": table.cols,
                        "table_quality_score": table.quality_score,
                        "table_quality_status": table.quality_status,
                        "table_quality_issues": table.quality_issues,
                        "table_csv_path": table.csv_path,
                        "table_html_path": table.html_path,
                        "table_json_path": table.json_path,
                    },
                )
            )

        for page in parsed.pages:
            visual_text = getattr(page, "visual_text", None)
            if not visual_text:
                continue
            ordinal += 1
            text = f"Visual extraction for page {page.page_number}\n\n{visual_text}"
            chunks.append(
                ChunkPayload(
                    id=self._chunk_id(parsed.document_id, ordinal, text),
                    document_id=parsed.document_id,
                    ordinal=ordinal,
                    text=text,
                    raw_text=text,
                    contextual_text=text,
                    content_type="image",
                    page_start=page.page_number,
                    page_end=page.page_number,
                    section_path=["Visual extraction"],
                    citation_label=f"{parsed.file_name}, p. {page.page_number}, visual extraction",
                    extraction_method=page.extraction_method,
                    token_estimate=estimate_tokens(text),
                    metadata={
                        "page_image_path": page.image_path,
                        "visual_model": parsed.metadata.get("markitdown_llm_model"),
                    },
                )
            )

        return chunks

    def _section_hint(self, text: str) -> str | None:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        for line in lines[:8]:
            if 4 <= len(line) <= 90 and self._looks_like_heading(line):
                return line
        return None

    def _looks_like_heading(self, line: str) -> bool:
        if re.search(r"\.{4,}", line):
            return False
        alpha = [char for char in line if char.isalpha()]
        if not alpha:
            return False
        uppercase_ratio = sum(1 for char in alpha if char.isupper()) / len(alpha)
        title_words = sum(1 for word in line.split() if word[:1].isupper())
        return uppercase_ratio > 0.55 or title_words >= max(2, len(line.split()) - 1)

    def _chunk_id(self, document_id: str, ordinal: int, text: str) -> str:
        return f"{document_id}:c{ordinal:05d}:{stable_id(text, 10)}"
