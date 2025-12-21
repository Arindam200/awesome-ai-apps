"""Content Team SEO Workflow - AI-Powered Content Optimization for Google AI Search

This advanced workflow helps content teams optimize articles for Google AI Search ranking.
It supports two modes:

1. **Existing Article Optimization**: Analyze and improve existing content (from URL or pasted text)
   - Keyword research via Google AI Mode & AI Overview
   - Content audit and improvement recommendations
   - Section-level rewrites with keyword optimization

2. **Pre-Writing Content Brief**: Generate SEO-optimized content guidelines before writing
   - Keyword and topic insights from SERP analysis
   - Content structure recommendations
   - Target headings, FAQs, and entity suggestions

Key capabilities:
- Google AI Mode & AI Overview research
- Keyword extraction and clustering
- Content gap analysis
- E-E-A-T optimization suggestions
- Section-level content improvements
- Actionable SEO recommendations

Run `pip install -e .` to install dependencies.

Uses Nebius Token Factory for LLM inference:
- Tool calling: moonshotai/Kimi-K2-Instruct
- Content writing: nvidia/Llama-3_1-Nemotron-Ultra-253B-v1
"""

import asyncio
import os
from pathlib import Path
from shutil import rmtree
from textwrap import dedent
from typing import Optional
from urllib.parse import urlparse
from datetime import datetime

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.nebius import Nebius
from agno.tools import tool
from agno.utils.pprint import pprint_run_response
from agno.workflow.types import WorkflowExecutionInput
from agno.workflow.workflow import Workflow
from pydantic import BaseModel

from tools import (
    google_ai_mode_search,
    google_ai_overview_search,
    extract_text_from_url,
)
import json


# --- Response models ---
class ArticleTopic(BaseModel):
    """Extracted topic and title from article content."""

    main_topic: str
    article_title: str
    key_themes: str
    search_query_suggestion: str


class SearchInsights(BaseModel):
    """Keyword and topic insights from SERP research."""

    primary_keywords: str
    related_keywords: str
    related_questions: str
    search_intent: str
    competitor_analysis: str
    ai_overview_summary: str


class ContentBrief(BaseModel):
    """Pre-writing content brief for new articles."""

    target_intent: str
    content_outline: str
    recommended_headings: str
    key_entities_to_mention: str
    faq_suggestions: str
    keyword_placement_guidance: str
    content_structure_recommendations: str
    writing_guidelines: str


class ArticleAudit(BaseModel):
    """Audit and improvement plan for existing articles."""

    content_strengths: str
    content_gaps: str
    keyword_opportunities: str
    structure_improvements: str
    e_e_a_t_assessment: str
    missing_sections: str
    prioritized_recommendations: str


class SectionEdits(BaseModel):
    """Improved section rewrites with keyword optimization."""

    improved_sections: str
    keyword_integration_summary: str
    changes_explanation: str


# --- File management ---
tmp_dir = Path(__file__).parent.joinpath(".tmp")
tmp_dir.mkdir(parents=True, exist_ok=True)

reports_dir = tmp_dir.joinpath("reports", "content_seo")
if reports_dir.is_dir():
    rmtree(path=reports_dir, ignore_errors=True)
reports_dir.mkdir(parents=True, exist_ok=True)

articles_dir = tmp_dir.joinpath("articles")
articles_dir.mkdir(parents=True, exist_ok=True)

search_insights_report = str(reports_dir.joinpath("search_insights.md"))
content_brief_report = str(reports_dir.joinpath("content_brief.md"))
article_audit_report = str(reports_dir.joinpath("article_audit.md"))
section_edits_report = str(reports_dir.joinpath("section_edits.md"))


# --- Custom tools for agents ---
@tool()
def search_google_ai_mode(query: str) -> dict:
    """Search Google AI Mode for a query. Returns raw search results dictionary."""
    results = google_ai_mode_search(query)
    return results


@tool()
def search_google_ai_overview(query: str) -> dict:
    """Search Google AI Overview for a query. Returns raw AI overview results dictionary."""
    results = google_ai_overview_search(query)
    return results


