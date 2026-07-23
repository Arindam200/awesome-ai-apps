# Financial Document OS

**Upload your financial documents. Get a database you can query, audit, and edit.**

Bank statements, contracts, loan agreements, tax filings, investment statements,
audit reports — the numbers you need are trapped inside PDFs. **Financial Document OS**
uses [Unsiloed](https://unsiloed.ai) to turn those documents into structured,
queryable financial entities, where **every value is traceable to the exact region on
the exact page it came from**. From there you can browse it like a database, ask
questions in plain English, catch anomalies automatically, and edit a value across
every PDF at once.

No RAG. No vector database. Your documents become a real relational database, and
every answer carries a clickable citation back to the source pixel.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [What it does](#what-it-does)
- [How Unsiloed is used](#how-unsiloed-is-used)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [The demo corpus (included PDFs)](#the-demo-corpus-included-pdfs)
- [Prerequisites](#prerequisites)
- [Setup & run](#setup--run)
- [Environment variables](#environment-variables)
- [Choosing an LLM provider](#choosing-an-llm-provider)
- [Using the app](#using-the-app)
- [The Edit API (calibrated first)](#the-edit-api-calibrated-first)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Safety model](#safety-model)
- [Troubleshooting](#troubleshooting)

---

## Why this exists

Finance lives in PDFs, and PDFs are where structured data goes to die. A single
quarterly statement can bury 200+ numbers across 20 pages; export it to text and the
tables flatten into mush; and every figure a human re-keys into a spreadsheet is one
un-cited copy-paste away from being wrong.

Financial Document OS reads a document the way an auditor does: it extracts every value
*and* remembers exactly where it came from, so nothing in the resulting database is
unaccountable. Click any number and it highlights the source region on the original page.

## What it does

- **Entity Explorer** — accounts, transactions, vendors, contracts/loans, investments,
  obligations, and tax items rendered as sortable tables. Click any extracted value to
  see it highlighted on the source PDF (the **Evidence Viewer**).
- **Vendor resolution** — the same party is resolved across every document it appears in.
  "Deloitte LLP" on a contract + eight bank statements + an audit collapses into **one**
  vendor record with its total paid and every reference.
- **Ask (NL→SQL)** — natural-language questions answered with **real SQL over the
  extracted database**, not retrieval. *"Which vendors did we pay more than $100,000?"*
  Every result row links back to its source evidence.
- **Anomaly detection** — duplicate payments, vendors paid over their contract value,
  valuation drops, expenses missing from tax filings, expiring contracts, and large
  obligations — each flagged with cited evidence.
- **Cross-document editing** — change a value once (e.g. a company address) and rewrite
  it in **every PDF it appears in**, preserving layout, via the Unsiloed Edit API. An
  impact analysis previews every affected document before anything is written.

## How Unsiloed is used

The app exercises **all four** Unsiloed capabilities:

| Capability | Role in the pipeline |
|---|---|
| **classify** | Route each uploaded PDF to the right extraction schema (bank statement vs. contract vs. tax filing …). |
| **extract** | Schema-driven structured extraction with **confidence scores** and **word-level bounding-box citations** for every field. |
| **parse** | Layout-aware fallback for dense tables where schema extraction needs reinforcement. |
| **Edit API** | Rewrite values across documents **by coordinate**, preserving the original layout. |

## Architecture

```
                  ┌── classify ── extract (schema + citations) ──┐
upload PDFs ──────┤                                              ├──▶ 7 typed entity tables
(bank stmt,       └── render pages (pymupdf) ────────────────────┘    + bbox citations
 contracts,                                                                │
 tax, loans,            ┌──────────────────────────────────────────────────┤
 investments)          ▼                  ▼                ▼                 ▼
                  Entity Explorer    Ask (NL→SQL)     Anomalies        Edit across PDFs
                  + Evidence Viewer  read-only SQL    duplicate pay,   (Unsiloed Edit API,
                  (click any value   not RAG; every   over-contract,   change once → rewrite
                   → highlighted      row → evidence   valuation drop   everywhere)
                   source region)                      … with evidence
```

The pipeline (`backend/app/pipeline/orchestrator.py`) ingests a PDF, classifies it,
extracts entities against the matching JSON schema, stores each value with its citation,
renders page images for the viewer, then resolves entities across documents and runs the
anomaly rules.

## Tech stack

- **Backend** — Python · FastAPI · SQLAlchemy · PostgreSQL
- **Frontend** — Next.js 15 · React 19 · Tailwind v4
- **Documents** — Unsiloed APIs (classify / extract / parse / edit) · pymupdf for page rendering
- **LLM** (NL→SQL + synthesis) — OpenAI by default; pluggable to **Nebius Token Factory**,
  Anthropic, or MiniMax (see [below](#choosing-an-llm-provider))
- **NL→SQL safety** — read-only Postgres role + `sqlglot` SELECT-only AST allowlist

## The demo corpus (included PDFs)

This repo ships a ready-to-use synthetic corpus in **[`backend/data/corpus/`](backend/data/corpus)** —
**23 interlinked, multi-page financial PDFs** so you can try every feature without
sourcing your own documents. They're generated deterministically by
`backend/app/seed/generate_corpus.py` and intentionally wired with cross-document
overlaps so each feature has something to show:

| What's seeded | Demonstrates |
|---|---|
| "Deloitte LLP" recurs across 8 statements + a contract + audits + tax filings | **Vendor resolution** (one entity, many docs) |
| Deloitte paid far above its $80k contract | **Over-contract anomaly** |
| One company address across every contract + loan | **Cross-PDF edit** target |
| A duplicate payment within a quarter | **Duplicate-payment anomaly** |
| A brokerage holding (Globex) drops across two statements | **Valuation-drop anomaly** |
| Atlassian paid in statements but omitted from tax filings | **Missing-from-tax anomaly** |

Document types: quarterly **bank statements** (30–40 transactions each, flowing across
pages — this is what genuinely exercises Unsiloed's table extraction), **contracts**,
**loan/line-of-credit** agreements, **tax filings**, **investment statements**, an
**audit report**, and an **annual report**.

> To **upload** them in the app: go to the Documents page and add the PDFs from
> `backend/data/corpus/`, then hit **Process**. To **regenerate** them from scratch:
> `python -m app.seed.generate_corpus`.

## Prerequisites

- **Docker** (for PostgreSQL)
- **Python 3.11+** and [`uv`](https://github.com/astral-sh/uv) (or pip)
- **Node 18+** and [`pnpm`](https://pnpm.io)
- An **Unsiloed API key** → https://unsiloed.ai
- An **LLM key** — OpenAI by default, or a Nebius, Anthropic, or MiniMax key (see below)

## Setup & run

```bash
# 1. Configure
cp .env.example .env          # fill in UNSILOED_API_KEY + an LLM key (RESEND optional)

# 2. Database — Postgres on :5434 (container name: findoc-db)
docker compose up -d

# 3. Backend
cd backend
uv venv .venv && uv pip install -e . --python .venv/bin/python

# Create the read-only role used by NL→SQL (defense in depth):
docker exec findoc-db psql -U findoc -d financial_document_os -c \
  "CREATE ROLE findoc_ro LOGIN PASSWORD 'findoc_ro'; \
   GRANT CONNECT ON DATABASE financial_document_os TO findoc_ro; \
   GRANT USAGE ON SCHEMA public TO findoc_ro; \
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO findoc_ro; \
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO findoc_ro; \
   ALTER ROLE findoc_ro SET default_transaction_read_only = on; \
   ALTER ROLE findoc_ro SET statement_timeout = '5000';"

# (optional) regenerate the demo PDFs — they're already in backend/data/corpus/
.venv/bin/python -m app.seed.generate_corpus

.venv/bin/uvicorn app.main:app --port 8001

# 4. Frontend (new terminal)
cd ../frontend
pnpm install && pnpm dev --port 3006        # → http://localhost:3006
```

Then open **http://localhost:3006**, upload the PDFs from `backend/data/corpus/` on the
Documents page, click **Process**, and explore.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `UNSILOED_API_KEY` | ✅ | Unsiloed key for classify / extract / parse / edit. |
| `LLM_PROVIDER` | – | `openai` (default), `nebius`, `anthropic`, or `minimax`. |
| `OPENAI_API_KEY` | ✅ (default provider) | Used for NL→SQL + synthesis when provider is `openai`. |
| `NEBIUS_API_KEY` | when `LLM_PROVIDER=nebius` | Nebius Token Factory key. |
| `ANTHROPIC_API_KEY` | when `LLM_PROVIDER=anthropic` | Anthropic key. |
| `MINIMAX_API_KEY` | when `LLM_PROVIDER=minimax` | MiniMax API key. |
| `MINIMAX_REGION` | when `LLM_PROVIDER=minimax` | `global_en` or `cn_zh`; selects the matching regional endpoints. |
| `MINIMAX_PROTOCOL` | when `LLM_PROVIDER=minimax` | `openai` or `anthropic`; selects the compatible API. |
| `MINIMAX_SYNTHESIS_MODEL` | – | Defaults to `MiniMax-M3`. |
| `MINIMAX_SENTIMENT_MODEL` | – | Defaults to `MiniMax-M2.7`. |
| `RESEND_API_KEY` | optional | Board-report email (stretch feature). |
| `DATABASE_URL` | ✅ | Primary Postgres connection (compose default provided). |
| `DATABASE_READONLY_URL` | ✅ | Read-only role connection for NL→SQL. |
| `APP_URL` | – | Frontend URL (default `http://localhost:3006`). |
| `NEXT_PUBLIC_API_URL` | – | Backend URL the frontend calls (default `http://localhost:8001`). |

## Choosing an LLM provider

NL→SQL and synthesis run on an LLM. **OpenAI is the default and nothing changes if you
leave it.** To switch providers, set `LLM_PROVIDER` in `.env` and provide that provider's
key, then restart the backend.

- **OpenAI** (default) — `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`
- **Nebius Token Factory** (OpenAI-compatible) — `LLM_PROVIDER=nebius`, `NEBIUS_API_KEY=...`.
  Models default to `nvidia/Nemotron-3-Ultra-550b-a55b`; override with
  `NEBIUS_SYNTHESIS_MODEL` / `NEBIUS_SENTIMENT_MODEL`. The integration calls the standard
  OpenAI SDK against Nebius's `base_url` and falls back to JSON-object mode + Pydantic
  validation if a model doesn't support structured parse.
- **Anthropic** — `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`
- **MiniMax** — `LLM_PROVIDER=minimax`, `MINIMAX_API_KEY=...`. Set
  `MINIMAX_REGION=global_en` or `cn_zh` and choose `MINIMAX_PROTOCOL=openai` or
  `anthropic`. The default models are `MiniMax-M3` for synthesis and `MiniMax-M2.7`
  for sentiment. OpenAI-compatible requests use the regional `/v1` endpoint; Anthropic-
  compatible requests use the regional `/anthropic` endpoint. See the [global API
  overview](https://platform.minimax.io/docs/api-reference/api-overview) or [China API
  overview](https://platform.minimaxi.com/docs/api-reference/api-overview).

## Using the app

1. **Documents** — upload PDFs (or the bundled `backend/data/corpus/` set) and click
   **Process**. Watch the pipeline classify → extract → render.
2. **Explorer** — browse the typed entity tables. Click any value to open the **Evidence
   Viewer** and see it highlighted on the source page.
3. **Vendors** — see each party resolved across every document, with total paid and all
   references.
4. **Ask** — type a question (*"Which vendors did we pay more than $100,000?"*). You get a
   table plus the generated SQL, and every row links to its evidence.
5. **Anomalies** — review automatically flagged issues, each with cited evidence.
6. **Edit** — change a value (e.g. the company address), preview the **impact analysis**
   across all affected PDFs, then apply and download the rewritten documents.

## The Edit API (calibrated first)

Editing is gated behind a calibration test, because the Edit API edits by **coordinates**
and runs on a different host than extraction. Validate it before trusting the feature:

```bash
cd backend && .venv/bin/python -m scripts.calibrate_edit
```

It builds a known PDF, extracts it, edits a known string using the stored citation bbox,
downloads the result, and asserts the replacement landed in the right place. **Result on
this corpus: PASSED** — the editor uses the citation's own coordinate space (corners
as-is). `editing_enabled` defaults to `true`; if calibration fails in your environment the
feature ships off and everything else is unaffected.

> For prose where a value wraps mid-sentence, coordinate replacement can't reflow the
> paragraph — keep edit targets (addresses, names, IDs) on their own line for clean results.

## API reference

Backend runs on `:8001`. Key endpoints (`backend/app/api/routes.py`):

| Method & path | Purpose |
|---|---|
| `POST /documents/upload` | Upload a PDF. |
| `GET /documents` | List uploaded documents + status. |
| `POST /runs` | Run the ingest → extract pipeline. |
| `GET /runs/{id}` · `GET /runs` | Pipeline run status / history. |
| `GET /entities/kinds` | Available entity kinds. |
| `GET /entities/{kind}` | Rows for an entity kind. |
| `GET /entities/{kind}/{id}/citations` | Citations (bbox + page) for a value. |
| `GET /vendors` · `GET /vendors/{id}/references` | Resolved vendors + cross-doc references. |
| `POST /ask` | Natural-language question → SQL → rows + evidence. |
| `GET /anomalies` | Detected anomalies with evidence. |
| `POST /edit/impact` | Preview every document a value-change would touch. |
| `POST /edit/apply` · `GET /edit/download/{id}` | Apply a cross-document edit / download result. |
| `GET /assets/pages/{document_id}/{page_no}.png` | Rendered page image for the viewer. |

## Project structure

```
financial-document-os/
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # all HTTP endpoints
│   │   ├── pipeline/              # ingest → classify → extract → render orchestration
│   │   ├── unsiloed/              # Unsiloed client, classify registry, JSON schemas
│   │   ├── intelligence/          # NL→SQL, entity resolution, anomalies, normalization
│   │   ├── seed/generate_corpus.py# deterministic synthetic corpus generator
│   │   ├── models.py              # typed entity tables + citations + anomalies + edits
│   │   └── config.py              # settings (env-driven)
│   ├── scripts/calibrate_edit.py  # Edit API coordinate calibration test
│   └── data/corpus/               # 23 bundled demo PDFs  ← included
├── frontend/                      # Next.js app (Explorer, Ask, Anomalies, Edit)
└── docker-compose.yml             # Postgres (findoc-db on :5434)
```

## Safety model

NL→SQL is the one place untrusted natural language reaches the database, so it has **two
independent guardrails**:

1. **Read-only Postgres role** (`findoc_ro`) — `default_transaction_read_only = on`, a
   5s statement timeout, and `SELECT`-only grants. Even a malicious query can't write.
2. **`sqlglot` AST allowlist** — the generated SQL is parsed and rejected unless it's a
   single read-only `SELECT`. No DML/DDL, no multiple statements.

## Troubleshooting

- **`docker exec findoc-db ...` fails** — the Postgres container is named `findoc-db`;
  make sure `docker compose up -d` succeeded and the container is healthy.
- **NL→SQL errors about the read-only role** — you skipped the `CREATE ROLE findoc_ro`
  step; run it, or check `DATABASE_READONLY_URL`.
- **Editing is disabled** — calibration failed in your environment; run
  `python -m scripts.calibrate_edit` to see why. Every other feature still works.
- **Frontend can't reach the API** — confirm the backend is on `:8001` and
  `NEXT_PUBLIC_API_URL` matches.
- **Empty Explorer** — upload the `backend/data/corpus/` PDFs and click **Process**
  first; extraction has to run before entities exist.

---

Built to show what document extraction looks like when every number keeps its receipt.
Powered by [Unsiloed](https://unsiloed.ai).
