# Webpage Analyzer Agent

Paste any URL and get instant AI-powered analysis using **Llama 3.3 70B on Cloudflare Workers AI**.
No API keys for third-party scrapers — just a URL and your Cloudflare account.

## Features

- **4 analysis modes** — Summary, SEO Analysis, Competitive Intelligence, Content Gaps
- **Instant insights** — fetches and analyses any public webpage in seconds
- **Actionable output** — structured markdown with headers, bullets, and recommendations
- **Raw content preview** — see exactly what the agent analysed

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM | Llama 3.3 70B (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`) |
| Inference | [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) |
| Web fetching | `httpx` |
| UI | Streamlit |

## Getting Started

### Prerequisites

- Python 3.10+
- A [Cloudflare](https://dash.cloudflare.com) account

### 1 — Get your Cloudflare credentials

| Value | Where to find it |
|---|---|
| **Account ID** | [dash.cloudflare.com](https://dash.cloudflare.com) → right-hand sidebar |
| **API Token** | My Profile → API Tokens → **Create Token** → Workers AI template |

### 2 — Install

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/simple_ai_agents/webpage_analyzer_agent

pip install -r requirements.txt
```

### 3 — Configure

```bash
cp .env.example .env
# Fill in CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN
```

### 4 — Run

```bash
streamlit run main.py
```

Open [http://localhost:8501](http://localhost:8501).

## Usage

1. Enter your Cloudflare credentials in the sidebar
2. Paste a URL in the input field
3. Choose an analysis type:
   - **Summary & Key Points** — overview, key takeaways, audience, tone
   - **SEO Analysis** — keywords, readability, SEO recommendations
   - **Competitive Intelligence** — value proposition, strengths, weaknesses
   - **Content Gaps** — missing topics, unanswered questions, suggested additions
4. Click **Analyse**

## Project Structure

```
webpage_analyzer_agent/
├── main.py          # Streamlit app
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Contributing

See the repo-level [CONTRIBUTING.md](../../CONTRIBUTING.md).

## License

MIT — see [LICENSE](../../LICENSE).
