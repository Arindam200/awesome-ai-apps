import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from textwrap import dedent
import asyncio
load_dotenv()
async def run_gibsonai_agent(message: str):
    """Run the GibsonAI agent with the given message."""
    mcp_tools = MCPTools(
        "uvx --from gibson-cli@latest gibson mcp run",
        timeout_seconds=300,  # Extended timeout for GibsonAI operations
    )

    # Connect to the MCP server
    await mcp_tools.connect()

    agent = Agent(
        name="GibsonAIAgent",
        model=Nebius(
            id="meta-llama/Meta-Llama-3.1-70B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY")  # Explicitly pass the API key
        ),
        tools=[mcp_tools],
        description="Agent for managing database projects and schemas",
        instructions=dedent("""\
            You are a GibsonAI database assistant. Help users manage their database projects and schemas.

            Your capabilities include:
            - Creating new GibsonAI projects
            - Managing database schemas (tables, columns, relationships)
            - Deploying schema changes to hosted databases
            - Querying database schemas and data
            - Providing insights about database structure and best practices
        """),
        markdown=True,
        show_tool_calls=True,
    )

    # Run the agent
    await agent.aprint_response(message, stream=True)

    # Close the MCP connection
    await mcp_tools.close()


# Example usage
if __name__ == "__main__":
    asyncio.run(
        run_gibsonai_agent(
            """
            Create a new GibsonAI project for my Blog Application.
            You can decide the schema of the tables without double checking with me.
            """
        )
    )