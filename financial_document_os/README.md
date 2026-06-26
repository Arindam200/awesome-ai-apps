# Financial Document OS

**Upload your financial documents. Get a database.**

Bank statements, contracts, loan agreements, tax filings, investment statements,
audit reports — the information you need is trapped inside PDFs. Financial
Document OS uses [Unsiloed](https://unsiloed.ai) to turn those documents into
structured, queryable financial entities, each value traceable to the exact spot
on the exact page it came from. Then you can browse it like a database, ask
questions in plain English, catch anomalies, and edit values across every PDF at
once.

It uses **all four** Unsiloed capabilities: **classify** (route each document),
**extract** (schema-driven, with confidence scores + word-level bbox citations),
**parse** (layout-aware fallback for dense tables), and the **Edit API** (rewrite
values across documents by coordinate, preserving layout).

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

## Features

- **Entity Explorer** — accounts, transactions, vendors, contracts/loans,
  investments, obligations, tax items as sortable tables. Click any extracted
  value to see it highlighted in the source PDF (the Evidence Viewer).
- **Vendors** — the same party resolved across every document it appears in
  (Deloitte across a contract + statements + an audit = one vendor, with its
  total paid and every reference).
- **Ask** — natural-language questions answered with SQL over the extracted
  database (not RAG). "Which vendors did we pay more than $100,000?" Two
  guardrails: a read-only Postgres role and a `sqlglot` SELECT-only allowlist.
  Every result row links to its source evidence.
- **Anomalies** — duplicate payments, vendors paid over contract value,
  valuation drops, expenses missing from tax filings, expiring contracts, large
  obligations — each flagged with cited evidence.
- **Edit across documents** — change a value once (e.g. a company address) and
  rewrite it in every PDF it appears in, preserving layout, via the Unsiloed
  Edit API. Impact analysis previews every affected document first.

## Stack

Python/FastAPI · PostgreSQL · Next.js + Tailwind · Unsiloed APIs · OpenAI (gpt-5)
for NL→SQL · pymupdf for page rendering. No RAG, no vector DB — documents become
a real relational database.

## Quickstart

```bash
cp .env.example .env          # add UNSILOED_API_KEY, OPENAI_API_KEY (RESEND optional)
docker compose up -d          # Postgres on :5434

cd backend
uv venv .venv && uv pip install -e . --python .venv/bin/python
# read-only role for NL→SQL:
docker exec findoc-db psql -U findoc -d financial_document_os -c \
  "CREATE ROLE findoc_ro LOGIN PASSWORD 'findoc_ro'; \
   GRANT CONNECT ON DATABASE financial_document_os TO findoc_ro; \
   GRANT USAGE ON SCHEMA public TO findoc_ro; \
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO findoc_ro; \
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO findoc_ro; \
   ALTER ROLE findoc_ro SET default_transaction_read_only = on; \
   ALTER ROLE findoc_ro SET statement_timeout = '5000';"
.venv/bin/python -m app.seed.generate_corpus     # synthetic demo PDFs
.venv/bin/uvicorn app.main:app --port 8001

cd ../frontend
pnpm install && pnpm dev --port 3006              # http://localhost:3006
```

Upload documents on the Documents page (or use the generated `backend/data/corpus`),
hit **Process**, then explore.

## The Edit API (validated first)

Editing is gated behind a calibration test because the Edit API edits by
**coordinates** and lives on a different host than extraction. Run it before
trusting the feature:

```bash
cd backend && .venv/bin/python -m scripts.calibrate_edit
```

It makes a known PDF, extracts it, edits the known string using the stored
citation bbox, downloads the result, and asserts the replacement landed in the
right place. **Result: PASSED** — the editor uses the citation's own coordinate
space (corners as-is). `editing_enabled` defaults to `true`; if calibration fails
in your environment it ships off and every other feature is unaffected.

For prose where a value wraps mid-sentence, coordinate replacement can't reflow
the paragraph — keep edit targets (addresses, names, IDs) on their own lines for
clean results.

## Synthetic demo corpus

`app/seed/generate_corpus.py` generates 8 interlinked documents (deterministic)
with intentional cross-document overlaps so every feature demos:

- "Deloitte LLP" in a contract + bank statements + an audit → resolves to one vendor
- One company address across 2 contracts + a loan → the cross-PDF edit target
- A duplicate $12,500 payment, Deloitte paid $120k against an $80k contract,
  a 36% investment valuation drop, a vendor expensed but absent from the tax
  filing → the anomalies