# --- Agents ---
search_insights_agent = Agent(
    name="Search Insights Agent",
    model=Nebius(
        id="moonshotai/Kimi-K2-Instruct",
        api_key=os.getenv("NEBIUS_API_KEY"),
    ),
    tools=[search_google_ai_mode, search_google_ai_overview],
    description=dedent(
        """\
    You are an expert SEO researcher specializing in Google AI Search optimization.
    Your role is to call the search tools to gather raw SERP data.
    Your expertise includes:
    
    - Conducting comprehensive SERP research
    - Using Google AI Mode and AI Overview tools effectively
    - Gathering complete search result data\
    """
    ),
    instructions=dedent(
        """\
    Your task is to gather comprehensive SERP data by calling both search tools:
    1. Call search_google_ai_mode with the search query
    2. Call search_google_ai_overview with the search query
    3. Return the raw results from both tools
    
    You don't need to analyze or format the results - just gather the data.\
    """
    ),
)

serp_analysis_agent = Agent(
    name="SERP Analysis Agent",
    model=Nebius(
        id="moonshotai/Kimi-K2-Instruct",
        api_key=os.getenv("NEBIUS_API_KEY"),
    ),
    description=dedent(
        """\
    You are an expert SEO analyst specializing in understanding and structuring SERP data.
    Your expertise includes:
    
    - Keyword research and clustering
    - Search intent analysis
    - SERP feature identification
    - Competitor content analysis
    - AI Overview pattern recognition
    - Related question extraction
    - Understanding relationships between search results\
    """
    ),
    instructions=dedent(
        """\
    Analyze the raw SERP results from both Google AI Mode and AI Overview searches.
    
    1. Understand the search landscape
       - Identify primary keywords and semantic keyword clusters
       - Extract related questions and search queries
       - Understand search intent (informational, commercial, navigational)
       - Identify key entities and concepts mentioned
    
    2. Analyze competitor content
       - Review top-ranking organic results
       - Identify content strengths and patterns
       - Note what topics and angles are covered
       - Identify content gaps and opportunities
    
    3. Understand AI Overview patterns
       - Analyze what information Google's AI Overview highlights
       - Identify key facts, statistics, or claims mentioned
       - Note the structure and format of AI Overview content
       - Understand what Google considers authoritative
    
    4. Synthesize insights
       - Compile primary keywords (most important for ranking)
       - List related keywords (semantic variations and related terms)
       - Extract related questions (FAQ opportunities)
       - Determine search intent (what users are really looking for)
       - Summarize competitor analysis (what top results do well)
       - Summarize AI Overview insights (what Google emphasizes)
    
    Provide comprehensive, actionable insights that will inform content strategy.\
    """
    ),
    output_schema=SearchInsights,
)

content_strategist_agent = Agent(
    name="Content Strategist Agent",
    model=Nebius(
        id="nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
        api_key=os.getenv("NEBIUS_API_KEY"),
    ),
    description=dedent(
        """\
    You are a senior content strategist specializing in SEO-optimized content creation.
    Your expertise includes:
    
    - Content structure optimization
    - Keyword placement strategies
    - E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) optimization
    - Content gap analysis
    - User intent alignment
    - Schema markup recommendations\
    """
    ),
    instructions=dedent(
        """\
    Your instructions will be dynamically set based on whether we're creating a content brief
    for a new article or auditing an existing article. Follow the specific mode instructions
    provided in each task.\
    """
    ),
)

topic_extraction_agent = Agent(
    name="Topic Extraction Agent",
    model=Nebius(
        id="moonshotai/Kimi-K2-Instruct",
        api_key=os.getenv("NEBIUS_API_KEY"),
    ),
    description=dedent(
        """\
    You are an expert at analyzing article content and extracting the main topic, title, and key themes.
    Your expertise includes:
    
    - Identifying the primary subject matter of articles
    - Extracting article titles from content
    - Understanding key themes and focus areas
    - Determining the best search query for SEO research\
    """
    ),
    instructions=dedent(
        """\
    Analyze the provided article content and extract:
    1. MAIN TOPIC: The core subject matter in 3-8 words (e.g., "Python async programming best practices")
    2. ARTICLE TITLE: The actual or inferred article title
    3. KEY THEMES: Main themes and subtopics covered (2-4 key themes)
    4. SEARCH QUERY SUGGESTION: The best search query to use for SEO research (should be specific and match what users would search for)
    
    Be specific and accurate - this will be used for keyword research, so it must reflect the actual article content.\
    """
    ),
    output_schema=ArticleTopic,
)

