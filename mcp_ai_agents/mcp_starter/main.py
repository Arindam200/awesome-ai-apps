import asyncio
import os
from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    set_tracing_disabled,
)
from agents.mcp import  MCPServer, MCPServerStdio
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ["NEBIUS_API_KEY"]
base_url = "https://api.tokenfactory.nebius.com/v1" 
client = AsyncOpenAI(base_url=base_url, api_key=api_key)
set_tracing_disabled(disabled=True)

async def run(mcp_server: MCPServer, repo_url: str):

    parts = repo_url.strip("/").split("/")
    owner = parts[-2] if len(parts) >= 2 else None
    repo = parts[-1] if len(parts) >= 1 else None
    
    if not owner or not repo:
        print("Invalid repository URL. Please provide URL in format: owner/repo")
        return

    agent = Agent(
        name="GitHub Assistant",
        instructions=f"""You are a GitHub repository analyzer for {repo_url}.
        Focus on providing detailed analysis of repository issues and commits.
        For issues, use list_issues with sort='created' and direction='desc' to get the latest issues.
        For commits, use list_commits to get the latest commits.
        When using numeric parameters like per_page, do not include quotes as they should be numbers, not strings.
        Provide detailed explanations of the findings.""",
        mcp_servers=[mcp_server],
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            openai_client=client
        )
    )

    async def run_query(message):
        print("\n" + "-" * 40)
        print(f"Running: {message}")
        result = await Runner.run(starting_agent=agent, input=message)
        print(result.final_output)

    # Updated queries with correct parameter types
    queries = [
        f"""Using list_issues tool, find and analyze the most recent issue in the repository.
        Parameters to use:
        - owner: {owner}
        - repo: {repo}
        - state: 'all'
        - sort: 'created'
        - direction: 'desc'
        - per_page: 1  # Note: This is a number, not a string""",
        
        f"""Using list_commits tool, analyze the most recent commit to the repository.
        Parameters to use:
        - owner: {owner}
        - repo: {repo}
        - per_page: 1  # Note: This is a number, not a string"""
    ]

    for query in queries:
        await run_query(query)

async def main():
    print("GitHub Repository Analysis Tool")
    print("-" * 30)
    repo_url = input("Enter GitHub repository URL (format: owner/repo): ")

    async with MCPServerStdio(
        cache_tools_list=True,
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-github"
            ],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            }
        },
    ) as server:
        try:
            await run(server, repo_url)
        except Exception as e:
            print(f"Error analyzing repository: {e}")

if __name__ == "__main__":

    load_dotenv()
    if not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"):
        raise RuntimeError("GITHUB_PERSONAL_ACCESS_TOKEN not found in environment variables")
    
    set_tracing_disabled(disabled=True)
    asyncio.run(main())