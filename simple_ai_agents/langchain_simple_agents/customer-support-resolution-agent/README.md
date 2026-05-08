# Customer Support Resolution Agent

Production use case: support teams need agents that combine ticket text, order state, policies, and safe workflow recommendations.

This project uses **Nebius through LangChain** with tools for KB search, order lookup, and draft-only refund/replacement recommendations.

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

- Ticket triage and prioritization
- Policy-grounded responses
- Draft-only actions with approval flags
- CRM-ready internal note
- Tool audit trail
