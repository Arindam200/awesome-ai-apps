import os
import json
import sqlite3
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from scrapegraph_py import Client
from langgraph.prebuilt import create_react_agent
from langchain_nebius import ChatNebius
from http.client import RemoteDisconnected
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import SecretStr

load_dotenv("api.env")

SMARTCRAWLER_KEY = os.getenv("SMARTCRAWLER_API_KEY")
NEBIUS_KEY = os.getenv("NEBIUS_API_KEY")

if not SMARTCRAWLER_KEY or not NEBIUS_KEY:
    raise EnvironmentError(
        "SMARTCRAWLER_API_KEY and NEBIUS_API_KEY must be set in api.env"
    )

sg_client = Client(api_key=SMARTCRAWLER_KEY)
llm = ChatNebius(model="NousResearch/Hermes-4-70B", api_key=SecretStr(NEBIUS_KEY))


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def run_smartcrawler(url: str) -> str:
    """Simplified SmartCrawler request with doc-style polling and LLM summary"""
    try:
        schema = {
            "type": "object",
            "properties": {
                "Overview": {"type": "string"},
                "Founders": {"type": "array"},
                "Funding": {"type": "array"},
                "Industry": {"type": "string"},
                "Market Size": {"type": "string"},
                "Competitors": {"type": "array"},
            },
        }

        print(f"\n[Crawl] Starting for: {url}")
        crawl_response = sg_client.crawl(
            url=url,
            prompt="Extract detailed company information",
            data_schema=schema,
            cache_website=True,
            depth=2,
            max_pages=5,
            same_domain_only=True,
        )

        crawl_id = crawl_response.get("id") or crawl_response.get("task_id")
        if crawl_id:
            print("[Crawl] Crawl started, polling for result...")
            for i in range(60):
                time.sleep(5)
                result = sg_client.get_crawl(crawl_id)

                print("[DEBUG] Full API Response:", json.dumps(result, indent=2))

                status = result.get("status")
                if status == "success" and result.get("result"):
                    print("[Crawl] Completed successfully.")
                    pages = result["result"].get("pages", [])
                    if pages:
                        markdown_content = "\n\n".join(
                            p.get(
                                "markdown",
                                json.dumps(
                                    p.get("content", {}), indent=2, ensure_ascii=False
                                ),
                            )
                            for p in pages
                        )
                    else:
                        markdown_content = json.dumps(
                            result["result"], indent=2, ensure_ascii=False
                        )
                    # LLM summarize
                    prompt = (
                        "You are a precise company research assistant.\n"
                        "Summarize the following data into structured company insights.\n"
                        "Sections: Overview, Founders, Funding, Industry, Market Size, Competitors.\n\n"
                        f"{markdown_content}"
                    )
                    return llm.invoke(prompt).content
                elif status == "failed":
                    return "Crawl failed."
                print(f"[Crawl] Status={status}, waiting... ({5 * (i + 1)}s elapsed)")
            return "Crawl timeout after 5 minutes."
        else:
            return "No crawl ID found, check URL or API key."

    except Exception as e:
        print(f"[Crawl] Exception: {e}")
        return "Exception during crawling."


def extract_company_name(url: str) -> str:
    """URL se simple company name extract kare"""
    import re

    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    name = match.group(1).replace("-", " ").replace(".com", "") if match else url
    return name.title()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def searchscraper_request(query: str, num_results: int = 5) -> dict:
    """SearchScraper call with retry on connection failures"""
    try:
        print(f"\n[SearchScraper] Searching for: {query}")
        resp = sg_client.searchscraper(user_prompt=query, num_results=num_results)
        return resp
    except RemoteDisconnected:
        print("[SearchScraper] RemoteDisconnected, retrying...")
        raise
    except Exception as e:
        print(f"[SearchScraper] Exception: {e}")
        raise


