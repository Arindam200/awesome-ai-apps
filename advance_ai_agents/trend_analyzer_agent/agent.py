from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import Agent
from datetime import datetime, timedelta
from google.genai import types

from exa_py import Exa
from tavily import TavilyClient
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
api_base = os.getenv("NEBIUS_API_BASE")
api_key = os.getenv("NEBIUS_API_KEY")

# Model configuration
nebius_model = LiteLlm(
    model="openai/meta-llama/Meta-Llama-3.1-8B-Instruct",
    api_base=api_base,
    api_key=api_key
)

# --- Tool 1: Exa Search ---
def exa_search_ai(_: str) -> dict:
    try:
        results = Exa(api_key=os.getenv("EXA_API_KEY")).search_and_contents(
            query="Latest AI news OR new LLM models OR AI/Agents advancements",
            include_domains=["twitter.com", "x.com"],
            num_results=10,
            text=True,
            type="auto",
            highlights={"highlights_per_url": 2, "num_sentences": 3},
            start_published_date=(datetime.now() - timedelta(days=30)).isoformat()
        )
        return {
            "type": "exa",
            "results": [r.__dict__ for r in results.results]
        }
    except Exception as e:
        return {
            "type": "exa",
            "error": f"Exa search failed: {str(e)}",
            "results": []
        }

# --- Tool 2: Tavily Search ---
def tavily_search_ai_analysis(_: str) -> dict:
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query="AI benchmarks OR AI/LLM statistics OR AI providers analysis",
            search_depth="advanced",  # search depth for more comprehensive results
            time_range="week",        # time range one week
            include_domains=["artificialanalysis.ai"]  # Replace with relevant websites
        )
        return {
            "type": "tavily",
            "results": response.get("results", [])
        }
    except Exception as e:
        return {
            "type": "tavily",
            "error": f"Tavily search failed: {str(e)}",
            "results": []
        }

# --- Tool 3: Firecrawl scrapper ---
def firecrawl_scrape_nebius(_: str) -> dict:
    firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    try:
        scrape_result = firecrawl.scrape_url(
            url="https://studio.nebius.com/",
            formats=["markdown"],
            only_main_content=True
        )
        
        if scrape_result.success:
            return {
                "type": "firecrawl",
                "markdown": scrape_result.markdown
            }
        else:
            return {
                "type": "firecrawl",
                "error": "Scraping failed."
            }

    except Exception as e:
        return {
            "type": "firecrawl",
            "error": str(e)
        }

# --- Agent 1: Exa AI News ---
exa_agent = LlmAgent(
    name="ExaAgent",
    model=nebius_model,
    description="Fetches latest AI news, LLMs, and advancements using Exa.",
    instruction="""
       Use the exa_search_ai tool to fetch the latest information about AI, new LLMs, and advancements in the field from Twitter and X.
       Prefix your response with "**🔥ExaAgent:**" to clearly identify your output.
       """,
    tools=[exa_search_ai],
    output_key="exa_results"
)

# --- Agent 2: Tavily AI Analysis ---
tavily_agent = LlmAgent(
    name="TavilyAgent",
    model=nebius_model,
    description="Fetches AI benchmarks, statistics, and analysis using Tavily.",
    instruction="""
    Use the tavily_search_ai_analysis tool to retrieve benchmarks, statistics, and relevant analysis on AI.
    Prefix your response with "**🐳TavilyAgent:**" to clearly identify your output.
    """,
    tools=[tavily_search_ai_analysis],
    output_key="tavily_results"
)

# --- Agent 3: Summary & Formatting ---
summary_agent = LlmAgent(
    name="SummaryAgent",
    model=nebius_model,
    description="Summarizes and formats Exa and Tavily results.",
    instruction="""
You are a summarizer and formatter.
- Combine the information from 'exa_results' (latest AI updates) and 'tavily_results' (AI benchmarks and analysis).
- Present a structured summary, highlighting key trends, new LLMs, and relevant statistics.
- Use markdown formatting for clarity and readability.
- Use emojis like 🚀 for new launches, 📊 for statistics, and 📈 for trends to make the summary more engaging.
- Structure information using bullet points and headings for better organization.
- Prefix your response with "**🍥SummaryAgent:**" to clearly identify your output.
""",
    tools=[],
    output_key="final_summary"
)

# --- Agent 4: Firecrawl Scrape ---
firecrawl_agent = LlmAgent(
    name="FirecrawlAgent",
    model=nebius_model,
    description="Scrapes Nebius Studio homepage using Firecrawl.",
    instruction="""
    Use the firecrawl_scrape_nebius tool to fetch markdown content from Nebius Studio website in proper format. 
    Prefix your response with "**🔥FirecrawlAgent:**"
    """,
    tools=[firecrawl_scrape_nebius],
    output_key="firecrawl_content"
)

# --- Agent 5: Analysis & Stats ---
analysis_agent = LlmAgent(  
    name="AnalysisAgent",
    model=LiteLlm(
        model="openai/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",  # New Nebius model
        api_base=api_base,
        api_key=api_key
    ),
    instruction="""
You are an AI analyst specializing in the latest AI trends and Large Language Models (LLMs).
- Analyze the 'final_summary', combining it with your knowledge of AI advancements and the information extracted from 'exa_results' and 'tavily_results'.
- Identify key trends, growth areas, and notable statistics related to AI and LLMs.
- Carefully examine the 'firecrawl_content', which contain data from Nebius AI Studio's `llms.txt`. This file provides details about available models on Nebius, including their names, pricing, token limits, and availability.
- Instead of focusing solely on model names, analyze the functional capabilities and intended use cases of LLMs mentioned in the 'final_summary'.
- Cross-reference the LLMs' functionalities with the Nebius AI Studio offerings in 'firecrawl_content', prioritizing models with similar features such as context window size, training data, or specialized capabilities.
- Utilize any available metadata in 'firecrawl_content', such as model descriptions, tags, or categories, for more accurate matching.
- If a relevant LLM is found on Nebius, provide a specific recommendation to the user, highlighting its features, pricing, token limits, and potential benefits based on the context from the 'final_summary'.
- If no exact match is found, suggest alternative Nebius models with the closest functional alignment to the desired capabilities.
- If a close match is found, suggest the possibility of fine-tuning the Nebius model to better align with the specific requirements.
- Present your analysis with clear and concise language, supported by quantifiable data and insights.
- Utilize markdown tables for statistics, as demonstrated below:

| Metric | Value |
|---|---|
| Growth Rate | 25% |
| Market Size | \$100 Billion |

- Always prefix your response with "**🔍AnalysisAgent:**" for clear identification.
""",
    description="Analyzes the summary and presents insights and statistics.",
    output_key="analysis_results"
)

# --- Agent 6: Sequential pipeline (Orchestrator Agent) ---
pipeline = SequentialAgent(
    name="AIPipelineAgent",
    sub_agents=[exa_agent, tavily_agent, summary_agent, firecrawl_agent, analysis_agent]
)

# --- Runner setup ---
APP_NAME = "ai_analysis_pipeline"
USER_ID = "colab_user"
SESSION_ID = "ai_analysis_session"

session_service = InMemorySessionService()
session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=pipeline, app_name=APP_NAME, session_service=session_service)

# --- Run it ---
def run_ai_analysis():
    content = types.Content(role="user", parts=[types.Part(text="Start the AI analysis")])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
    for event in events:
        if event.is_final_response():
            print("📢 AI News Analysis and Insights:\n")
            print(event.content.parts[0].text)

if __name__ == "__main__":
    run_ai_analysis()

root_agent = pipeline
