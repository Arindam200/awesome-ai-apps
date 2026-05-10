"""
Workflow Agent Demo - Multi-Agent Research Pipeline
"""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands_tools import http_request

load_dotenv()

# Create model
model = LiteLLMModel(
    client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
    model_id="nebius/zai-org/GLM-4.5",
)

# Create specialized agents
# Researcher Agent with web capabilities
researcher_agent = Agent(
    model=model,
    system_prompt=(
        "You are a Researcher Agent that gathers information from the web. "
        "1. Determine if the input is a research query or factual claim "
        "2. Use your research tools (http_request, retrieve) to find relevant information "
        "3. Include source URLs and keep findings under 500 words"
    ),
    callback_handler=None,
    tools=[http_request],
)

# Analyst Agent for verification and insight extraction
analyst_agent = Agent(
    callback_handler=None,
    model=model,
    system_prompt=(
        "You are an Analyst Agent that verifies information. "
        "1. For factual claims: Rate accuracy from 1-5 and correct if needed "
        "2. For research queries: Identify 3-5 key insights "
        "3. Evaluate source reliability and keep analysis under 400 words"
    ),
)

writer_agent = Agent(
    model=model,
    system_prompt=(
        "You are a Writer Agent that creates clear reports. "
        "1. For fact-checks: State whether claims are true or false "
        "2. For research: Present key insights in a logical structure "
        "3. Keep reports under 500 words with brief source mentions"
    ),
)


def run_research_workflow(user_input: str):
    """Execute the complete research workflow."""
    print(f"🔍 Researching: {user_input}")

    # Step 1: Research
    research_response = researcher_agent(
        f"Research: '{user_input}'. Use tools to find reliable sources with URLs."
    )
    research_findings = str(research_response)
    print(f"✅ Research completed ({len(research_findings)} chars)")

    # Step 2: Analysis
    analyst_response = analyst_agent(
        f"Analyze these findings about '{user_input}':\n\n{research_findings}"
    )
    analysis = str(analyst_response)
    print(f"✅ Analysis completed ({len(analysis)} chars)")

    # Step 3: Writing
    final_report = writer_agent(
        f"Create a report on '{user_input}' based on:\n\n{analysis}"
    )
    print(f"✅ Report completed ({len(str(final_report))} chars)")

    return {
        "query": user_input,
        "research": research_findings,
        "analysis": analysis,
        "report": str(final_report),
    }


def run_fact_check(claim: str):
    """Execute fact-checking workflow."""
    print(f"🔍 Fact-checking: {claim}")

    # Research the claim
    research = researcher_agent(
        f"Fact-check: '{claim}'. Find evidence for/against this claim with sources."
    )

    # Analyze evidence
    analysis = analyst_agent(
        f"Analyze evidence for: '{claim}'\n\nResearch: {str(research)}\n\n"
        f"Provide verdict (TRUE/FALSE/PARTIALLY TRUE), confidence level, and evidence."
    )

    # Create fact-check report
    report = writer_agent(
        f"Create fact-check report for: '{claim}'\n\nAnalysis: {str(analysis)}"
    )

    return {
        "claim": claim,
        "research": str(research),
        "analysis": str(analysis),
        "report": str(report),
    }


def main():
    """Demo the workflow."""
    print("\n 🔬 Multi-Agent Research Workflow Demo")
    print("=" * 50)

    # Research example
    query = "Latest developments in AI safety"
    print(f"\n📝 Query: {query}")
    results = run_research_workflow(query)

    print(f"\n📊 Final Report:")
    print("-" * 30)
    print(results["report"])

    # Fact-check example
    print("\n" + "=" * 50)
    claim = "OpenAI's GPT-4 was released in March 2023"
    print(f"\n📝 Claim: {claim}")
    fact_results = run_fact_check(claim)

    print(f"\n📊 Fact-Check Report:")
    print("-" * 30)
    print(fact_results["report"])


if __name__ == "__main__":
    main()