def run_searchscraper(company_overview: str) -> str:
    """Fetch competitor data with enhanced queries and better competitor analysis"""

    # Extract company name from overview for better targeting
    company_name_match = company_overview.split()[
        :3
    ]  # Take first few words as likely company name
    company_name = " ".join(company_name_match)

    # Create multiple targeted queries for comprehensive competitor research
    queries = [
        f"{company_name} competitors direct rivals and similar companies",
        f"{company_name} vs competitors comparison market",
    ]

    all_results = []

    try:
        # Run multiple queries to get comprehensive competitor data
        for query in queries:
            raw_resp = searchscraper_request(query)
            if raw_resp and raw_resp.get("result"):
                all_results.append(raw_resp["result"])

        if not all_results:
            return "No competitor data found."

        # Combine all search results - convert dictionaries to strings
        combined_results = []
        for result in all_results:
            if isinstance(result, dict):
                # Extract companies information if available
                if "companies" in result and result["companies"]:
                    companies_text = []
                    for company in result["companies"]:
                        if isinstance(company, dict):
                            name = company.get("name", "Unknown")
                            desc = company.get("description", "No description")
                            companies_text.append(f"{name}: {desc}")
                        else:
                            companies_text.append(str(company))
                    combined_results.append("\n".join(companies_text))
                else:
                    # Fallback: convert entire dict to string
                    combined_results.append(str(result))
            else:
                combined_results.append(str(result))

        combined_data = "\n\n---\n\n".join(combined_results)

        prompt = (
            "You are an expert competitive intelligence analyst with deep experience in market research.\n\n"
            "MISSION: Analyze the provided search data and identify ONLY the most direct, relevant competitors.\n"
            "Focus on companies that directly compete for the same customers with similar value propositions.\n\n"
            "STRICT OUTPUT FORMAT:\n\n"
            "# 🏢 Direct Competitors Analysis\n\n"
            "## [Company Name 1]\n"
            "**🎯 Core Focus:** [What they do in 8-10 words]\n"
            "**💰 Business Model:** [Revenue model - SaaS, freemium, etc.]\n"
            "**📊 Market Position:** [Leader/Challenger/Niche - with brief context]\n"
            "**🏢 Company Size:** [Stage + employee range if known]\n"
            "**💵 Funding/Revenue:** [Latest known financial data]\n"
            "**🎯 Target Market:** [Primary customer segments]\n"
            "**⚡ Key Differentiator:** [Main competitive advantage]\n"
            "**🌍 Geographic Reach:** [Primary markets/regions]\n\n"
            "## [Company Name 2]\n"
            "[Same format...]\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- Include ONLY 4-6 most relevant direct competitors\n"
            "- Each bullet point: maximum 12 words\n"
            "- Skip indirect competitors or loosely related companies\n"
            "- Use 'Not available' only if truly no data exists\n"
            "- Prioritize companies that target similar customers with competing solutions\n"
            "- Focus on actionable competitive intelligence\n\n"
            f"COMPANY BEING ANALYZED:\n{company_overview}\n\n"
            f"SEARCH RESULTS TO ANALYZE:\n{combined_data}"
        )

        result = llm.invoke(prompt).content

        # Ensure result is always a string
        if isinstance(result, list):
            result = "\n".join(str(item) for item in result)
        else:
            result = str(result) if result else ""

        # Enhanced validation and cleanup
        if not result or ("##" not in result and "# " not in result):
            return "❌ Unable to extract structured competitor data from search results.\n\n**Suggestion:** Try with a more specific company name or URL."

        # Clean up the result
        if "# 🏢 Direct Competitors Analysis" not in result:
            result = "# 🏢 Direct Competitors Analysis\n\n" + result

        return result

    except RemoteDisconnected:
        print("[SearchScraper] RemoteDisconnected, retrying...")
        raise
    except Exception as e:
        print(f"[SearchScraper] Failed: {e}")
        return "Error fetching competitor data."


def save_to_db(url: str, feature: str, content: str, db_path="company_data.db"):
    if not content.strip():
        content = "No content generated."
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            feature TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "INSERT INTO reports (url, feature, content) VALUES (?, ?, ?)",
        (url, feature, content),
    )
    conn.commit()
    conn.close()
    print(f"[DB] Saved report for {url}, feature={feature}")


def fetch_all_data(db_path="company_data.db") -> List[tuple]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, feature, created_at FROM reports ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_reports_by_url(
    url: str, limit: int = 5, db_path: str = "company_data.db"
) -> List[tuple]:
    """Return recent reports for a URL including content.

    Returns tuples: (id, url, feature, content, created_at)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, url, feature, content, created_at FROM reports WHERE url = ? ORDER BY id DESC LIMIT ?",
        (url, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_latest_by_feature(
    url: str, feature: str, db_path: str = "company_data.db"
) -> str | None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content FROM reports WHERE url = ? AND feature = ? ORDER BY id DESC LIMIT 1",
        (url, feature),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def assemble_cached_combined(url: str, db_path: str = "company_data.db") -> str | None:
    """Try to combine latest SmartCrawler + SearchScraper content from DB for given URL.

    Returns combined markdown string if both exist; if only one exists, returns that one; otherwise None.
    """
    sc = fetch_latest_by_feature(url, "smartcrawler", db_path=db_path)
    ss = fetch_latest_by_feature(url, "searchscraper", db_path=db_path)
    if sc and ss:
        return f"## 🕷️ Crawler Data:\n{sc}\n\n## 🔍 Scraper Data:\n{ss}"
    if sc:
        return f"## 🕷️ Crawler Data:\n{sc}"
    if ss:
        return f"## 🔍 Scraper Data:\n{ss}"
    return None


# ---------------------------
# Unified tool for all agents
# ---------------------------
def company_market_tool(url: str, feature: str = "research") -> str:
    """
    Combine SmartCrawler + SearchScraper to fetch company research and competitor insights.

    Args:
        url (str): Target company URL.
        feature (str, optional): Feature type for DB storage. Defaults to "research".

    Returns:
        str: Combined report from SmartCrawler and SearchScraper.
    """
    sc_data = run_smartcrawler(url)
    sc_content = f"## 🕷️ Crawler Data:\n{sc_data}"

    # Extract overview (first paragraph)
    overview_lines = sc_data.splitlines()
    company_overview = " ".join(overview_lines[:2]) if overview_lines else url

    # Use overview for searchscraper
    ss_data = run_searchscraper(company_overview)
    ss_content = f"\n## 🔍 Scraper Data:\n{ss_data}"

    full_content = sc_content + ss_content
    save_to_db(url, feature, full_content)
    return full_content


# ---------------------------
# Agents
# ---------------------------
research_agent = create_react_agent(
    model=llm,
    tools=[company_market_tool],
    prompt="""
