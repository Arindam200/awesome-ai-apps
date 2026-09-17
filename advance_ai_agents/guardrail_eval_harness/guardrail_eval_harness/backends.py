from collections.abc import AsyncIterator
from typing import Any

from agents import Model
from agents.items import ModelResponse, TResponseOutputItem, TResponseStreamEvent
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)


class ScriptedModel(Model):
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = iter(responses)
        self.raw_responses: list[ModelResponse] = []

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:
        try:
            items = next(self.responses)
        except StopIteration:
            raise RuntimeError("script_exhausted") from None
        output: list[TResponseOutputItem] = []
        for item in items:
            if item["type"] == "function_call":
                output.append(ResponseFunctionToolCall(**item))
            else:
                output.append(
                    ResponseOutputMessage(
                        id="message",
                        type="message",
                        role="assistant",
                        status="completed",
                        content=[
                            ResponseOutputText(
                                type="output_text", text=item["text"], annotations=[]
                            )
                        ],
                    )
                )
        response = ModelResponse(output=output, usage=Usage(), response_id=None)
        self.raw_responses.append(response)
        return response

    def stream_response(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[TResponseStreamEvent]:
        raise NotImplementedError("Streaming is not supported")
