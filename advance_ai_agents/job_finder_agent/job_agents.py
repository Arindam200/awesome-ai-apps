import os
import logging
import asyncio
from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    set_tracing_disabled,
)
from agents.mcp import MCPServer
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

async def run_analysis(mcp_server: MCPServer, linkedin_url: str):
    logger.info(f"Starting analysis for LinkedIn URL: {linkedin_url}")
    api_key = os.environ["NEBIUS_API_KEY"]
    base_url = "https://api.studio.nebius.ai/v1" 
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    set_tracing_disabled(disabled=True)

    linkedin_agent = Agent(
        name="LinkedIn Profile Analyzer",
        instructions=f"""You are a LinkedIn profile analyzer.
        Analyze profiles for:
        
        - Professional experience and career progression
        - Education and certifications
        - Core skills and expertise
        - Current role and company
        - Previous roles and achievements
        - Industry reputation (recommendations/endorsements)
        
        Provide a structured analysis with bullet points and a brief executive summary.
        
        NOTE: If the user has no experience, just say "No experience found" and don't make up any information. Also if any of the information is not available, just say "Not available" and don't make up any information.
        DISCLAIMER: This Agent should call the tool to get the information. Once the tool is called, it will return the information in the response. It should not call the tool Multiple times after the tool is called.
        """,
        mcp_servers=[mcp_server],
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )

    job_suggestions_agent = Agent(
        name="Job Suggestions",
        instructions=f"""You are a domain classifier that identifies the primary professional domain from a LinkedIn profile.

        Select ONE domain from:
        - Software Engineering (for programming, development, technical skills)
        - Design & UI/UX (for design, user experience, visual skills)
        - Product Management (for product strategy, roadmap, feature planning)
        - Recruiting & HR (for talent acquisition, HR operations, people management)
        - Sales (for sales, business development)
        - Science (for research, data science, scientific expertise)
        - Marketing (for Content Writing, Technical Writing, Developer Relations,Developer Advocacy, advertising, brand management)
        Rules:
        - Choose based on PRIMARY skills and experience
        - If multiple domains exist, pick the most recent/relevant one
        - Default to Software Engineering if unclear
        - Return "No experience found" for empty profiles
        - Never make up or assume skills

        Format response as JSON:
        {{
            "selected_domain": "chosen domain",
            "confidence_score": 0-100,
            "selection_reason": "brief explanation"
        }}
        """,
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )

    url_generator_agent = Agent(
        name="URL Generator",
        instructions=f"""You are a URL generator that creates Y Combinator job board URLs based on domains.

        Input: JSON from job suggestions agent with format:
        {{
            "selected_domain": "domain name",
            "confidence_score": number,
            "selection_reason": "reason"
        }}

        Map domains to URLs:
        - "Software Engineering" -> "ycombinator.com/jobs/role/software-engineer"
        - "Design & UI/UX" -> "ycombinator.com/jobs/role/designer"
        - "Product Management" -> "ycombinator.com/jobs/role/product-manager"
        - "Recruiting & HR" -> "ycombinator.com/jobs/role/recruiting-hr"
        - "Sales" -> "ycombinator.com/jobs/role/sales-manager"
        - "Science" -> "ycombinator.com/jobs/role/science"
        - "Marketing" -> "ycombinator.com/jobs/role/marketing"

        Output format:
        {{
            "job_board_url": "mapped url",
            "domain": "original domain"
        }}

        Rules:
        - Return exact URL match for domain
        - If domain not found, return "ycombinator.com/jobs"
        - Keep original domain in output
        """,
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )

    Job_search_agent = Agent(
        name="Job Finder",
        instructions=f"""You are a job finder that extracts job listings from Y Combinator's job board.

        Steps:
        1. Take the URL from job_link_result agent's JSON response
        2. Use the provided URL to fetch job listings ONCE.

        3. For each job listing, extract ONLY these fields:
           - Company name (from the company link text)
           - Job title (from the job link text)
           - Job type (Full-time/Part-time/Contract)
           - Location (including remote status)
           - Apply URL (from the Apply button href)

        4. Format output as:
        ## Job Matches for [Domain]
        ### [Job Title]
        - **Company:** [Company Name]
        - **Type:** [Job Type]
        - **Location:** [Location]
        - **Apply:** [Apply URL]

        Rules:
        - Only extract information from the first 5 most relevant job listings
        - Skip navigation links, footer content, and other non-job elements
        - Use exact text from the job listing
        - Return "No jobs found" if no listings are available
        - Ignore job categories and location filters
        - Do not include any additional information not present in the job listing
        - IMPORTANT: Call the tool EXACTLY ONCE to fetch the job listings

        Note: No information should be added to the response that is not provided in the input. Don't make up any information.
        """,
        mcp_servers=[mcp_server],
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )
    
    url_parser_agent = Agent(
        name="URL Parser",
        instructions=f"""You are a URL parser that transforms Y Combinator authentication URLs into direct job URLs.

        Input: Job listings with authentication URLs in format:
        ## Job Matches for [Domain]
        ### [Job Title]
        - **Company:** [Company Name]
        - **Type:** [Job Type]
        - **Location:** [Location]
        - **Apply:** [Auth URL]

        Rules:
        1. Extract job_id from the authentication URL
           - Look for 'signup_job_id=' parameter
           - Example: from '...signup_job_id=75187...' extract '75187'
        
        2. Create new direct URL format:
           - Base URL: 'https://www.workatastartup.com/jobs/'
           - Append job_id
           - Example: 'https://www.workatastartup.com/jobs/75187'

        3. Replace the Apply URL in each job listing with the new direct URL

        Output format:
        ## Job Matches for [Domain]
        ### [Job Title]
        - **Company:** [Company Name]
        - **Type:** [Job Type]
        - **Location:** [Location]
        - **Apply:** [Direct URL]

        Note: Keep all other information exactly the same, only transform the Apply URLs.
        """,
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )
    
    summary_agent = Agent(
        name="Summary Agent",
        instructions=f"""You are a summary agent that creates comprehensive career analysis reports.
        Your task is to:
        1. Take the inputs from various agents (LinkedIn analysis, job suggestions, and job matches)
        2. Create a well-structured, professional summary in markdown format that includes:
           - A concise profile summary
           - Top skills identified
           - Recommended career paths
           - Detailed role suggestions with reasons and requirements
           - Current job matches with match scores
           - Skills to develop
           - Career development suggestions
        
        Format your response in markdown with the following structure:
        ```markdown
        ## 👤 Profile Summary
        [Write a brief summary of the person's career profile]

        ## 🎯 Your Top Skills:
        - [Skill 1]
        - [Skill 2]

        ...

        ## 💡 Suggested Roles:
        ### [Role Title]
        - **Why this role?** [Explanation]
        - **Required Skills:** [Skill 1, Skill 2, ...]
        - **Potential Companies:** [Company 1, Company 2, ...]
        - **Growth Potential:** [Growth opportunities]
        - **Salary Range:** [Salary range if available]

        ## 💼 Current Job Matches:
        ### [Job Title] at [Company]
          - [Brief description]
          - Match Score: [Score]%
          - [Apply Here]([Job URL])
        ...
        ```
        
        Note: No information should be added to the response that is not provided in the input. Don't make up any information.
        Ensure your response is well-formatted markdown that can be directly displayed.""",
        model=OpenAIChatCompletionsModel(
            model="meta-llama/Llama-3.3-70B-Instruct",
            openai_client=client
        )
    )
    
    query = f"""Analyze the LinkedIn profile at {linkedin_url}.
    Focus on gathering comprehensive information about the person's professional background.
    Then, find the best job for the user based on their profile.
    """

    try:
        # Get LinkedIn profile analysis
        logger.info("Running LinkedIn profile analysis")
        linkedin_result = await Runner.run(starting_agent=linkedin_agent, input=query)
        logger.info("LinkedIn profile analysis completed")

        # Get job suggestions
        logger.info("Getting job suggestions")
        suggestions_result = await Runner.run(starting_agent=job_suggestions_agent, input=linkedin_result.final_output)
        logger.info("Job suggestions completed")

        # Get specific job matches
        logger.info("Getting job link")
        job_link_result = await Runner.run(starting_agent=url_generator_agent, input=suggestions_result.final_output)
        logger.info("Job link generation completed")

        # Get job matches
        logger.info("Getting job matches")
        job_search_result = await Runner.run(starting_agent=Job_search_agent, input=job_link_result.final_output)
        logger.info("Job search completed")

        # Parse URLs to get direct job links
        logger.info("Parsing job URLs")
        parsed_urls_result = await Runner.run(starting_agent=url_parser_agent, input=job_search_result.final_output)
        logger.info("URL parsing completed")

        # Create a single input for the summary agent
        logger.info("Generating final summary")
        summary_input = f"""LinkedIn Profile Analysis:
        {linkedin_result.final_output}

        Job Suggestions:
        {suggestions_result.final_output}

        Job Matches:
        {parsed_urls_result.final_output}

        Please analyze the above information and create a comprehensive career analysis report in markdown format."""
        
        # Get final summary with a single call
        summary_result = await Runner.run(starting_agent=summary_agent, input=summary_input)
        logger.info("Summary generation completed")
        return summary_result.final_output

    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        raise e 