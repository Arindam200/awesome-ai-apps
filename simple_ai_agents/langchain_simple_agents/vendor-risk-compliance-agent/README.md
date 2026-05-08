# Vendor Risk Compliance Agent

Production use case: security, privacy, and procurement teams need fast vendor reviews grounded in internal controls and contract evidence.

This project uses **Nebius through LangChain** to inspect a vendor questionnaire, search controls, read contract language, and produce a risk register with approval conditions.

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

- Policy-grounded agentic review
- Data residency and personal-data checks
- Risk register as typed JSON
- Contract redline suggestions
- Conditional go-live decision
