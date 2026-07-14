import pytest
from pydantic import ValidationError

import voice_note_analyst.settings as settings_module
from voice_note_analyst.models import ActionItem, TranscriptionResult, VoiceNoteBrief
from voice_note_analyst.settings import load_settings


def test_load_settings_uses_safe_defaults():
    settings = load_settings({})

    assert settings.funasr_base_url == "http://127.0.0.1:8000/v1"
    assert settings.funasr_model == "sensevoice"
    assert settings.funasr_api_key is None
    assert settings.funasr_timeout_seconds == 120
    assert settings.nebius_api_key is None
    assert settings.nebius_base_url == "https://api.tokenfactory.nebius.com/v1"
    assert settings.nebius_model == "Qwen/Qwen3-235B-A22B"
    assert settings.nebius_timeout_seconds == 60


def test_load_settings_normalizes_optional_keys_and_overrides():
    settings = load_settings(
        {
            "FUNASR_BASE_URL": "https://asr.example/v1/",
            "FUNASR_MODEL": " custom-asr ",
            "FUNASR_API_KEY": " secret ",
            "FUNASR_TIMEOUT_SECONDS": "15.5",
            "NEBIUS_API_KEY": "  ",
            "NEBIUS_MODEL": " openai/gpt-oss-20b ",
        }
    )

    assert settings.funasr_base_url == "https://asr.example/v1"
    assert settings.funasr_model == "custom-asr"
    assert settings.funasr_api_key == "secret"
    assert settings.funasr_timeout_seconds == 15.5
    assert settings.nebius_api_key is None
    assert settings.nebius_model == "openai/gpt-oss-20b"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FUNASR_BASE_URL", "localhost:8000"),
        ("FUNASR_BASE_URL", "ftp://asr.example/v1"),
        ("FUNASR_BASE_URL", "https://token@asr.example/v1"),
        ("FUNASR_BASE_URL", "https://asr.example/v1?token=secret"),
        ("NEBIUS_BASE_URL", "https://api.example/v1#models"),
    ],
)
def test_load_settings_rejects_unsafe_provider_url(name, value):
    with pytest.raises(ValueError, match=name):
        load_settings({name: value})


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "not-a-number"])
def test_load_settings_rejects_invalid_timeout(value):
    with pytest.raises(ValueError, match="NEBIUS_TIMEOUT_SECONDS"):
        load_settings({"NEBIUS_TIMEOUT_SECONDS": value})


def test_load_settings_rejects_empty_model_name():
    with pytest.raises(ValueError, match="FUNASR_MODEL"):
        load_settings({"FUNASR_MODEL": "  "})


def test_funasr_settings_ignore_invalid_optional_nebius_configuration():
    settings = settings_module.load_funasr_settings(
        {
            "FUNASR_BASE_URL": "http://localhost:9000/v1",
            "NEBIUS_BASE_URL": "not-a-url",
            "NEBIUS_TIMEOUT_SECONDS": "not-a-number",
        }
    )

    assert settings.funasr_base_url == "http://localhost:9000/v1"
    assert settings.funasr_model == "sensevoice"


def test_nebius_settings_remain_strict_when_analysis_is_requested():
    with pytest.raises(ValueError, match="NEBIUS_TIMEOUT_SECONDS"):
        settings_module.load_nebius_settings({"NEBIUS_TIMEOUT_SECONDS": "not-a-number"})


def test_nebius_api_key_can_be_read_without_validating_other_nebius_values():
    key = settings_module.load_nebius_api_key(
        {
            "NEBIUS_API_KEY": " optional-key ",
            "NEBIUS_BASE_URL": "not-a-url",
        }
    )

    assert key == "optional-key"


def test_result_models_validate_structured_provider_output():
    transcription = TranscriptionResult(text="  Ship the release.  ", language="en")
    brief = VoiceNoteBrief(
        summary="  Release plan  ",
        key_points=["  Validate the package  "],
        action_items=[ActionItem(task="  Run tests  ", owner=None, due=None)],
        follow_up_message="  The release is ready.  ",
    )

    assert transcription.text == "Ship the release."
    assert brief.summary == "Release plan"
    assert brief.key_points == ["Validate the package"]
    assert brief.action_items[0].task == "Run tests"
    assert brief.follow_up_message == "The release is ready."


@pytest.mark.parametrize(
    "factory",
    [
        lambda: TranscriptionResult(text=" "),
        lambda: ActionItem(task=" "),
        lambda: VoiceNoteBrief(
            summary=" ", key_points=[], action_items=[], follow_up_message="Message"
        ),
    ],
)
def test_result_models_reject_blank_required_text(factory):
    with pytest.raises(ValidationError):
        factory()
