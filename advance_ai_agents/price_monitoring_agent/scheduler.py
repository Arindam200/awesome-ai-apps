import json
import os

from agents.crewai_agents import run_agents
from apscheduler.schedulers.blocking import BlockingScheduler
TRACKED_URLS_FILE = "tracked_urls.json"
PRODUCT_DATA_FILE = "product_data.json"

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

def check_prices():
    tracked_data = load_json(TRACKED_URLS_FILE, {})
    previous_data_all = load_json(PRODUCT_DATA_FILE, {})
    updated_data_all = {}

    for url, old_data in tracked_data.items():
        try:
            prev_data = previous_data_all.get(url, {})
            new_data = run_agents(url, prev_data)
            updated_data_all[url] = new_data if new_data else prev_data
        except Exception:
            updated_data_all[url] = previous_data_all.get(url, {})

    save_json(PRODUCT_DATA_FILE, updated_data_all)

scheduler = BlockingScheduler()
scheduler.add_job(check_prices, 'interval', minutes=30)