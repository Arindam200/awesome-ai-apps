from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
from markitdown import MarkItDown
from openai import OpenAI

from boeing_rag.config import Settings
from boeing_rag.table_quality import assess_table_quality
from boeing_rag.utils import (
    clean_text,
    infer_report_type,
    infer_report_year,
    infer_report_year_from_text,
    sha256_file,
    slugify,
)


@dataclass(frozen=True)
class PagePayload:
    page_number: int
    text: str
    image_path: str | None
    image_count: int
    extraction_method: str
    visual_text: str | None = None


@dataclass(frozen=True)
class TablePayload:
    ordinal: int
    markdown: str
    page_number: int | None
    rows: int
    cols: int
    quality_score: float
    quality_status: str
    quality_issues: list[str]
    csv_path: str | None
    html_path: str | None
    json_path: str | None


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    file_name: str
    file_path: str
    file_hash: str
    title: str | None
    report_year: int | None
    report_type: str
    page_count: int
    pages: list[PagePayload]
    tables: list[TablePayload]
    docling_markdown_path: str
    docling_json_path: str
    metadata: dict[str, Any]


class MarkItDownPdfParser:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._md: MarkItDown | None = None
        self._plain_md: MarkItDown | None = None

    def parse(
        self,
        pdf_path: Path,
        render_pages: bool = True,
        do_ocr: bool | None = None,
    ) -> ParsedDocument:
        pdf_path = pdf_path.resolve()
        file_hash = sha256_file(pdf_path)
        report_year = infer_report_year(pdf_path.name)
        report_type = infer_report_type(pdf_path.name)
        base_id = slugify(pdf_path.stem)[:56].strip("_") or "document"
        document_id = f"{base_id}_{file_hash[:8]}"
        artifact_dir = self.settings.parsed_dir / document_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        full_markdown = clean_text(self._convert_local(pdf_path, with_llm=False))
        pages = self._extract_pages(pdf_path, document_id, full_markdown, render_pages, bool(do_ocr))
        full_markdown = "\n\n".join(f"<!-- page:{page.page_number} -->\n\n{page.text}" for page in pages)
        markdown_path = artifact_dir / "markitdown.md"
        json_path = artifact_dir / "markitdown.json"
        markdown_path.write_text(full_markdown, encoding="utf-8")

        if report_year is None:
            report_year = infer_report_year_from_text("\n".join(page.text for page in pages[:3]))
        title = self._title_from_markdown(pdf_path, full_markdown)
        tables = self._extract_tables(pages, artifact_dir)

        json_path.write_text(
            json.dumps(
                {
                    "parser": "markitdown",
                    "file_name": pdf_path.name,
                    "page_count": len(pages),
                    "tables": [table.__dict__ for table in tables],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return ParsedDocument(
            document_id=document_id,
            file_name=pdf_path.name,
            file_path=str(pdf_path),
            file_hash=file_hash,
            title=title,
            report_year=report_year,
            report_type=report_type,
            page_count=len(pages),
            pages=pages,
            tables=tables,
            docling_markdown_path=str(markdown_path),
            docling_json_path=str(json_path),
            metadata={
                "parser": "markitdown",
                "markitdown_markdown_path": str(markdown_path),
                "markitdown_json_path": str(json_path),
                "source_size_bytes": pdf_path.stat().st_size,
                "markitdown_llm_model": self.settings.nebius_vision_model,
                "markitdown_ocr_requested": bool(do_ocr),
            },
        )

    def _markitdown(self, with_llm: bool = True) -> MarkItDown:
        if not with_llm:
            if self._plain_md is None:
                self._plain_md = MarkItDown(enable_plugins=True)
            return self._plain_md
        if self._md is None:
            kwargs: dict[str, Any] = {"enable_plugins": True}
            if self.settings.use_nebius_vision:
                kwargs["llm_client"] = OpenAI(
                    api_key=self.settings.nebius_api_key,
                    base_url=self.settings.nebius_base_url,
                )
                kwargs["llm_model"] = self.settings.nebius_vision_model
                kwargs["llm_prompt"] = (
                    "Extract all visible text, table-like data, labels, numbers, chart legends, "
                    "and meaningful visual descriptions. Preserve tables as Markdown when possible."
                )
            self._md = MarkItDown(**kwargs)
        return self._md

    def _extract_pages(
        self,
        pdf_path: Path,
        document_id: str,
        full_markdown: str,
        render_pages: bool,
        visual_ocr_requested: bool,
    ) -> list[PagePayload]:
        page_dir = self.settings.page_image_dir / document_id
        if render_pages:
            page_dir.mkdir(parents=True, exist_ok=True)

        pages: list[PagePayload] = []
        page_texts = self._split_markitdown_pages(full_markdown)
        visual_pages_used = 0
        with fitz.open(pdf_path) as pdf:
            for index, page in enumerate(pdf, start=1):
                text = page_texts.get(index, "")
                if not text:
                    text = f"## Page {index}"

                image_path = None
                if render_pages:
                    image_path = str(page_dir / f"page-{index:04d}.png")
                    if not Path(image_path).exists():
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
                        pix.save(image_path)

                visual_text = None
                if (
                    image_path
                    and self.settings.use_nebius_vision
                    and (visual_ocr_requested or self.settings.visual_parse)
                    and visual_pages_used < self.settings.visual_parse_max_pages
                    and self._needs_visual_pass(text, page)
                ):
                    visual_text = self._convert_local(Path(image_path), with_llm=True)
                    visual_pages_used += 1
                    visual_text = clean_text(visual_text)
                    if visual_text and visual_text not in text:
                        text = clean_text(f"{text}\n\nVisual/OCR extraction:\n{visual_text}")

                pages.append(
                    PagePayload(
                        page_number=index,
                        text=clean_text(text),
                        image_path=image_path,
                        image_count=len(page.get_images(full=True)),
                        extraction_method="markitdown",
                        visual_text=visual_text,
                    )
                )
        return pages

    def _split_markitdown_pages(self, markdown: str) -> dict[int, str]:
        matches = list(re.finditer(r"(?m)^## Page (\d+)\s*$", markdown))
        if not matches:
            return {1: markdown}
        pages: dict[int, str] = {}
        for offset, match in enumerate(matches):
            start = match.start()
            end = matches[offset + 1].start() if offset + 1 < len(matches) else len(markdown)
            page_number = int(match.group(1))
            pages[page_number] = clean_text(markdown[start:end])
        return pages

    def _convert_local(self, path: Path, with_llm: bool) -> str:
        try:
            result = self._markitdown(with_llm=with_llm).convert_local(str(path))
            return result.text_content or ""
        except Exception:
            if with_llm:
                try:
                    result = self._markitdown(with_llm=False).convert_local(str(path))
                    return result.text_content or ""
                except Exception:
                    return ""
            return ""

    def _normalize_page_heading(self, text: str, page_number: int) -> str:
        text = clean_text(text)
        text = re.sub(r"^## Page 1\b", f"## Page {page_number}", text)
        return text

    def _needs_visual_pass(self, text: str, page: fitz.Page) -> bool:
        visible_chars = len(re.sub(r"\s+", "", text or ""))
        return visible_chars < self.settings.min_page_text_chars_for_ocr or bool(page.get_images(full=True))

    def _extract_tables(self, pages: list[PagePayload], artifact_dir: Path) -> list[TablePayload]:
        tables: list[TablePayload] = []
        table_dir = artifact_dir / "tables"
        table_dir.mkdir(parents=True, exist_ok=True)
        for page in pages:
            for df in self._tables_from_markdown(page.text):
                df = _dedupe_columns(df)
                markdown = clean_text(df.to_markdown(index=False))
                if not markdown:
                    continue
                ordinal = len(tables) + 1
                csv_path = table_dir / f"table-{ordinal:04d}.csv"
                html_path = table_dir / f"table-{ordinal:04d}.html"
                json_path = table_dir / f"table-{ordinal:04d}.json"
                df.to_csv(csv_path, index=False)
                html_path.write_text(df.to_html(index=False), encoding="utf-8")
                json_path.write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
                quality = assess_table_quality(df, None)
                tables.append(
                    TablePayload(
                        ordinal=ordinal,
                        markdown=markdown,
                        page_number=page.page_number,
                        rows=quality.rows,
                        cols=quality.cols,
                        quality_score=quality.score,
                        quality_status=quality.status,
                        quality_issues=quality.issues,
                        csv_path=str(csv_path),
                        html_path=str(html_path),
                        json_path=str(json_path),
                    )
                )
        return tables

    def _tables_from_markdown(self, text: str) -> list[pd.DataFrame]:
        tables: list[pd.DataFrame] = []
        tables.extend(self._pipe_tables(text))
        tables.extend(self._financial_plaintext_tables(text))
        return tables

    def _pipe_tables(self, text: str) -> list[pd.DataFrame]:
        lines = [line.strip() for line in text.splitlines()]
        tables: list[pd.DataFrame] = []
        index = 0
        while index < len(lines):
            if "|" not in lines[index]:
                index += 1
                continue
            start = index
            while index < len(lines) and "|" in lines[index]:
                index += 1
            block = lines[start:index]
            parsed = _parse_pipe_table(block)
            if parsed is not None:
                tables.append(parsed)
        return tables

    def _financial_plaintext_tables(self, text: str) -> list[pd.DataFrame]:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        tables: list[pd.DataFrame] = []
        index = 0
        while index < len(lines):
            years = re.findall(r"\b(?:20|19)\d{2}\b", lines[index])
            if len(years) < 2:
                index += 1
                continue
            rows: list[list[str]] = []
            header = ["Metric", *years]
            index += 1
            misses = 0
            while index < len(lines) and misses < 3:
                row = _split_plain_table_row(lines[index], len(years))
                if row:
                    rows.append(row)
                    misses = 0
                elif rows and _looks_like_table_section(lines[index]):
                    rows.append([lines[index], *[""] * len(years)])
                    misses = 0
                else:
                    misses += 1
                index += 1
            data_rows = [row for row in rows if sum(1 for cell in row[1:] if cell) >= max(2, len(years) - 1)]
            numeric_density = len(data_rows) / max(len(rows), 1)
            if len(data_rows) >= 3 and numeric_density >= 0.55:
                tables.append(pd.DataFrame(rows, columns=header))
            continue
        return tables

    def _title_from_markdown(self, pdf_path: Path, markdown: str) -> str | None:
        with fitz.open(pdf_path) as pdf:
            title = (pdf.metadata or {}).get("title")
        if title:
            return clean_text(title)
        for line in markdown.splitlines():
            line = clean_text(line.strip("# "))
            if line and not line.startswith("Page "):
                return line[:300]
        return None


DoclingPdfParser = MarkItDownPdfParser


def _parse_pipe_table(lines: list[str]) -> pd.DataFrame | None:
    cleaned = [line.strip().strip("|") for line in lines if line.strip()]
    if len(cleaned) < 2:
        return None
    rows = [[cell.strip() for cell in line.split("|")] for line in cleaned]
    rows = [row for row in rows if not all(re.fullmatch(r":?-{2,}:?", cell or "") for cell in row)]
    if len(rows) < 2:
        return None
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header, body = rows[0], rows[1:]
    if not body:
        return None
    return pd.DataFrame(body, columns=header)


def _split_plain_table_row(line: str, expected_values: int) -> list[str] | None:
    value_pattern = r"(?:\(?\$?-?\d[\d,]*(?:\.\d+)?%?\)?|\$?\(?-?\d[\d,]*(?:\.\d+)?\)?|N/A|-)"
    matches = list(re.finditer(value_pattern, line))
    if len(matches) < expected_values:
        return None
    selected = matches[-expected_values:]
    label = clean_text(line[: selected[0].start()])
    values = [clean_text(match.group(0)) for match in selected]
    if not label or len(label) > 160:
        return None
    return [label, *values]


def _looks_like_table_section(line: str) -> bool:
    return bool(re.search(r":$", line)) and len(line) <= 120


def _dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict[str, int] = {}
    columns: list[str] = []
    for column in df.columns:
        name = str(column).strip() or "Column"
        count = seen.get(name, 0)
        seen[name] = count + 1
        columns.append(name if count == 0 else f"{name}_{count + 1}")
    df = df.copy()
    df.columns = columns
    return df
