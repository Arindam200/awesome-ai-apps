
from dataclasses import dataclass

import pytest

from vision import describe_pdf_pages
from interfaces.vision import VisionResult


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

    results = describe_pdf_pages(pages, model)

    assert model.called_pages == [1, 2]
    assert len(results) == 2
    assert results[0].page_number == 1
    assert results[1].page_number == 2
    assert results[0].content_type == "visual_description"


def test_skips_pages_without_rendered_images():
    model = FakeVisionModel()

    pages = [
        FakePage(1, None),
        FakePage(2, FAKE_PNG),
    ]

    results = describe_pdf_pages(pages, model)

    assert model.called_pages == [2]
    assert len(results) == 1
    assert results[0].page_number == 2


def test_rejects_invalid_page_number():
    model = FakeVisionModel()

    with pytest.raises(ValueError, match="page_number"):
        describe_pdf_pages([FakePage(0, FAKE_PNG)], model)


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
