<h1 align="center">Smart GTM Agent</h1>
<p align="center">
   <i>An AI-powered Go-To-Market Strategy Assistant for lightning-fast market intelligence & GTM execution</i>
</p>

<p align="center">
  <a href="https://streamlit.io/"><img src="https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/></a>
  <a href="https://langchain-ai.github.io/langgraph/"><img src="https://img.shields.io/badge/Workflow-LangGraph-2A5ADA?style=for-the-badge&logo=langchain&logoColor=white"/></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Language-Python%203.9+-3776AB?style=for-the-badge&logo=python&logoColor=white"/></a>
</p>



## ✨ What is Smart GTM Agent?

Smart GTM Agent is your **AI-powered growth co-pilot**.
It combines **SmartCrawler**, **LangGraph**, and **Nebius LLMs** to generate **company research, competitor insights, GTM playbooks, and distribution strategies** — all in minutes, not weeks.

> Perfect for **founders, marketers, analysts, and consultants** who need structured market intelligence at speed.

---

## 🚀 Features & Use Cases

### 🔎 Company Research
✅ Auto-generated structured profiles (industry, team, HQ, website, socials, contacts)
✅ Competitor analysis & funding insights
✅ Market landscape discovery

### 📊 Go-To-Market Playbook
✅ Define **Target Market** & **ICP (Ideal Customer Profile)**
✅ Craft **Key Messaging & Positioning**
✅ Pricing & packaging recommendations
✅ Growth strategy & channel mix
✅ Identify high-impact **Growth Channels**

### 🌐 Channel Strategy
✅ Find distribution & reseller partners
✅ Map sales + marketing channels
✅ Industry-specific scaling tactics

---

## ⚡ AI Stack Under the Hood

- **[SmartCrawler](https://docs.scrapegraphai.com/services/smartcrawler)** → Automated structured data extraction
- **[SearchScraper](https://docs.scrapegraphai.com/services/searchscraper)** → Web search–based data collection & enrichment
- **LangGraph Agents** → Orchestrated reasoning workflows
- **[Nebius LLM](https://dub.sh/nebius)** → Hermes-4-70B inference
- **SQLite** → Lightweight persistence

---


## 📂 Project Structure

```
Smart GTM Agent/
├── app/
│   ├── __init__.py
│   └── agents.py
├── assets/
│   └── nebius.png
├── api.env
├── app.py
├── pyproject.toml
├── uv.lock
├── company_data.db
└── README.md
```
## How It Works
![smart_gtm](https://github.com/user-attachments/assets/4bf4cbf2-9d90-445f-9fe0-f6c17e02d414)



## 🔑 Setup Instructions

#### 1️⃣ Clone Repository

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd advance_ai_agents/smart_gtm_agent
```


### 2️⃣ Create Virtual Environment

If you’re using UV (UltraVenv) for dependency management:
```
uv venv
source .venv/bin/activate   # (Linux/Mac)

.venv\Scripts\activate      # (Windows)
```

### 3️⃣ Install Dependencies

```
uv sync
```
(If you’re not using UV, you can use pip directly.)


### 4️⃣ Add API Keys

Create a file named api.env in the project root:

```
SMARTCRAWLER_API_KEY=your_smartcrawler_key_here
NEBIUS_API_KEY=your_nebius_key_here
```
Alternatively, enter them manually inside the Streamlit sidebar when running the app.

### ▶️ Running the App

```
uv run streamlit run app.py
```

## 📝 Usage Workflow

1. **Enter API Keys**
   - Add your **Nebius** and **SmartCrawler** keys in the sidebar.

2. **Select Feature**
   - 🔎 **Research** → Company profile & competitors
   - 📊 **Go-to-Market** → Market size & GTM playbook
   - 🌐 **Channel** → Distribution insights

3. **Enter Company URL**
   - Example: `https://www.studio1hq.com/`, `https://www.langchain.com/`

4. **Run Analysis**
   - Click on **🚀 Analyze Company**

5. **View Outputs**
   - 📝 **Markdown Summary** (rendered in the app)
   - 💾 **Saved in Database** (`company_data.db`)


