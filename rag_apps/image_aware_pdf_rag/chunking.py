
"""Split extracted PDF text into chunks while preserving page citations."""

from dataclasses import dataclass


@dataclass
class TextChunk:
    page_number: int
    chunk_index: int
    text: str
    start_char: int
    end_char: int


@dataclass
class ChunkingResult:
    chunks: list[TextChunk]
    pages_without_text: list[int]


def chunk_pages(
    pages,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> ChunkingResult:
    """Chunk page-level extraction results without losing source pages.

    Empty-text pages are reported separately so scanned pages are not
    silently discarded.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks = []
    pages_without_text = []

    for page in pages:
        leading_offset = len(page.text) - len(page.text.lstrip())
        text = page.text.strip()
        page_number = page.page_number

        if not text:
            pages_without_text.append(page_number)
            continue

        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Avoid splitting words when a natural boundary is nearby.
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    TextChunk(
                        page_number=page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        start_char=leading_offset + start,
                        end_char=leading_offset + end,
                    )
                )
                chunk_index += 1

            if end >= len(text):
                break

            next_start = max(0, end - overlap)
            next_space = text.find(" ", next_start)
            if next_space != -1 and next_space < end:
                next_start = next_space + 1

            # Guarantee progress even when whitespace is unusual.
            start = next_start if next_start > start else end

    return ChunkingResult(
        chunks=chunks,
        pages_without_text=pages_without_text,
    )
