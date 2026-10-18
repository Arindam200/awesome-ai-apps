import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from interfaces.vision import VisionImageTooLargeError
from providers import groq_vision
from providers.groq_vision import GroqVisionModel


class FakeGroqClient:
    def __init__(self, content, finish_reason):
        self.last_request = None

        choice = SimpleNamespace(
            message=SimpleNamespace(content=content),
            finish_reason=finish_reason,
        )
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=self.create
            )
        )

        self.choice = choice

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(choices=[self.choice])


def make_png(width, height):
    image = Image.new("RGB", (width, height))
    image.putdata([
        (x * 17 % 256, y * 31 % 256, (x * y) % 256)
        for y in range(height)
        for x in range(width)
    ])
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_describe_page_returns_complete_description():
    model = GroqVisionModel(
        client=FakeGroqClient("A chart shows revenue growth.", "stop")
    )

    result = model.describe_page(b"\x89PNG\r\n\x1a\nimage", 1)

    assert result.description == "A chart shows revenue growth."


def test_describe_page_rejects_truncated_description():
    model = GroqVisionModel(
        client=FakeGroqClient("A chart shows revenue...", "length")
    )

    with pytest.raises(RuntimeError, match="incomplete"):
        model.describe_page(b"\x89PNG\r\n\x1a\nimage", 1)


def test_describe_page_compresses_image_to_fit_payload_limit(monkeypatch):
    monkeypatch.setattr(groq_vision, "MAX_BASE64_IMAGE_BYTES", 4096)
    client = FakeGroqClient("A chart.", "stop")
    model = GroqVisionModel(client=client)

    model.describe_page(make_png(128, 128), 1)

    image_url = client.last_request["messages"][0]["content"][1]["image_url"][
        "url"
    ]
    media_type, encoded_image = image_url.removeprefix("data:").split(
        ";base64,"
    )
    compressed_image = base64.b64decode(encoded_image)

    assert media_type == "image/jpeg"
    assert len(encoded_image) <= groq_vision.MAX_BASE64_IMAGE_BYTES
    assert compressed_image.startswith(b"\xff\xd8")


def test_describe_page_composites_transparency_onto_white(monkeypatch):
    monkeypatch.setattr(groq_vision, "MAX_BASE64_IMAGE_BYTES", 1024)
    image = Image.new("RGBA", (128, 128))
    image.putdata([
        (x * 17 % 256, y * 31 % 256, (x * y) % 256,
         255 if x == 0 and y == 0 else 0)
        for y in range(128)
        for x in range(128)
    ])
    output = BytesIO()
    image.save(output, format="PNG")
    assert len(output.getvalue()) > 768
    model = GroqVisionModel(
        client=FakeGroqClient("A chart.", "stop")
    )

    prepared_image, media_type = model._prepare_image(output.getvalue())

    with Image.open(BytesIO(prepared_image)) as result:
        result.load()
        assert media_type == "image/jpeg"
        assert result.getpixel((7, 7))[0] > 245
        assert result.getpixel((0, 0))[0] < 20


def test_describe_page_reports_image_that_cannot_fit(monkeypatch):
    monkeypatch.setattr(groq_vision, "MAX_BASE64_IMAGE_BYTES", 4)
    model = GroqVisionModel(client=FakeGroqClient("A chart.", "stop"))

    with pytest.raises(VisionImageTooLargeError, match="request limit"):
        model.describe_page(make_png(8, 8), 1)


def test_describe_page_retries_on_truncation_and_succeeds():
    class RetryClient:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="Truncated initial text"),
                            finish_reason="length",
                        )
                    ]
                )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Complete concise summary: Bar chart of revenue."),
                        finish_reason="stop",
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=RetryClient()))
    model = GroqVisionModel(client=client)

    result = model.describe_page(b"\x89PNG\r\n\x1a\nimage", 1)

    assert "Complete concise summary" in result.description
    assert client.chat.completions.calls == 2


def test_describe_page_handles_rate_limit_error():
    class RateLimitClient:
        def create(self, **kwargs):
            exc = Exception("Rate limit exceeded for TPM/RPM")
            exc.status_code = 429
            raise exc

    client = SimpleNamespace(chat=SimpleNamespace(completions=RateLimitClient()))
    model = GroqVisionModel(client=client)

    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        model.describe_page(b"\x89PNG\r\n\x1a\nimage", 1)


def test_describe_page_rejects_empty_response():
    class EmptyContentClient:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="   "),
                        finish_reason="stop",
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=EmptyContentClient()))
    model = GroqVisionModel(client=client)

    with pytest.raises(RuntimeError, match="empty page description"):
        model.describe_page(b"\x89PNG\r\n\x1a\nimage", 1)

