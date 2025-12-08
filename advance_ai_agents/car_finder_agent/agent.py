

import os
import json

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import ScrapegraphScrapeTool

from db import (
    upsert_cars,
    find_cars,
    chat_debug_collection,
    scraped_pages_collection,
)

load_dotenv("api.env")

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
NEBIUS_MODEL_NAME = os.getenv("NEBIUS_MODEL_NAME", "NousResearch/Hermes-4-70B")

SCRAPEGRAPH_API_KEY = os.getenv("SCRAPEGRAPH_API_KEY")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

SEED_SEARCH_URLS = [
    "https://www.cars.com/new-cars/",
    "https://www.cars.com/shopping/results/?body_style_slugs%5B%5D=suv&zip=60606&maximum_distance=30&sort=best_match_desc",
    "https://www.cars.com/shopping/results/?zip=60606&maximum_distance=30&makes%5B%5D=bmw&sort=best_match_desc",
    "https://www.cars.com/shopping/results/?makes%5B%5D=mercedes_benz&zip=60606&maximum_distance=30&sort=best_match_desc",
    "https://www.cars.com/trucks/",
]

SYSTEM_PROMPT = """
You are an intelligent and highly reliable Car Recommendation Expert.
Your role is to help users find the best car options based strictly on the real
listings stored in MongoDB.

FOLLOW THESE RULES:

1. **Use ONLY the car listings provided in the database context.**
   - Never invent cars, prices, mileage, or details.
   - Every recommended car must come directly from the database list.

2. **Response Style**
   - Keep answers short, clear, and highly readable.
   - Use clean bullet points.
   - Start with a brief 1–2 line summary.
   - Then show the top 3–5 matching cars (if available), numbered.

3. **Details for Each Recommended Car**
   - Mention: Title/Model, Price, Mileage, Location, and Listing Number.
   - Use the numbering from the database list (do NOT reorder unless needed).

4. **If no good matches are found**
   - Politely say that no listings match the user's criteria.
   - Suggest how the user can refine or adjust their search:
     • expand budget  
     • try nearby locations  
     • choose similar brands  
     • adjust year, type, or mileage filters  

5. **Tone**
   - Professional, concise, and helpful.
   - Avoid unnecessary text, emojis, or storytelling.

Your goal is to act as a trusted car-buying advisor and guide the user toward
the best options based on the real listings available.
"""



def scrape_cars(search_url: str):
    if not SCRAPEGRAPH_API_KEY:
        raise RuntimeError("SCRAPEGRAPH_API_KEY missing in api.env")

    if not search_url or not search_url.startswith(("http://", "https://")):
        raise ValueError("Invalid Cars.com search URL.")

    already = scraped_pages_collection.find_one({"url": search_url})
    if already:
        print(f"[SCRAPER] Page already scraped, skipping: {search_url}")
        return [], 0

    tool = ScrapegraphScrapeTool(
        api_key=SCRAPEGRAPH_API_KEY,
        website_url=search_url,
        user_prompt=(
            "Extract all car listings from this Cars.com page and return ONLY a STRICT JSON array. "
            "For each visible car card, read the title, price, mileage (odometer) and location/city text shown "
            "near the price. Each object MUST include these keys: "
            "title, price, mileage, location, details_url, image_url. "
            "If mileage or location is not shown for a listing, set them to null, but still include the keys. "
            "Return ONLY the JSON array, with no additional text."
        ),
    )

    result = tool.run()
    print("Using Tool: Scrapegraph website scraper")
    print("RAW SCRAPE RESULT TYPE:", type(result))
    print("RAW SCRAPE RESULT PREVIEW:", str(result)[:400])

    if isinstance(result, str):
        try:
            data = json.loads(result)
        except Exception:
            data = []
    elif isinstance(result, (list, tuple)):
        data = list(result)
    elif isinstance(result, dict):
        inner = result.get("result") or result
        if isinstance(inner, dict) and "car_listings" in inner:
            data = inner["car_listings"]
        elif "data" in result:
            data = result["data"]
        else:
            data = []
    else:
        data = []

    cleaned_docs = []
    for item in data:
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        price = item.get("current_price") or item.get("price")
        mileage = item.get("mileage")
        location = item.get("location")
        url = item.get("details_url") or item.get("url")

        if not url:
            continue
        if not title and not price:
            continue

        image_url = (
            item.get("image_url")
            or item.get("image")
            or item.get("thumbnail")
            or item.get("img_url")
        )

        price_numeric = None
        if isinstance(price, str):
            digits = "".join(ch for ch in price if ch.isdigit())
            if digits:
                try:
                    price_numeric = int(digits)
                except ValueError:
                    price_numeric = None
        elif isinstance(price, (int, float)):
            price_numeric = int(price)

        doc = {
            "title": title,
            "price": price,
            "price_numeric": price_numeric,
            "mileage": mileage,
            "location": location,
            "details_url": url,
            "image_url": image_url,
        }
        cleaned_docs.append(doc)

    upsert_count = upsert_cars(cleaned_docs)
    print(f"[SCRAPER] Upserted {upsert_count} docs into MongoDB")

    if upsert_count > 0:
        scraped_pages_collection.update_one(
            {"url": search_url},
            {"$set": {"url": search_url}},
            upsert=True,
        )

    return cleaned_docs, upsert_count



