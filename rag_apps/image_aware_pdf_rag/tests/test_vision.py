
import logging
from dataclasses import dataclass

import pytest

from vision import describe_pdf_pages
from interfaces.vision import VisionImageTooLargeError, VisionResult


FAKE_PNG = b"\x89PNG\r\n\x1a\nfake-image-data"


@dataclass
class FakePage:
    page_number: int
    image_png: bytes | None


class FakeVisionModel:
    def __init__(self):
        self.called_pages = []

    def describe_page(self, image_png: bytes, page_number: int):
        self.called_pages.append(page_number)

        return VisionResult(
            page_number=page_number,
            description=f"Chart description for page {page_number}",
        )


def test_describes_pages_and_preserves_page_numbers():
    model = FakeVisionModel()

    pages = [
        FakePage(1, FAKE_PNG),
        FakePage(2, FAKE_PNG),
    ]

    batch = describe_pdf_pages(pages, model)

    assert model.called_pages == [1, 2]
    assert len(batch.descriptions) == 2
    assert batch.descriptions[0].page_number == 1
    assert batch.descriptions[1].page_number == 2
    assert batch.descriptions[0].content_type == "visual_description"
    assert batch.failures == {}


def test_skips_pages_without_rendered_images():
    model = FakeVisionModel()

    pages = [
        FakePage(1, None),
        FakePage(2, FAKE_PNG),
    ]

    batch = describe_pdf_pages(pages, model)

    assert model.called_pages == [2]
    assert len(batch.descriptions) == 1
    assert batch.descriptions[0].page_number == 2


def test_rejects_invalid_page_number():
    model = FakeVisionModel()

    with pytest.raises(ValueError, match="page_number"):
        describe_pdf_pages([FakePage(0, FAKE_PNG)], model)


def test_records_invalid_image_and_continues(caplog):
    model = FakeVisionModel()
    pages = [
        FakePage(1, b"invalid image"),
        FakePage(2, FAKE_PNG),
    ]

    with caplog.at_level(logging.ERROR):
        batch = describe_pdf_pages(pages, model)

    assert model.called_pages == [2]
    assert [description.page_number for description in batch.descriptions] == [2]
    assert 1 in batch.failures
    assert "PNG image data" in batch.failures[1]
    assert "Visual description failed for page 1" in caplog.text


def test_rejects_mismatched_page_number():
    class WrongPageVisionModel:
        def describe_page(self, image_png, page_number):
            return VisionResult(
                page_number=page_number + 1,
                description="Incorrect page",
            )

    with pytest.raises(ValueError, match="different page number"):
        describe_pdf_pages(
            [FakePage(1, FAKE_PNG)],
            WrongPageVisionModel(),
        )


def test_skips_oversized_page_and_continues(caplog):
    class OversizedPageVisionModel(FakeVisionModel):
        def describe_page(self, image_png, page_number):
            if page_number == 1:
                raise VisionImageTooLargeError("image exceeds provider limit")
            return super().describe_page(image_png, page_number)

    model = OversizedPageVisionModel()
    pages = [FakePage(1, FAKE_PNG), FakePage(2, FAKE_PNG)]

    with caplog.at_level(logging.ERROR):
        batch = describe_pdf_pages(pages, model)

    assert model.called_pages == [2]
    assert [result.page_number for result in batch.descriptions] == [2]
    assert 1 in batch.failures
    assert "image exceeds provider limit" in batch.failures[1]
    assert "Visual description failed for page 1" in caplog.text


def test_records_provider_failure_and_continues(caplog):
    class FailingPageVisionModel(FakeVisionModel):
        def describe_page(self, image_png, page_number):
            self.called_pages.append(page_number)
            if page_number == 1:
                raise RuntimeError("provider unavailable")
            return VisionResult(page_number, f"Description for page {page_number}")

    model = FailingPageVisionModel()
    pages = [FakePage(1, FAKE_PNG), FakePage(2, FAKE_PNG)]

    with caplog.at_level(logging.ERROR):
        batch = describe_pdf_pages(pages, model)

    assert model.called_pages == [1, 2]
    assert [result.page_number for result in batch.descriptions] == [2]
    assert batch.failures == {1: "provider unavailable"}
    assert "Visual description failed for page 1" in caplog.text
