from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from create_sample_pdf import (
    SAMPLE_VISUAL_DESCRIPTIONS,
    build_sample_pdf,
    load_visual_descriptions,
    write_sample_files,
)
from rag import (
    ImageAwarePdfRag,
    NebiusAnswerGenerator,
    NebiusVisionDescriber,
    PdfNotIndexedError,
    PdfValidationError,
)


class RecordingVisionDescriber:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def describe(self, image_png: bytes, page_number: int) -> str:
        assert image_png.startswith(b"\x89PNG")
        self.pages.append(page_number)
        return f"Rendered visual evidence from page {page_number}."


class FailingVisionDescriber:
    def describe(self, image_png: bytes, page_number: int) -> str:
        raise RuntimeError(f"provider unavailable for page {page_number}")


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


def test_visual_provider_failure_keeps_text_pages_indexable() -> None:
    rag = ImageAwarePdfRag(vision_describer=FailingVisionDescriber())

    pages = rag.index_pdf(build_sample_pdf())

    assert len(pages) == 3
    assert all(not page.visual_description for page in pages)
    assert rag.search("annual recurring revenue", top_k=1)[0].page_number == 1


def test_visual_description_sidecar_round_trip(tmp_path: Path) -> None:
    pdf_path, sidecar_path = write_sample_files(tmp_path)

    descriptions = load_visual_descriptions(sidecar_path)
    pages = ImageAwarePdfRag().index_pdf(pdf_path.read_bytes(), descriptions)

    assert set(descriptions) == {1, 2, 3}
    assert pages[1].visual_description == SAMPLE_VISUAL_DESCRIPTIONS[2]


def test_nebius_clients_use_configured_endpoint_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    calls: list[dict[str, object]] = []

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    NebiusVisionDescriber("secret", "vision-model", "https://nebius.example/v1", 17.0)
    NebiusAnswerGenerator("secret", "answer-model", "https://nebius.example/v1", 17.0)

    assert calls == [
        {
            "api_key": "secret",
            "base_url": "https://nebius.example/v1",
            "timeout": 17.0,
            "max_retries": 2,
        },
        {
            "api_key": "secret",
            "base_url": "https://nebius.example/v1",
            "timeout": 17.0,
            "max_retries": 2,
        },
    ]


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
