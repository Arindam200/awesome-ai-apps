
import pytest

from interfaces.chat import (
    ChatModel,
    validate_messages,
)


class FakeChatModel:
    """Mock implementation; no API key or network required."""

    def generate(self, messages: list[dict[str, str]]) -> str:
        validate_messages(messages)
        return "Revenue increased by 20%."


def test_fake_provider_implements_chat_contract():
    model = FakeChatModel()

    assert isinstance(model, ChatModel)


def test_generate_returns_string():
    model = FakeChatModel()

    result = model.generate([
        {"role": "user", "content": "Summarize the PDF."}
    ])

    assert isinstance(result, str)
    assert result == "Revenue increased by 20%."


def test_accepts_system_and_user_messages():
    validate_messages([
        {"role": "system", "content": "Answer using PDF evidence."},
        {"role": "user", "content": "What does the chart show?"},
    ])


def test_rejects_empty_messages():
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_messages([])


def test_rejects_invalid_role():
    with pytest.raises(ValueError, match="invalid role"):
        validate_messages([
            {"role": "developer", "content": "Do something."}
        ])


def test_rejects_empty_content():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_messages([
            {"role": "user", "content": "   "}
        ])


def test_rejects_missing_content():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_messages([
            {"role": "user"}
        ])


def test_rejects_non_dictionary_message():
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_messages(["invalid"])
