"""
Job Search Workflow
Uses LangChain for agent orchestration and ExaAI for web search
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional
from exa_py import Exa
from langchain_nebius import ChatNebius
from langchain_core.messages import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()

# System prompt for job extraction and processing
JOB_EXTRACTION_SYSTEM_PROMPT = """You are an expert job search assistant. Your task is to extract and structure job information from web search results.

When processing job listings, you should:
1. Extract the job title accurately
2. Identify the company name from the content
3. Determine the location if mentioned
4. Identify work style (Remote, Hybrid, Onsite) if mentioned
5. Extract salary information if available
6. Create a concise description (max 500 characters)

Be precise and only extract information that is clearly stated in the content. If information is missing, use placeholder values like "Location not specified" or "Not specified".
"""


# Pydantic models
class JobSearchConfig(BaseModel):
    job_title: str = Field(..., min_length=1)
    location: Optional[str] = None
    work_style: Optional[str] = Field(None, pattern="^(Remote|Hybrid|Onsite|Any)$")
    num_jobs: int = Field(default=5, ge=1, le=20)


class JobListing(BaseModel):
    title: str
    company: str
    location: str
    work_style: str
    url: str
    description: str
    salary: Optional[str] = None


def build_search_query(config: JobSearchConfig) -> str:
    """Build a search query from config"""
    query_parts = [config.job_title]

    if config.location:
        query_parts.append(config.location)

    if config.work_style and config.work_style != "Any":
        query_parts.append(config.work_style)

    # Add job-specific keywords
    query_parts.append("job opening")
    query_parts.append("hiring")

    return " ".join(query_parts)


def search_jobs_with_exa(config: JobSearchConfig) -> List[dict]:
    """Search for jobs using ExaAI from multiple sources"""
    try:
        # Initialize ExaAI client
        exa_key = os.getenv("EXA_API_KEY")
        if not exa_key:
            raise Exception("EXA_API_KEY not set in environment variables")

        exa_client = Exa(api_key=exa_key)
        search_query = build_search_query(config)

        # Calculate date 7 days ago for filtering
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

        # Build domain filters for job sites - split into groups for better distribution
        job_domain_groups = [
            ["indeed.com", "glassdoor.com"],
            ["monster.com", "ziprecruiter.com"],
            ["careerbuilder.com", "jobs.com"],
            ["linkedin.com"],  # LinkedIn separately to ensure we get other sources too
        ]

        # Search with ExaAI from multiple sources
        all_results = []
        seen_urls = set()

        # Search across different domain groups to get diversity
        for domain_group in job_domain_groups:
            try:
                results = exa_client.search_and_contents(
                    query=search_query,
                    num_results=max(
                        5, config.num_jobs // 2
                    ),  # Get a good sample from each
                    include_domains=domain_group,
                    text=True,
                    type="auto",
                    start_published_date=seven_days_ago,  # Only jobs from last 7 days
                )

                # Add unique results
                for result in results.results:
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        all_results.append(result)

                # If we have enough unique results, we can stop early
                if len(all_results) >= config.num_jobs * 2:
                    break
            except Exception:
                # Continue if one domain group fails
                continue

        # If we still need more results, do a general search
        if len(all_results) < config.num_jobs:
            try:
                all_domains = [
                    "indeed.com",
                    "glassdoor.com",
                    "monster.com",
                    "ziprecruiter.com",
                    "careerbuilder.com",
                    "jobs.com",
                    "linkedin.com",
                ]
                results = exa_client.search_and_contents(
                    query=search_query,
                    num_results=config.num_jobs * 2,
                    include_domains=all_domains,
                    text=True,
                    type="auto",
                    start_published_date=seven_days_ago,
                )

                for result in results.results:
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        all_results.append(result)
            except Exception:
                pass

        # Initialize LLM for better extraction if API key is available
        llm = None
        nebius_key = os.getenv("NEBIUS_API_KEY")
        if nebius_key:
            try:
                llm = ChatNebius(
                    model="Qwen/Qwen3-Coder-480B-A35B-Instruct",
                    temperature=0.6,
                    top_p=0.95,
                    api_key=nebius_key,
                )
            except Exception:
                llm = None

        # Process results into job listings
        job_listings = []
        for result in all_results:
            try:
                # Extract job information from result using LLM-enhanced extraction
                job_data = {
                    "title": result.title or "Job Opening",
                    "company": extract_company(result.text or "", llm=llm),
                    "location": config.location or "Location not specified",
                    "work_style": config.work_style or "Any",
                    "url": result.url,
                    "description": (
                        result.text if result.text else "No description available"
                    ),
                    "salary": extract_salary(result.text or ""),
                }
                job_listings.append(job_data)
            except Exception as e:
                continue

        # Limit to requested number
        return job_listings[: config.num_jobs]

    except Exception as e:
        raise Exception(f"Error searching for jobs: {str(e)}")


def extract_company(text: str, llm=None) -> str:
    """Extract company name from job description using LLM if available"""
    import re

    # Try LLM-based extraction first if available
    if llm:
        try:
            prompt = f"""Extract the company name from this job description. Return only the company name, nothing else.

Job description:
{text[:1000]}

Company name:"""
            response = llm.invoke(
                [
                    SystemMessage(content=JOB_EXTRACTION_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            company = response.content.strip()
            if (
                company
                and len(company) < 100
                and company.lower() not in ["none", "not specified", "n/a", "unknown"]
            ):
                return company
        except Exception:
            pass

    # Fallback to regex extraction
    # Look for patterns like "at Company Name" or "Company Name is hiring"
    patterns = [
        r"at\s+([A-Z][a-zA-Z\s&]+?)(?:\s|,|\.|$)",
        r"([A-Z][a-zA-Z\s&]+?)\s+is\s+hiring",
        r"([A-Z][a-zA-Z\s&]{2,30})\s+(?:is|seeks|looking)",
        r"(?:company|employer):\s*([A-Z][a-zA-Z\s&]{2,50})",
        r"([A-Z][a-zA-Z\s&]{2,50})\s+(?:is\s+)?hiring\s+(?:a|an|the)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:300], re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean up common words
            company = re.sub(
                r"\b(at|is|seeks|looking|hiring|company|employer)\b",
                "",
                company,
                flags=re.IGNORECASE,
            ).strip()
            if len(company) > 2 and len(company) < 50:
                return company

    return "Company not specified"


def extract_salary(text: str) -> Optional[str]:
    """Extract salary information from job description"""
    import re

    # Look for salary patterns
    patterns = [
        r"\$(\d{1,3}(?:,\d{3})*(?:k|K)?)\s*-\s*\$(\d{1,3}(?:,\d{3})*(?:k|K)?)",
        r"\$(\d{1,3}(?:,\d{3})*(?:k|K)?)\s*(?:to|-)\s*\$(\d{1,3}(?:,\d{3})*(?:k|K)?)",
        r"(\d{1,3}(?:,\d{3})*)\s*-\s*(\d{1,3}(?:,\d{3})*)\s*(?:USD|per year|annually)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:500])
        if match:
            return match.group(0).strip()

    return None


def process_job_search(config: JobSearchConfig) -> List[JobListing]:
    """Main workflow to search and process jobs"""
    # Search for jobs
    job_data_list = search_jobs_with_exa(config)

    # Convert to JobListing objects
    job_listings = []
    for job_data in job_data_list:
        try:
            job_listing = JobListing(**job_data)
            job_listings.append(job_listing)
        except Exception as e:
            # Skip invalid listings
            continue

    return job_listings
