"""
AI Consultant Workflow
Uses LangChain for reasoning and Tavily for web/case-study research.
"""

import os
from typing import List, Optional, Tuple, Any

from dotenv import load_dotenv
from tavily import TavilyClient
from pydantic import BaseModel, Field

# Load environment variables from .env if present
load_dotenv()


class CompanyProfile(BaseModel):
    """Structured description of the company and its AI needs."""

    company_name: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    company_size: str = Field(
        ...,
        description="Rough size band, e.g. '1-50', '51-200', '201-1000', '1000+'.",
    )
    region: Optional[str] = Field(
        default=None,
        description="Geography or market (e.g. 'US', 'EU', 'Global', 'APAC').",
    )
    tech_maturity: str = Field(
        ...,
        description="Low / Medium / High description of data & engineering maturity.",
    )
    goals: List[str] = Field(
        default_factory=list,
        description="High-level business goals for AI (cost, revenue, CX, risk, innovation).",
    )
    ai_focus_areas: List[str] = Field(
        default_factory=list,
        description="Where to consider AI (workflows, support, analytics, product, ecosystem).",
    )
    budget_range: str = Field(
        ...,
        description="Rough budget band (e.g. '<$50k', '$50k-$250k', '$250k-$1M', '>$1M').",
    )
    time_horizon: str = Field(
        ...,
        description="Time horizon for initial AI rollout (e.g. '0-3 months', '3-6 months').",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Free-text context: constraints, data sources, regulatory considerations, etc.",
    )


class ResearchSnippet(BaseModel):
    """Single Tavily search result distilled for prompting."""

    title: str
    url: str
    snippet: str


def _build_research_query(profile: CompanyProfile) -> str:
    """Build a focused search query for AI adoption / case studies."""
    parts: List[str] = [
        profile.industry,
        "AI adoption case studies",
        "enterprise",
    ]

    if profile.company_size:
        parts.append(f"company size {profile.company_size}")

    if profile.region:
        parts.append(profile.region)

    if profile.goals:
        parts.append(" ".join(profile.goals))

    return " ".join(parts)


def search_ai_case_studies_with_tavily(
    profile: CompanyProfile, max_results: int = 5
) -> List[ResearchSnippet]:
    """
    Use Tavily to retrieve a handful of relevant AI case studies / examples.
    """
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        raise RuntimeError("TAVILY_API_KEY not set in environment variables")

    client = TavilyClient(api_key=tavily_key)
    query = _build_research_query(profile)

    try:
        # Use advanced depth to get richer snippets; return up to max_results
        results = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
        )
    except Exception as e:
        raise RuntimeError(f"Error calling Tavily: {e}") from e

    snippets: List[ResearchSnippet] = []
    for r in results.get("results", []):
        title = (r.get("title") or "AI case study").strip()
        url = r.get("url") or ""
        text = (r.get("content") or r.get("snippet") or "").strip()
        snippet_text = text[:800] if text else ""
        if not (title or url or snippet_text):
            continue
        snippets.append(
            ResearchSnippet(
                title=title,
                url=url,
                snippet=snippet_text,
            )
        )

    return snippets


def run_ai_assessment(
    profile: CompanyProfile, openai_client: Any
) -> Tuple[str, List[ResearchSnippet]]:
    """
    Main workflow:
    - Pull a few relevant case studies via Tavily.
    - Ask the LLM (LangChain-compatible) to produce a structured consulting report.

    Returns:
        assessment_markdown: str  -> Markdown report for display.
        research_snippets: List[ResearchSnippet] -> For optional debugging / display.
    """
    # Step 1: web research
    research_snippets = search_ai_case_studies_with_tavily(profile, max_results=5)

    # Step 2: build prompt for the consultant LLM
    research_section = ""
    if research_snippets:
        lines: List[str] = []
        for i, s in enumerate(research_snippets, start=1):
            lines.append(f"{i}. {s.title} ({s.url})\n" f"{s.snippet}\n")
        research_section = "\n".join(lines)
    else:
        research_section = (
            "No external case studies were found. Rely on your general knowledge."
        )

    goals_str = ", ".join(profile.goals) if profile.goals else "Not specified"
    areas_str = (
        ", ".join(profile.ai_focus_areas) if profile.ai_focus_areas else "Not specified"
    )

    system_prompt = (
        "You are a senior AI transformation consultant. "
        "You give pragmatic, business-focused advice about whether and how a company "
        "should adopt AI, including costs, risks, and change management."
    )

    user_prompt = (
        f"Company profile:\n"
        f"- Name: {profile.company_name}\n"
        f"- Industry: {profile.industry}\n"
        f"- Company size: {profile.company_size}\n"
        f"- Region / market: {profile.region or 'Not specified'}\n"
        f"- Tech maturity: {profile.tech_maturity}\n"
        f"- Goals: {goals_str}\n"
        f"- AI focus areas: {areas_str}\n"
        f"- Budget range: {profile.budget_range}\n"
        f"- Time horizon: {profile.time_horizon}\n"
        f"- Additional notes: {profile.notes or 'None'}\n\n"
        f"Relevant AI adoption / case-study research:\n"
        f"{research_section}\n\n"
        "Task:\n"
        "1. Decide whether they should integrate AI now, later, or not at all. Be explicit.\n"
        "2. Recommend specific AI use cases, grouped by area (workforce, internal tools, ecosystem, etc.).\n"
        "3. Provide rough cost bands (e.g. '<$50k', '$50k-$250k', '$250k-$1M', '>$1M') and key cost drivers.\n"
        "4. Call out major risks, dependencies, and change-management considerations.\n"
        "5. Summarize concrete next steps the company should take in the next 30–90 days.\n\n"
        "Respond in clear Markdown with the following sections and nothing else:\n"
        "## Recommendation\n"
        "## Priority AI Use Cases\n"
        "## Cost & Complexity\n"
        "## Risks & Considerations\n"
        "## Next Steps\n"
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"Error calling consultant LLM: {e}") from e

    assessment_markdown = response.choices[0].message.content
    return assessment_markdown, research_snippets
