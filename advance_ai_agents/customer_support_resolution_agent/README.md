# Customer Support Resolution Agent

> A SaaS-style customer support agent that answers product questions,
> looks up real order status, and escalates to a human ticket when it
> can't confidently resolve the issue.

Built with **LangChain** for the agent + tool-calling layer and
**Nebius Token Factory** for both the LLM (`Qwen/Qwen3-30B-A3B`) and
the embedding model (`Qwen/Qwen3-Embedding-8B`).

## 🚀 Features

- **Knowledge-grounded answers** — every policy answer is retrieved
  from a FAISS index built over the FAQ, refund policy, and shipping
  policy docs.
- **Real order lookups** — `lookup_order` reads from a sample order
  database and verifies the customer's email before exposing details.
- **Confidence-aware escalation** — when the agent can't resolve an
  issue from the knowledge base + order data, it opens a human ticket
  via `create_ticket` and tells the customer the ticket ID.
- **Tool-calling agent** — uses LangChain's `create_agent` so the LLM
  picks the right tool for each turn instead of hard-coded routing.
- **Streamlit UI + CLI** — run as a chat app or in the terminal.

## 🛠️ Tech Stack

- **LangChain** — agent, tools, retrievers, prompt templates
- **Nebius Token Factory** — LLM and embeddings (OpenAI-compatible API)
- **FAISS** — local vector store for the knowledge base
- **Streamlit** — chat UI
- **Python 3.10+**

## 🧰 The four tools

| Tool                    | What it does                                                     |
| ----------------------- | ---------------------------------------------------------------- |
| `lookup_order`          | Order status, items, totals, tracking — gated on customer email  |
| `kb_search`             | Semantic search across FAQ + policy docs                         |
| `refund_policy_search`  | Search restricted to the refund / returns policy                 |
| `create_ticket`         | Opens a human ticket and escalates the conversation              |

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- A [Nebius Token Factory](https://nebius.com/services/token-factory) API key

### 1. Install

```bash
cd advance_ai_agents/customer_support_resolution_agent
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or with uv:
uv pip install -e .
```

### 2. Configure environment

```bash
cp env.example .env
# edit .env and add your NEBIUS_API_KEY
```

### 3. Build the knowledge base (one-time)

```bash
python ingest.py
```

This embeds the docs in `data/*.md` with `Qwen/Qwen3-Embedding-8B` and writes
the FAISS index to `kb_index/`.

### 4. Run

Streamlit chat UI:

```bash
streamlit run app.py
```

Terminal CLI:

```bash
python main.py
```

## 💬 Demo prompts to try

### Order Lookups
- *"I need to check on my order NC-10234. My email is alex@example.com."*
- *"What's the status of order NC-10235? My email is customer@domain.com"*
- *"Can you track order NC-10234 for me? Email: alex@example.com"*

### Policy & FAQ Questions
- *"How long does shipping take?"*
- *"What's your refund policy?"*
- *"How long do refunds take to a credit card?"*
- *"Can I cancel my order?"*
- *"What's your return window?"*

### Escalation Scenarios
- *"My package arrived broken. What do I do?"* — escalates to human ticket
- *"I think someone used my card to place an order, can a human help me?"* — escalates
- *"I've been trying to get a refund for 2 weeks, please escalate this"*
- *"My order never arrived and I need immediate help"*

### Combination Queries
- *"Where's order NC-10234 (email: alex@example.com)? Also, can I still cancel it?"*
- *"What's your return policy for damaged items? My order NC-10235 arrived with a broken product"*

## 📂 Project structure

```
customer_support_resolution_agent/
├── agent.py            # LangChain tool-calling agent + system prompt
├── tools.py            # lookup_order, kb_search, refund_policy_search, create_ticket
├── ingest.py           # Build / load FAISS index over data/*.md
├── app.py              # Streamlit chat UI
├── main.py             # Terminal CLI
├── data/
│   ├── faq.md
│   ├── refund_policy.md
│   ├── shipping_policy.md
│   ├── orders.json     # Sample order DB
│   └── tickets.json    # Tickets created by create_ticket
├── kb_index/           # FAISS index (created by ingest.py)
├── pyproject.toml
└── env.example
```

## 🧠 How escalation works

The agent's system prompt lists explicit conditions under which it
must call `create_ticket` — low confidence from `kb_search`, customer
asking for a human, damaged items, refund disputes, or any tool error
it cannot resolve in one more step. When it escalates, it returns the
ticket ID to the customer and the ticket is appended to
`data/tickets.json` so you can see it in the Streamlit sidebar.

## 🔁 Extending it

- Swap `data/orders.json` for a real database query.
- Replace FAISS with a managed vector DB (Qdrant, Pinecone) — only
  `ingest.py` and `tools._get_kb` change.
- Add tools: `update_shipping_address`, `issue_store_credit`,
  `start_return`. Register them in `tools.ALL_TOOLS`.
- Plug `create_ticket` into Zendesk / Linear / your real ticketing
  system.

## 📄 License

MIT — see the repo root [LICENSE](../../LICENSE).
