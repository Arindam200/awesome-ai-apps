# Data Quality Operations Agent

Production use case: data teams need read-only agents that can inspect pipelines, query governed datasets, and recommend next actions when metrics break.

This project uses **Nebius through LangChain** with a guarded SQLite query tool. The agent can inspect schema, run read-only SQL, correlate pipeline changes, and produce an incident-style data quality report.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add NEBIUS_API_KEY
python main.py
```

## Production Pattern Demonstrated

- Read-only SQL guardrails
- Schema discovery before analysis
- Pipeline-change correlation
- Typed data quality report
- SQL/audit trail for reproducibility
