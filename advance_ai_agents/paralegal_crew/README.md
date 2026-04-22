# Paralegal Crew ⚖️

A multi-agent **CrewAI** system that reviews commercial contracts end-to-end: extracts every material clause, scores each one for risk from your client's perspective, and produces an executive-ready Contract Review Memo with recommended redlines.

## 🧑‍⚖️ The Crew

1. **🧾 Contract Clause Extractor** — reads the full contract, tags each clause by category (Term, Liability, IP, Indemnity, Governing Law, etc.), and returns verbatim quotes plus plain-English summaries.
2. **🛡️ Legal Risk Analyst** — scores each clause `Low / Medium / High` from the chosen party perspective, explains why it matters, and proposes a redline.
3. **📝 Senior Paralegal Reviewer** — consolidates everything into a single Markdown memo: executive summary, key clauses, risk assessment, top redlines, and open questions for counsel.

The three agents run **sequentially**, each consuming the previous task's output as context.

## 🛠️ Tech Stack

- **Framework**: [CrewAI](https://www.crewai.com/)
- **Inference**: [Nebius Token Factory](https://dub.sh/AIStudio) (Qwen3-235B by default; Llama 3.3 70B and DeepSeek V3 also available)
- **PDF parsing**: [`pypdf`](https://pypi.org/project/pypdf/)
- **UI**: Streamlit

## 📋 Prerequisites

- Python 3.10+
- Nebius Token Factory API key

## ⚡ Quick Start

```bash
cd advance_ai_agents/paralegal_crew

# Install dependencies
pip install -r requirements.txt
# or
uv pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# then paste your NEBIUS_API_KEY into .env

# Launch the UI
streamlit run app.py
```

## 💡 How to Use

1. **Upload a PDF** or **paste contract text** (a sample NDA is pre-filled).
2. In the sidebar, set the **perspective** for the review (e.g. _"the Receiving Party (our client)"_, _"the Vendor"_, _"the Buyer"_).
3. Pick a Nebius model.
4. Click **Run Paralegal Crew**.
5. Review the generated memo and **download** it as Markdown.

## 🧠 What You Get

The final memo includes:

- **Executive Summary** — 3–5 bullets: what the contract is, key commercial terms, overall risk verdict.
- **Key Clauses** — Markdown table with category, section, verbatim quote, and summary.
- **Risk Assessment** — Markdown table with risk level, rationale, and suggested redline per clause, followed by an **Overall Contract Risk** rating.
- **Recommended Redlines** — top 5–8 changes to request, each with a one-line rationale.
- **Open Questions for Counsel** — items that cannot be answered from the document alone.

## 📁 Files

- `crew.py` — Agents, tasks, and crew wiring.
- `app.py` — Streamlit UI (PDF upload + paste tab).
- `requirements.txt` / `pyproject.toml` — dependencies.
- `.env.example` — required env vars.

## ⚠️ Disclaimer

This tool is informational only and **not legal advice**. Always have qualified counsel review contracts before signing.
