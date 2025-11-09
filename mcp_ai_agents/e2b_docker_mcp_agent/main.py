import os
import asyncio
import dotenv

dotenv.load_dotenv()

from e2b import Sandbox
from e2b.sandbox.mcp import GithubOfficial, Notion, McpServer
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
from openai import AsyncOpenAI


api_key = os.getenv("NEBIUS_API_KEY")
if not api_key:
    raise ValueError("NEBIUS_API_KEY is not set in the environment variables")

# Get model name and base URL from environment variables with defaults
model_name = os.getenv("EXAMPLE_MODEL_NAME", "moonshotai/Kimi-K2-Instruct")
base_url = os.getenv("EXAMPLE_BASE_URL", "https://api.tokenfactory.nebius.com/v1")

model = OpenAIChatCompletionsModel(
    model=model_name,
    openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key)
)

async def main():
    # Get required environment variables
    openai_api_key = os.environ["OPENAI_API_KEY"].strip()
    notion_api_key = os.environ["NOTION_TOKEN"].strip()
    github_token = os.environ["GITHUB_TOKEN"].strip()
    
    # Ensure the OpenAI API key is set in the environment for the agents SDK
    os.environ["OPENAI_API_KEY"] = openai_api_key
    
    print(f"OpenAI API Key loaded: {openai_api_key[:20]}... (length: {len(openai_api_key)})")

    # Create sandbox with MCP servers configured
    notion = Notion(internalIntegrationToken=notion_api_key)
    github = GithubOfficial(githubPersonalAccessToken=github_token)
    mcp_servers = McpServer(notion=notion, githubOfficial=github)

    sandbox = Sandbox.beta_create(
        envs={"OPENAI_API_KEY": openai_api_key}, mcp=mcp_servers, timeout=600
    )

    # Get MCP connection details
    mcp_url = sandbox.beta_get_mcp_url()
    mcp_token = sandbox.beta_get_mcp_token()

    print(f"MCP Gateway URL: {mcp_url}")
    print(f"MCP Token: {mcp_token[:20]}...")

    # Connect to the E2B MCP Gateway using OpenAI Agents SDK
    try:
        async with MCPServerStreamableHttp(
            name="E2B MCP Gateway",
            params={
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {mcp_token}"},
                "timeout": 180,
            },
            cache_tools_list=True,
            max_retry_attempts=2,
        ) as server:
            # List available tools
            tools = await server.list_tools()
            print(f"\nAvailable tools ({len(tools)}):")
            for tool in tools[:10]:  # Show first 10 tools
                print(f"  - {tool.name}: {tool.description[:80] if tool.description else 'No description'}...")

            # Create an agent with access to the MCP servers
            agent = Agent(
                model=model,
                name="GitHub and Notion Assistant",
                instructions="""
                You are a helpful assistant with access to GitHub and Notion MCP servers.
                
                When creating Notion pages:
                1. First search for available parent pages using notion-search_pages
                2. Use simple text content for page children - just use "paragraph" type with plain text
                3. Keep the content structure simple and valid according to Notion's API
                4. If you encounter formatting errors, try again with simpler formatting
                
                When working with GitHub:
                1. List repositories and get their details
                2. Sort by stars to find the most popular ones
                
                Always be clear about what you're doing and provide informative responses.
                """,
                mcp_servers=[server],
            )

            # Run task using the agent
            task = """
            Use the GitHub MCP server to list my repositories,
            then use the Notion MCP server to create a page summarizing the top 3 repositories by stars.
            
            For the Notion page:
            - Search for an available parent page to attach it to
            - Create a simple page with a title like "Top GitHub Repositories"
            - Add paragraph blocks with simple text describing each repository (name, stars, description)
            - Keep the formatting simple to avoid API errors
            """

            print(f"\nRunning task: {task}\n")
            print("=" * 80)

            result = await Runner.run(agent, task)

            print("\n" + "=" * 80)
            print("\nAgent Result:")
            print(result.final_output)
            
            # Display usage statistics if available
            if hasattr(result, 'usage') and result.usage:
                print(f"\nUsage: {result.usage}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up sandbox
        try:
            sandbox.kill()
            print("\nSandbox terminated.")
        except Exception as e:
            print(f"Warning: Error terminating sandbox: {e}")


if __name__ == "__main__":
    asyncio.run(main())
