"""
HackerNews Tech News Analyst Agent

A sophisticated AI agent that analyzes HackerNews content, tracks tech trends,
and provides intelligent insights about technology discussions and patterns.

Note: This application requires the 'agno' framework. Install with:
    pip install agno
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

# Check for required dependencies
try:
    from agno.agent import Agent
    from agno.tools.hackernews import HackerNewsTools
    from agno.models.nebius import Nebius
    AGNO_AVAILABLE = True
except ImportError as e:
    AGNO_AVAILABLE = False
    # Type stubs for when agno is not available
    Agent = type(None)
    HackerNewsTools = type(None)
    Nebius = type(None)
    logging.error(f"agno framework not available: {e}")
    print("ERROR: agno framework is required but not installed.")
    print("Please install it with: pip install agno")
    print("Or check the project README for installation instructions.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tech_analyst.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded successfully")

# Define instructions for the agent
INSTRUCTIONS = """You are an intelligent HackerNews analyst and tech news curator. Your capabilities include:

1. Analyzing HackerNews content:
   - Track trending topics and patterns
   - Analyze user engagement and comments
   - Identify interesting discussions and debates
   - Provide insights about tech trends
   - Compare stories across different time periods

2. When analyzing stories:
   - Look for patterns in user engagement
   - Identify common themes and topics
   - Highlight particularly insightful comments
   - Note any controversial or highly debated points
   - Consider the broader tech industry context

3. When providing summaries:
   - Be engaging and conversational
   - Include relevant context and background
   - Highlight the most interesting aspects
   - Make connections between related stories
   - Suggest why the content matters

Always maintain a helpful and engaging tone while providing valuable insights."""

def create_agent() -> Optional[object]:
    """Create and configure the HackerNews analyst agent.
    
    Returns:
        Agent: Configured agent ready for tech news analysis, or None if dependencies unavailable
        
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
        # Initialize tools
        hackernews_tools = HackerNewsTools()
        logger.info("HackerNews tools initialized successfully")
        
        # Create the agent with enhanced capabilities
        agent = Agent(
            name="Tech News Analyst",
            instructions=[INSTRUCTIONS],
            tools=[hackernews_tools],
            show_tool_calls=True,
            model=Nebius(
                id="Qwen/Qwen3-30B-A3B",
                api_key=api_key
            ),
            markdown=True,
            # memory=True,  # Enable memory for context retention
        )
        
        logger.info("Tech News Analyst agent created successfully")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise


def display_welcome_message() -> None:
    """Display welcome message and available features."""
    welcome_text = """
🤖 Tech News Analyst is ready!

I can help you with:
1. Top stories and trends on HackerNews
2. Detailed analysis of specific topics
3. User engagement patterns
4. Tech industry insights

Type 'exit' to quit or ask me anything about tech news!
"""
    logger.info("Displaying welcome message")
    print(welcome_text)


def get_user_input() -> str:
    """Get user input with proper error handling.
    
    Returns:
        str: User input string, or 'exit' if EOF encountered
    """
    try:
        user_input = input("\nYou: ").strip()
        return user_input
    except (EOFError, KeyboardInterrupt):
        logger.info("User interrupted input, exiting gracefully")
        return 'exit'


def main() -> None:
    """Main application entry point."""
    logger.info("Starting Tech News Analyst application")
    
    if not AGNO_AVAILABLE:
        print("❌ Cannot start application - agno framework is not available")
        print("Please install with: pip install agno")
        return
    
    try:
        # Create agent
        agent = create_agent()
        
        # Display welcome message
        display_welcome_message()
        
        # Main interaction loop
        while True:
            user_input = get_user_input()
            
            if user_input.lower() == 'exit':
                logger.info("User requested exit")
                print("Goodbye! 👋")
                break
            
            if not user_input:
                logger.warning("Empty input received, prompting user again")
                print("Please enter a question or 'exit' to quit.")
                continue
                
            try:
                # Add timestamp to the response
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"\n[{timestamp}]")
                logger.info(f"Processing user query: {user_input[:50]}...")
                
                # Get agent response
                if agent is not None:
                    agent.print_response(user_input)
                    logger.info("Response generated successfully")
                else:
                    print("Agent is not available. Please check agno framework installation.")
                
            except Exception as e:
                logger.error(f"Error processing user query: {e}")
                print(f"Sorry, I encountered an error: {e}")
                print("Please try again with a different question.")
                
    except Exception as e:
        logger.error(f"Critical error in main application: {e}")
        print(f"Application failed to start: {e}")
        return

if __name__ == "__main__":
    main()