<h1 align="center">🚗 Cars Finder Agent</h1>





> **AI-powered used car recommendation system** that scrapes real listings from **Cars.com**, stores them in **MongoDB**, and gives smart car suggestions through **CrewAI + Nebius LLM** — all inside a clean, interactive **Streamlit** dashboard.

Smartly find the best car options based on your budget, mileage needs, brand preference, and city using real-time AI reasoning and memory.


<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white"></a>
  <a href="https://streamlit.io/"><img src="https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white"></a>
  <a href="https://www.mongodb.com/"><img src="https://img.shields.io/badge/Database-MongoDB-47A248?logo=mongodb&logoColor=white"></a>
  <a href="https://www.crewai.com/"><img src="https://img.shields.io/badge/Agents-CrewAI-111827?logo=github&logoColor=white"></a>
  <a href="https://nebius.ai/"><img src="https://img.shields.io/badge/LLM-Nebius-4B9CD3?logo=azurepipelines&logoColor=white"></a>
  <a href="https://scrapegraphai.com/"><img src="https://img.shields.io/badge/Scraper-Scrapegraph.ai-0EA5E9?logo=webstorm&logoColor=white"></a>
</p>

## 🧩 Overview

**Cars Finder Agent** is an AI assistant that:

- Scrapes real car listings from **Cars.com** using **Scrapegraph.ai**
- Stores them in **MongoDB**
- Uses **CrewAI + Nebius LLM** to recommend the best cars based on user requirements
- Provides a clean, dark-themed **Streamlit UI** for interaction

The app lets users paste a **Cars.com filtered search URL**, scrape it, store all cars, and then ask queries like:

> “Suggest Jeep under $55,000 in New York with good mileage”

---

## ✨ Features

- 🔍 **Scrape & Save from Cars.com**
  - Uses `ScrapegraphScrapeTool` to extract:
    - `title`, `price`, `mileage`, `location`, `details_url`, `image_url`
  - Data is normalized and stored in MongoDB with upserts 

- 🤖 **AI Car Recommendation Agent**
  - CrewAI `Agent` + `Task` with Nebius LLM
  - Reads:
    - User query
    - Matching car listings from MongoDB
  - Returns:
    - Short summary
    - 3–5 recommended cars
    - Next-step guidance

- 💾 **MongoDB Storage Layer**
  - Collections:
    - `cars_listings` – car data
    - `scraped_pages` – which URLs already scraped
    - `chat_debug` – debug log of AI answers  

- 📊 **Health & Status in UI**
  - DB Health: `DB connected (MongoDB ping OK)` or error
  - Total car records count

- 🎨 **Modern Dark UI**
  - Custom CSS in `st.markdown`
  - Logos for Scrapegraph, CrewAI & Memori in the header
  - Sidebar sections for:
    - API keys
    - Storage & memory status
    - Workflow steps

---

## 🏗️ Architecture


1. **User**:
   - Enters **Nebius** & **Scrapegraph** API keys (sidebar)

2. **Scrape Layer (`scrape_cars`)**:
   - Uses `ScrapegraphScrapeTool` 
   - Scrapes all car cards → JSON array
     -        "https://www.cars.com/new-cars/",
              "https://www.cars.com/shopping/results/?body_style_slugs%5B%5D=suv&zip=60606&maximum_distance=30&sort=best_match_desc",
              "https://www.cars.com/shopping/results/?zip=60606&maximum_distance=30&makes%5B%5D=bmw&sort=best_match_desc",
              "https://www.cars.com/shopping/results/?makes%5B%5D=mercedes_benz&zip=60606&maximum_distance=30&sort=best_match_desc",
              "https://www.cars.com/trucks/",
   - Normalizes fields and extracts numeric price (`price_numeric`)
   - Saves to `cars_listings` with `upsert_cars()`
   - Marks page as scraped in `scraped_pages`

4. **UI (`app.py`)**:
   - Shows answer under **“Suggested for You”**
   - Below that, shows **cars from MongoDB** with:
     - Title
     - Price
     - Mileage
     - Location
     - Image (if available)
     - Link → “View on Cars.com”

---

## 🧰 Tech Stack

| Layer       | Technology                                   |
|------------|-----------------------------------------------|
| Frontend   | Streamlit                                     |
| Agents     | CrewAI        |
| LLM        | Nebius (`nebius/NousResearch/Hermes-4-70B`)   |
| Scraper    | ScrapegraphScrapeTool (Scrapegraph.ai)        |  
| Database   | MongoDB                                       |
| Language   | Python                                        |

---

## 📂 Project Structure

```bash
CarsFinder
├── app.py          # Streamlit UI: sidebar, controls, main chat & results
├── agent.py        # Scraper, Memori setup, CrewAI+Nebius logic & handlers
├── db.py           # MongoDB client, collections, helpers & health check
├── assets/
│   └── nebius.png  # Logo shown in sidebar
├── api.env         
└── requirements.txt
└── pyproject.toml
└── README.md

```

---

## 🔑 Environment Setup

Create `api.env`:

```
NEBIUS_API_KEY=your_nebius_key

SCRAPEGRAPH_API_KEY=your_scrapegraph_api_key

MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=cars_db
```
## Create a virtualenv
```
# python -m venv venv
# source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate 
```
## Install dependencies
```
pip install -r requirements.txt
```
## Run the Streamlit app
```
streamlit run app.py
```
## How to Use the App

1. Sidebar – API Keys & Scraping

      - Enter Nebius API Key
    
      -  Enter Scrapegraph API Key
    
      - Click “💾 Save Keys”

You will see: "Keys saved for this session" if successful

2. Scrape Cars.com

   - In sidebar:
  
      - Enter User ID (e.g. user_1)


3. Check System Status

   Under Storage & Memory Status in the sidebar:

        -  Database: Active / Unavailable
      
        - Memory Engine: Operational / Inactive
        
        - Total Car Records: <number>


4. Ask AI for Recommendations

In the main page:

- Type your question in the text box, e.g.:

      - “Recommend Toyota or Honda cars under $20,000 in Chicago with low mileage”
  
- Click “Enter”

 - App will:

      - Scrape listings using Scrapegraph.ai
    
      - Clean the data
      
      - Upsert into MongoDB
      
      - Mark URL as scraped in scraped_pages

  - You’ll see a message like:

        - Scraped & saved 35 car listings in MongoDB ✅


## Contributing

Contributions, issues and feature requests are welcome!
Feel free to:

  - Fork this repo
  
  - Create a new branch
  
  - Submit a pull request 🚀
        



