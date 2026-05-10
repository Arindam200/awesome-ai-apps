"""
Lesson 1: Basic Agent Creation

This script demonstrates the fundamentals of creating a simple AI agent using the AWS Strands SDK.

We will build a weather assistant that can:
1.  Understand a natural language query about weather.
2.  Use the `http_request` tool to fetch data from the National Weather Service API.
3.  Synthesize the data into a human-readable response.
"""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands_tools import http_request

# Load environment variables from a .env file
load_dotenv()

# Define a detailed system prompt to guide the agent's behavior
WEATHER_SYSTEM_PROMPT = """You are a friendly and helpful weather assistant with HTTP capabilities.

Your primary function is to provide accurate weather forecasts for locations in the United States by using the National Weather Service API.

Follow these steps to fulfill a user's request:
1.  First, if you don't have grid coordinates, use the points API endpoint to get them.
    - For latitude and longitude: https://api.weather.gov/points/{latitude},{longitude}
    - For a US zipcode: https://api.weather.gov/points/{zipcode}
2.  The points API will return a `forecast` URL. Use this URL to make a second HTTP request to get the actual weather forecast.
3.  Process the forecast data and present it to the user in a clear, easy-to-understand format.

When displaying your response:
-   Highlight key information like temperature, precipitation, and any weather alerts.
-   Explain technical terms in simple language.
-   If you encounter an error, apologize and explain that you couldn't retrieve the weather information.
"""


def create_weather_agent() -> Agent:
    """
    Creates and configures a weather-focused agent.

    Returns:
        An Agent instance configured with a model, system prompt, and tools.
    """
    # Configure the language model (LLM) that will power the agent.
    # We use LiteLLMModel to connect to a provider like Nebius, OpenAI, or Anthropic.
    model = LiteLLMModel(
        client_args={
            "api_key": os.getenv("NEBIUS_API_KEY"),
        },
        model_id="nebius/deepseek-ai/DeepSeek-V3-0324",
        params={
            "max_tokens": 1500,
            "temperature": 0.7,
        },
    )

    # Create the agent instance.
    # The agent is the core component that orchestrates the LLM, tools, and system prompt.
    weather_agent = Agent(
        system_prompt=WEATHER_SYSTEM_PROMPT,
        tools=[http_request],  # Grant the agent the ability to make HTTP requests.
        model=model,
    )
    return weather_agent


def main():
    """
    Main function to run the weather agent.
    """
    # Create the weather agent
    weather_agent = create_weather_agent()

    # Define a user query
    user_query = "Compare the temperature in New York, NY and Chicago, IL this weekend."

    # Invoke the agent with the query and get the response
    print(f"User Query: {user_query}\n")
    response = weather_agent(user_query)

    # Print the agent's final response
    print("Weather Agent Response:")
    print(response)


if __name__ == "__main__":
    main()