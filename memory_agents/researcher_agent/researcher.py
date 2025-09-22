from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List

from pydantic_ai import Agent, RunContext, Tool
from pydantic import BaseModel
from linkup import LinkupClient
from dotenv import load_dotenv
import os

from memori import Memori, create_memory_tool

# Load environment variables
load_dotenv()

# Create tmp directory for saving reports
cwd = Path(__file__).parent.resolve()
tmp = cwd.joinpath("tmp")
if not tmp.exists():
    tmp.mkdir(exist_ok=True, parents=True)

today = datetime.now().strftime("%Y-%m-%d")


class SearchResult(BaseModel):
    """Structure for search results"""

    content: str
    source: str
    url: str = ""


class LinkupSearchTool:
    """Linkup search integration for PydanticAI"""

    def __init__(self, api_key: str):
        self.client = LinkupClient(api_key=api_key)

    def search(self, query: str, depth: str = "deep") -> str:
        """Search using Linkup API

        Args:
            query: The search query
            depth: Search depth ("deep" for comprehensive results)
        """
        try:
            response = self.client.search(
                query=query,
                depth=depth,
                output_type="sourcedAnswer",
                include_images=False,
            )

            # Format the response for the agent
            if hasattr(response, "answer"):
                return f"Search Results for '{query}':\n{response.answer}"
            elif isinstance(response, dict) and "answer" in response:
                return f"Search Results for '{query}':\n{response['answer']}"
            else:
                return f"Search Results for '{query}':\n{str(response)}"

        except Exception as e:
            return f"Search error for '{query}': {str(e)}"


# Dependencies for the agents
class ResearchDeps:
    def __init__(self, linkup_tool, memory_tool):
        self.linkup_tool = linkup_tool
        self.memory_tool = memory_tool


class MemoryDeps:
    def __init__(self, memory_tool):
        self.memory_tool = memory_tool


# Define tool functions OUTSIDE the class
async def web_search_tool(ctx: RunContext[ResearchDeps], query: str) -> str:
    """Search the web for current information using Linkup

    Args:
        query: The search query to find current information
    """
    return ctx.deps.linkup_tool.search(query)


async def research_memory_search_tool(ctx: RunContext[ResearchDeps], query: str) -> str:
    """Search the agent's memory for past conversations and research information.

    Args:
        query: What to search for in memory (e.g., "past research on AI", "findings on quantum computing")
    """
    try:
        if not query.strip():
            return "Please provide a search query"

        result = ctx.deps.memory_tool.execute(query=query.strip())

        if result and str(result).strip():
            return str(result)
        else:
            return f"No specific memories found for '{query}'. You might try broader search terms or continue our conversation to build more searchable memories."

    except Exception as e:
        return f"Memory search error: {str(e)}"


async def memory_agent_search_tool(ctx: RunContext[MemoryDeps], query: str) -> str:
    """Search the agent's memory for past conversations and research information.

    Args:
        query: What to search for in memory (e.g., "past research on AI", "findings on quantum computing")
    """
    try:
        if not query.strip():
            return "Please provide a search query"

        result = ctx.deps.memory_tool.execute(query=query.strip())

        if result and str(result).strip():
            return str(result)
        else:
            return f"No specific memories found for '{query}'. The search was performed but no matching content was located in the memory database. You might try broader terms or different keywords."

    except Exception as e:
        return f"Memory search error: {str(e)}"


