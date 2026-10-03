# Cloudflare Workers AI Starter

A minimal chat agent built with **Llama on Cloudflare Workers AI** — the fastest way to run
open-source LLMs without managing GPU infrastructure.

## Features

- **Multi-model support** — switch between Llama 3.3 70B, Llama 3.1 8B, and Llama 3.2 11B Vision
- **Persistent chat history** — conversation context maintained across turns
- **Configurable system prompt** — customise the agent's persona from the sidebar
- **Zero infrastructure** — runs entirely on Cloudflare's global edge network

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM | Llama 3.3 70B / 3.1 8B / 3.2 11B Vision |
| Inference | [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) |
| UI | Streamlit |

## Getting Started

### Prerequisites

- Python 3.10+
- A [Cloudflare](https://dash.cloudflare.com) account (free tier works)

### 1 — Get your Cloudflare credentials

| Value | Where to find it |
|---|---|
| **Account ID** | [dash.cloudflare.com](https://dash.cloudflare.com) → right-hand sidebar |
| **API Token** | My Profile → API Tokens → **Create Token** → Workers AI template |

### 2 — Install

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/cloudflare_workers_ai_starter

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

## Project Structure

```
cloudflare_workers_ai_starter/
├── main.py          # Streamlit chat app
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Available Models

| Model | ID | Best For |
|---|---|---|
| Llama 3.3 70B (Fast) | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | General use, high quality |
| Llama 3.1 8B | `@cf/meta/llama-3.1-8b-instruct` | Low latency, lightweight |
| Llama 3.2 11B Vision | `@cf/meta/llama-3.2-11b-vision-instruct` | Multimodal tasks |

## Contributing

See the repo-level [CONTRIBUTING.md](../../CONTRIBUTING.md).

## License

MIT — see [LICENSE](../../LICENSE).
