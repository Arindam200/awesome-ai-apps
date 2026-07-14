import json
from types import SimpleNamespace

import pytest

import voice_note_analyst.clients as clients_module
from voice_note_analyst.clients import NebiusBriefClient, ProviderError


VALID_BRIEF = {
    "summary": "The team agreed to ship on Friday.",
    "key_points": ["The package is ready for validation."],
    "action_items": [{"task": "Run the release tests", "owner": "Mina", "due": "Friday"}],
    "follow_up_message": "The release is planned for Friday after validation.",
}


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_client(*, content=None, response=None, error=None):
    if response is None:
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    completions = FakeCompletions(response=response, error=error)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def make_brief_client(fake, *, api_key=None):
    return NebiusBriefClient(
        api_key=api_key,
        base_url="https://api.tokenfactory.nebius.com/v1",
        model="Qwen/Qwen3-235B-A22B",
        client=fake,
    )


def test_missing_api_key_raises_before_constructing_real_client(monkeypatch):
    def unexpected_openai(**_):
        raise AssertionError("OpenAI must not be constructed")

    monkeypatch.setattr(clients_module, "OpenAI", unexpected_openai)

    with pytest.raises(ValueError, match="NEBIUS_API_KEY"):
        NebiusBriefClient(
            api_key="  ",
            base_url="https://api.tokenfactory.nebius.com/v1",
            model="Qwen/Qwen3-235B-A22B",
        )


def test_real_client_configuration_strips_key_and_uses_provider_settings(monkeypatch):
    captured = {}
    fake, _ = fake_client(content=json.dumps(VALID_BRIEF))

    def capture_openai(**kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(clients_module, "OpenAI", capture_openai)

    NebiusBriefClient(
        api_key=" private-key ",
        base_url="https://api.tokenfactory.nebius.com/v1",
        model=" Qwen/Qwen3-235B-A22B ",
        timeout_seconds=42,
    )

    assert captured == {
        "api_key": "private-key",
        "base_url": "https://api.tokenfactory.nebius.com/v1",
        "timeout": 42,
    }


def test_create_brief_sends_structured_same_language_request():
    fake, completions = fake_client(content=json.dumps(VALID_BRIEF))
    client = make_brief_client(fake)
    transcript = "We will ship Friday after Mina runs the release tests."

    brief = client.create_brief(transcript)

    assert brief.summary == VALID_BRIEF["summary"]
    assert brief.action_items[0].owner == "Mina"
    assert len(completions.calls) == 1
    request = completions.calls[0]
    assert request["model"] == "Qwen/Qwen3-235B-A22B"
    assert request["temperature"] == 0.2
    assert request["max_tokens"] == 1200
    assert request["response_format"] == {"type": "json_object"}
    system_prompt = request["messages"][0]["content"].lower()
    assert "same language" in system_prompt
    assert "do not invent" in system_prompt
    assert "owner" in system_prompt
    assert "due date" in system_prompt
    assert request["messages"][1] == {"role": "user", "content": transcript}


def test_create_brief_accepts_single_markdown_json_fence():
    content = f"```json\n{json.dumps(VALID_BRIEF)}\n```"
    fake, _ = fake_client(content=content)

    brief = make_brief_client(fake).create_brief("Release transcript")

    assert brief.key_points == VALID_BRIEF["key_points"]


def test_create_brief_rejects_empty_transcript_before_provider_call():
    fake, completions = fake_client(content=json.dumps(VALID_BRIEF))

    with pytest.raises(ValueError, match="Transcript is empty"):
        make_brief_client(fake).create_brief("  ")

    assert completions.calls == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (SimpleNamespace(choices=[]), "empty response"),
        (
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))]),
            "empty response",
        ),
        (
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]),
            "invalid JSON shape",
        ),
        (
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"summary": "Only one field"}')
                    )
                ]
            ),
            "invalid JSON shape",
        ),
    ],
)
def test_create_brief_rejects_malformed_provider_response(response, message):
    fake, _ = fake_client(response=response)

    with pytest.raises(ProviderError, match=message):
        make_brief_client(fake).create_brief("Release transcript")


def test_create_brief_wraps_provider_exception_without_leaking_key():
    api_key = "private-nebius-token"
    fake, _ = fake_client(error=RuntimeError(f"provider rejected {api_key}"))

    with pytest.raises(ProviderError) as caught:
        make_brief_client(fake, api_key=api_key).create_brief("Release transcript")

    assert str(caught.value) == "Nebius could not generate the voice-note brief."
    assert api_key not in str(caught.value)
