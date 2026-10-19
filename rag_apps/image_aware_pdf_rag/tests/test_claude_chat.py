from types import SimpleNamespace

import pytest

from providers.claude_chat import ClaudeChatModel


class FakeClaudeClient:
    def __init__(self):
        self.messages = SimpleNamespace(create=self.create)
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Answer")],
            stop_reason="end_turn",
        )


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "user"}],
        [{"role": "user", "content": "  "}],
        [{"role": "unknown", "content": "Question"}],
    ],
)
def test_generate_rejects_invalid_messages_before_request(messages):
    client = FakeClaudeClient()
    model = ClaudeChatModel(client=client)

    with pytest.raises(ValueError):
        model.generate(messages)

    assert client.last_request is None
