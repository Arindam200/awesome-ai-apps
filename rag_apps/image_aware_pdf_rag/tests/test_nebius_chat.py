from types import SimpleNamespace

import pytest

from providers.nebius_chat import NebiusChatModel


class FakeNebiusClient:
    def __init__(self, content="Mock answer", finish_reason=None):
        self.content = content
        self.finish_reason = finish_reason
        self.last_request = None
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.last_request = kwargs

        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message, finish_reason=self.finish_reason)

        return SimpleNamespace(choices=[choice])


def test_generate_returns_answer(monkeypatch):
    monkeypatch.delenv("NEBIUS_CHAT_MODEL", raising=False)
    client = FakeNebiusClient("Revenue increased by 20%.")
    model = NebiusChatModel(client=client)

    result = model.generate([
        {"role": "user", "content": "What happened to revenue?"}
    ])

    assert result == "Revenue increased by 20%."
    assert client.last_request["model"] == "openai/gpt-oss-120b"


def test_generate_strips_whitespace():
    model = NebiusChatModel(client=FakeNebiusClient("  Answer  "))

    assert model.generate([
        {"role": "user", "content": "Question"}
    ]) == "Answer"


def test_rejects_empty_messages():
    model = NebiusChatModel(client=FakeNebiusClient())

    with pytest.raises((ValueError, TypeError)):
        model.generate([])


def test_rejects_empty_response():
    model = NebiusChatModel(client=FakeNebiusClient("  "))

    with pytest.raises(RuntimeError, match="empty"):
        model.generate([
            {"role": "user", "content": "Question"}
        ])


def test_rejects_truncated_response():
    model = NebiusChatModel(client=FakeNebiusClient("Partial answer", "length"))

    with pytest.raises(RuntimeError, match="truncated"):
        model.generate([
            {"role": "user", "content": "Question"}
        ])


def test_rejects_no_choices():
    class EmptyClient:
        def __init__(self):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(choices=[])
                )
            )

    model = NebiusChatModel(client=EmptyClient())

    with pytest.raises(RuntimeError, match="no completion choices"):
        model.generate([
            {"role": "user", "content": "Question"}
        ])


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    with pytest.raises(ValueError, match="NEBIUS_API_KEY"):
        NebiusChatModel()
