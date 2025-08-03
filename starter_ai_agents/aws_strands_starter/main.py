import os
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands_tools import http_request
from dotenv import load_dotenv

# Define a weather-focused system prompt
WEATHER_SYSTEM_PROMPT = """You are a weather assistant with HTTP capabilities. You can:

1. Make HTTP requests to the National Weather Service API
2. Process and display weather forecast data
3. Provide weather information for locations in the United States

When retrieving weather information:
1. First get the coordinates or grid information using https://api.weather.gov/points/{latitude},{longitude} or https://api.weather.gov/points/{zipcode}
2. Then use the returned forecast URL to get the actual forecast

When displaying responses:
- Format weather data in a human-readable way
- Highlight important information like temperature, precipitation, and alerts
- Handle errors appropriately
- Convert technical terms to user-friendly language

Always explain the weather conditions clearly and provide context for the forecast.
"""

load_dotenv()

model = LiteLLMModel(
    client_args={
        "api_key": os.getenv("NEBIUS_API_KEY"),
    },
    # **model_config
    model_id="nebius/deepseek-ai/DeepSeek-V3-0324",
    params={
        "max_tokens": 1000,
        "temperature": 0.7,
    },
)

weather_agent = Agent(
    system_prompt=WEATHER_SYSTEM_PROMPT,
    tools=[http_request],  # Explicitly enable http_request tool
    model=model,  # Use the LiteLLMModel instance
)
response = weather_agent("Compare the temperature in New York and Chicago this weekend")
print(response)