seo_editor_agent = Agent(
    name="SEO Editor Agent",
    model=Nebius(
        id="nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
        api_key=os.getenv("NEBIUS_API_KEY"),
    ),
    description=dedent(
        """\
    You are an expert SEO editor specializing in improving existing content while maintaining
    its core message and value. Your expertise includes:
    
    - Natural keyword integration
    - Content structure improvement
    - Heading optimization
    - Scannability enhancement
    - Meaning preservation
    - Keyword density optimization\
    """
    ),
    instructions=dedent(
        """\
    1. Preserve original meaning
       - Keep the core message and value proposition intact
       - Maintain the author's voice and style
       - Don't add fluff or unnecessary content
    2. Optimize with keywords
       - Integrate keywords naturally and contextually
       - Improve headings for SEO and scannability
       - Enhance content structure for better readability
    3. Focus on high-impact changes
       - Prioritize sections that need the most improvement
       - Make minimal but strategic edits
       - Explain why each change improves SEO potential\
    """
    ),
    output_schema=SectionEdits,
)


# --- Execution function ---
async def content_seo_execution(
    execution_input: WorkflowExecutionInput,
    topic: Optional[str] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    url: Optional[str] = None,
) -> str:
    """Execute the Content Team SEO workflow."""

    # Determine mode and normalize inputs
    article_text = None
    article_title = None
    is_existing_article = False

    if url:
        print(f"🌐 Extracting content from URL: {url}")
        article_text = extract_text_from_url(url)
        if article_text:
            is_existing_article = True
            print(f"✓ Extracted {len(article_text)} characters from URL")

            # Save extracted article to articles folder
            try:
                # Generate filename from URL or use timestamp
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace("www.", "").replace(".", "_")
                path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
                if path_parts:
                    filename_base = (
                        path_parts[-1].replace(".html", "").replace(".htm", "")
                    )
                else:
                    filename_base = "article"

                # Clean filename
                filename_base = "".join(
                    c for c in filename_base if c.isalnum() or c in ("-", "_")
                )[:50]
                if not filename_base:
                    filename_base = "article"

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                article_filename = f"{domain}_{filename_base}_{timestamp}.md"
                article_filepath = articles_dir.joinpath(article_filename)

                # Save article content
                with open(article_filepath, "w", encoding="utf-8") as f:
                    f.write(f"# Extracted Article\n\n")
                    f.write(f"**Source URL:** {url}\n\n")
                    f.write(
                        f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    )
                    f.write("---\n\n")
                    f.write(article_text)

                print(f"✓ Article saved to: {article_filepath}")
            except Exception as e:
                print(f"⚠️ Warning: Could not save article to file: {e}")
        else:
            print(
                "⚠️ Failed to extract content from URL. Proceeding with topic-only mode."
            )

    if title and content:
        article_title = title
        article_text = content
        is_existing_article = True
        print(f"✓ Using provided title and content ({len(content)} characters)")

    if not topic and not is_existing_article:
        return "Error: Please provide either a topic, URL, or title+content."

    # Extract topic from article if we have content but no explicit topic
    if is_existing_article and not topic:
        print("\n📝 Extracting article topic and title from content...")
        topic_extraction_prompt = f"""
        Analyze this article content and extract the main topic, title, and key themes:
        
        {'TITLE: ' + article_title + chr(10) if article_title else ''}
        CONTENT:
        {article_text[:6000]}  # Limit to avoid token limits
        
        Extract the main topic, article title, key themes, and suggest the best search query for SEO research.
        """

        try:
            topic_result = await topic_extraction_agent.arun(topic_extraction_prompt)
            extracted_topic = topic_result.content

            # Use extracted topic for search query
            search_query = extracted_topic.search_query_suggestion
            if not article_title and extracted_topic.article_title:
                article_title = extracted_topic.article_title

            print(f"✓ Extracted topic: {extracted_topic.main_topic}")
            print(f"✓ Article title: {extracted_topic.article_title}")
            print(f"✓ Search query: {search_query}")
        except Exception as e:
            print(f"⚠️ Error extracting topic: {e}")
            # Fallback: use title or first few words of content
            if article_title:
                search_query = article_title
            else:
                # Extract first sentence or first 50 words as fallback
                first_words = article_text.split()[:10] if article_text else []
                search_query = (
                    " ".join(first_words) if first_words else "content optimization"
                )
            print(f"⚠️ Using fallback search query: {search_query}")
    else:
        # Use provided topic or title
        search_query = (
            topic
            if topic
            else (article_title if article_title else "content optimization")
        )

    print(f"\n{'='*70}")
    print(
        f"Mode: {'EXISTING ARTICLE OPTIMIZATION' if is_existing_article else 'PRE-WRITING CONTENT BRIEF'}"
    )
    print(f"Search Query: {search_query}")
    print(f"{'='*70}\n")

    # Phase 1: Search Insights
    print("PHASE 1: SEARCH INSIGHTS & KEYWORD RESEARCH")
    print("=" * 70)

    # Step 1: Gather raw SERP data using tools
    print("🔍 Gathering raw SERP data from Google AI Mode and AI Overview...")
    print("📊 Fetching search results...")

    ai_mode_results = {}
    ai_overview_results = {}

    try:
        ai_mode_results = google_ai_mode_search(search_query)
        print("✓ Google AI Mode results fetched")
    except Exception as e:
        print(f"⚠️ Error fetching Google AI Mode results: {e}")

    try:
        ai_overview_results = google_ai_overview_search(search_query)
        print("✓ Google AI Overview results fetched")
    except Exception as e:
        print(f"⚠️ Error fetching Google AI Overview results: {e}")

    # Step 2: Format results for analysis
    def format_serp_results_for_analysis(results: dict, result_type: str) -> str:
        """Format SERP results into a readable format for agent analysis."""
        if not results:
            return f"No {result_type} results available."

        formatted = [f"\n{result_type.upper()} RESULTS:"]

        # Extract organic results
        organic_results = results.get("organic_results", [])
        if organic_results:
            formatted.append("\nTop Ranking Pages:")
            for i, result in enumerate(organic_results[:10], 1):
                title = result.get("title", "No title")
                snippet = result.get("snippet", "No snippet")
                link = result.get("link", "No link")
                formatted.append(f"{i}. {title}")
                formatted.append(f"   URL: {link}")
                formatted.append(f"   Snippet: {snippet[:200]}...")
                formatted.append("")

        # Extract related questions
        related_questions = results.get("related_questions", [])
        if related_questions:
            formatted.append("\nRelated Questions:")
            for q in related_questions[:15]:
                question = q.get("question", "") if isinstance(q, dict) else str(q)
                if question:
                    formatted.append(f"- {question}")

        # Extract People Also Ask
        people_also_ask = results.get("people_also_ask", [])
        if people_also_ask:
            formatted.append("\nPeople Also Ask:")
            for item in people_also_ask[:15]:
                question = (
                    item.get("question", "") if isinstance(item, dict) else str(item)
                )
                if question:
                    formatted.append(f"- {question}")

        # Extract related searches
        related_searches = results.get("related_searches", [])
        if related_searches:
            formatted.append("\nRelated Searches:")
            for search in related_searches[:15]:
                query = (
                    search.get("query", "") if isinstance(search, dict) else str(search)
                )
                if query:
                    formatted.append(f"- {query}")

        # Extract AI Overview if present
        ai_overview = results.get("ai_overview", {})
        if ai_overview:
            formatted.append("\nAI Overview Content:")
            if isinstance(ai_overview, dict):
                answer = ai_overview.get("answer", "")
                if answer:
                    formatted.append(answer[:1000])  # Limit length
            else:
                formatted.append(str(ai_overview)[:1000])

        return "\n".join(formatted)

    # Step 3: Analyze raw results with the analysis agent
    print("🧠 Analyzing SERP results and extracting insights...")

    ai_mode_formatted = format_serp_results_for_analysis(
        ai_mode_results, "Google AI Mode"
    )
    ai_overview_formatted = format_serp_results_for_analysis(
        ai_overview_results, "Google AI Overview"
    )

    analysis_prompt = f"""
    Analyze the SERP results from both Google AI Mode and AI Overview searches for: {search_query}
    
    {ai_mode_formatted}
    
    {ai_overview_formatted}
    
    Based on these comprehensive SERP results, analyze and provide structured insights:
    
    1. PRIMARY KEYWORDS: Identify the main keywords and phrases that are most important for ranking. Consider what terms appear in titles, snippets, and are emphasized in the AI Overview.
    
    2. RELATED KEYWORDS: List semantic variations, related terms, and keyword clusters that are relevant to this topic. Include synonyms, related concepts, and long-tail variations.
    
    3. RELATED QUESTIONS: Extract all questions from "Related Questions" and "People Also Ask" sections. These represent FAQ opportunities and user intent patterns.
    
    4. SEARCH INTENT: Determine the primary user intent (informational, commercial, navigational, transactional). Analyze what users are really trying to accomplish with this search.
    
    5. COMPETITOR ANALYSIS: Analyze the top-ranking organic results. What topics do they cover? What angles do they take? What content patterns emerge? What are their strengths?
    
    6. AI OVERVIEW SUMMARY: Summarize what Google's AI Overview highlights. What key information, facts, or claims does Google emphasize? What structure and format does it use?
    
    Provide comprehensive, actionable SEO insights that will inform content strategy for ranking on Google AI Search.
    """

    analysis_result = await serp_analysis_agent.arun(analysis_prompt)
    search_insights = analysis_result.content

    # Save search insights
    with open(search_insights_report, "w") as f:
        f.write("# Search Insights & Keyword Research\n\n")
        if article_title:
            f.write(f"**Article Title:** {article_title}\n\n")
        f.write(f"**Search Query:** {search_query}\n\n")
        f.write(f"## Primary Keywords\n{search_insights.primary_keywords}\n\n")
        f.write(f"## Related Keywords\n{search_insights.related_keywords}\n\n")
        f.write(f"## Related Questions\n{search_insights.related_questions}\n\n")
        f.write(f"## Search Intent\n{search_insights.search_intent}\n\n")
        f.write(f"## Competitor Analysis\n{search_insights.competitor_analysis}\n\n")
        f.write(f"## AI Overview Summary\n{search_insights.ai_overview_summary}\n")

    print(f"✓ Search insights saved to {search_insights_report}")

    # Phase 2: Content Strategy (mode-specific)
    print(
        f"\nPHASE 2: {'ARTICLE AUDIT' if is_existing_article else 'CONTENT BRIEF GENERATION'}"
    )
    print("=" * 70)

    if is_existing_article:
        # Existing article mode: Audit and improvement plan
        content_strategist_agent.output_schema = ArticleAudit
        content_strategist_agent.instructions = dedent(
            """\
        1. Content Audit
           - Analyze the existing article structure and quality
           - Identify strengths and weaknesses
           - Compare against competitor content from search insights
           - Assess keyword usage and opportunities
        2. Gap Analysis
           - Identify missing sections or topics
           - Find keyword gaps compared to top-ranking content
           - Note structural improvements needed
        3. E-E-A-T Assessment
           - Evaluate Experience, Expertise, Authoritativeness, Trustworthiness signals
           - Suggest improvements for authority building
        4. Prioritized Recommendations
           - Rank improvements by impact and ease
           - Focus on high-impact, actionable changes
           - Provide specific, implementable suggestions\
        """
        )

        audit_prompt = f"""
        Analyze and audit this existing article for SEO optimization:
        
        TITLE: {article_title or 'Untitled'}
        
        CONTENT:
        {article_text[:12000]}  # Increased limit for better analysis
        
        SEARCH INSIGHTS:
        - Primary Keywords: {search_insights.primary_keywords}
        - Related Keywords: {search_insights.related_keywords}
        - Related Questions: {search_insights.related_questions}
        - Search Intent: {search_insights.search_intent}
        - Competitor Analysis: {search_insights.competitor_analysis}
        - AI Overview: {search_insights.ai_overview_summary}
        
        Provide a comprehensive audit with prioritized improvement recommendations.
        """

        print("📊 Auditing article and identifying improvements...")
        audit_result = await content_strategist_agent.arun(audit_prompt)
        article_audit = audit_result.content

        # Save audit report
        with open(article_audit_report, "w") as f:
            f.write("# Article SEO Audit & Improvement Plan\n\n")
            f.write(f"**Article Title:** {article_title or 'Untitled'}\n\n")
            f.write(f"## Content Strengths\n{article_audit.content_strengths}\n\n")
            f.write(f"## Content Gaps\n{article_audit.content_gaps}\n\n")
            f.write(
                f"## Keyword Opportunities\n{article_audit.keyword_opportunities}\n\n"
            )
            f.write(
                f"## Structure Improvements\n{article_audit.structure_improvements}\n\n"
            )
            f.write(f"## E-E-A-T Assessment\n{article_audit.e_e_a_t_assessment}\n\n")
            f.write(f"## Missing Sections\n{article_audit.missing_sections}\n\n")
            f.write(
                f"## Prioritized Recommendations\n{article_audit.prioritized_recommendations}\n"
            )

        print(f"✓ Article audit saved to {article_audit_report}")

        # Phase 3: Section Rewrites (only for existing articles)
        print("\nPHASE 3: SECTION OPTIMIZATION & REWRITES")
        print("=" * 70)

        rewrite_prompt = f"""
        Based on the audit below, rewrite and optimize key sections of the article.
        Focus on sections that need the most improvement while keeping the main content and meaning intact.
        
        IMPORTANT: You have access to the FULL article content. Use the complete content to make informed,
        context-aware improvements. Don't just optimize isolated sections - consider how changes affect
        the overall article flow and coherence.
        
        ORIGINAL ARTICLE:
        Title: {article_title or 'Untitled'}
        
        FULL CONTENT:
        {article_text}
        
        AUDIT FINDINGS:
        - Content Gaps: {article_audit.content_gaps}
        - Keyword Opportunities: {article_audit.keyword_opportunities}
        - Structure Improvements: {article_audit.structure_improvements}
        - Prioritized Recommendations: {article_audit.prioritized_recommendations}
        
        SEARCH INSIGHTS:
        - Primary Keywords: {search_insights.primary_keywords}
        - Related Keywords: {search_insights.related_keywords}
        - Related Questions: {search_insights.related_questions}
        
        Provide improved versions of the most important sections with natural keyword integration.
        Explain what changed and why each change improves SEO potential.
        """

        print("✏️ Optimizing sections with keyword integration...")
        rewrite_result = await seo_editor_agent.arun(rewrite_prompt)
        section_edits = rewrite_result.content

        # Save section edits
        with open(section_edits_report, "w") as f:
            f.write("# Optimized Section Rewrites\n\n")
            f.write(f"**Article Title:** {article_title or 'Untitled'}\n\n")
            f.write(f"## Improved Sections\n{section_edits.improved_sections}\n\n")
            f.write(
                f"## Keyword Integration Summary\n{section_edits.keyword_integration_summary}\n\n"
            )
            f.write(f"## Changes Explanation\n{section_edits.changes_explanation}\n")

        print(f"✓ Section rewrites saved to {section_edits_report}")

        # Final summary
        summary = f"""
CONTENT SEO OPTIMIZATION COMPLETED

Article: {article_title or 'Untitled'}
Mode: Existing Article Optimization

Reports Generated:
• Search Insights: {search_insights_report}
• Article Audit: {article_audit_report}
• Section Rewrites: {section_edits_report}

Key Improvements Identified:
{article_audit.prioritized_recommendations[:300]}...

Next Steps:
1. Review the audit report for prioritized recommendations
2. Implement the optimized section rewrites
3. Address missing sections and keyword gaps
4. Improve E-E-A-T signals as suggested
"""
    else:
        # Pre-writing mode: Content brief
        content_strategist_agent.output_schema = ContentBrief
        content_strategist_agent.instructions = dedent(
            """\
        1. Content Structure Planning
           - Create a comprehensive outline based on search insights
           - Design heading hierarchy (H1, H2, H3) for SEO
           - Identify key sections and subsections
        2. Keyword Strategy
           - Plan primary keyword placement (title, first paragraph, headings)
           - Integrate related keywords naturally throughout
           - Identify semantic keyword opportunities
        3. Content Elements
           - Suggest FAQ sections based on related questions
           - Identify key entities and concepts to mention
           - Recommend examples, case studies, or data points
        4. Writing Guidelines
           - Provide do's and don'ts for SEO-optimized writing
           - Suggest content length and depth
           - Recommend schema markup opportunities\
        """
        )

        brief_prompt = f"""
        Create a comprehensive content brief for writing an SEO-optimized article on: {search_query}
        
        SEARCH INSIGHTS:
        - Primary Keywords: {search_insights.primary_keywords}
        - Related Keywords: {search_insights.related_keywords}
        - Related Questions: {search_insights.related_questions}
        - Search Intent: {search_insights.search_intent}
        - Competitor Analysis: {search_insights.competitor_analysis}
        - AI Overview: {search_insights.ai_overview_summary}
        
        Provide a detailed content brief that will guide the writing of a rankable article.
        """

        print("📝 Generating content brief and writing guidelines...")
        brief_result = await content_strategist_agent.arun(brief_prompt)
        content_brief = brief_result.content

        # Save content brief
        with open(content_brief_report, "w") as f:
            f.write("# Content Brief & SEO Writing Guidelines\n\n")
            f.write(f"**Topic:** {search_query}\n\n")
            f.write(f"## Target Intent\n{content_brief.target_intent}\n\n")
            f.write(f"## Content Outline\n{content_brief.content_outline}\n\n")
            f.write(
                f"## Recommended Headings\n{content_brief.recommended_headings}\n\n"
            )
            f.write(
                f"## Key Entities to Mention\n{content_brief.key_entities_to_mention}\n\n"
            )
            f.write(f"## FAQ Suggestions\n{content_brief.faq_suggestions}\n\n")
            f.write(
                f"## Keyword Placement Guidance\n{content_brief.keyword_placement_guidance}\n\n"
            )
            f.write(
                f"## Content Structure Recommendations\n{content_brief.content_structure_recommendations}\n\n"
            )
            f.write(f"## Writing Guidelines\n{content_brief.writing_guidelines}\n")

        print(f"✓ Content brief saved to {content_brief_report}")

        # Final summary
        summary = f"""
CONTENT SEO BRIEF GENERATION COMPLETED

Topic: {search_query}
Mode: Pre-Writing Content Brief

Reports Generated:
• Search Insights: {search_insights_report}
• Content Brief: {content_brief_report}

Key Recommendations:
{content_brief.content_structure_recommendations[:300]}...

Next Steps:
1. Review the content outline and recommended headings
2. Follow the keyword placement guidance
3. Include suggested FAQs and entities
4. Use the writing guidelines while drafting
"""

    return summary


