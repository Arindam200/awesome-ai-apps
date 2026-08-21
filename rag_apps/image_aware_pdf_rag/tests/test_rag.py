from __future__ import annotations

import pymupdf
import pytest

from create_sample_pdf import SAMPLE_VISUAL_DESCRIPTIONS, build_sample_pdf
from rag import ImageAwarePdfRag, PdfNotIndexedError, PdfValidationError


class RecordingVisionDescriber:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def describe(self, image_png: bytes, page_number: int) -> str:
        assert image_png.startswith(b"\x89PNG")
        self.pages.append(page_number)
        return f"Rendered visual evidence from page {page_number}."


def test_visual_question_ranks_chart_page_and_cites_it() -> None:
    rag = ImageAwarePdfRag()
    rag.index_pdf(build_sample_pdf(), SAMPLE_VISUAL_DESCRIPTIONS)

    answer = rag.ask("Which quarter had the highest activation rate?", top_k=2)

    assert [hit.page_number for hit in answer.hits] == [2]
    assert answer.citations == (2,)
    assert "Q4 is the highest bar" in answer.text
    assert "[p. 2]" in answer.text
    assert "[p. 3]" not in answer.text


def test_text_question_ranks_executive_summary() -> None:
    rag = ImageAwarePdfRag()
    rag.index_pdf(build_sample_pdf(), SAMPLE_VISUAL_DESCRIPTIONS)

    hits = rag.search("How much did annual recurring revenue grow?", top_k=1)

    assert len(hits) == 1
    assert hits[0].page_number == 1
    assert "revenue" in hits[0].matched_terms


def test_explicit_descriptions_do_not_call_remote_provider() -> None:
    describer = RecordingVisionDescriber()
    rag = ImageAwarePdfRag(vision_describer=describer)

    pages = rag.index_pdf(build_sample_pdf(), SAMPLE_VISUAL_DESCRIPTIONS)

    assert describer.pages == []
    assert pages[1].visual_description == SAMPLE_VISUAL_DESCRIPTIONS[2]


def test_visual_provider_receives_every_rendered_page() -> None:
    describer = RecordingVisionDescriber()
    rag = ImageAwarePdfRag(vision_describer=describer)

    pages = rag.index_pdf(build_sample_pdf())

    assert describer.pages == [1, 2, 3]
    assert all(page.visual_description for page in pages)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "empty"),
        (b"this is not a pdf", "not a readable PDF"),
    ],
)
def test_invalid_pdf_has_helpful_error(payload: bytes, message: str) -> None:
    rag = ImageAwarePdfRag()

    with pytest.raises(PdfValidationError, match=message):
        rag.index_pdf(payload)


def test_blank_pdf_requires_text_or_visual_description() -> None:
    document = pymupdf.open()
    document.new_page()
    payload = document.tobytes()
    document.close()

    with pytest.raises(PdfValidationError, match="no extractable text"):
        ImageAwarePdfRag().index_pdf(payload)


def test_search_requires_an_index_and_nonempty_question() -> None:
    rag = ImageAwarePdfRag()

    with pytest.raises(PdfNotIndexedError, match="Index a PDF"):
        rag.search("revenue")

    rag.index_pdf(build_sample_pdf(), SAMPLE_VISUAL_DESCRIPTIONS)
    with pytest.raises(ValueError, match="Question must not be empty"):
        rag.search("  ")


def test_unmatched_question_returns_no_evidence() -> None:
    rag = ImageAwarePdfRag()
    rag.index_pdf(build_sample_pdf(), SAMPLE_VISUAL_DESCRIPTIONS)

    answer = rag.ask("What is the orbital velocity of Neptune?")

    assert answer.hits == ()
    assert answer.citations == ()
    assert answer.text == "No relevant evidence was found in the indexed pages."
