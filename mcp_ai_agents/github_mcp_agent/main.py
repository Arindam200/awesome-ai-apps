import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from textwrap import dedent
import asyncio
import base64
import streamlit as st
load_dotenv()


# Page config
st.set_page_config(page_title="GitHub MCP Agent", page_icon="🦑", layout="wide")

# Load logo and prepare title
try:
    with open("./assets/agno.png", "rb") as agno_file:
        agno_base64 = base64.b64encode(agno_file.read()).decode()
except FileNotFoundError:
    st.error("Logo file not found. Please check that ./assets/agno.png exists.")
    agno_base64 = ""

# Title and description
title_html = f"""
<div style="display: flex; align-items: center; gap: 0px; margin: 0; padding: 0;">
    <h1 style="margin: 0; padding: 0;">
    GitHub MCP Agent with
    <img src="data:image/png;base64,{agno_base64}" style="height: 70px; margin: 0; padding: 0;color: #FF4500;"/>
    </h1>
</div>
"""

st.markdown(title_html, unsafe_allow_html=True)
st.markdown("Explore GitHub repositories with natural language using the Model Context Protocol")

# Setup sidebar for API key
with st.sidebar:
    st.image("./assets/Nebius.png", width=150)

        # API key input
    api_key = st.text_input("Enter your Nebius API key", type="password")

    if api_key:
        os.environ["NEBIUS_API_KEY"] = api_key

    st.divider()

    st.header("🔑 Authentication")
    github_token = st.text_input("GitHub Token", type="password", help="Create a token with repo scope at github.com/settings/tokens")

    if github_token:
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
    st.markdown("---")



# Query input
col1, col2 = st.columns([3, 1])
with col1:
    repo = st.text_input("Repository", value="Arindam200/awesome-ai-apps", help="Format: owner/repo")
with col2:
    query_type = st.selectbox("Query Type", [
        "Info", "Issues", "Pull Requests", "Repository Activity", "Custom"
    ])

# Create predefined queries based on type
if query_type == "Info":
    query_template = f"Tell me all about {repo}"
elif query_type == "Issues":
    query_template = f"Find recent issues in {repo}"
elif query_type == "Pull Requests":
    query_template = f"Show me recent merged PRs in {repo}"
elif query_type == "Repository Activity":
    query_template = f"Analyze code quality trends in {repo}"
else:
    query_template = ""

query = st.text_area("Your Query", value=query_template,
                     placeholder="What would you like to know about this repository?")

# Main function to run agent
async def run_github_agent(message):
    if not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"):
        return "Error: GitHub token not provided"
    if not api_key:
        return "Error: Nebius API key not provided"

    # …rest of your implementation…
    try:
        server_params = StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "ghcr.io/github/github-mcp-server"
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
            }
        )

        # Create client session with proper error handling
        try:
            async with stdio_client(server_params) as (read, write):
                try:
                    async with ClientSession(read, write) as session:
                        # Initialize MCP toolkit
                        mcp_tools = MCPTools(session=session)
                        try:
                            await mcp_tools.initialize()

                            # Create agent
                            agent = Agent(
                                tools=[mcp_tools],
                                instructions=dedent("""\
                                    You are a GitHub assistant. Help users explore repositories and their activity.
                                    - Provide organized, concise insights about the repository
                                    - For Info, Provide Details from the Respositorie's README.md file
                                    - For Issues, Provide Details from the Issues section of the Repository
                                    - For Pull Requests, Provide Details from the Pull Requests section of the Repository
                                    - For Repository Activity, Provide Details from the Repository Activity section of the Repository
                                    - For Custom, Provide Details from the Repository based on the query
                                    - Focus on facts and data from the GitHub API
                                    - Use markdown formatting for better readability
                                    - Present numerical data in tables when appropriate
                                    - Include links to relevant GitHub pages when helpful
                                    - Use Tables for better readability when presenting data like issues, pull requests, etc. also add links to the issues and pull requests
                                    - IMPORTANT: When using MCP tools that require numeric parameters (like pullNumber or page), ensure they are passed as float64 values
                                    - Convert any string numbers to float64 before passing them to MCP tools
                                    - For pagination, use float64 values for page numbers
                                    - For date-related parameters (like 'since' in list_issues), always provide a valid ISO 8601 formatted date string
                                    - When using list_issues, if no specific date is provided, use a default date of 30 days ago in ISO 8601 format
                                    - Never pass nil or null values for required parameters
                                """),
                                markdown=True,
                                show_tool_calls=True,
                                model=Nebius(
                                        id="Qwen/Qwen3-30B-A3B",
                                        api_key=api_key  # Explicitly pass the API key
                                )
                            )

                            # Run agent with error handling
                            try:
                                response = await agent.arun(message)
                                return response.content
                            except Exception as agent_error:
                                return f"Error running agent: {str(agent_error)}"

                        except Exception as init_error:
                            return f"Error initializing MCP tools: {str(init_error)}"

                except Exception as session_error:
                    return f"Error creating client session: {str(session_error)}"

        except Exception as client_error:
            return f"Error creating stdio client: {str(client_error)}"

    except Exception as e:
        return f"Error setting up server parameters: {str(e)}"

# Run button
if st.button("Run Query", type="primary", use_container_width=True):
    if not github_token:
        st.error("Please enter your GitHub token in the sidebar")
    elif not query:
        st.error("Please enter a query")
    else:
        with st.spinner("Analyzing GitHub repository..."):
            try:
                # Ensure the repository is explicitly mentioned in the query
                if repo and repo not in query:
                    full_query = f"{query} in {repo}"
                else:
                    full_query = query

                result = asyncio.run(run_github_agent(full_query))

                # Display results in a nice container
                st.markdown("### Results")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")