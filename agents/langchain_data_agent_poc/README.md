# LangChain Data Agent PoC

This is a small natural-language-to-SQL data agent inspired by the architecture of
`eosho/langchain_data_agent`, but implemented from scratch for this cookbook.

The goal is a compact PoC, not a full data platform. It keeps the useful shape:

1. Rewrite follow-up questions into standalone questions.
2. Route the question to a specialized data domain.
3. Generate SQL for the selected schema.
4. Validate that the SQL is read-only and scoped to allowed tables.
5. Execute against a local sample dataset.
6. Summarize the result and suggest a simple chart.

It uses **Nebius Token Factory** through LangChain's OpenAI-compatible client,
plus **LangGraph** for the pipeline and **Streamlit** for the UI.

## What is included

- Two data domains:
  - `sales`: orders, products, customers, revenue, inventory
  - `support`: support tickets, priorities, status, resolution time
- Local CSV sample data loaded into an in-memory SQLite database.
- A read-only SQL guard that blocks writes, multiple statements, comments, and
  tables outside the selected domain.
- Streamlit UI with sample questions, generated SQL, result tables, and charts.
- CLI for quick terminal testing.

## Setup

```bash
cd agents/langchain_data_agent_poc
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp env.example .env
```

Edit `.env` and add your Nebius key:

```bash
NEBIUS_API_KEY=your-nebius-token-factory-key
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B
```

## Run the Streamlit UI

```bash
streamlit run app.py
```

## Run the CLI

```bash
python main.py
```

## Sample questions

Sales:

- What is revenue by region?
- Which products generated the most revenue?
- Show monthly revenue by channel.
- Which products are below reorder level?

Support:

- How many open support tickets are there by priority?
- What is the average resolution time by ticket category?
- Which customer segments have the most urgent tickets?
- Show support tickets by status.

## Project structure

```text
langchain_data_agent_poc/
├── agent.py          # LangGraph pipeline and Nebius LLM calls
├── app.py            # Streamlit UI
├── config.py         # Domain definitions and sample prompts
├── dataset.py        # CSV to in-memory SQLite loader
├── main.py           # CLI entrypoint
├── sql_safety.py     # Read-only SQL validation
├── visualization.py  # Simple chart suggestion logic
├── data/
│   ├── customers.csv
│   ├── orders.csv
│   ├── products.csv
│   └── support_tickets.csv
├── env.example
└── pyproject.toml
```

## Notes

This example deliberately avoids external database ingestion, cloud warehouse
connectors, auth adapters, A2A protocol, and production config loaders. Those are
valuable in a full platform, but they obscure the core data-agent loop for a
cookbook PoC.
