from dotenv import load_dotenv
from brightdata import bdclient
from agno.models.nebius import Nebius
from agno.agent import Agent
from pydantic import BaseModel, Field
from typing import List
import json
import os
import re

# Load environment variables from the .env file
load_dotenv()

# Initialize the Bright Data SDK client
brightdata_client = bdclient(api_token=os.getenv("BRIGHTDATA_API_KEY"))

# Initialize Nebius AI model
nebius_model = Nebius(
    id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
    api_key=os.getenv("NEBIUS_API_KEY"),
)


# Pydantic models
class Config(BaseModel):
    search_queries: List[str] = Field(..., min_length=1)
    num_news: int = Field(..., gt=0)


class URLList(BaseModel):
    urls: List[str]


class NewsAnalysis(BaseModel):
    title: str
    url: str
    summary: str
    sentiment_analysis: str
    insights: List[str]


def get_google_news_page_urls(search_queries):
    # Retrieve SERPs for the given search queries
    serp_results = brightdata_client.search(
        search_queries,
        search_engine="google",
        parse=True,  # To get the SERP result as a parsed JSON string
    )

    news_page_urls = []
    for serp_result in serp_results:
        # Loading the JSON string to a dictionary
        serp_data = json.loads(serp_result)
        # Extract the Google News URL from each parsed SERP
        if serp_data.get("navigation"):
            for item in serp_data["navigation"]:
                if item["title"] == "News":
                    news_url = item["href"]
                    news_page_urls.append(news_url)

    return news_page_urls


def scrape_news_pages(news_page_urls):
    # Scrape each news page in parallel and return their content in Markdown
    return brightdata_client.scrape(
        url=news_page_urls,
        data_format="markdown",
    )


def get_best_news_urls(news_pages, num_news):
    # Use Nebius AI to extract the most relevant news URLs
    agent = Agent(
        name="News URL Extractor",
        description=f"Extract the {num_news} most relevant news for brand reputation monitoring from the text and return them as a list of URL strings.",
        model=nebius_model,
        markdown=True,
    )

    response = agent.run(
        f"Extract the {num_news} most relevant news URLs for brand reputation monitoring from this content:\n\n"
        + "\n\n---------------\n\n".join(news_pages)
        + "\n\nReturn only the URLs as a simple list, one per line. Each URL must start with http:// or https://"
    )

    # Convert RunOutput to string - FIX for 'RunOutput' object has no attribute 'split'
    response_text = (
        str(response.content) if hasattr(response, "content") else str(response)
    )

    # Parse URLs from response using regex for better accuracy
    urls = []

    # Use regex to find all URLs that start with http:// or https://
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    found_urls = re.findall(url_pattern, response_text)

    for url in found_urls:
        # Clean up URL - remove trailing punctuation
        url = url.rstrip(".,;:!?)]")
        # Validate it's a proper URL
        if url.startswith("http://") or url.startswith("https://"):
            urls.append(url)

    # If regex didn't find enough URLs, try line-by-line parsing as fallback
    if len(urls) < num_news:
        for line in response_text.split("\n"):
            line = line.strip()
            if line and ("http://" in line or "https://" in line):
                # Extract URL from line
                if "https://" in line:
                    idx = line.find("https://")
                    url = line[idx:]
                elif "http://" in line:
                    idx = line.find("http://")
                    url = line[idx:]
                else:
                    continue

                # Remove everything after first space
                if " " in url:
                    url = url.split(" ")[0]

                # Remove trailing punctuation
                url = url.rstrip(".,;:!?)]")

                # Validate and add if not already in list
                if (
                    url.startswith("http://") or url.startswith("https://")
                ) and url not in urls:
                    urls.append(url)

    return urls[:num_news]  # Return only the requested number


def scrape_news_articles(news_urls):
    # Scrape each news URL and return a list of dicts with URL and content
    news_content_list = brightdata_client.scrape(
        url=news_urls,
        data_format="markdown",
    )

    news_list = []
    for url, content in zip(news_urls, news_content_list):
        news_list.append(
            {
                "url": url,
                "content": content,
            }
        )

    return news_list


