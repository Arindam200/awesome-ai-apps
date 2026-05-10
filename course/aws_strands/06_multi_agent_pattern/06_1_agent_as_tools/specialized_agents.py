"""
Lesson 6.1: Agent as Tools (Worker Agents)

This file defines the "worker" agents that will be used as tools by the
main orchestrator agent. Each agent is a specialist in a specific domain.

By decorating a function that returns an agent with `@tool`, we can make
that agent available as a callable tool for another agent to use.
"""

import os
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands_tools import http_request, retrieve

# Load environment variables
load_dotenv()

# --- Model Configuration ---
# A single model instance can be shared among all the specialized agents.
LLM = LiteLLMModel(
    client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
    model_id="nebius/moonshotai/Kimi-K2-Instruct",
)

# --- Specialized Agent Definitions ---


@tool
def research_assistant(query: str) -> str:
    """
    A specialized agent for research-related queries.

    This agent uses the `retrieve` and `http_request` tools to find factual,
    well-sourced information.

    Args:
        query: A research question requiring factual information.

    Returns:
        A detailed research answer, ideally with citations.
    """
    print(f"--- Delegating to Research Assistant ---")
    research_agent = Agent(
        model=LLM,
        system_prompt="""You are a specialized research assistant.
        Your sole purpose is to provide factual, well-sourced information.
        Always cite your sources when possible.""",
        tools=[retrieve, http_request],
    )
    response = research_agent(query)
    return str(response)


@tool
def product_recommendation_assistant(query: str) -> str:
    """
    A specialized agent for handling product recommendation queries.

    This agent can search for products and provide personalized recommendations.

    Args:
        query: A product inquiry with user preferences.

    Returns:
        Personalized product recommendations with clear reasoning.
    """
    print(f"--- Delegating to Product Recommendation Assistant ---")
    product_agent = Agent(
        model=LLM,
        system_prompt="""You are a specialized product recommendation assistant.
        Provide personalized product suggestions based on user preferences.""",
        tools=[retrieve, http_request],
    )
    response = product_agent(query)
    return str(response)


@tool
def trip_planning_assistant(query: str) -> str:
    """
    A specialized agent for creating travel itineraries and giving travel advice.

    Args:
        query: A travel planning request with destination and preferences.

    Returns:
        A detailed travel itinerary or relevant travel advice.
    """
    print(f"--- Delegating to Trip Planning Assistant ---")
    travel_agent = Agent(
        model=LLM,
        system_prompt="""You are a specialized travel planning assistant.
        Create detailed travel itineraries based on user preferences, including
        recommendations for flights, accommodations, and activities.""",
        tools=[retrieve, http_request],
    )
    response = travel_agent(query)
    return str(response)