# --- Workflow definition ---
content_seo_workflow = Workflow(
    name="Content Team SEO Workflow",
    description="AI-powered content optimization for Google AI Search ranking",
    db=SqliteDb(
        session_table="workflow_session",
        db_file=str(tmp_dir.joinpath("workflows.db")),
    ),
    steps=content_seo_execution,
    session_state={},
)


if __name__ == "__main__":

    async def main():
        from rich.prompt import Prompt

        print("=" * 70)
        print("Content Team SEO Workflow - Google AI Search Optimization")
        print("=" * 70)
        print("\nChoose your input method:")
        print("1. Topic only (pre-writing content brief)")
        print("2. URL to existing article (optimize existing content)")
        print("3. Title + Content (optimize existing content)")
        print()

        choice = Prompt.ask(
            "[bold]Enter choice (1/2/3)[/bold]",
            default="1",
        )

        topic = None
        title = None
        content = None
        url = None

        if choice == "1":
            topic = Prompt.ask("[bold]Enter the topic[/bold]")
        elif choice == "2":
            url = Prompt.ask("[bold]Enter the article URL[/bold]")
        elif choice == "3":
            title = Prompt.ask("[bold]Enter the article title[/bold]")
            print(
                "\n[dim]Paste your article content (press Enter twice when done):[/dim]"
            )
            lines = []
            while True:
                try:
                    line = input()
                    if line == "" and lines and lines[-1] == "":
                        break
                    lines.append(line)
                except EOFError:
                    break
            content = "\n".join(lines).strip()
        else:
            print("Invalid choice. Using topic mode.")
            topic = Prompt.ask("[bold]Enter the topic[/bold]")

        result = await content_seo_workflow.arun(
            input="Generate SEO optimization analysis",
            topic=topic,
            title=title,
            content=content,
            url=url,
        )

        pprint_run_response(result, markdown=True)

    asyncio.run(main())
