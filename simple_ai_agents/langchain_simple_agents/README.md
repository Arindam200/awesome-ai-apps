# LangChain Simple Agents

Production-oriented LangChain examples powered by Nebius Token Factory. Each example is self-contained with its own `requirements.txt`, `.env.example`, source files, and local sample data.

## Examples

| Example | Production use case | What it demonstrates |
| --- | --- | --- |
| [Incident Response Agent](incident-response-agent/) | SRE incident triage | Tool-driven log search, runbook lookup, deploy correlation, typed mitigation plan |
| [Customer Support Resolution Agent](customer-support-resolution-agent/) | CX ticket resolution | KB search, order lookup, policy-grounded draft responses, approval-aware workflow recommendations |
| [Vendor Risk Compliance Agent](vendor-risk-compliance-agent/) | Security/privacy vendor review | Policy control search, contract evidence review, data-residency checks, risk register output |
| [Data Quality Ops Agent](data-quality-ops-agent/) | Data operations investigation | Guarded read-only SQL, schema discovery, pipeline change correlation, reproducible data quality report |

## Setup pattern

```bash
cd simple_ai_agents/langchain_simple_agents/<example-folder>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add NEBIUS_API_KEY
python main.py
```

## Safety notes

- The examples use local fixtures and read-only or draft-only tools.
- No real infrastructure, refunds, shipments, or vendor approvals are executed.
- `.env.example` files contain placeholders only; add real keys locally.
