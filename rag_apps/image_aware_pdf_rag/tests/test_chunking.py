
from dataclasses import dataclass

import pytest

from chunking import chunk_pages


@dataclass
class FakePage:
    page_number: int
    text: str


def test_chunk_preserves_page_number():
    pages = [FakePage(3, "A " * 100)]

    result = chunk_pages(pages, chunk_size=50, overlap=10)

    assert result.chunks
    assert all(chunk.page_number == 3 for chunk in result.chunks)


def test_chunks_respect_size():
    pages = [FakePage(1, "word " * 500)]

    result = chunk_pages(pages, chunk_size=100, overlap=20)

    assert all(len(chunk.text) <= 100 for chunk in result.chunks)


def test_empty_page_is_reported():
    pages = [
        FakePage(1, "Some extracted text"),
        FakePage(2, ""),
    ]

    result = chunk_pages(pages)

    assert result.pages_without_text == [2]
    assert all(chunk.page_number != 2 for chunk in result.chunks)


def test_overlap_preserves_context():
    pages = [FakePage(1, "abcdefghij" * 10)]

    result = chunk_pages(pages, chunk_size=30, overlap=10)

    assert len(result.chunks) > 1

    first = result.chunks[0]
    second = result.chunks[1]

    assert second.start_char < first.end_char


def test_offsets_refer_to_original_page_text_and_chunks_start_at_word_boundaries():
    page = FakePage(1, "  aa bb cc dd ee ff  ")

    result = chunk_pages([page], chunk_size=12, overlap=4)

    first, second = result.chunks[:2]
    assert (first.start_char, first.end_char) == (2, 13)
    assert second.text.startswith("dd")
    assert second.start_char == 11


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError):
        chunk_pages([], chunk_size=100, overlap=100)
