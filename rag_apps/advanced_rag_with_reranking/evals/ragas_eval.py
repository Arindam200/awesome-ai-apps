"""
RAGAS evaluation for the Boeing RAG pipeline.

Runs Boeing-specific questions through the live RAG API, then scores each
response with four reference-free RAGAS metrics using the Nebius LLM as judge.

Metrics:
  - Faithfulness:      Is the answer grounded in the retrieved context?
  - Answer Relevancy:  Is the answer relevant to the question asked?
  - Context Relevance: What fraction of retrieved context is useful?
  - Context Precision:  Are the most useful contexts ranked highest?

Usage:
    # Make sure the API is running (uvicorn boeing_rag.api:app)
    python evals/ragas_eval.py [--limit N] [--out-dir evals/results]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from openai import AsyncOpenAI

from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithoutReference,
    ContextRelevance,
    Faithfulness,
    ResponseGroundedness,
)

API_BASE = "http://localhost:8000"


@dataclass(frozen=True)
class TestCase:
    id: str
    question: str
    filters: dict[str, Any] = field(default_factory=dict)
    top_k: int = 8
    category: str = "general"


TEST_CASES: list[TestCase] = [
    # --- Sustainability ---
    TestCase("r01", "What does Boeing say about sustainable aviation fuel?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r02", "What does Boeing report about the ecoDemonstrator program?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r03", "What does Boeing say about greenhouse gas emissions?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r04", "What does Boeing say about water consumption?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r05", "What does Boeing say about renewable electricity?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r06", "What does Boeing say about safety culture?",
             {}, category="mixed"),
    TestCase("r07", "What does Boeing say about community engagement or social impact?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r08", "What does Boeing say about STEM education or future workforce programs?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r09", "What does Boeing say about solid waste or landfill reduction?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r10", "What does Boeing say about climate risk?",
             {}, category="mixed"),

    # --- Annual / Financial ---
    TestCase("r11", "What are Boeing's major business segments in the 2023 annual report?",
             {"report_type": "annual_report", "report_year": 2023}, category="annual"),
    TestCase("r12", "What does Boeing say about aircraft production rates?",
             {"report_type": "annual_report"}, category="annual"),
    TestCase("r13", "What does Boeing say about debt in recent annual reports?",
             {"report_type": "annual_report", "report_year_min": 2020}, category="annual"),
    TestCase("r14", "What does Boeing say about supply chain constraints?",
             {"report_type": "annual_report"}, category="risk"),
    TestCase("r15", "What does Boeing say about backlog in annual reports?",
             {"report_type": "annual_report"}, category="annual"),
    TestCase("r16", "Summarize Commercial Airplanes performance in the 2023 annual report.",
             {"report_type": "annual_report", "report_year": 2023}, category="annual"),
    TestCase("r17", "How did Boeing discuss COVID-19 impacts in the 2020 annual report?",
             {"report_type": "annual_report", "report_year": 2020}, category="annual"),
    TestCase("r18", "What does Boeing Global Services do according to the annual reports?",
             {"report_type": "annual_report"}, category="annual"),
    TestCase("r19", "What does Boeing say about product safety in sustainability reports?",
             {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("r20", "What does Boeing say about diversity, equity, inclusion, or belonging?",
             {"report_type": "sustainability_report"}, category="sustainability"),

    # --- Locator / comparison ---
    TestCase("r21", "Where does Boeing discuss 737 MAX risks in annual reports?",
             {"report_type": "annual_report"}, category="risk"),
    TestCase("r22", "What does the 2023 sustainability report say about safety or aerospace safety?",
             {"report_type": "sustainability_report", "report_year": 2023}, category="year_filter"),
    TestCase("r23", "What does Boeing say about regulatory or certification risks?",
             {"report_type": "annual_report"}, category="risk"),
    TestCase("r24", "Across all documents, what are the strongest cited themes about environmental responsibility?",
             {}, category="mixed"),
    TestCase("r25", "What does Boeing say about creating or launching its second century?",
             {"report_type": "annual_report", "report_year_min": 2015, "report_year_max": 2016}, category="annual"),
]


def query_rag(case: TestCase) -> dict[str, Any]:
    resp = requests.post(
        f"{API_BASE}/query",
        json={"question": case.question, "filters": case.filters, "top_k": case.top_k},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


async def run_ragas_eval(
    cases: list[TestCase],
    llm,
    embeddings,
    out_dir: Path,
) -> None:
    faithfulness = Faithfulness(llm=llm)
    answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
    context_relevance = ContextRelevance(llm=llm)
    context_precision = ContextPrecisionWithoutReference(llm=llm)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jsonl_path = out_dir / f"ragas_eval_{stamp}.jsonl"
    md_path = out_dir / f"ragas_eval_{stamp}.md"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx:02d}/{len(cases)}] {case.id}: {case.question}", flush=True)
        started = time.time()

        try:
            rag_response = query_rag(case)
        except Exception as exc:
            print(f"  RAG API error: {exc}")
            row = _error_row(case, str(exc), time.time() - started)
            rows.append(row)
            _append_jsonl(jsonl_path, row)
            continue

        answer = rag_response.get("answer", "")
        sources = rag_response.get("sources", [])
        contexts = [s.get("text", "")[:2000] for s in sources if s.get("text")]

        if not answer.strip() or not contexts:
            print("  Empty answer or no contexts -- skipping RAGAS scoring")
            row = _error_row(case, "empty answer or contexts", time.time() - started)
            rows.append(row)
            _append_jsonl(jsonl_path, row)
            continue

        scores: dict[str, float | None] = {}
        for name, scorer, kwargs in [
            ("faithfulness", faithfulness, {
                "user_input": case.question, "response": answer, "retrieved_contexts": contexts,
            }),
            ("answer_relevancy", answer_relevancy, {
                "user_input": case.question, "response": answer,
            }),
            ("context_relevance", context_relevance, {
                "user_input": case.question, "retrieved_contexts": contexts,
            }),
            ("context_precision", context_precision, {
                "user_input": case.question, "response": answer, "retrieved_contexts": contexts,
            }),
        ]:
            try:
                result = await scorer.ascore(**kwargs)
                scores[name] = result.value
                print(f"  {name}: {result.value:.3f}")
            except Exception as exc:
                print(f"  {name}: ERROR ({exc})")
                scores[name] = None

        elapsed = round(time.time() - started, 2)
        row = {
            "case": case.__dict__,
            "answer_preview": answer[:300],
            "source_count": len(sources),
            "scores": scores,
            "elapsed_seconds": elapsed,
        }
        rows.append(row)
        _append_jsonl(jsonl_path, row)

    _write_summary(md_path, rows, jsonl_path)
    print(f"\nWrote {jsonl_path}")
    print(f"Wrote {md_path}")


def _error_row(case: TestCase, error: str, elapsed: float) -> dict[str, Any]:
    return {
        "case": case.__dict__,
        "answer_preview": "",
        "source_count": 0,
        "scores": {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_relevance": None,
            "context_precision": None,
        },
        "error": error,
        "elapsed_seconds": round(elapsed, 2),
    }


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_summary(path: Path, rows: list[dict[str, Any]], jsonl_path: Path) -> None:
    metric_names = ["faithfulness", "answer_relevancy", "context_relevance", "context_precision"]
    metric_vals: dict[str, list[float]] = {m: [] for m in metric_names}

    for row in rows:
        for m in metric_names:
            v = row.get("scores", {}).get(m)
            if v is not None:
                metric_vals[m].append(v)

    lines = [
        "# RAGAS Evaluation Summary",
        "",
        f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Cases evaluated: {len(rows)}",
        f"- Detailed JSONL: `{jsonl_path}`",
        "",
        "## Aggregate Scores",
        "",
        "| Metric | Mean | Min | Max | Count |",
        "|--------|------|-----|-----|-------|",
    ]
    for m in metric_names:
        vals = metric_vals[m]
        if vals:
            lines.append(
                f"| {m} | {statistics.mean(vals):.3f} | {min(vals):.3f} | {max(vals):.3f} | {len(vals)} |"
            )
        else:
            lines.append(f"| {m} | N/A | N/A | N/A | 0 |")

    lines.extend(["", "## Per-Question Scores", ""])
    for row in rows:
        case = row["case"]
        s = row.get("scores", {})
        error = row.get("error", "")
        score_str = " | ".join(
            f"{s.get(m, 'ERR')}" if s.get(m) is None else f"{s[m]:.2f}" for m in metric_names
        )
        status = "ERROR" if error else "OK"
        lines.append(f"| {case['id']} | {case['question'][:60]} | {score_str} | {status} |")

    lines.extend(["", "## Weak Cases (any metric < 0.65)", ""])
    for row in rows:
        case = row["case"]
        s = row.get("scores", {})
        weak_metrics = [
            m for m in metric_names
            if s.get(m) is not None and s[m] < 0.65
        ]
        if weak_metrics or row.get("error"):
            lines.append(f"### {case['id']} - {case['question']}")
            if row.get("error"):
                lines.append(f"- Error: {row['error']}")
            for m in weak_metrics:
                lines.append(f"- **{m}**: {s[m]:.3f}")
            lines.append(f"- Answer preview: {row.get('answer_preview', '')[:200]}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS evaluation for Boeing RAG")
    parser.add_argument("--limit", type=int, default=25, help="Max test cases to evaluate")
    parser.add_argument("--out-dir", type=Path, default=Path("evals/results"))
    args = parser.parse_args()

    from boeing_rag.config import get_settings
    settings = get_settings()

    if not settings.nebius_api_key:
        raise SystemExit("NEBIUS_API_KEY is required for RAGAS evaluation (LLM judge)")

    async_client = AsyncOpenAI(
        api_key=settings.nebius_api_key,
        base_url=settings.nebius_base_url,
    )
    llm = llm_factory(
        settings.nebius_chat_model or "MiniMaxAI/MiniMax-M2.5",
        client=async_client,
    )
    embeddings = RagasOpenAIEmbeddings(
        client=async_client,
        model=settings.nebius_embed_model or "Qwen/Qwen3-Embedding-8B",
    )

    cases = TEST_CASES[: args.limit]
    asyncio.run(run_ragas_eval(cases, llm, embeddings, args.out_dir))


if __name__ == "__main__":
    main()
