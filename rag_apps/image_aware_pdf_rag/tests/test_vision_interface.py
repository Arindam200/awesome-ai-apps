
import pytest

from interfaces.vision import (
    VisionModel,
    VisionResult,
    validate_vision_input,
)


VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-content"


class FakeVisionModel:
    """Mock vision provider for interface tests."""

    def describe_page(
        self,
        image_png: bytes,
        page_number: int,
    ) -> VisionResult:
        validate_vision_input(image_png, page_number)

        return VisionResult(
            page_number=page_number,
            description="The chart shows increasing quarterly revenue.",
        )


def test_fake_provider_implements_vision_contract():
    model = FakeVisionModel()

    assert isinstance(model, VisionModel)


def test_describe_page_returns_visual_description():
    model = FakeVisionModel()

    result = model.describe_page(VALID_PNG, 3)

    assert isinstance(result, VisionResult)
    assert result.page_number == 3
    assert "quarterly revenue" in result.description


def test_page_number_is_preserved():
    model = FakeVisionModel()

    result = model.describe_page(VALID_PNG, 7)

    assert result.page_number == 7


@pytest.mark.parametrize("page_number", [0, -1, True, 1.5])
def test_rejects_invalid_page_numbers(page_number):
    with pytest.raises(ValueError):
        validate_vision_input(VALID_PNG, page_number)


@pytest.mark.parametrize("image", [b"", None, "not bytes"])
def test_rejects_invalid_image_input(image):
    with pytest.raises(ValueError):
        validate_vision_input(image, 1)


def test_rejects_non_png_data():
    with pytest.raises(ValueError, match="PNG"):
        validate_vision_input(b"not a PNG", 1)


def test_rejects_empty_description():
    with pytest.raises(ValueError, match="description"):
        VisionResult(page_number=1, description="  ")


def test_rejects_zero_page_in_result():
    with pytest.raises(ValueError, match="one-based"):
        VisionResult(page_number=0, description="A chart.")


def test_rejects_boolean_page_in_result():
    with pytest.raises(ValueError, match="one-based"):
        VisionResult(page_number=True, description="A chart.")