def scrape_seed_pages():
    """
    Scrape all fixed seed URLs (4–5 pages) and load them into MongoDB.
    Uses scraped_pages_collection so it won't re-scrape the same URL twice.
    """
    total_upserted = 0
    for url in SEED_SEARCH_URLS:
        try:
            print(f"[SCRAPER] Scraping seed page: {url}")
            _, count = scrape_cars(url)
            total_upserted += count
        except Exception as e:
            print(f"[SCRAPER] Error scraping {url}: {e}")

    print(f"[SCRAPER] Total upserted from seed pages: {total_upserted}")
    return total_upserted


def format_cars_for_prompt(cars):
    if not cars:
        return "No matching cars found for these filters."
    lines = []
    for i, car in enumerate(cars, start=1):
        lines.append(
            f"{i}. {car.get('title')} | Price: {car.get('price')} | "
            f"Mileage: {car.get('mileage')} | Location: {car.get('location')} | "
            f"URL: {car.get('details_url')}"
        )
    return "\n".join(lines)


def _extract_brand_keyword(user_query: str) -> str | None:
    """
    Very simple brand keyword extraction from user query.
    e.g. 'I want BMW' -> 'bmw'
    """
    brands = [
        "bmw", "mercedes", "tesla", "honda", "toyota", "audi",
        "ford", "hyundai", "kia", "mazda", "jeep", "lexus",
        "chevrolet", "chevy", "gmc", "volkswagen", "vw", "volvo",
        "porsche", "mini", "subaru", "nissan", "genesis", "polestar",
        "range rover", "land rover", "jaguar", "infiniti", "acura",
    ]
    q = user_query.lower()
    for b in brands:
        if b in q:
            return b
    return None


def _get_nebius_llm() -> LLM:
    if not NEBIUS_API_KEY:
        raise RuntimeError("NEBIUS_API_KEY missing in api.env")

    return LLM(
        model=f"nebius/{NEBIUS_MODEL_NAME}",
        api_key=NEBIUS_API_KEY,
    )


def run_crewai_with_nebius(task_description: str) -> str:
    """
    Run a CrewAI Agent + Task with Nebius LLM for recommendations.
    - inject relevant context automatically
    """
    llm = _get_nebius_llm()

    advisor_agent = Agent(
        name="Car Advisor Agent",
        llm=llm,
        role="Car Recommendation Agent",
        goal="Help the user pick the best cars based on filters and listings.",
        backstory=(
            "You are an expert in used car markets. You know how to read listings "
            "and suggest options clearly to a non-technical user."
        ),
        verbose=False,
    )

    recommendation_task = Task(
        description=task_description,
        expected_output=(
            "A clear, structured answer with:\n"
            "- Short summary\n"
            "- 3–5 recommended cars (if available) with numbers\n"
            "- Simple guidance on next steps"
        ),
        agent=advisor_agent,
    )

    crew = Crew(
        agents=[advisor_agent],
        tasks=[recommendation_task],
        verbose=False,
    )

    result = crew.kickoff()

    try:
        answer = str(recommendation_task.output)
    except Exception:
        answer = str(result)

    return answer


def handle_chat(user_id: str, user_query: str, max_price=None, city=None, search_url=None):
    """
    Flow:
    1. Check DB for matches
    2. If no matches → auto-scrape all seed pages
    3. Save to DB
    4. Re-check DB
    5. Then run CrewAI agent
    """
    print("user_query:", user_query)
    keyword = _extract_brand_keyword(user_query)
    print("extracted keyword:", keyword)
    
    cars = find_cars(max_price=max_price, city=city, keyword=keyword)
    print("cars found in DB:", len(cars))


    if not cars:
        print("[HANDLE_CHAT] No matching cars in DB → scraping seed pages...")
        if search_url:
            try:
                scrape_cars(search_url)
            except Exception as e:
                print(f"[HANDLE_CHAT] Error scraping custom URL {search_url}: {e}")

        upserted = scrape_seed_pages()

        if upserted == 0:
            return (
                "❌ No matching cars in the database, and scraping seed pages didn't add any new listings.",
                [],
            )


        cars = find_cars(max_price=max_price, city=city, keyword=keyword)

    cars_str = format_cars_for_prompt(cars)

    task_description = f"""
SYSTEM:
{SYSTEM_PROMPT}

USER QUERY:
{user_query}

MATCHING CARS:
{cars_str}
"""

    answer = run_crewai_with_nebius(task_description)

    chat_debug_collection.insert_one(
        {"user_id": user_id, "query": user_query, "answer": answer}
    )

    return answer, cars
