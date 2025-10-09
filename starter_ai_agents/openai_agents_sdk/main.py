import os
import resend

from __future__ import annotations
from agents import (
from openai import AsyncOpenAI
import asyncio
    Agent,
    Model,
    ModelProvider,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    function_tool,
    set_tracing_disabled,
)

# Load environment variables
resend.api_key = os.getenv("RESEND_API_KEY")
api_key = os.getenv("NEBIUS_API_KEY")
if not resend.api_key:
    raise ValueError("RESEND_API_KEY is not set in the environment variables")
if not api_key:
    raise ValueError("NEBIUS_API_KEY is not set in the environment variables")
base_url = os.getenv("EXAMPLE_BASE_URL", "https://api.studio.nebius.ai/v1")
model_name = os.getenv("EXAMPLE_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")

client = AsyncOpenAI(base_url=base_url, api_key=api_key)
set_tracing_disabled(disabled=True)


class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        """
        Returns an OpenAI chat completions model instance configured with the specified model name.

        Args:
            model_name: The name of the model to use, or None to use the default.

        Returns:
            An OpenAIChatCompletionsModel initialized with the given model name and OpenAI client.
        """
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


CUSTOM_MODEL_PROVIDER = CustomModelProvider()


@function_tool
def send_email(to:str, subject:str, body:str):
    """
    Sends an email using the Resend API.

    Args:
        to: Recipient email address.
        subject: Subject line of the email.
        body: HTML content of the email.

    Returns:
        A dictionary with status "success" and the message ID if sent, or status "error" and an error message if sending fails.
    """
    print(f"Sending email to {to}")
    params = {
        "from": "hi@arindammajumder.com",  # Replace with your verified sender email
        "to": [to],
        "subject": subject,
        "html": body,
    }
    try:
        response = resend.Emails.send(params)
        return {"status": "success", "message_id": response.get("id")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def main():
    """
    Runs an example agent that sends an email using a haiku response style.

    Creates an agent with haiku-only instructions and the email-sending tool, then executes a prompt to send a test email using a custom model provider. Prints the agent's final output.
    """
    agent = Agent(name="Assistant", instructions="You only respond in haikus.", tools=[send_email])

    result = await Runner.run(
        agent,
        "Send an email to studioone.tech@gmail.com with the subject 'Test Email' and the body 'Demo for the Video'",
        run_config=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER),
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())