You are a professional Company Research & Market Intelligence Assistant.
Your role is to ALWAYS call `company_market_tool` first to gather grounded insights. Do not fabricate missing facts; if data is unavailable, write "Not found".
Analyze and summarize the target company with clear, structured sections:

1. **Company Overview** – history, mission, vision, key offerings.
2. **Funding & Financials** – latest funding rounds, investors, financial health.
3. **Industry & Market Size** – sector, growth rate, TAM/SAM/SOM if available.
4. **Competitors** – top direct & indirect competitors with brief comparison.
5. **Market Insights & Trends** – opportunities, risks, and emerging trends.

Output must be **well-formatted, concise yet insightful**, and suitable for business/strategic decision-making.
Guidelines:
- Be concise, factual, and business-ready. Use bullet points where possible.
- When listing numbers, include units (USD, %, year) and avoid ranges unless present in sources.
- If uncertain, explicitly state the uncertainty instead of guessing.
- End with a short section: **Assumptions & Gaps** capturing missing or ambiguous items.
""",
)

gtm_agent = create_react_agent(
    model=llm,
    tools=[company_market_tool],
    prompt="""
You are a professional Go-To-Market (GTM) Strategist.
ALWAYS use the insights from `company_market_tool` output to generate a structured GTM playbook. Do not invent market sizes, pricing, or ICP details beyond what is supported; when unavailable, state "Not found" and provide a reasonable next-step to validate.
Ensure recommendations are practical, data-driven, and tailored for business execution.

Your GTM Playbook must include the following sections:

1. **Target Market** – clearly define market segments, size, and opportunities.
2. **Ideal Customer Profile (ICP)** – demographics, firmographics, pain points, and buying behavior.
3. **Core Messaging & Value Proposition** – key narratives, positioning statements, and differentiators.
4. **Pricing Strategy** – pricing model, competitive positioning, and justification.
5. **Distribution & Sales Strategy** – direct, indirect, online/offline, partner ecosystem.
6. **Growth Channels** – short-term & long-term channels (SEO, paid ads, partnerships, community, etc.).

Output should be **professional, actionable, and formatted in clear sections** suitable for use in GTM presentations or strategic planning.
Add a final section **Metrics & KPIs** with 5-8 measurable indicators to track.
""",
)

channel_agent = create_react_agent(
    model=llm,
    tools=[company_market_tool],
    prompt="""
You are a Distribution & Channel Strategy Expert.
If the user message already contains company research data, use that information directly. If the user provides only a URL, use `company_market_tool` to gather company insights first. Do not hallucinate partner names; only include if present or widely-known and relevant.

Your recommendations should cover:

1. **Primary Channels** – direct sales, online platforms, retail, partnerships, or resellers.
2. **Digital Channels** – SEO, paid ads, marketplaces, app stores, social media, influencer marketing.
3. **Partnerships & Alliances** – distributors, affiliates, VARs, or strategic partners.
4. **Emerging/Innovative Channels** – communities, niche platforms, co-marketing opportunities.
5. **Channel Justification** – explain why each recommended channel fits the company's ICP, market, and product type.

Output must be **well-structured, business-oriented, and actionable**, providing clear guidance for the company's go-to-market execution.
Include a short **Risks & Dependencies** section covering channel risks and mitigations.
""",
)


def report_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("already_called"):
        return state
    state["already_called"] = True
    messages = state.get("messages", [])
    content = (
        "\n\n---\n\n".join(getattr(m, "content", str(m)) for m in messages)
        or "No content generated."
    )
    save_to_db(state.get("url", "unknown_url"), state.get("feature", "report"), content)
    state["db_saved"] = True
    return state


def generate_full_company_report(url: str) -> str:
    smartcrawler_data = run_smartcrawler(url)
    print(f"[Report] SmartCrawler done for {url}")

    try:
        overview_lines = smartcrawler_data.splitlines()
        company_name = overview_lines[0] if overview_lines else url
        query = f"Companies similar to {company_name} in the same industry"
    except Exception as e:
        print(f"[Report] Error extracting company name: {e}")
        query = f"Companies similar to {url}"

    searchscraper_data = run_searchscraper(query)
    print(f"[Report] SearchScraper done for query: {query}")

    full_report = (
        f"### Company Research Report for {url}\n\n"
        f"---\n**SmartCrawler Data:**\n{smartcrawler_data}\n\n"
        f"---\n**Market & Competitor Data (SearchScraper):**\n{searchscraper_data}\n"
    )

    save_to_db(url, "full_report", full_report)
    print(f"[Report] Full report saved for {url}")

    return full_report
