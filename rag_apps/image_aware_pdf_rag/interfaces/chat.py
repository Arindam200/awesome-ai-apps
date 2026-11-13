
"""Provider-independent interface for chat models.

Provider adapters should implement this contract without changing
the core RAG pipeline.

Potential adapters:
- Hugging Face
- Groq
- OpenAI
- Anthropic Claude
- Local chat models
"""

from typing import Protocol, runtime_checkable


# Standard message format shared by all chat providers.
ChatMessage = dict[str, str]


@runtime_checkable
class ChatModel(Protocol):
    """Contract for a chat model used by the RAG pipeline."""

    def generate(self, messages: list[ChatMessage]) -> str:
        """Generate a text response from chat messages.

        Args:
            messages: A list of dictionaries containing:
                - role: "system", "user", or "assistant"
                - content: Message text

        Returns:
            The generated response as a string.

        Raises:
            ValueError: If the input messages are invalid.
            RuntimeError: If generation fails.
        """
        ...
        

def validate_messages(messages: list[ChatMessage]) -> None:
    """Validate messages before passing them to a provider adapter."""
    if not messages:
        raise ValueError("messages cannot be empty")

    valid_roles = {"system", "user", "assistant"}

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"Message {index} must be a dictionary")

        if message.get("role") not in valid_roles:
            raise ValueError(
                f"Message {index} has an invalid role"
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Message {index} must have non-empty string content"
            )
