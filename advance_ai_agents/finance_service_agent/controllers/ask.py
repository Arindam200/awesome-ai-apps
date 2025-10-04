"""
Ask

Module description goes here.
"""

from typing import List, Dict, Optional, Union, Any
import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.nebius import Nebius

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


load_dotenv()

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

if not NEBIUS_API_KEY:
    raise ValueError("Please provide a NEBIUS API key")

# Create agent for chat functionality
chat_agent = Agent(
    model=Nebius(id="meta-llama/Llama-3.3-70B-Instruct", api_key=NEBIUS_API_KEY),
    instructions=[
        "You are an AI investment assistant.",
        "You are here to help users with investment-related questions.",
        "Provide clear, helpful, and accurate financial advice."
    ],
    markdown=True
)

def nebius_chat(query: str):
    if not query:
        return {"error": "Query parameter is required"}
    
    try:
        response = chat_agent.run(query)
        answer = response.content
        return {"question": query, "answer": answer}
    
    except Exception as e:
        return {"error": str(e)}