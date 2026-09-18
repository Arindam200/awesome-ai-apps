import os

from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner
from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct"
DEFAULT_PROMPT = "Give me a diet plan for an 18-year-old boy."


def create_agent() -> Agent:
    """Create the example agent from environment-based configuration."""
    load_dotenv()

    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("NEBIUS_API_KEY is not set in the environment variables")

    client = AsyncOpenAI(
        base_url=os.getenv("EXAMPLE_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
    )
    model = OpenAIChatCompletionsModel(
        model=os.getenv("EXAMPLE_MODEL_NAME", DEFAULT_MODEL_NAME),
        openai_client=client,
    )
    return Agent(
        name="Assistant",
        instructions=(
            "You're an expert doctor specializing in nutrition and preventive care. "
            "Provide evidence-based medical advice and include appropriate disclaimers."
        ),
        model=model,
    )


def main() -> None:
    """Run the basic example synchronously and print its final response."""
    result = Runner.run_sync(create_agent(), DEFAULT_PROMPT)
    print(result.final_output)


if __name__ == "__main__":
    main()
