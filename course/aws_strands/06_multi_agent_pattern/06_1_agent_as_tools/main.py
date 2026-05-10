"""
Lesson 6.1: Agent as Tools (Orchestrator Agent)

This script demonstrates the "Agent as Tools" pattern, where a main
"orchestrator" agent delegates tasks to a team of specialized "worker" agents.

The orchestrator decides which specialist is best suited for a given query
and can even chain them together to solve complex, multi-step problems.
"""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel

# Import the specialized agents, which are decorated as tools
from specialized_agents import (
    research_assistant,
    product_recommendation_assistant,
    trip_planning_assistant,
)

# Load environment variables
load_dotenv()

# The system prompt for the orchestrator is crucial. It acts as a routing logic.
ORCHESTRATOR_SYSTEM_PROMPT = """
You are a master assistant that routes complex queries to a team of specialized agents.
Based on the user's request, determine the best tool to use.

-   For research questions and factual information → Use the `research_assistant`.
-   For product recommendations and shopping → Use the `product_recommendation_assistant`.
-   For travel planning and itineraries → Use the `trip_planning_assistant`.
-   For simple greetings or questions you can answer directly → Answer without using a tool.

If a query requires multiple steps (e.g., planning a trip AND recommending products for it),
call the necessary assistants in a logical sequence.
"""


def create_orchestrator_agent() -> Agent:
    """
    Creates the main orchestrator agent.

    Returns:
        An Agent instance configured to delegate tasks to other agents.
    """
    # Configure the language model for the orchestrator
    model = LiteLLMModel(
        client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
        model_id="nebius/moonshotai/Kimi-K2-Instruct",
    )

    # Create the orchestrator agent and provide it with the specialized agents as tools.
    orchestrator = Agent(
        model=model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[
            research_assistant,
            product_recommendation_assistant,
            trip_planning_assistant,
        ],
    )
    return orchestrator


def main():
    """
    Main function to demonstrate the orchestrator agent.
    """
    orchestrator = create_orchestrator_agent()

    # This complex query requires both travel planning and product recommendations.
    user_query = "I'm planning a hiking trip to Patagonia next month and need recommendations for waterproof boots."

    print("\n--- Orchestrator Agent ---\n\n")
    print(f"User Query: {user_query}\n")

    # The orchestrator will first call the trip_planning_assistant to understand
    # the context (Patagonia in a month) and then call the
    # product_recommendation_assistant with that context to suggest boots.
    final_response = orchestrator(user_query)

    print("\n--- Final Response from Orchestrator ---\n\n")
    print(final_response)


if __name__ == "__main__":
    main()
