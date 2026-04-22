# Trustworthy RAG

A RAG (Retrieval-Augmented Generation) application that adds a **citation verification** and **hallucination scoring** layer on top of any standard RAG pipeline. Built with Streamlit, LlamaIndex, and [Nebius Token Factory](https://tokenfactory.nebius.com/).

Every factual sentence in the answer is:
1. Forced to carry an inline citation (`[1]`, `[2,3]`, ...) pointing to the retrieved chunks.
2. Re-checked by a separate verifier LLM that classifies the claim as `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, or `CONTRADICTED` against the cited evidence.
3. Aggregated into a single **Trust Score** and its complement, the **Hallucination Risk**.

## Features

- 📄 PDF upload with LlamaIndex indexing and Nebius embeddings (`BAAI/bge-en-icl`)
- 🔗 Forced inline citations in the generated answer
- 🕵️ Separate verifier model for independent claim checking (LLM-as-judge entailment)
- 📊 Trust Score and Hallucination Risk metrics
- 🧩 Per-claim breakdown with verdict, confidence, citations, and reason
- 🔌 Fully powered by Nebius Token Factory — choose different models for generation vs. verification

## Prerequisites

- Python 3.10+
- [Nebius Token Factory](https://tokenfactory.nebius.com/) account and API key

## Installation

1. Clone the repository and enter this directory:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/rag_apps/trustworthy_rag
```

2. Install dependencies:

```bash
# pip
pip install -r requirements.txt

# or uv (recommended)
uv sync
```

3. Configure environment variables:

```bash
cp .env.example .env
# then edit .env and set NEBIUS_API_KEY
```

## Usage

```bash
streamlit run main.py
```

Then:
1. Upload a PDF in the sidebar.
2. Pick an **Answer Model** and a **Verifier Model** (use different models to reduce self-confirmation bias).
3. Ask a question and click **Run Trustworthy RAG**.
4. Inspect the answer, the trust/hallucination metrics, the per-claim verdicts, and the retrieved sources.

## How It Works

```
PDF ─► LlamaIndex + Nebius embeddings ─► retrieved chunks (with IDs)
                                              │
                                              ▼
                   Answer Model (Nebius) ─► cited answer "...fact [1]. ...fact [2,3]."
                                              │
                          split into claims ──┘
                                              ▼
                   Verifier Model (Nebius) ─► {verdict, confidence, reason} per claim
                                              │
                                              ▼
                          Trust Score  =  Σ(weight × confidence) / Σ(confidence) × 100
                          Hallucination = 100 − Trust Score
```

Verdict weights: `SUPPORTED = 1.0`, `PARTIAL = 0.5`, `UNSUPPORTED = 0.0`, `CONTRADICTED = −0.5`.

## Models Used (defaults)

- **Embeddings**: `BAAI/bge-en-icl`
- **Answer**: `Qwen/Qwen3-235B-A22B`
- **Verifier**: `meta-llama/Meta-Llama-3.1-70B-Instruct`

All models are served through Nebius Token Factory and can be swapped in the sidebar.

## Drop-in on Existing RAG

The verification layer in `main.py` (`split_claims`, `extract_cited_ids`, `verify_claim`, `compute_trust_score`) is independent of the retrieval stack. If you already have a RAG pipeline that returns a cited answer plus the retrieved chunks with integer IDs, you can reuse these functions directly.

## Contributing

Issues and PRs are welcome. See the root `CONTRIBUTING.md`.
