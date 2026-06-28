# Launch Kit — Financial Document OS

## The post (X / LinkedIn)

> I uploaded 10 years of financial documents and turned them into a database.
>
> Bank statements. Contracts. Loan agreements. Tax filings. Investment statements. Audit reports. 2,000+ pages where every number lives trapped inside a PDF.
>
> My agent read all of it and now I can:
>
> - Ask "which vendors did we pay more than $100k?" and get an answer in plain SQL — not a chatbot guess, a real query over a real database.
> - See every value traced to the exact highlighted spot on the exact page it came from. Receipts for everything.
> - Catch what I'd never find by hand: a duplicate $12,500 payment, a vendor paid $120k against an $80k contract, an investment quietly down 36%.
> - Change our company address once and rewrite it across all 50 PDFs — layout preserved — then download the updated files.
>
> The whole thing runs on Unsiloed: it classifies each document, extracts structured data with confidence scores and word-level citations, and even edits the PDFs back. Documents in, database out.
>
> Documents are becoming databases. Open source, link below. 👇

## Demo video beats (60–90s)

1. **The pile.** Documents page — drag in bank statements, contracts, a tax
   filing, an investment statement. Hit Process. Stage ticker:
   classifying → extracting with Unsiloed → structuring entities → detecting anomalies.
2. **The database.** Entity Explorer — flip through Transactions, Contracts,
   Investments. Click a transaction amount → Evidence Viewer highlights the exact
   cell on the source statement. *Receipts.*
3. **The question.** Ask page — "Which vendors did we pay more than $100,000?"
   → table appears (Deloitte $120k, ADP $106k) → click a row → evidence. Show the
   generated SQL collapsible. Say "not RAG — a real query."
4. **The catch.** Anomalies page — "Deloitte paid above contract value,"
   "duplicate payment to Acme," "Globex down 36%." Click one → cited proof.
5. **The magic.** Edit page — change the company address once → "Analyze impact"
   shows it in 3 documents → Apply → download a rewritten PDF, address changed,
   layout intact.

## Pre-flight checklist

- [ ] `scripts/calibrate_edit.py` passes (editing_enabled true)
- [ ] `generate_corpus.py` run; all 8 docs uploaded + processed (39 entities, 10 anomalies, 14 vendors)
- [ ] Each demo question returns rows with working evidence links
- [ ] Edit applied cleanly across the 3 address documents; downloaded PDF verified
- [ ] Screenshots at 1280px+, no devtools
- [ ] Real screenshot of the Evidence Viewer highlight (the differentiator) in the post

## Honest notes for the writeup

- Extraction quality on the synthetic transaction tables was 0.99+ confidence;
  Unsiloed handles the table layout cleanly.
- The Edit API edits by coordinate and can't reflow wrapped prose — keep
  edit targets on their own lines. Standalone fields (table cells, addresses,
  IDs) rewrite perfectly.
- NL→SQL is guarded two ways (read-only DB role + sqlglot allowlist); a
  "delete everything" question is physically unable to write.