def process_news_list(news_list):
    # Where to store the analyzed news articles
    news_analysis_list = []

    # Create agent for news analysis
    analysis_agent = Agent(
        name="News Analysis Agent",
        description="""Given news content, analyze it for brand reputation monitoring:
1. Extract the title
2. Extract the URL
3. Write a summary in no more than 30 words
4. Extract the sentiment as "positive", "negative", or "neutral"
5. Extract 3-5 actionable insights about brand reputation (10-12 words each)

Format your response as:
TITLE: [title]
URL: [url]
SUMMARY: [summary]
SENTIMENT: [positive/negative/neutral]
INSIGHTS:
- [insight 1]
- [insight 2]
- [insight 3]
- [insight 4]
- [insight 5]""",
        model=nebius_model,
        markdown=True,
    )

    # Analyze each news article with Nebius AI for brand reputation monitoring insights
    for news in news_list:
        response = analysis_agent.run(
            f"NEWS URL: {news['url']}\n\nNEWS CONTENT: {news['content']}"
        )

        # Convert RunOutput to string - FIX for 'RunOutput' object has no attribute 'split'
        response_text = (
            str(response.content) if hasattr(response, "content") else str(response)
        )

        # Parse the response into NewsAnalysis object
        analysis = parse_news_analysis(response_text, news["url"])
        news_analysis_list.append(analysis)

    return news_analysis_list


def parse_news_analysis(response_text, original_url):
    """Parse the agent response into a NewsAnalysis object"""
    lines = response_text.split("\n")

    title = ""
    summary = ""
    sentiment = "neutral"
    insights = []

    for line in lines:
        line = line.strip()
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif line.startswith("SENTIMENT:"):
            sentiment = line.replace("SENTIMENT:", "").strip().lower()
        elif line.startswith("- "):
            insights.append(line.replace("- ", "").strip())

    # Fallback values if parsing fails
    if not title:
        title = "News Article"
    if not summary:
        summary = "Summary not available"
    if sentiment not in ["positive", "negative", "neutral"]:
        sentiment = "neutral"
    if not insights:
        insights = ["Analysis in progress"]

    return NewsAnalysis(
        title=title,
        url=original_url,
        summary=summary,
        sentiment_analysis=sentiment,
        insights=insights,
    )


def main():
    # Read the config file and validate it
    with open("config.json", "r", encoding="utf-8") as f:
        raw_config = json.load(f)
        config = Config.model_validate(raw_config)

    search_queries = config.search_queries
    print(
        f"Retrieving Google News page URLs for the following search queries: {', '.join(search_queries)}"
    )
    google_news_page_urls = get_google_news_page_urls(search_queries)
    print(f"{len(google_news_page_urls)} Google News page URL(s) retrieved!\n")

    print("Scraping content from each Google News page...")
    scraped_news_pages = scrape_news_pages(google_news_page_urls)
    print("Google News pages scraped!\n")

    print("Extracting the most relevant news URLs...")
    news_urls = get_best_news_urls(scraped_news_pages, config.num_news)
    print(
        f"{len(news_urls)} news articles found:\n"
        + "\n".join(f"- {news}" for news in news_urls)
        + "\n"
    )

    print("Scraping the selected news articles...")
    news_list = scrape_news_articles(news_urls)
    print(f"{len(news_urls)} news articles scraped!")

    print("Analyzing each news for brand reputation monitoring...")
    news_analysis_list = process_news_list(news_list)
    print("News analysis complete!\n")

    print("\n" + "=" * 80)
    print("BRAND REPUTATION MONITORING REPORT")
    print("=" * 80)

    for i, analysis in enumerate(news_analysis_list, 1):
        print(f"\n{i}. {analysis.title}")
        print(f"   URL: {analysis.url}")
        print(f"   Summary: {analysis.summary}")
        print(f"   Sentiment: {analysis.sentiment_analysis}")
        print("   Key Insights:")
        for insight in analysis.insights:
            print(f"   - {insight}")
        print("-" * 60)

    print("\nReport generation complete!")


# Run the main function
if __name__ == "__main__":
    main()
