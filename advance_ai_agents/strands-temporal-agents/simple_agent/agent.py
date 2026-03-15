import os
from datetime import datetime
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from config import NEBIUS_API_KEY, NEBIUS_MODEL_ID, WEATHER_TIMEOUT


@tool
def get_time() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


@tool
def list_files() -> str:
    try:
        files = [f for f in os.listdir('.') if f.endswith('.py')]
        return f"Python files: {', '.join(files[:5])}"
    except Exception as e:
        return f"File listing error: {str(e)}"


@tool
def get_weather(city: str) -> str:
    try:
        import requests
        
        url = f"https://wttr.in/{city}?format=%C+%t"
        response = requests.get(url, timeout=WEATHER_TIMEOUT)
        
        if response.status_code == 200:
            weather_data = response.text.strip()
            return f"{city}: {weather_data}"
        
        return f"Weather data unavailable for {city}"
        
    except Exception as e:
        return f"Weather service error for {city}: {str(e)}"


def create_agent() -> Agent:
    return Agent(
        model=LiteLLMModel(
            client_args={
                "api_key": NEBIUS_API_KEY,
            },
            model_id=NEBIUS_MODEL_ID,
            params={
                "max_tokens": 1500,
                "temperature": 0.7,
            },
        ),
        tools=[get_time, list_files, get_weather],
        system_prompt="Use available tools to provide accurate, helpful responses."
    )


def main():
    print("Simple Agent Demo")
    print("Type 'quit' to exit")
    print()
    
    agent = create_agent()
    
    while True:
        try:
            task = input("Enter task: ").strip()
            
            if task.lower() in ['quit', 'q', 'exit']:
                print("Goodbye!")
                break
            
            if not task:
                continue
            
            print("Processing...")
            result = agent(task)
            print(f"Result: {result}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


if __name__ == "__main__":
    main()
