from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import voice_note_analyst.clients as clients_module
from voice_note_analyst.clients import ProviderError
from voice_note_analyst.models import ActionItem, TranscriptionResult, VoiceNoteBrief


APP_PATH = Path(__file__).parents[1] / "app.py"


class FakeFunASRClient:
    calls = []
    error = None

    def __init__(self, **kwargs):
        self.calls.append({"init": kwargs})

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def transcribe(self, audio_bytes, *, filename, language=None):
        self.calls.append(
            {
                "audio_bytes": audio_bytes,
                "filename": filename,
                "language": language,
            }
        )
        if self.error is not None:
            raise self.error
        return TranscriptionResult(text="Initial transcript", language="en")


class FakeNebiusClient:
    calls = []
    error = None

    def __init__(self, **kwargs):
        self.calls.append({"init": kwargs})

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def create_brief(self, transcript):
        self.calls.append({"transcript": transcript})
        if self.error is not None:
            raise self.error
        return VoiceNoteBrief(
            summary="![remote](https://example.com/pixel.png)",
            key_points=["<script>alert(1)</script>"],
            action_items=[ActionItem(task="Review the note")],
            follow_up_message="[Follow up](https://example.com)",
        )


@pytest.fixture(autouse=True)
def reset_fake_clients(monkeypatch):
    FakeFunASRClient.calls = []
    FakeFunASRClient.error = None
    FakeNebiusClient.calls = []
    FakeNebiusClient.error = None
    monkeypatch.setattr(clients_module, "FunASRClient", FakeFunASRClient)
    monkeypatch.setattr(clients_module, "NebiusBriefClient", FakeNebiusClient)


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_initial_app_view_renders_without_provider_calls():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "FunASR + Nebius Voice Note Analyst"
    assert any(button.label == "Transcribe" for button in app.button)
    assert any(button.label == "Generate brief" for button in app.button)
    assert app.text_input[0].label == "Nebius API key (optional)"


def test_environment_api_key_is_not_written_into_password_widget(monkeypatch):
    secret = "environment-nebius-secret"
    monkeypatch.setenv("NEBIUS_API_KEY", secret)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.text_input[0].value == ""
    assert secret not in str(app)


def test_invalid_nebius_configuration_does_not_block_transcription(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "environment-key")
    monkeypatch.setenv("NEBIUS_TIMEOUT_SECONDS", "not-a-number")

    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.file_uploader[0].set_value(("note.wav", b"first-audio", "audio/wav")).run()
    button(app, "Transcribe").click().run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "FunASR + Nebius Voice Note Analyst"
    assert app.session_state["transcript_editor"] == "Initial transcript"
    assert any("ready" in caption.value for caption in app.caption)


def test_stateful_transcription_analysis_edit_and_reset(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "environment-key")
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert any("not checked" in caption.value for caption in app.caption)
    app.file_uploader[0].set_value(("note.wav", b"first-audio", "audio/wav")).run()
    button(app, "Transcribe").click().run(timeout=20)

    assert app.session_state["transcript_editor"] == "Initial transcript"
    assert app.session_state["detected_language"] == "en"
    assert FakeFunASRClient.calls[-1] == {
        "audio_bytes": b"first-audio",
        "filename": "note.wav",
        "language": "auto",
    }
    assert any(item.label == "Download transcript" for item in app.get("download_button"))

    app.text_input[0].set_value("widget-key").run()
    button(app, "Generate brief").click().run(timeout=20)

    assert app.session_state["brief"]["action_items"][0]["task"] == "Review the note"
    assert FakeNebiusClient.calls[0]["init"]["api_key"] == "widget-key"
    assert FakeNebiusClient.calls[-1] == {"transcript": "Initial transcript"}
    rendered_plain_text = [item.value for item in app.text]
    assert "![remote](https://example.com/pixel.png)" in rendered_plain_text
    assert "- <script>alert(1)</script>" in rendered_plain_text
    assert "[Follow up](https://example.com)" in rendered_plain_text
    assert "1. Review the note\nOwner: Not specified\nDue: Not specified" in rendered_plain_text
    assert not app.dataframe

    app.text_area[0].set_value("Edited transcript").run(timeout=20)

    assert app.session_state["brief"] is None
    assert app.session_state["transcript_editor"] == "Edited transcript"

    button(app, "Generate brief").click().run(timeout=20)
    assert FakeNebiusClient.calls[-1] == {"transcript": "Edited transcript"}
    button(app, "Reset").click().run(timeout=20)

    assert app.session_state["transcript_editor"] == ""
    assert app.session_state["detected_language"] is None
    assert app.session_state["brief"] is None
    assert app.session_state["transcribed_audio_fingerprint"] is None


def test_changed_audio_clears_old_output_and_provider_failures_are_isolated(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "environment-key")
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.file_uploader[0].set_value(("first.wav", b"first-audio", "audio/wav")).run()
    button(app, "Transcribe").click().run(timeout=20)
    button(app, "Generate brief").click().run(timeout=20)

    app.file_uploader[0].set_value(("second.wav", b"second-audio", "audio/wav")).run()

    assert app.session_state["transcript_editor"] == ""
    assert app.session_state["brief"] is None

    FakeFunASRClient.error = ProviderError("Safe ASR failure")
    button(app, "Transcribe").click().run(timeout=20)

    assert app.session_state["transcript_editor"] == ""
    assert any(error.value == "Safe ASR failure" for error in app.error)

    FakeFunASRClient.error = None
    button(app, "Transcribe").click().run(timeout=20)
    FakeNebiusClient.error = ProviderError("Safe Nebius failure")
    button(app, "Generate brief").click().run(timeout=20)

    assert app.session_state["transcript_editor"] == "Initial transcript"
    assert app.session_state["brief"] is None
    assert any(error.value == "Safe Nebius failure" for error in app.error)
