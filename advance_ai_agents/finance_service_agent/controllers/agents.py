"""
Agents

Module description goes here.
"""

from typing import List, Dict, Optional, Union, Any
import logging
import os

from dotenv import load_dotenv
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# AI assistant imports
from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.yfinance import YFinanceTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.agent import Agent, RunResponse

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

if not NEBIUS_API_KEY:
    raise ValueError("Please provide a NEBIUS API key")


web_search_agent = Agent(
    name="web_agent",
    role="search the web for information based on the user given input",
    model=Nebius(id="deepseek-ai/DeepSeek-R1-0528", api_key=NEBIUS_API_KEY),
    tools=[
        DuckDuckGoTools(search=True, news=True),

    ],
    instructions=[
        "You are a very professional web search AI agent",
        "your job is to search the web for information based on the user given input",
        "provide exact information to the user available on the web",
    ]
)

financial_agent = Agent(
    name="financial_agent",
    role="get financial information",
    model=Nebius(id="Qwen/Qwen3-32B", api_key=NEBIUS_API_KEY),
    tools=[
        YFinanceTools(stock_price=True,
                    analyst_recommendations=True,
                    stock_fundamentals=True,
                    company_info=True,
                    technical_indicators=True,
                    historical_prices=True,
                    key_financial_ratios = True,
                    income_statements = True,
                    ),
    ],
    instructions=[
        "You are a very professional financial advisor AI agent",
        "your job is to provide financial information to users",
        "you can provide stock price, analyst recommendations, and stock fundamentals",
        "you can also provide information about companies, industries, and financial terms",
    ]
)

multi_ai = Agent(
    team=[web_search_agent, financial_agent],
    model=Nebius(id="meta-llama/Llama-3.3-70B-Instruct", api_key=NEBIUS_API_KEY),
    markdown=True,
)