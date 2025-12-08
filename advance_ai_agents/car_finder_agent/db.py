import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

load_dotenv("api.env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "cars_db")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]


cars_collection = db["cars_listings"]
chat_debug_collection = db["chat_debug"] 
scraped_pages_collection = db["scraped_pages"]


cars_collection.create_index("details_url", unique=True)
scraped_pages_collection.create_index("url", unique=True)


def upsert_cars(cars_docs):
    """
    Upserts scraped car documents into MongoDB.
    cars_docs: list[dict]
    """
    if not cars_docs:
        return 0

    count = 0
    for doc in cars_docs:
        url = doc.get("details_url")
        if not url:
            continue
        cars_collection.update_one(
            {"details_url": url},
            {"$set": doc},
            upsert=True,
        )
        count += 1
    return count


def find_cars(max_price=None, city=None, keyword=None, limit=20):
    """
    Fetches filtered cars from MongoDB.
    Optional:
      - max_price
      - city
      - keyword (brand or any text, e.g. 'bmw')
    """
    query = {}
    if max_price is not None:
        query["price_numeric"] = {"$lte": max_price}
    if city:
        query["location"] = {"$regex": city, "$options": "i"}
    if keyword:
        query["title"] = {"$regex": keyword, "$options": "i"}

    return list(cars_collection.find(query).limit(limit))


def check_db_health():
    """
    MongoDB / DB health check.
    Returns: (ok: bool, message: str)
    """
    try:
        client.admin.command("ping")
        return True, "DB connected (MongoDB ping OK)"
    except ServerSelectionTimeoutError as e:
        return False, f"DB connection failed (timeout): {e}"
    except Exception as e:
        return False, f"DB error: {e}"


