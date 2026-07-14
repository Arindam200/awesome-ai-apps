import httpx
import pytest

from voice_note_analyst.clients import (
    FunASRClient,
    ProviderError,
    build_transcriptions_url,
)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://localhost:8000", "http://localhost:8000/v1/audio/transcriptions"),
        ("http://localhost:8000/v1/", "http://localhost:8000/v1/audio/transcriptions"),
        (
            "https://asr.example/api/v1/audio/transcriptions",
            "https://asr.example/api/v1/audio/transcriptions",
        ),
    ],
)
def test_build_transcriptions_url_normalizes_supported_shapes(base_url, expected):
    assert build_transcriptions_url(base_url) == expected


@pytest.mark.parametrize(
    "base_url",
    [
        "localhost:8000",
        "ftp://asr.example/v1",
        "https://token@asr.example/v1",
        "https://asr.example/v1?token=secret",
        "https://asr.example/v1#endpoint",
    ],
)
def test_build_transcriptions_url_rejects_unsafe_url(base_url):
    with pytest.raises(ValueError, match="FunASR base URL"):
        build_transcriptions_url(base_url)


def test_transcribe_posts_openai_compatible_multipart_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert request.method == "POST"
        assert str(request.url) == "https://asr.example/v1/audio/transcriptions"
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert b'name="file"; filename="meeting.wav"' in body
        assert b"Content-Type: audio/wav" in body
        assert b"audio-content" in body
        assert b'name="model"\r\n\r\nsensevoice' in body
        assert b'name="response_format"\r\n\r\nverbose_json' in body
        assert b'name="language"\r\n\r\nen' in body
        return httpx.Response(200, json={"text": "  Hello team.  ", "language": "en"})

    with FunASRClient(
        base_url="https://asr.example/v1",
        model="sensevoice",
        api_key=" test-token ",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.transcribe(
            b"audio-content",
            filename="../../meeting.wav",
            language="en",
        )

    assert result.text == "Hello team."
    assert result.language == "en"


def test_transcribe_omits_authorization_and_auto_language():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert "Authorization" not in request.headers
        assert b'name="language"' not in body
        return httpx.Response(200, json={"text": "Ni hao", "language": "auto"})

    with FunASRClient(
        base_url="http://localhost:8000",
        model="sensevoice",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.transcribe(b"audio", filename="note.webm", language="auto")

    assert result.language is None


def test_transcribe_rejects_empty_audio_before_request():
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    with FunASRClient(
        base_url="http://localhost:8000",
        model="sensevoice",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ValueError, match="Audio is empty"):
            client.transcribe(b"", filename="empty.wav")


def test_client_rejects_empty_model_name():
    with pytest.raises(ValueError, match="model"):
        FunASRClient(base_url="http://localhost:8000", model="  ")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (httpx.Response(200, json={"language": "en"}), "missing the string field 'text'"),
        (httpx.Response(200, json={"text": "  "}), "empty transcript"),
    ],
)
def test_transcribe_rejects_malformed_success_response(response, message):
    transport = httpx.MockTransport(lambda _: response)
    with FunASRClient(
        base_url="http://localhost:8000",
        model="sensevoice",
        transport=transport,
    ) as client:
        with pytest.raises(ProviderError, match=message):
            client.transcribe(b"audio", filename="note.mp3")


def test_transcribe_reports_bounded_single_line_http_error_and_redacts_key():
    api_key = "private-funasr-token"
    body = f"invalid\nrequest {api_key} " + ("x" * 1_500)
    transport = httpx.MockTransport(lambda _: httpx.Response(400, text=body))

    with FunASRClient(
        base_url="http://localhost:8000",
        model="sensevoice",
        api_key=api_key,
        transport=transport,
    ) as client:
        with pytest.raises(ProviderError) as caught:
            client.transcribe(b"audio", filename="note.m4a")

    message = str(caught.value)
    assert message.startswith("FunASR returned HTTP 400:")
    assert "\n" not in message
    assert api_key not in message
    assert "[redacted]" in message
    assert len(message) < 1_100


def test_transcribe_wraps_connection_error_with_safe_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network details", request=request)

    with FunASRClient(
        base_url="https://asr.example/v1",
        model="sensevoice",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(
            ProviderError,
            match=r"Could not reach FunASR at https://asr\.example/v1/audio/transcriptions",
        ):
            client.transcribe(b"audio", filename="note.wav")


def test_transcribe_reports_timeout_separately():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow provider", request=request)

    with FunASRClient(
        base_url="http://localhost:8000",
        model="sensevoice",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ProviderError, match="transcription timed out"):
            client.transcribe(b"audio", filename="note.wav")
