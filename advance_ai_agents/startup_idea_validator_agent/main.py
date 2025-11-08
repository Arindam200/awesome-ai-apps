import os

from IPython.display import display, Markdown
from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.langchain_tool import LangchainTool
from google.genai import types
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field
import asyncio
import prompts
load_dotenv()

NEBIUS_LLM = LiteLlm(
    model="nebius/Qwen/Qwen3-235B-A22B-Instruct-2507",
    api_key=os.getenv("NEBIUS_API_KEY")
)

tavily_tool_instance = TavilySearch(
    max_results=3,
    search_depth="basic",
    include_answer=True,
    include_raw_content=False,
    include_images=False,
)

tavily_search = LangchainTool(tool=tavily_tool_instance)

idea_clarifier_agent = LlmAgent(
    name="IdeaClarifierAgent",
    model=NEBIUS_LLM,
    instruction=prompts.IDEA_PROMPT,
    description="Helps clarify and refine the startup idea.",
    # output_schema=IdeaClarification,
    output_key="clarified_idea"
)


market_research_agent = LlmAgent(
    name="MarketResearchAgent",
    model=NEBIUS_LLM,
    instruction=prompts.MARKET_RESEARCH_PROMPT,
    description="Conducts market research for the startup idea.",
    tools=[tavily_search],
    # output_schema=MarketResearch,
    output_key="market_research"
)



competitor_analysis_agent = LlmAgent(
    name="CompetitorAnalysisAgent",
    model=NEBIUS_LLM,
    instruction=prompts.COMPETITOR_ANALYSIS_PROMPT,
    description="Conducts competitor analysis for the startup idea.",
    tools=[tavily_search],
    # output_schema=CompetitorAnalysis,
    output_key="competitor_analysis"
)

report_agent = LlmAgent(
    name="ReportAgent",
    model=NEBIUS_LLM,
    instruction=prompts.REPORT_PROMPT,
    description="Generates a report based on the analysis findings.",
    # output_schema=ValidationReport,
    output_key="validation_report"
)

print(f"📝 Generating comprehensive validation report...")


startup_validation_agent = SequentialAgent(
    name="StartupValidationAgent",
    sub_agents=[
        idea_clarifier_agent,
        market_research_agent,
        competitor_analysis_agent,
        report_agent
    ],
    description="Validates startup ideas through a structured analysis process."

)

APP_NAME = "startup_validator"
USER_ID = "arindam_1729"
SESSION_ID = "startup_validation_session"

async def run_validation(idea: str):

    initial_state = {"idea": idea}
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID, state=initial_state)

    runner = Runner(
        agent=startup_validation_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    content = types.Content(role="user", parts=[types.Part(text=idea)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content )
    for event in events:
        if event.is_final_response():
            formatted_output = f"{event.content.parts[0].text}"
            print(formatted_output)
            # display(Markdown(formatted_output))
            # return formatted_output

    session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)


    import ast
    def safe_parse(val):
        if isinstance(val, dict):
            return val
        try:
            return ast.literal_eval(val)
        except Exception:
            return {}

    clarified_idea = safe_parse(session.state.get('clarified_idea', {}))
    market_research = safe_parse(session.state.get('market_research', {}))
    competitor_analysis = safe_parse(session.state.get('competitor_analysis', {}))
    validation_report = safe_parse(session.state.get('validation_report', {}))

    summary = f"""
🎉 **STARTUP IDEA VALIDATION COMPLETED!**

## 📊 Validation Summary

- **Startup Idea:** {idea}
- **Idea Clarification:** ✅ Completed
- **Market Research:** ✅ Completed
- **Competitor Analysis:** ✅ Completed
- **Final Report:** ✅ Generated

## 📈 Key Market Insights

- **TAM:** {market_research.get('total_addressable_market', '')}
- **Target Segments:** {market_research.get('target_customer_segments', '')}

## 🏆 Competitive Positioning

{competitor_analysis.get('positioning', '')}

---

## 📋 Comprehensive Validation Report

{validation_report.get('executive_summary', '')}

{validation_report.get('idea_assessment', '')}

{validation_report.get('market_opportunity', '')}

{validation_report.get('competitive_landscape', '')}

{validation_report.get('recommendations', '')}

{validation_report.get('next_steps', '')}

---

> ⚠️ *Disclaimer: This validation is for informational purposes only. Conduct additional due diligence before making investment decisions.*

"""
    # display(Markdown(summary))
    print(summary)

    return summary


if __name__ == "__main__":
    asyncio.run(run_validation("A CodeReview Agent that reviews your code in each PR"))