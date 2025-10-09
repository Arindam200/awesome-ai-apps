from typing import Dict, AsyncIterator, Optional, List, Any
import json
import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.storage.sqlite import SqliteStorage
from agno.tools.firecrawl import FirecrawlTools
from agno.utils.log import logger
from agno.utils.pprint import pprint_run_response
from dotenv import load_dotenv
from textwrap import dedent
import asyncio
load_dotenv()

# Get API keys from environment variables
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

# Validate API keys
if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY environment variable is not set. Please set it in your .env file or environment.")
if not NEBIUS_API_KEY:
    raise ValueError("NEBIUS_API_KEY environment variable is not set. Please set it in your .env file or environment.")

# Newsletter Research Agent: Handles web searching and content extraction using Firecrawl
newsletter_agent = Agent(
    model=Nebius(
        id="meta-llama/Meta-Llama-3.1-70B-Instruct",
        api_key=NEBIUS_API_KEY
    ),
    tools=[
        FirecrawlTools(
            search=True,
            formats=["markdown", "links"],
            search_params={
                "limit": 2,
                "tbs": "qdr:w",
            },
        ),
    ],
    description=dedent("""\
    You are NewsletterResearch-X, an elite research assistant specializing in discovering
    and extracting high-quality content for compelling newsletters. Your expertise includes:

    - Finding authoritative and trending sources across multiple domains
    - Extracting and synthesizing content efficiently while maintaining accuracy
    - Evaluating content credibility, relevance, and potential impact
    - Identifying diverse perspectives, expert opinions, and emerging trends
    - Ensuring comprehensive topic coverage with balanced viewpoints
    - Maintaining journalistic integrity and ethical reporting standards
    - Creating engaging narratives that resonate with target audiences
    - Adapting content style and depth based on audience expertise level\
    """),
    instructions=dedent("""\
    1. Initial Research & Discovery:
       - Use firecrawl_search to find recent articles about the topic
       - Search for authoritative sources, expert opinions, and industry leaders
       - Look for industry reports, market analysis, and academic research
       - Focus on the most recent and relevant content (prioritize last 7 days)
       - Identify key stakeholders and their perspectives
       - Look for contrasting viewpoints to ensure balanced coverage

    2. Content Analysis & Processing:
       - Extract key insights, trends, and patterns from each article
       - Identify important quotes, statistics, and data points
       - Evaluate source credibility, expertise, and potential biases
       - Assess the impact and implications of the information
       - Look for connections between different pieces of information
       - Identify gaps in coverage that need additional research

    3. Content Organization & Structure:
       - Group related information by theme and significance
       - Identify main story angles and supporting narratives
       - Create a logical flow of information
       - Prioritize content based on relevance and impact
       - Ensure balanced coverage of different perspectives
       - Structure content for optimal reader engagement

    4. Newsletter Creation:
       - Follow the exact template structure below
       - Create compelling headlines that capture attention
       - Write engaging introductions that set context
       - Develop clear, concise, and informative sections
       - Include relevant quotes and statistics to support key points
       - Maintain consistent tone and style throughout
       - Use markdown formatting effectively
       - Ensure proper attribution for all content
       - Include actionable insights and practical takeaways
       - Add relevant links for further reading

    Guidelines:
    - Always use firecrawl_search to gather comprehensive information
    - Prioritize recent (within 7 days) and authoritative sources
    - Maintain proper attribution and citation for all content
    - Focus on actionable insights and practical implications
    - Keep content engaging, accessible, and well-structured
    - Use markdown formatting consistently and effectively
    - Ensure proper formatting and structure throughout
    - Replace all {placeholder} fields with specific, relevant content
    - Create specific, topic-relevant titles for sections
    - Include diverse perspectives and balanced viewpoints
    - Add value through analysis and expert insights
    - Maintain journalistic integrity and ethical standards
    - STRICTLY follow the expected_output format

    """),
    expected_output=dedent("""\
        # ${Compelling Subject Line}

        ## Welcome
        {Engaging hook and context}

        ## ${Main Story}
        {Key insights and analysis}
        {Expert quotes and statistics}

        ## Featured Content
        {Deeper exploration}
        {Real-world examples}

        ## Quick Updates
        {Actionable insights}
        {Expert recommendations}

        ## This Week's Highlights
        - {Notable update 1}
        - {Important news 2}
        - {Key development 3}

        ## Sources & Further Reading
        {Properly attributed sources with links}
    """),
    markdown=True,
    show_tool_calls=True,
    add_datetime_to_instructions=True,
    # Ensure database directory exists
    # os.makedirs("tmp", exist_ok=True)

    storage=SqliteStorage(
        table_name="newsletter_agent",
        db_file="tmp/newsletter_agent.db",
    )
)

def NewsletterGenerator(topic: str, search_limit: int = 5, time_range: str = "qdr:w") -> Dict[str, Any]:
    """
    Generate a newsletter based on the given topic and search parameters.

    Args:
        topic (str): The topic to generate the newsletter about
        search_limit (int): Maximum number of articles to search and analyze
        time_range (str): Time range for article search (e.g., "qdr:w" for past week)

    Returns:
        Dict[str, Any]: Processed newsletter content with structured metadata

    Raises:
        ValueError: If configuration validation fails
        RuntimeError: If newsletter generation fails
    """
    try:
        # Update search parameters
        newsletter_agent.tools[0].search_params.update({
            'limit': search_limit,
            'tbs': time_range
        })

        response = newsletter_agent.run(topic)
        logger.info('Newsletter generated successfully')
        return response
    except ValueError as ve:
        logger.error('Configuration error: %s', ve)
        raise
    except Exception as e:
        logger.error('Unexpected error in newsletter generation: %s', e, exc_info=True)
        raise RuntimeError('Newsletter generation failed: %s' % e) from e

if __name__ == "__main__":
    NewsletterGenerator("Latest developments in AI")