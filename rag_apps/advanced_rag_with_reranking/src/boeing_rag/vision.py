from __future__ import annotations

import base64
from pathlib import Path

from openai import OpenAI
from PIL import Image

from boeing_rag.config import Settings
from boeing_rag.parser import PagePayload, ParsedDocument


class VisionParser:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: OpenAI | None = None
        if settings.use_nebius_vision:
            self.client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)

    def enabled(self) -> bool:
        return self.client is not None and self.settings.visual_parse

    def select_pages(self, parsed: ParsedDocument) -> list[PagePayload]:
        if not self.enabled():
            return []

        table_pages = {
            table.page_number
            for table in parsed.tables
            if table.page_number
            and table.quality_status in {"review", "fail"}
        }
        page_by_number = {page.page_number: page for page in parsed.pages if page.image_path}
        candidates: list[PagePayload] = [
            page_by_number[page_number]
            for page_number in sorted(table_pages)
            if page_number in page_by_number
        ]

        for page in parsed.pages:
            if not page.image_path:
                continue
            if page.page_number in table_pages:
                continue
            has_low_text = len(page.text.strip()) < self.settings.min_page_text_chars_for_ocr
            has_image = page.image_count > 0
            if has_low_text or (
                self.settings.visual_parse_include_all_image_pages and has_image
            ):
                candidates.append(page)
        return candidates[: self.settings.visual_parse_max_pages]

    def parse_page(self, parsed: ParsedDocument, page: PagePayload) -> str:
        if not self.client or not page.image_path:
            return ""
        image_url = self._image_data_url(Path(page.image_path))
        prompt = (
            "You are extracting visual evidence from a Boeing report page for a citation-grounded RAG system.\n"
            "Use only what is visible in the image. Be precise and avoid speculation.\n\n"
            "Return concise Markdown with these sections when present:\n"
            "- Visible page title or section\n"
            "- Figures, photos, diagrams, charts, or visual callouts\n"
            "- Tables or table-like structures, preserving rows/columns as Markdown if readable\n"
            "- Numbers, labels, legends, units, and footnotes visible in the image\n"
            "- Any extraction caveats such as unreadable text or ambiguous cells\n\n"
            f"Document: {parsed.file_name}\n"
            f"Page: {page.page_number}\n"
        )
        response = self.client.chat.completions.create(
            model=self.settings.nebius_vision_model or "",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            temperature=0.0,
            timeout=self.settings.visual_parse_timeout_seconds,
        )
        return (response.choices[0].message.content or "").strip()

    def _image_data_url(self, path: Path) -> str:
        image_path = self._compressed_jpeg(path)
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"

    def _compressed_jpeg(self, path: Path) -> Path:
        cache_path = path.with_suffix(".vlm.jpg")
        if cache_path.exists():
            return cache_path
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((1600, 2200))
            image.save(cache_path, "JPEG", quality=82, optimize=True)
        return cache_path
