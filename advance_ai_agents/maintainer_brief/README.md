# Maintainer Intelligence Brief

**The email every open source maintainer wishes they had.**

Every week, this app reads everything happening around your project — GitHub issues,
Hacker News threads, Reddit posts, security advisories, **and the stuff nobody has time
to read: conference decks, CFP PDFs, industry reports, RFCs** — and sends you a
five-minute intelligence brief with receipts.

The receipts are the point. Document signals are extracted with
[Unsiloed](https://unsiloed.ai), which returns structured JSON with per-field
**confidence scores and word-level bounding-box citations**. Every insight in the
newsletter deep-links to a viewer that highlights the exact spot on the exact page
of the source document it came from.

```
sources                        pipeline                                 output
─────────────────────────────  ──────────────────────────────────────  ─────────────────────
GitHub issues / discussions ─┐
  / releases                 │
Hacker News (Algolia)     ───┤   INGEST                                 ┌─ HTML email (Resend)
Reddit                    ───┼─▶ normalize ─▶ trends ─▶ LLM brief ───▶──┤
OSV / advisories          ───┘      ▲           (SQL)    (structured)   └─ Next.js dashboard
                                    │                                      └─ bbox citation viewer
Conference decks (PDF)    ───┐      │
Reports / RFCs / CFPs     ───┼─▶ Unsiloed classify ─▶ extract ──────────▶ signals + citations
Advisory PDFs / uploads   ───┘   (category routing)   (schema-driven,     (confidence + bbox)
                                                       citations on)
```

## Honest routing: what Unsiloed does vs. plain APIs

GitHub, Hacker News, Reddit, and OSV already speak JSON — those go straight to
normalization. **Unsiloed handles the sources that don't**: PDFs, PPTX decks, DOCX,
scans, reports — data trapped in *layout*, where its vision-first parsing, calibrated
confidence scores, and word-level bbox citations do work no API can. That's where the
unique signals hide: which projects got keynote mentions, what competitors announced
in their decks, what an industry survey's tables say about your category. Right tool
per source.

## Stack

- **Backend** — Python / FastAPI, SQLAlchemy, PostgreSQL, APScheduler (cron), pymupdf (page rendering)
- **Extraction** — Unsiloed `/classify` + `/v2/extract` (async jobs, schema registry in `backend/app/unsiloed/schemas/`)
- **Intelligence** — configurable structured LLM outputs for the brief and batched sentiment
- **Email** — Jinja2 table-layout HTML via Resend
- **Frontend** — Next.js + Tailwind: brief viewer, signals explorer, citation viewer

## Quickstart

```bash
# 1. Keys
cp .env.example .env   # fill in UNSILOED_API_KEY, an LLM key, RESEND_API_KEY, GITHUB_TOKEN

# 2. Postgres
docker compose up -d

# 3. Backend (http://localhost:8000)
cd backend
uv venv .venv && uv pip install -e . --python .venv/bin/python
.venv/bin/uvicorn app.main:app --port 8000

# 4. Frontend (http://localhost:3005)
cd ../frontend
pnpm install
pnpm dev --port 3005
```

Then either click **Run brief now** on the dashboard, or:

```bash
curl -X POST localhost:8000/runs -H "Content-Type: application/json" \
  -d '{"project_id": 1, "dry_run": true}'   # dry_run skips the email send
```

## LLM provider configuration

Set `LLM_PROVIDER=minimax` and provide `MINIMAX_API_KEY` to use MiniMax. Set
`MINIMAX_REGION=global_en` or `cn_zh` to select the regional endpoints, then set
`MINIMAX_PROTOCOL=openai` or `anthropic` to select the compatible API. The default
models are `MiniMax-M3` for synthesis and `MiniMax-M2.7` for sentiment. OpenAI-compatible
requests use the regional `/v1` endpoint, while Anthropic-compatible requests use the
regional `/anthropic` endpoint. See the [global API overview](https://platform.minimax.io/docs/api-reference/api-overview)
or [China API overview](https://platform.minimaxi.com/docs/api-reference/api-overview).

## Configure your project

Everything is driven by `projects/<slug>.yaml` — repos, keywords, competitors,
subreddits, HN queries, OSV packages, newsletter recipients/cadence, and the
**document drop**: a list of PDF/deck URLs to extract. You can also upload documents
from the dashboard. Copy `projects/meshery.yaml` and restart the backend.

## Bbox calibration (do this once, first)

Unsiloed returns bounding boxes per extracted field; their coordinate space
(PDF points vs rendered pixels) is verified empirically:

```bash
cd backend && .venv/bin/python scripts/calibrate_bbox.py
```

This generates a PDF with text at known coordinates, extracts it, and writes
`overlay_pt.png` / `overlay_px.png` under `backend/data/calibration/`. Whichever
overlay has rectangles sitting on the text is the correct space — set it as the
default `bboxSpace` in `frontend/src/components/CitationViewer.tsx` (there's also a
runtime toggle in the viewer UI).

## Scheduling

The backend runs an in-process APScheduler cron per project (`cadence: weekly` →
Mondays 08:00 UTC, `daily` → every day 08:00 UTC). No external job runner needed.

## Cost & rate-limit notes

- Unsiloed: 60 req/60s limit — the client uses a shared 50/60s token bucket across
  submits *and* polls; extraction results are cached by content hash, so a document
  is never extracted twice.
- A failed document never blocks the brief; connectors are best-effort per source.
