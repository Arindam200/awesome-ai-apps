"""
Lesson 4: Integrating External Tools with MCP

This script demonstrates how to dynamically grant an agent new capabilities
by connecting it to an external tool server using the Multi-Capability
Protocol (MCP).

We will connect to a public MCP server that provides tools for searching
the official AWS documentation, allowing our agent to answer questions
about AWS services with up-to-date information.
"""

import os
from dotenv import load_dotenv
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands.tools.mcp import MCPClient

load_dotenv()

# Validate API key
nebius_api_key = os.getenv("NEBIUS_API_KEY")
if not nebius_api_key:
    raise ValueError("NEBIUS_API_KEY environment variable is required")

# Configure the language model
model = LiteLLMModel(
    client_args={"api_key": nebius_api_key},
    model_id="nebius/deepseek-ai/DeepSeek-V3-0324",
)

# Set up MCP client to connect to AWS documentation server
mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"]
        )
    )
)

# Create agent with AWS documentation tools
with mcp_client:
    aws_tools = mcp_client.list_tools_sync()
    print(f"Successfully loaded {len(aws_tools)} tools from the MCP server.")

    agent = Agent(
        model=model,
        tools=aws_tools,
        system_prompt=(
            "You are an expert on Amazon Web Services. "
            "Use the provided tools to answer questions about AWS services "
            "based on the official documentation. Always provide accurate, "
            "up-to-date information from the AWS docs."
        ),
    )

    # Query the agent
    user_query = "What is the maximum invocation payload size for AWS Lambda?"
    print("\n--- Querying AWS Documentation ---")
    print(f"User Query: {user_query}\n")

    response = agent(user_query)

    print("--- Agent Response ---")
    print(response)