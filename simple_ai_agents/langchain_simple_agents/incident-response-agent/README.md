# Incident Response Commander Agent

Production use case: SRE teams need fast, evidence-backed triage during incidents without giving an LLM the ability to mutate infrastructure directly.

This project uses **LangChain tool calling** with **Nebius** as the model backend. The agent reads an alert, searches logs, checks runbooks, reviews recent deploys, and drafts a mitigation/comms plan.

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

- Evidence-gathering tools before recommendation
- Read-only diagnostics
- Human-approved mitigation plan instead of direct infra changes
- Typed JSON output for incident systems
- Audit trail of tools used
