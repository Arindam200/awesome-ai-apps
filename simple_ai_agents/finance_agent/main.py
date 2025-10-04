"""
AI Finance Agent Application

A sophisticated finance analysis agent using xAI's Llama model for stock analysis,
market insights, and financial data processing with advanced tools integration.
"""

import logging
import os
from typing import List, Optional

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.yfinance import YFinanceTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.playground import Playground, serve_playground_app
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('finance_agent.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded successfully")


def create_finance_agent() -> Agent:
    """Create and configure the AI finance agent.
    
    Returns:
        Agent: Configured finance agent with tools and model
        
    Raises:
        ValueError: If NEBIUS_API_KEY is not found in environment
    """
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        logger.error("NEBIUS_API_KEY not found in environment variables")
        raise ValueError("NEBIUS_API_KEY is required but not found in environment")
    
    try:
        # Initialize financial tools
        yfinance_tools = YFinanceTools(
            stock_price=True, 
            analyst_recommendations=True, 
            stock_fundamentals=True
        )
        duckduckgo_tools = DuckDuckGoTools()
        logger.info("Financial analysis tools initialized successfully")
        
        # Create the finance agent
        agent = Agent(
            name="xAI Finance Agent",
            model=Nebius(
                id="meta-llama/Llama-3.3-70B-Instruct",
                api_key=api_key
            ),
            tools=[duckduckgo_tools, yfinance_tools],
            instructions=[
                "Always use tables to display financial/numerical data.",
                "For text data use bullet points and small paragraphs.",
                "Provide clear, actionable financial insights.",
                "Include risk disclaimers when appropriate."
            ],
            show_tool_calls=True,
            markdown=True,
        )
        
        logger.info("xAI Finance Agent created successfully")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create finance agent: {e}")
        raise


def create_playground_app() -> any:
    """Create the Playground application for the finance agent.
    
    Returns:
        FastAPI app: Configured playground application
        
    Raises:
        RuntimeError: If agent creation fails
    """
    try:
        agent = create_finance_agent()
        playground = Playground(agents=[agent])
        app = playground.get_app()
        logger.info("Playground application created successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to create playground application: {e}")
        raise RuntimeError(f"Could not initialize finance agent application: {e}")


# Create the application instance
try:
    app = create_playground_app()
    logger.info("Finance agent application ready to serve")
except Exception as e:
    logger.critical(f"Critical error during application initialization: {e}")
    raise


def main() -> None:
    """Main entry point for running the finance agent server."""
    try:
        logger.info("Starting xAI Finance Agent server")
        serve_playground_app("xai_finance_agent:app", reload=True)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    main()