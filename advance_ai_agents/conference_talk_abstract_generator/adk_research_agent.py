import os
import io
import asyncio
from datetime import datetime, timedelta

# Google ADK and LLM Imports
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

# Google GenAI types
from google.genai import types

# Tool client imports
from exa_py import Exa
from tavily import TavilyClient
from linkup import LinkupClient

nebius_model = LiteLlm(
    model="nebius/Qwen/Qwen3-235B-A22B",
    api_base=os.getenv("NEBIUS_API_BASE"),
    api_key=os.getenv("NEBIUS_API_KEY")
)
# --- Tool Definitions (Adapted to accept a dynamic topic) ---

def exa_search_ai(topic: str) -> dict:
    """Performs a search using the Exa API based on the provided topic."""
    try:
        exa_client = Exa(api_key=os.getenv("EXA_API_KEY"))
        results = exa_client.search_and_contents(
            query=f"Latest developments, discussions, and news about {topic}",
            num_results=5,
            text=True,
            type="auto",
            highlights={"highlights_per_url": 2, "num_sentences": 3},
            start_published_date=(datetime.now() - timedelta(days=90)).isoformat()
        )
        return {"type": "exa", "results": [r.__dict__ for r in results.results]}
    except Exception as e:
        return {"type": "exa", "results": [], "error": f"Exa search failed: {str(e)}"}

def tavily_search_ai_analysis(topic: str) -> dict:
    """Performs a search on social platforms using the Tavily API."""
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query=f"Recent community sentiment, technical questions, and debates about {topic}",
            search_depth="advanced",
            time_range="month",
            include_domains=["x.com", "reddit.com", "dev.to"]
        )
        return {"type": "tavily", "results": response.get("results", [])}
    except Exception as e:
        return {"type": "tavily", "results": [], "error": f"Tavily search failed: {str(e)}"}

def linkup_search_ai(topic: str) -> dict:
    """Performs a deep search on technical sites using the Linkup API."""
    try:
        client = LinkupClient(api_key=os.getenv("LINKUP_API_KEY"))
        search_response = client.search(
            query=f"In-depth technical articles, code repositories, and best practices on {topic}",
            depth="deep",
            output_type="searchResults",
            include_domains=["https://ycombinator.com/", "https://github.com", "https://stackoverflow.com"]
        )
        results = search_response.results if hasattr(search_response, 'results') else []
        return {"type": "linkup", "results": [r.__dict__ for r in results]}
    except Exception as e:
        return {"type": "linkup", "results": [], "error": str(e)}

# --- Main Runnable Function ---

def run_adk_research(topic: str) -> str:
    """
    Runs the full ADK pipeline for a given topic and returns the final analysis.
    """
    # Define models (replace with your actual model initialization)
    nebius_base_model = LiteLlm(
        model="nebius/Qwen/Qwen3-235B-A22B",
        api_base=os.getenv("NEBIUS_API_BASE"),
        api_key=os.getenv("NEBIUS_API_KEY")
    )
    analysis_llm = LiteLlm(
        model="nebius/Qwen/Qwen3-235B-A22B", # Using a powerful model for final analysis
        api_base=os.getenv("NEBIUS_API_BASE"),
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    # --- Agent Definitions (with dynamic instructions) ---
    # These agents perform the research in parallel.

    exa_agent = LlmAgent(
        name="ExaAgent", model=nebius_base_model,
        instruction=f"Use the exa_search_ai tool to fetch the latest news and developments about '{topic}'.",
        tools=[exa_search_ai], output_key="exa_results"
    )

    tavily_agent = LlmAgent(
        name="TavilyAgent", model=nebius_base_model,
        instruction=f"Use the tavily_search_ai_analysis tool to understand community sentiment about '{topic}' from X.com and Reddit.",
        tools=[tavily_search_ai_analysis], output_key="tavily_results"
    )

    linkup_agent = LlmAgent(
        name="LinkupAgent", model=nebius_base_model,
        instruction=f"Use the linkup_search_ai tool to find technical deep-dives and code for '{topic}' from YCombinator and Github.",
        tools=[linkup_search_ai], output_key="linkup_results"
    )

    # # This agent synthesizes the parallel search results.
    # summary_agent = LlmAgent(
    #     name="SummaryAgent", model=nebius_base_model,
    #     instruction="""You are a meticulous research summarizer. Combine the information from 'exa_results', 
    #     'tavily_results', and 'linkup_results' into a single, coherent summary. Focus on the latest trends, 
    #     key talking points, important code repositories, and any emerging technologies related to the topic.
    #     Use markdown for clear formatting.""",
    #     output_key="final_summary"
    # )

      # This agent synthesizes the parallel search results.
    summary_agent = LlmAgent(
        name="SummaryAgent", model=nebius_base_model,
        instruction="""You are a meticulous research summarizer. Combine the information from 'exa_results' into a single, coherent summary. Focus on the latest trends, 
        key talking points, important code repositories, and any emerging technologies related to the topic.
        Use markdown for clear formatting.""",
        output_key="final_summary"
    )
    
    # This final agent provides the actionable insights we need.
    analysis_agent = LlmAgent(
        name="AnalysisAgent", model=analysis_llm,
        instruction=f"""As an expert AI analyst, your task is to provide actionable insights about the topic: '{topic}'.
        Analyze the 'final_summary' and, if necessary, the raw data from the preceding tool calls.
        Your output should be a well-structured analysis that identifies:
        1.  **Key Trends:** What are the 2-3 most important current trends?
        2.  **Novel Angles:** What are some surprising or unique perspectives?
        3.  **Potential Gaps:** What questions are people asking that aren't being fully answered?
        4.  **Contrarian Viewpoints:** Are there any interesting debates or disagreements?
        This analysis will be used to brainstorm a unique conference talk proposal. Structure your response clearly.""",
        output_key="final_analysis"
    )

    # --- Orchestrator Definition ---
    # parallel_search_agent = ParallelAgent(
    #     name="ParallelSearchAgent",
    #     sub_agents=[exa_agent, tavily_agent, linkup_agent]
    # )

    parallel_search_agent = ParallelAgent(
        name="ParallelSearchAgent",
        sub_agents=[exa_agent]
    )

    # pipeline = SequentialAgent(
    #     name="AIPipelineAgent",
    #     sub_agents=[parallel_search_agent, summary_agent, analysis_agent]
    # )

    pipeline = SequentialAgent(
        name="AIPipelineAgent",
        sub_agents=[parallel_search_agent, summary_agent]
    )

    # --- Runner Setup & Execution ---
    APP_NAME = "adk_research_app"
    USER_ID = "streamlit_user"
    SESSION_ID = f"session_{datetime.now().strftime('%Y%m%d%H%M%S%f')}" # Use microseconds for uniqueness

    session_service = InMemorySessionService()
    # Create session synchronously if needed
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID))
        loop.close()
    except:
        # Fallback for synchronous session creation
        pass
    
    runner = Runner(agent=pipeline, app_name=APP_NAME, session_service=session_service)

    content = types.Content(role="user", parts=[types.Part(text=f"Start analysis for {topic}")])
    # Note: If your ADK version uses async, you would 'await runner.run(...)'
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
    
    final_result = "ADK research agent failed to produce a final analysis."
    for event in events:
        if event.is_final_response():
            final_result = event.content.parts[0].text

    return final_result