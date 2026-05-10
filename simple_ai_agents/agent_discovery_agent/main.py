"""
AI Agent Discovery Agent - Find and compare AI agents across multiple registries.

Uses the Registry Broker API to search NANDA, MCP, Virtuals, A2A, and ERC-8004 agents.
"""

import os
import httpx
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.nebius import Nebius

load_dotenv()

REGISTRY_BROKER_BASE = "https://hol.org/registry/api/v1"


def search_agents(query: str, limit: int = 10) -> dict:
    """
    Search for AI agents across multiple registries.

    Args:
        query: Search query (e.g., "code review", "data analysis", "trading")
        limit: Maximum number of results to return

    Returns:
        Dictionary containing search results with agent metadata
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{REGISTRY_BROKER_BASE}/search", params={"q": query, "limit": limit}
        )
        response.raise_for_status()
        return response.json()


def get_agent_details(uaid: str) -> dict:
    """
    Get detailed information about a specific agent.

    Args:
        uaid: Universal Agent Identifier

    Returns:
        Dictionary containing agent details, capabilities, and metadata
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{REGISTRY_BROKER_BASE}/agents/{uaid}")
        response.raise_for_status()
        return response.json()


def get_similar_agents(uaid: str, limit: int = 5) -> dict:
    """
    Find agents similar to a given agent.

    Args:
        uaid: Universal Agent Identifier of the reference agent
        limit: Maximum number of similar agents to return

    Returns:
        Dictionary containing similar agents
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{REGISTRY_BROKER_BASE}/agents/{uaid}/similar", params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()


def get_search_facets() -> dict:
    """
    Get available search facets (categories, registries, capabilities).

    Returns:
        Dictionary containing available facets for filtering
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{REGISTRY_BROKER_BASE}/search/facets")
        response.raise_for_status()
        return response.json()


def format_agent_results(results: dict) -> str:
    """Format search results for display."""
    if not results.get("agents"):
        return "No agents found matching your query."

    output = []
    for agent in results["agents"][:10]:
        name = agent.get("name", "Unknown")
        registry = agent.get("registry", "Unknown")
        description = agent.get("description", "No description")[:150]
        uaid = agent.get("uaid", "")

        output.append(f"**{name}** ({registry})")
        output.append(f"  UAID: {uaid}")
        output.append(f"  {description}")
        output.append("")

    total = results.get("total", len(results["agents"]))
    output.append(f"Total results: {total}")
    return "\n".join(output)


# Create the agent with tools
agent = Agent(
    name="AI Agent Discovery",
    model=Nebius(id="Qwen/Qwen3-30B-A3B"),
    tools=[search_agents, get_agent_details, get_similar_agents, get_search_facets],
    instructions=[
        "You are an AI agent discovery assistant that helps users find the right AI agents for their needs.",
        "Use the search_agents tool to find agents matching user queries.",
        "Use get_agent_details to provide detailed information about specific agents.",
        "Use get_similar_agents to suggest alternatives.",
        "Use get_search_facets to show available categories and registries.",
        "Always explain which registries the agents come from (NANDA, MCP, Virtuals, A2A, ERC-8004).",
        "Help users compare agents and make informed decisions.",
    ],
    markdown=True,
    show_tool_calls=True,
)


def main():
    """Run the agent discovery assistant."""
    print("=" * 60)
    print("AI Agent Discovery Assistant")
    print("Powered by Registry Broker - Universal AI Agent Index")
    print("=" * 60)
    print("\nI can help you discover AI agents across multiple registries:")
    print("- NANDA (MIT Network for AI Networked Digital Agents)")
    print("- MCP (Model Context Protocol servers)")
    print("- Virtuals Protocol agents")
    print("- A2A (Agent-to-Agent protocol)")
    print("- ERC-8004 on-chain agents")
    print("\nExample queries:")
    print('- "Find code review agents"')
    print('- "Show me trading bots on Virtuals"')
    print('- "What MCP servers are available for databases?"')
    print('- "Compare similar agents to [agent name]"')
    print("\nType 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            if not user_input:
                continue

            response = agent.run(user_input)
            print(f"\nAssistant: {response.content}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
