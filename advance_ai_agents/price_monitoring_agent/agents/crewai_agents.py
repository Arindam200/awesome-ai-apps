import json
import os

from crewai import Agent, Task, Crew
from crewai_tools import ScrapegraphScrapeTool
from dotenv import load_dotenv
from tools.custom_tools import DecisionTool, NotifyTool
import litellm
PRODUCT_DATA_FILE = "product_data.json"

class NebiusLLM:
    def __init__(self, api_key, model="nebius/Qwen/Qwen3-14B"):
        self.api_key = api_key
        self.model = model
        self.api_base = "https://api.studio.nebius.com/v1/"

    def __call__(self, prompt, **kwargs):
        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                api_base=self.api_base,
                provider="nebius"
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            print(f"[NebiusLLM Error] {e}")
            return {"error": "Error generating response from LLM."}


def load_json(file_path, default_value):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default_value
    return default_value


def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def generate_message(data):
    return (
        f"{data.get('title', 'Unknown Product')} is now "
        f"{data.get('availability', 'Unknown')} at price "
        f"{data.get('current_price', 'N/A')}. Rating: {data.get('rating', 'N/A')}"
    )


def run_agents(product_url, previous_data=None):
    load_dotenv("api.env")

    if not product_url or not product_url.startswith(("http://", "https://")):
        return {"error": "No valid product URL provided."}

    all_previous_data = load_json(PRODUCT_DATA_FILE, {})
    if previous_data is None:
        previous_data = all_previous_data.get(product_url, {})

    NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
    SCRAPEGRAPH_API_KEY = os.getenv("SCRAPEGRAPH_API_KEY")

    if not NEBIUS_API_KEY or not SCRAPEGRAPH_API_KEY:
        raise ValueError("API keys missing in api.env!")

    nebius_llm = NebiusLLM(api_key=NEBIUS_API_KEY)

    scraper_tool = ScrapegraphScrapeTool(api_key=SCRAPEGRAPH_API_KEY)
    decision_tool = DecisionTool(previous_data=previous_data)
    notify_tool = NotifyTool(generate_message_fn=generate_message)

    scraper_agent = Agent(
        name="Scraper Agent",
        role="Fetches product data from websites",
        goal="Extract current price, title, availability, and rating",
        backstory="A smart e-commerce web scraper using ScrapeGraph AI.",
        tools=[scraper_tool],
        llm=nebius_llm
    )

    decision_agent = Agent(
        name="Decision Agent",
        role="Analyzes scraped data vs old data",
        goal="Detect meaningful changes in price or availability",
        backstory="Experienced data analyst in retail monitoring.",
        tools=[decision_tool],
        llm=nebius_llm
    )

    notifier_agent = Agent(
        name="Notifier Agent",
        role="Sends alerts after each scrape",
        goal="Inform the user via SMS/WhatsApp every scrape",
        backstory="Handles alert generation and notification delivery.",
        tools=[notify_tool],
        llm=nebius_llm
    )

    scrape_task = Task(
        agent=scraper_agent,
        description=f"Scrape the latest product data from: {product_url}",
        expected_output=(
            "JSON with title, current_price, availability, rating, image_url, description, brand, recommended_uses_for_product. "
            "Recommended fields: title, current_price, availability, rating, image_url, description, brand, recommended_uses_for_product. "
            "Use N/A for missing fields."
        ),
        tool_kwargs={
            "website_url": product_url,
            "user_prompt": (
                "Extract ONLY the following information from the product page in strict JSON format:\n"
                "{\n"
                '  "title": "Product Name",\n'
                '  "current_price": "1234.56 INR",\n'
                '  "availability": "In Stock",\n'
                '  "rating": "4.5",\n'
                '  "image_url": "https://example.com/image.jpg",\n'
                '  "description": "Product description here",\n'
                '  "brand": "Brand Name",\n'
                '  "recommended_uses_for_product": "Recommended uses here"\n'
                "}\n"
                "Use N/A for missing fields. Only include these fields."
            )
        },
        output_key="scraped_data"
    )

    decision_task = Task(
        agent=decision_agent,
        description="Compare new scraped_data with previous_data to detect significant change.",
        expected_output="True if significant change, False otherwise.",
        context=[scrape_task],
        output_key="change_detected"
    )

    notify_task = Task(
        agent=notifier_agent,
        description="Send SMS/WhatsApp alert for every scrape.",
        expected_output="Notification sent.",
        context=[scrape_task]
    )

    crew = Crew(
        agents=[scraper_agent, decision_agent, notifier_agent],
        tasks=[scrape_task, decision_task, notify_task],
        verbose=True
    )
    crew.kickoff()

    scraped_data = {}
    if hasattr(scrape_task, "output") and scrape_task.output:
        try:
            raw = getattr(scrape_task.output, "raw_output", None) or str(scrape_task.output)
            scraped_data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            scraped_data = {
                "title": "N/A",
                "current_price": "N/A",
                "availability": "Unknown",
                "rating": "N/A",
                "image_url": ""
            }

    for tool in notifier_agent.tools:
        if isinstance(tool, NotifyTool):
            tool._run(scraped_data)

    all_previous_data[product_url] = scraped_data
    save_json(PRODUCT_DATA_FILE, all_previous_data)

    return scraped_data