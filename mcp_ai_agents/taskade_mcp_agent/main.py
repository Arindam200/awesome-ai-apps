import asyncio
import os
import streamlit as st
from textwrap import dedent
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from agno.models.nebius import Nebius
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

# Page config
st.set_page_config(
    page_title="Taskade MCP Agent",
    page_icon="https://taskade.com/favicon.ico",
    layout="wide",
)

# Title and description
st.title("Taskade MCP Agent")
st.markdown(
    "Manage your [Taskade](https://taskade.com) workspace with natural language "
    "using the [Model Context Protocol](https://github.com/taskade/mcp)."
)

# Sidebar for API keys
with st.sidebar:
    st.header("Configuration")

    nebius_key = st.text_input("Nebius API Key", type="password")
    if nebius_key:
        os.environ["NEBIUS_API_KEY"] = nebius_key

    st.divider()

    taskade_key = st.text_input(
        "Taskade API Key",
        type="password",
        help="Generate at https://taskade.com/settings/api",
    )
    if taskade_key:
        os.environ["TASKADE_API_KEY"] = taskade_key

    if st.button("Save Configuration"):
        if nebius_key and taskade_key:
            st.success("Configuration saved!")
        else:
            st.warning("Please enter both API keys.")

    st.divider()
    st.markdown(
        "**Resources**\n"
        "- [Taskade](https://taskade.com)\n"
        "- [Taskade MCP Server](https://github.com/taskade/mcp)\n"
        "- [Taskade AI Agents](https://taskade.com/agents)\n"
    )

# Query type selector
col1, col2 = st.columns([3, 1])
with col1:
    query_type = st.selectbox(
        "Query Type",
        [
            "List Projects",
            "Project Details",
            "Create Task",
            "Manage Tasks",
            "Custom",
        ],
    )
with col2:
    st.markdown("")  # Spacer

# Predefined query templates
templates = {
    "List Projects": "List all my Taskade projects and their status",
    "Project Details": "Show me the details and tasks for my most recent project",
    "Create Task": "Create a new task in my project",
    "Manage Tasks": "Show all incomplete tasks across my projects",
    "Custom": "",
}

query = st.text_area(
    "Your Query",
    value=templates.get(query_type, ""),
    placeholder="What would you like to do in your Taskade workspace?",
)


async def run_taskade_agent(message: str) -> str:
    """Run the Taskade MCP agent with the given message."""
    taskade_api_key = os.getenv("TASKADE_API_KEY")
    nebius_api_key = os.getenv("NEBIUS_API_KEY")

    if not taskade_api_key:
        return "Error: Taskade API key not provided. Please enter it in the sidebar."
    if not nebius_api_key:
        return "Error: Nebius API key not provided. Please enter it in the sidebar."

    try:
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@taskade/mcp-server"],
            env={
                "TASKADE_API_KEY": taskade_api_key,
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                mcp_tools = MCPTools(session=session)
                await mcp_tools.initialize()

                agent = Agent(
                    tools=[mcp_tools],
                    instructions=dedent("""\
                        You are a Taskade workspace assistant. Help users manage
                        their projects, tasks, and workflows on Taskade.

                        - Provide organized, concise information about projects and tasks
                        - Use markdown formatting and tables for readability
                        - When listing tasks, include their status and any due dates
                        - For project operations, confirm actions before making changes
                        - Include links to Taskade resources when helpful
                        - Be helpful and proactive in suggesting workspace improvements
                    """),
                    markdown=True,
                    show_tool_calls=True,
                    model=Nebius(
                        id="Qwen/Qwen3-30B-A3B",
                        api_key=nebius_api_key,
                    ),
                )

                response = await agent.arun(message)
                return response.content

    except Exception as e:
        return f"Error: {str(e)}"


# Run button
if st.button("Run Query", type="primary", use_container_width=True):
    if not os.getenv("TASKADE_API_KEY"):
        st.error("Please enter your Taskade API key in the sidebar.")
    elif not os.getenv("NEBIUS_API_KEY"):
        st.error("Please enter your Nebius API key in the sidebar.")
    elif not query:
        st.error("Please enter a query.")
    else:
        with st.spinner("Connecting to Taskade..."):
            try:
                result = asyncio.run(run_taskade_agent(query))
                st.markdown("### Results")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
