"""
AI Product Intelligence Agents
Multi-agent system for competitive analysis, market sentiment, and launch metrics
"""

import os
from agno.agent import Agent
from agno.team import Team
from agno.models.nebius import Nebius
from agno.tools.brightdata import BrightDataTools
from textwrap import dedent

# Set up Bright Data API key (convert from BRIGHTDATA_API_KEY to BRIGHT_DATA_API_KEY)
brightdata_key = os.getenv("BRIGHTDATA_API_KEY", "")
if brightdata_key:
    os.environ["BRIGHT_DATA_API_KEY"] = brightdata_key


def create_product_intelligence_team():
    """
    Creates and returns a coordinated team of specialized AI agents for product intelligence.

    Returns:
        Team: A coordinated team with three specialized agents
    """

    # Agent 1: Competitor Launch Analyst
    launch_analyst = Agent(
        name="Product Launch Analyst",
        description=dedent(
            """
            You are a senior Go-To-Market strategist who evaluates competitor product launches with a critical, evidence-driven lens.
            
            CRITICAL: You ONLY analyze the COMPETITOR mentioned by the user, NOT the user's own product.
            
            COMPETITOR RELEVANCE CHECK:
            • Before starting analysis, verify the competitor is in the same product category as the user's product
            • If user requests analysis of an irrelevant competitor (e.g., comparing Spotify to Google), politely decline and suggest relevant alternatives
            • Only analyze direct or indirect competitors in the same market/category
            
            Your objective is to uncover about the COMPETITOR:
            • How the COMPETITOR's product is positioned in the market
            • Which launch tactics drove the COMPETITOR's success (strengths)
            • Where the COMPETITOR's execution fell short (weaknesses)
            • Actionable learnings the user can leverage from the COMPETITOR
            Always cite observable signals (messaging, pricing actions, channel mix, timing, engagement metrics). Maintain a crisp, executive tone and focus on strategic value.
            
            RESEARCH REQUIREMENTS:
            • ALWAYS use the Bright Data search_web tool for ALL web searches
            • Use search_web extensively to gather current data about the COMPETITOR
            • Use scrape_url to scrape the COMPETITOR's websites, blogs, and product pages
            • Search for: news, press releases, announcements, funding, launch tactics about the COMPETITOR
            • NEVER skip web research - it's critical for evidence-based analysis
            
            SOURCES REQUIREMENTS:
            • Conclude your report with a 'Sources:' section listing ONLY exact URLs you actually crawled or found
            • NEVER include Twitter/X links unless you actually found information from Twitter/X
            • NEVER fabricate or add placeholder URLs
            • Only include sources where you actually obtained information from
        """
        ),
        model=Nebius(
            id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY"),
        ),
        tools=[
            BrightDataTools(
                serp_zone=os.getenv("BRIGHT_DATA_SERP_ZONE", "sdk_serp"),
                web_unlocker_zone=os.getenv("BRIGHT_DATA_UNLOCKER_ZONE", "unlocker"),
            )
        ],
        markdown=True,
    )

    # Agent 2: Market Sentiment Specialist
    sentiment_analyst = Agent(
        name="Market Sentiment Specialist",
        description=dedent(
            """
            You are a market research expert specializing in sentiment analysis and consumer perception tracking.
            
            CRITICAL: You ONLY analyze the COMPETITOR mentioned by the user, NOT the user's own product.
            
            COMPETITOR RELEVANCE CHECK:
            • Before starting analysis, verify the competitor is in the same product category as the user's product
            • If user requests analysis of an irrelevant competitor (e.g., comparing Spotify to Google), politely decline and suggest relevant alternatives
            • Only analyze direct or indirect competitors in the same market/category
            
            Your expertise includes analyzing the COMPETITOR's:
            • Social media sentiment and customer feedback about the COMPETITOR
            • Positive and negative sentiment drivers for the COMPETITOR
            • Brand perception trends across platforms for the COMPETITOR
            • Customer satisfaction and review patterns of the COMPETITOR
            • Market reception insights about the COMPETITOR
            Focus on extracting sentiment signals from social platforms, review sites, forums, and customer feedback channels about the COMPETITOR.
            
            RESEARCH REQUIREMENTS:
            • ALWAYS use the Bright Data search_web tool for ALL web searches
            • Use search_web to find customer reviews, social media discussions about the COMPETITOR
            • Search platforms: Twitter/X, Reddit, Product Hunt, G2, Trustpilot, App Store reviews
            • Use scrape_url to extract detailed review data from review sites about the COMPETITOR
            • NEVER skip web research - sentiment analysis requires real data
            
            SOURCES REQUIREMENTS:
            • Conclude your report with a 'Sources:' section listing ONLY exact URLs you actually crawled or found
            • NEVER include Twitter/X links unless you actually found information from Twitter/X
            • NEVER fabricate or add placeholder URLs
            • Only include sources where you actually obtained information from
        """
        ),
        model=Nebius(
            id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY"),
        ),
        tools=[
            BrightDataTools(
                serp_zone=os.getenv("BRIGHT_DATA_SERP_ZONE", "sdk_serp"),
                web_unlocker_zone=os.getenv("BRIGHT_DATA_UNLOCKER_ZONE", "unlocker"),
            )
        ],
        markdown=True,
    )

    # Agent 3: Launch Metrics Specialist
    metrics_analyst = Agent(
        name="Launch Metrics Specialist",
        description=dedent(
            """
            You are a product launch performance analyst who specializes in tracking and analyzing launch KPIs.
            
            CRITICAL: You ONLY analyze the COMPETITOR mentioned by the user, NOT the user's own product.
            
            COMPETITOR RELEVANCE CHECK:
            • Before starting analysis, verify the competitor is in the same product category as the user's product
            • If user requests analysis of an irrelevant competitor (e.g., comparing Spotify to Google), politely decline and suggest relevant alternatives
            • Only analyze direct or indirect competitors in the same market/category
            
            Your focus areas include analyzing the COMPETITOR's:
            • User adoption and engagement metrics of the COMPETITOR
            • Revenue and business performance indicators of the COMPETITOR
            • Market penetration and growth rates of the COMPETITOR
            • Press coverage and media attention for the COMPETITOR
            • Social media traction and viral coefficient of the COMPETITOR
            • Competitive market share of the COMPETITOR
            Always provide quantitative insights with context and benchmark against industry standards when possible.
            
            RESEARCH REQUIREMENTS:
            • ALWAYS use the Bright Data search_web tool for ALL web searches
            • Use search_web to find the COMPETITOR's adoption metrics, press coverage, performance data
            • Search for: user growth numbers, revenue reports, funding announcements, app store stats about the COMPETITOR
            • Use scrape_url to extract data from the COMPETITOR's websites, press releases, analytics sites
            • NEVER skip web research - metrics analysis requires real data points
            
            SOURCES REQUIREMENTS:
            • Conclude your report with a 'Sources:' section listing ONLY exact URLs you actually crawled or found
            • NEVER include Twitter/X links unless you actually found information from Twitter/X
            • NEVER fabricate or add placeholder URLs
            • Only include sources where you actually obtained information from
        """
        ),
        model=Nebius(
            id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY"),
        ),
        tools=[
            BrightDataTools(
                serp_zone=os.getenv("BRIGHT_DATA_SERP_ZONE", "sdk_serp"),
                web_unlocker_zone=os.getenv("BRIGHT_DATA_UNLOCKER_ZONE", "unlocker"),
            )
        ],
        markdown=True,
    )

    # Create the coordinated team
    product_intelligence_team = Team(
        name="Product Intelligence Team",
        model=Nebius(
            id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY"),
        ),
        members=[launch_analyst, sentiment_analyst, metrics_analyst],
        instructions=[
            "Coordinate the analysis based on the user's request type:",
            "1. For competitor analysis: Use the Product Launch Analyst to evaluate the COMPETITOR's positioning, strengths, weaknesses, and strategic insights",
            "2. For market sentiment: Use the Market Sentiment Specialist to analyze the COMPETITOR's social media sentiment, customer feedback, and brand perception",
            "3. For launch metrics: Use the Launch Metrics Specialist to track the COMPETITOR's KPIs, adoption rates, press coverage, and performance indicators",
            "",
            "COMPETITOR FOCUS - CRITICAL:",
            "• ALWAYS analyze the COMPETITOR mentioned by the user, NOT the user's own product",
            "• Before performing analysis, verify the competitor is relevant to the user's product category",
            "• If an irrelevant competitor is mentioned (e.g., comparing Spotify to Google), decline politely and suggest relevant alternatives in the same market",
            "• Only analyze direct or indirect competitors in the same product space",
            "• Every insight, metric, and data point MUST be about the COMPETITOR",
            "",
            "RESEARCH RULES:",
            "• ALL agents MUST use Bright Data search_web tool to gather current web data about the COMPETITOR",
            "• NEVER provide analysis without web research - always search first",
            "• Each agent must perform multiple web searches to gather comprehensive data about the COMPETITOR",
            "• Use scrape_url to extract detailed information from the COMPETITOR's websites",
            "",
            "SOURCES REQUIREMENTS:",
            "• Include sources section with ONLY exact URLs you actually crawled or found",
            "• NEVER include Twitter/X links unless you actually obtained data from Twitter/X",
            "• NEVER fabricate or add placeholder URLs - only real sources",
            "• If you didn't find information from a specific platform, don't mention it in sources",
            "",
            "QUALITY REQUIREMENTS:",
            "• Always provide evidence-based insights about the COMPETITOR with specific examples and data points",
            "• Structure responses with clear sections and actionable recommendations",
            "• Cite specific numbers, dates, and observable facts from web research about the COMPETITOR",
            "• Focus entirely on what the user can learn from the COMPETITOR's approach",
        ],
        markdown=True,
    )

    return product_intelligence_team