class Researcher:
    """A researcher class that manages Memori initialization and agent creation"""

    def __init__(self):
        self.memori = Memori(
            database_connect="sqlite:///research_memori.db",  # Using correct database
            conscious_ingest=True,  # Working memory
            auto_ingest=True,  # Dynamic search
            verbose=True,
        )
        self.memori.enable()
        self.memory_tool = create_memory_tool(self.memori)

        # Initialize Linkup client
        linkup_api_key = os.getenv("LINKUP_API_KEY")
        if not linkup_api_key:
            raise RuntimeError(
                "LINKUP_API_KEY is not set. Provide it via environment variable or the app sidebar."
            )
        self.linkup_tool = LinkupSearchTool(api_key=linkup_api_key)

        self.research_agent = None
        self.memory_agent = None
        self.research_agent_deps = None
        self.memory_agent_deps = None

    def define_agents(self):
        """Define and create research and memory agents"""
        # Create research agent
        self.research_agent = self._create_research_agent()

        # Create memory agent
        self.memory_agent = self._create_memory_agent()

        return self.research_agent, self.memory_agent

    def get_research_agent(self):
        """Get the research agent, creating it if necessary"""
        if self.research_agent is None:
            self.define_agents()
        return self.research_agent

    def get_memory_agent(self):
        """Get the memory agent, creating it if necessary"""
        if self.memory_agent is None:
            self.define_agents()
        return self.memory_agent

    def _create_research_agent(self):
        """Create a research agent with Memori memory capabilities and Linkup search"""

        # Create dependencies
        self.research_agent_deps = ResearchDeps(self.linkup_tool, self.memory_tool)

        # Create agent with tools registered via tools parameter
        agent = Agent(
            "openai:gpt-4o",
            deps_type=ResearchDeps,
            tools=[
                Tool(web_search_tool, name="web_search"),
                Tool(research_memory_search_tool, name="search_memory"),
            ],
            system_prompt=dedent(
                """\
                You are Professor X-1000, a distinguished AI research scientist with MEMORY CAPABILITIES!

                🧠 Your enhanced abilities:
                - Advanced research using real-time web search via Linkup
                - Persistent memory of all research sessions
                - Ability to reference and build upon previous research
                - Creating comprehensive, fact-based research reports

                Your writing style is:
                - Clear and authoritative
                - Engaging but professional
                - Fact-focused with proper citations
                - Accessible to educated non-specialists
                - Builds upon previous research when relevant

                RESEARCH WORKFLOW:
                1. FIRST: Use search_memory to find any related previous research on this topic
                2. Run 3 distinct web searches to gather comprehensive current information
                3. Analyze and cross-reference sources for accuracy and relevance
                4. If you find relevant previous research, mention how this builds upon it
                5. Structure your report following academic standards but maintain readability
                6. Include only verifiable facts with proper citations
                7. Create an engaging narrative that guides the reader through complex topics
                8. End with actionable takeaways and future implications

                Always mention if you're building upon previous research sessions!
                """
            ),
        )

        return agent

    def _create_memory_agent(self):
        """Create an agent specialized in retrieving research memories"""

        # Create dependencies
        self.memory_agent_deps = MemoryDeps(self.memory_tool)

        # Create agent with tools registered via tools parameter
        agent = Agent(
            "openai:gpt-4o",
            deps_type=MemoryDeps,
            tools=[Tool(memory_agent_search_tool, name="search_memory")],
            system_prompt=dedent(
                """\
                You are the Research Memory Assistant, specialized in helping users recall their research history!

                When you search memory and find results, provide a clear summary of what was found.

                When no specific results are found:
                1. Acknowledge that no direct matches were found for their query
                2. Suggest broader search terms they could try
                3. Offer to search for general topics that might be related
                4. Be helpful and encouraging about building their research memory over time

                🧠 Your capabilities:
                - Search through all past research sessions
                - Summarize previous research topics and findings
                - Help users find specific research they've done before
                - Connect related research across different sessions

                Your style:
                - Friendly and helpful
                - Organized and clear in presenting research history
                - Good at summarizing complex research into digestible insights

                When users ask about their research history:
                1. Use search_memory to find relevant past research
                2. Organize the results chronologically or by topic
                3. Provide clear summaries of each research session
                4. Highlight key findings and connections between research
                5. If they ask for specific research, provide detailed information

                Always search memory first, then provide organized, helpful summaries!
                """
            ),
        )

        return agent

    async def run_research_agent(self, user_input: str):
        """Run research agent with dependencies"""
        if self.research_agent is None:
            self.define_agents()
        return await self.run_agent_with_memory_deps(
            self.research_agent, self.research_agent_deps, user_input
        )

    async def run_memory_agent(self, user_input: str):
        """Run memory agent with dependencies"""
        if self.memory_agent is None:
            self.define_agents()
        return await self.run_agent_with_memory_deps(
            self.memory_agent, self.memory_agent_deps, user_input
        )

    async def run_agent_with_memory_deps(self, agent, deps, user_input: str):
        """Run agent with dependencies and record the conversation to memory"""
        try:
            # Run the agent with dependencies
            result = await agent.run(user_input, deps=deps)

            # Record this conversation step
            try:
                self.memori.record_conversation(
                    user_input=user_input,
                    ai_output=(
                        result.output if hasattr(result, "output") else str(result)
                    ),
                )
            except Exception as e:
                print(f"Memory recording error: {str(e)}")

            return result

        except Exception as e:
            print(f"Agent execution error: {str(e)}")
            raise

    # Legacy sync method for backward compatibility
    def run_agent_with_memory(self, agent, user_input: str):
        """Run agent and record the conversation to memory (DEPRECATED - use async version)"""
        try:
            # Run the agent
            result = agent.run_sync(user_input)

            # Record this conversation step
            try:
                self.memori.record_conversation(
                    user_input=user_input,
                    ai_output=(
                        result.content
                        if hasattr(result, "content")
                        else str(result.output)
                    ),
                )
            except Exception as e:
                print(f"Memory recording error: {str(e)}")

            return result

        except Exception as e:
            print(f"Agent execution error: {str(e)}")
            raise
