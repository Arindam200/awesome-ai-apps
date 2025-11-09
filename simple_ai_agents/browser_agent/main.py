import asyncio
import os

from dotenv import load_dotenv
from browser_use.llm import ChatOpenAI
from browser_use import Agent

# Load environment variables
load_dotenv()

api_key = os.getenv('NEBIUS_API_KEY')

if not api_key:
    raise ValueError('NEBIUS_API_KEY is not set')

async def run_search():
    agent = Agent(
        task=("Go to flipkart.com, search for laptop, sort by best rating, and give me the price of the first result in markdown"),
        llm=ChatOpenAI(
            base_url='https://api.tokenfactory.nebius.com/v1',
            model='Qwen/Qwen3-235B-A22B-Instruct-2507',
            api_key=api_key,
        ),
        use_vision=False,
    )
    await agent.run()


if __name__ == '__main__':
    asyncio.run(run_search())