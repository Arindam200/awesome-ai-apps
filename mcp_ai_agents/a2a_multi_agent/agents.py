"""The two framework-specific agents behind the A2A services."""

import os
from typing import TypedDict

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.run import RunStatus
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

MODEL = "openai/gpt-oss-120b"
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def get_api_key() -> str:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("Set NEBIUS_API_KEY in .env before starting an agent.")
    return api_key


async def draft_plan(topic: str) -> str:
    """Use Agno to make a short implementation plan for a user-supplied idea."""
    agent = Agent(
        name="Architect",
        model=Nebius(
            id=os.getenv("NEBIUS_MODEL", MODEL),
            base_url=NEBIUS_BASE_URL,
            api_key=get_api_key(),
        ),
        instructions=[
            "Draft a concrete three-step implementation plan for the user's idea.",
            "Keep the plan concise and make no claims about work already completed.",
        ],
    )
    response = await agent.arun(topic)
    if response.status == RunStatus.error:
        raise RuntimeError(str(response.content))
    return str(response.content)


class ReviewState(TypedDict):
    plan: str
    review: str


def build_review_graph():
    """Build a LangGraph that reviews the architect's plan."""
    model = ChatOpenAI(
        model=os.getenv("NEBIUS_MODEL", MODEL),
        base_url=NEBIUS_BASE_URL,
        api_key=get_api_key(),
    )

    async def review(state: ReviewState) -> dict[str, str]:
        response = await model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Review the implementation plan. Identify its most important risk "
                        "and propose one concrete improvement. Be concise."
                    )
                ),
                HumanMessage(content=state["plan"]),
            ]
        )
        return {"review": str(response.content)}

    graph = StateGraph(ReviewState)
    graph.add_node("review", review)
    graph.add_edge(START, "review")
    graph.add_edge("review", END)
    return graph.compile()


async def review_plan(plan: str) -> str:
    result = await build_review_graph().ainvoke({"plan": plan})
    return result["review"]
