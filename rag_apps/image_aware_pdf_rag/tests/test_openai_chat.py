from types import SimpleNamespace

import pytest

from providers.openai_chat import OpenAIChatModel


class FakeOpenAIClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Answer"),
                    finish_reason="stop",
                )
            ]
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
    client = FakeOpenAIClient()
    model = OpenAIChatModel(client=client)

    with pytest.raises(ValueError):
        model.generate(messages)

    assert client.last_request is None
