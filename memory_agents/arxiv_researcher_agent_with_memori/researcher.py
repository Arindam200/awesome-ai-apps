from pathlib import Path
import os

from agents import Agent, Runner, function_tool,  AsyncOpenAI, OpenAIChatCompletionsModel
from datetime import datetime
from dotenv import load_dotenv
from memori import Memori, create_memory_tool
from pydantic import BaseModel
from tavily import TavilyClient
from textwrap import dedent
import asyncio
load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")
if not api_key:
    raise ValueError("NEBIUS_API_KEY is not set in the environment variables")

# Get model name and base URL from environment variables with defaults
model_name = os.getenv("EXAMPLE_MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct")
base_url = os.getenv("EXAMPLE_BASE_URL", "https://api.studio.nebius.ai/v1")

model = OpenAIChatCompletionsModel(
    model=model_name,
    openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key)
)

# Create tmp directory for saving reports
cwd = Path(__file__).parent.resolve()
tmp = cwd.joinpath("tmp")
if not tmp.exists():
    tmp.mkdir(exist_ok=True, parents=True)

today = datetime.now().strftime("%Y-%m-%d")

class ArxivSearchResult(BaseModel):
    """Result model for arXiv search operations"""
    query: str
    results: str
    found_papers: bool

class MemorySearchResult(BaseModel):
    """Result model for memory search operations"""
    query: str
    results: str
    found_memories: bool

# Global variables to store the researcher instance for tool functions
_researcher_instance = None

@function_tool
def search_memory(query: str) -> MemorySearchResult:
    """Search the agent's memory for past conversations and research information.

    Args:
        query: What to search for in memory (e.g., "past research on AI", "findings on quantum computing")

    Returns:
        MemorySearchResult: Search results from the agent's memory
    """
    global _researcher_instance
    if _researcher_instance is None:
        return MemorySearchResult(
            query=query,
            results="Memory system not initialized",
            found_memories=False
        )

    try:
        if not query.strip():
            return MemorySearchResult(
                query=query,
                results="Please provide a search query",
                found_memories=False
            )

        result = _researcher_instance.memory_tool.execute(query=query.strip())
        found_memories = bool(
            result
            and "No relevant memories found" not in result
            and "Error" not in result
        )

        return MemorySearchResult(
            query=query,
            results=result if result else "No relevant memories found",
            found_memories=found_memories
        )

    except Exception as e:
        return MemorySearchResult(
            query=query,
            results=f"Memory search error: {str(e)}",
            found_memories=False
        )

@function_tool
def search_arxiv(query: str) -> ArxivSearchResult:
    """Search for research papers on arXiv related to the given topic.

    Args:
        query: Research topic to search for (e.g., "quantum computing", "machine learning", "neuroscience")

    Returns:
        ArxivSearchResult: Search results from arXiv with paper details
    """
    global _researcher_instance
    if _researcher_instance is None:
        return ArxivSearchResult(
            query=query,
            results="Research system not initialized",
            found_papers=False
        )

    try:
        if not query.strip():
            return ArxivSearchResult(
                query=query,
                results="Please provide a research topic to search for",
                found_papers=False
            )

        # Use Tavily to search for arXiv papers on the topic
        search_query = f"arXiv research papers {query} latest developments academic research"

        # Perform the search using Tavily
        search_result = _researcher_instance.tavily_client.search(
            query=search_query,
            search_depth="advanced",
            include_domains=["arxiv.org", "scholar.google.com", "researchgate.net"],
            max_results=10
        )

        if not search_result.get("results"):
            return ArxivSearchResult(
                query=query,
                results=f"No arXiv papers found for: {query}",
                found_papers=False
            )

        # Process and format the results
        papers = []
        for result in search_result["results"][:5]:  # Limit to top 5 results
            title = result.get("title", "No title available")
            url = result.get("url", "")
            content = result.get("content", "")

            # Extract key information
            paper_info = {
                "title": title,
                "url": url,
                "summary": content[:200] + "..." if len(content) > 200 else content
            }
            papers.append(paper_info)

        # Format the results as a structured output
        result_text = f"## arXiv Research Papers for: {query}\n\n"
        result_text += f"Found {len(papers)} relevant research papers:\n\n"

        for i, paper in enumerate(papers, 1):
            result_text += f"### {i}. {paper['title']}\n"
            result_text += f"**URL:** {paper['url']}\n"
            result_text += f"**Summary:** {paper['summary']}\n\n"

        result_text += "---\n"
        result_text += f"*Search performed using Tavily for academic research papers on {query}*"

        return ArxivSearchResult(
            query=query,
            results=result_text,
            found_papers=True
        )

    except Exception as e:
        return ArxivSearchResult(
            query=query,
            results=f"arXiv search error: {str(e)}",
            found_papers=False
        )

class Researcher:
    """A researcher class that manages Memori initialization and agent creation"""

    def __init__(self):
        global _researcher_instance
        _researcher_instance = self

        self.memori = Memori(
            database_connect="sqlite:///research_memori.db",
            conscious_ingest=True,  # Working memory
            auto_ingest=True,  # Dynamic search
            verbose=True,
        )
        self.memori.enable()
        self.memory_tool = create_memory_tool(self.memori)

        # Initialize Tavily client for arXiv search
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        self.research_agent = None
        self.memory_agent = None

    async def run_agent_with_memory(self, agent, user_input: str):
        """Run agent and record the conversation in memory"""
        try:
            # Run the agent with the user input
            result = await Runner.run(agent, input=user_input)

            # Get the response content
            response_content = (
                result.final_output if hasattr(result, "final_output") else str(result)
            )

            # Store the conversation in memory
            self.memori.record_conversation(
                user_input=user_input,
                ai_output=response_content
            )

            return result

        except Exception as e:
            print(f"Agent execution error: {str(e)}")
            raise

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
        """Create a research agent with Memori memory capabilities and arXiv search"""
        agent = Agent(
            name="ArXiv Research Agent",
            model=model,
            instructions=dedent(
                """\
                You are Professor X-1000, a distinguished AI research scientist with MEMORY CAPABILITIES!

                🧠 Your enhanced abilities:
                - Advanced research using arXiv paper search via Tavily
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
                2. Use search_arxiv to find relevant research papers on the topic
                3. Analyze and cross-reference sources for accuracy and relevance
                4. If you find relevant previous research, mention how this builds upon it
                5. Structure your report following academic standards but maintain readability
                6. Include only verifiable facts with proper citations
                7. Create an engaging narrative that guides the reader through complex topics
                8. End with actionable takeaways and future implications

                Always mention if you're building upon previous research sessions!
                Focus on academic research papers and scholarly sources.

                When presenting research findings, structure them clearly with:
                - Key research questions addressed
                - Methodology and approach
                - Main findings and conclusions
                - Implications for the field
                - Future research directions
            """
            ),
            tools=[search_memory, search_arxiv],
        )
        return agent

    def _create_memory_agent(self):
        """Create an agent specialized in retrieving research memories"""
        agent = Agent(
            name="Research Memory Assistant",
            instructions=dedent(
                """\
                You are the Research Memory Assistant, specialized in helping users recall their research history!

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
            tools=[search_memory],
        )
        return agent