import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from providers import groq_vision
from providers.claude_vison import ClaudeVisionModel


class FakeClaudeClient:
    def __init__(self):
        self.last_request = None
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="A chart.")],
            stop_reason="end_turn",
        )


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


def test_describe_page_compresses_image_and_uses_prepared_media_type(monkeypatch):
    monkeypatch.setattr(groq_vision, "MAX_BASE64_IMAGE_BYTES", 4096)
    client = FakeClaudeClient()
    model = ClaudeVisionModel(client=client)

    result = model.describe_page(make_png(128, 128), 1)

    image_source = client.last_request["messages"][0]["content"][0]["source"]
    image_bytes = base64.b64decode(image_source["data"])

    assert result.description == "A chart."
    assert image_source["media_type"] == "image/jpeg"
    assert len(image_source["data"]) <= groq_vision.MAX_BASE64_IMAGE_BYTES
    assert image_bytes.startswith(b"\xff\xd8")
