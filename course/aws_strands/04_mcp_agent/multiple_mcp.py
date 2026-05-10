"""
Multiple MCP Servers Integration Example

This script demonstrates how to connect an agent to multiple MCP servers
simultaneously, combining their tools to create a more powerful agent.

In this example, we connect to:
1. Exa AI Search MCP server - for web search capabilities
2. Airbnb MCP server - for accommodation search capabilities

The agent can then use tools from both servers to answer complex queries
that require both web search and accommodation data.
"""

from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands.tools.mcp import MCPClient
import os
from dotenv import load_dotenv

load_dotenv()

# Validate required API keys
nebius_api_key = os.getenv("NEBIUS_API_KEY")
exa_api_key = os.getenv("EXA_API_KEY")

if not nebius_api_key:
    raise ValueError("NEBIUS_API_KEY environment variable is required")
if not exa_api_key:
    raise ValueError("EXA_API_KEY environment variable is required")

# Configure the language model
model = LiteLLMModel(
    client_args={"api_key": nebius_api_key},
    model_id="nebius/deepseek-ai/DeepSeek-V3-0324",
)

# Set up the Exa AI web search MCP client
web_search_mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="npx",
            args=["-y", "mcp-remote", "https://mcp.exa.ai/mcp"],
            env={"EXA_API_KEY": exa_api_key},
        )
    )
)

# Set up the Airbnb MCP client
airbnb_mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="npx",
            args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
        )
    )
)

# Use both servers together and create agent
with web_search_mcp_client, airbnb_mcp_client:
    # Combine tools from both servers
    web_search_tools = web_search_mcp_client.list_tools_sync()
    airbnb_tools = airbnb_mcp_client.list_tools_sync()
    all_tools = web_search_tools + airbnb_tools

    print(f"Loaded {len(web_search_tools)} web search tools")
    print(f"Loaded {len(airbnb_tools)} Airbnb tools")
    print(f"Total tools available: {len(all_tools)}")

    # Create agent with all tools from both servers
    agent = Agent(
        tools=all_tools,
        model=model,
        system_prompt=(
            "You are a helpful travel assistant with access to both web search "
            "and accommodation search capabilities. Use the appropriate tools "
            "to help users find information and plan their travels."
        ),
    )

    # Query the agent
    user_query = "What's the fastest way to get to Barcelona from London?"
    print(f"\n--- Querying with Multiple MCP Servers ---")
    print(f"User Query: {user_query}\n")

    response = agent(user_query)

    print("--- Agent Response ---")
    print(response)

    user_query_2 = "Find rooms in Barcelona for 2 people for 2 nights?"
    print(f"\n--- Querying with Multiple MCP Servers ---")
    print(f"User Query: {user_query_2}\n")

    response = agent(user_query_2)

    print("--- Agent Response ---")
    print(response)