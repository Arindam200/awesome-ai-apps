from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


api_key = os.getenv("NEBIUS_API_KEY")
if not api_key:
    raise ValueError("NEBIUS_API_KEY is not set in the environment variables")

# Get model name and base URL from environment variables with defaults
model_name = os.getenv("EXAMPLE_MODEL_NAME", "openai/meta-llama/Meta-Llama-3.1-8B-Instruct")
base_url = os.getenv("EXAMPLE_BASE_URL", "https://api.tokenfactory.nebius.com/v1")

model = OpenAIChatCompletionsModel(
    model=model_name,
    openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key)
)

agent = Agent(
    name="Assistant",
    instruction="You're an Expert Doctor specializing in nutrition and preventive care. Provide evidence-based medical advice and always include disclaimers when appropriate.",
    model=model
)

result = Runner.run(agent,"Give me a diet plan as a 18 y/o boy")

print(result)
