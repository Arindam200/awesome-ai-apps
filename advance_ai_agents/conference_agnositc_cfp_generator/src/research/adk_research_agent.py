from typing import Dict, List, Any
import json
import os

from datetime import datetime, timedelta
from exa_py import Exa
from tavily import TavilyClient
import asyncio
import concurrent.futures

from ..config.nebius_client import NebiusClient
class ResearchOrchestrator:
    """Custom research orchestrator using Nebius AI directly"""

    def __init__(self):
        self.client = NebiusClient()

    def run_parallel_searches(self, topic: str) -> Dict[str, Any]:
        """Run Exa and Tavily searches in parallel"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both search tasks
            exa_future = executor.submit(self.exa_search, topic)
            tavily_future = executor.submit(self.tavily_search, topic)

            # Collect results
            exa_results = exa_future.result()
            tavily_results = tavily_future.result()

        return {
            "exa_results": exa_results,
            "tavily_results": tavily_results
        }

    def exa_search(self, topic: str) -> Dict[str, Any]:
        """Search using Exa API for latest developments"""
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
            return {
                "type": "exa",
                "results": [r.__dict__ for r in results.results],
                "success": True
            }
        except Exception as e:
            return {
                "type": "exa",
                "results": [],
                "error": f"Exa search failed: {str(e)}",
                "success": False
            }

    def tavily_search(self, topic: str) -> Dict[str, Any]:
        """Search using Tavily API for community sentiment"""
        try:
            client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
            response = client.search(
                query=f"Recent community sentiment, technical questions, and debates about {topic}",
                search_depth="advanced",
                time_range="month",
                include_domains=["x.com", "reddit.com", "dev.to"]
            )
            return {
                "type": "tavily",
                "results": response.get("results", []),
                "success": True
            }
        except Exception as e:
            return {
                "type": "tavily",
                "results": [],
                "error": f"Tavily search failed: {str(e)}",
                "success": False
            }

    def analyze_with_nebius(self, topic: str, search_results: Dict[str, Any]) -> str:
        """Use Nebius AI to analyze and synthesize the search results"""

        # Format the search results for analysis
        exa_data = search_results.get("exa_results", {})
        tavily_data = search_results.get("tavily_results", {})

        context = f"""
        **SEARCH RESULTS FOR TOPIC: {topic}**

        **EXA RESULTS (Latest News & Developments):**
        {json.dumps(exa_data, indent=2)}

        **TAVILY RESULTS (Community Sentiment):**
        {json.dumps(tavily_data, indent=2)}
        """

        analysis_prompt = [
            {
                "role": "system",
                "content": """You are a meticulous research analyst using advanced AI capabilities.
                Analyze the provided search results and create a comprehensive research summary.

                Focus on extracting:
                1. **Latest Developments**: What's new in the field?
                2. **Community Insights**: What are developers/practitioners discussing?
                3. **Technical Gaps**: What problems need solving?
                4. **Emerging Trends**: What's gaining momentum?

                Use clear markdown formatting and be comprehensive yet concise.
                Ignore any search errors and focus on successful results."""
            },
            {
                "role": "user",
                "content": f"Analyze these search results about '{topic}' and provide a structured research summary:\n\n{context}"
            }
        ]

        try:
            analysis = self.client.chat_completion(
                messages=analysis_prompt,
                temperature=0.7,
                max_tokens=3000
            )
            return analysis
        except Exception as e:
            return f"Analysis failed: {str(e)}\n\nRaw search results:\n{context}"


def run_adk_research(topic: str) -> str:
    """
    Runs the custom research pipeline for a given topic and returns the final analysis.
    Uses OpenRouter with Grok-4 directly without Google ADK dependencies.
    """

    try:
        # Initialize the research orchestrator
        orchestrator = ResearchOrchestrator()

        # Step 1: Run parallel searches
        print(f"🔍 Starting parallel research for: {topic}")
        search_results = orchestrator.run_parallel_searches(topic)

        # Step 2: Analyze results with Nebius AI
        print("🧠 Analyzing results with Nebius AI...")
        final_analysis = orchestrator.analyze_with_nebius(topic, search_results)

        return final_analysis

    except Exception as e:
        error_msg = f"Research pipeline failed: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg


# Legacy function name for backward compatibility
def run_research_agent(topic: str) -> str:
    """Alias for run_adk_research for backward compatibility"""
    return run_adk_research(topic)