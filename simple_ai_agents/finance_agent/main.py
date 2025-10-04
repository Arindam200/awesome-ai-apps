"""
AI Finance Agent Application

A sophisticated finance analysis agent using xAI's Llama model for stock analysis,
market insights, and financial data processing with advanced tools integration.

Note: This application requires the 'agno' framework. Install with:
    pip install agno
"""

from typing import List, Optional, Any
import logging
import os
import sys

from dotenv import load_dotenv
try:
    from agno.agent import Agent
    from agno.models.nebius import Nebius
    from agno.tools.yfinance import YFinanceTools
    from agno.tools.duckduckgo import DuckDuckGoTools
    from agno.playground import Playground, serve_playground_app
    AGNO_AVAILABLE = True
except ImportError as e:
    AGNO_AVAILABLE = False
    logging.error(f"agno framework not available: {e}")
    print("ERROR: agno framework is required but not installed.")
    print("Please install it with: pip install agno")
    print("Or check the project README for installation instructions.")

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


def create_finance_agent() -> Optional[Any]:
    """Create and configure the AI finance agent.

    Returns:
        Agent: Configured finance agent with tools and model, or None if dependencies unavailable

    Raises:
        ValueError: If NEBIUS_API_KEY is not found in environment
        RuntimeError: If agno framework is not available
    """
    if not AGNO_AVAILABLE:
        raise RuntimeError("agno framework is required but not available. Please install with: pip install agno")

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


def create_playground_app() -> Optional[Any]:
    """Create the Playground application for the finance agent.

    Returns:
        FastAPI app: Configured playground application, or None if dependencies unavailable

    Raises:
        RuntimeError: If agent creation fails or dependencies unavailable
    """
    if not AGNO_AVAILABLE:
        logger.error("Cannot create playground app: agno framework not available")
        return None

    try:
        agent = create_finance_agent()
        if agent is None:
            return None

        playground = Playground(agents=[agent])
        app = playground.get_app()
        logger.info("Playground application created successfully")
        return app

    except Exception as e:
        logger.error(f"Failed to create playground application: {e}")
        raise RuntimeError(f"Could not initialize finance agent application: {e}")


# Create the application instance
app = None
if AGNO_AVAILABLE:
    try:
        app = create_playground_app()
        logger.info("Finance agent application ready to serve")
    except Exception as e:
        logger.critical(f"Critical error during application initialization: {e}")
        app = None
else:
    logger.warning("Application not initialized: agno framework not available")


def main() -> None:
    """Main entry point for running the finance agent server."""
    if not AGNO_AVAILABLE:
        print("Cannot start server: agno framework is not available")
        print("Please install it with: pip install agno")
        sys.exit(1)

    if app is None:
        print("Cannot start server: application initialization failed")
        sys.exit(1)

    try:
        logger.info("Starting xAI Finance Agent server")
        serve_playground_app("xai_finance_agent:app", reload=True)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    main()