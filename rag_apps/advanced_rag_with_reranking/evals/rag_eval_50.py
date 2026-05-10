from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI


API_BASE = "http://localhost:8000"


@dataclass(frozen=True)
class TestCase:
    id: str
    question: str
    filters: dict[str, Any] = field(default_factory=dict)
    top_k: int = 8
    category: str = "general"


TEST_CASES: list[TestCase] = [
    TestCase("q001", "What does Boeing say about sustainable aviation fuel?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q002", "Compare Boeing sustainability priorities across 2021, 2022, 2023, and 2024. Cite sources.", {"report_type": "sustainability_report"}, category="comparison"),
    TestCase("q003", "What environmental reduction goals did Boeing report around greenhouse gas emissions, water, waste, energy, and hazardous waste?", {"report_type": "sustainability_report"}, category="table"),
    TestCase("q004", "Where does Boeing discuss CORSIA and carbon-neutral growth?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q005", "What does Boeing report about the ecoDemonstrator program?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q006", "What does the 2024 sustainability and social impact report say about social impact?", {"report_type": "sustainability_report", "report_year": 2024}, category="year_filter"),
    TestCase("q007", "What does the 2023 sustainability report say about safety or aerospace safety?", {"report_type": "sustainability_report", "report_year": 2023}, category="year_filter"),
    TestCase("q008", "What does the 2022 sustainability report say about sustainable aerospace?", {"report_type": "sustainability_report", "report_year": 2022}, category="year_filter"),
    TestCase("q009", "What does the 2021 sustainability report say about responding to COVID-19?", {"report_type": "sustainability_report", "report_year": 2021}, category="year_filter"),
    TestCase("q010", "What does Boeing say about environmental leadership in the 2020 global environment report?", {"report_type": "sustainability_report", "report_year": 2020}, category="year_filter"),
    TestCase("q011", "What locations are visible in the visual extraction from the scanned sustainability document?", {"content_type": "image"}, category="visual"),
    TestCase("q012", "What information is visible in visual extraction chunks from image-only pages?", {"content_type": "image"}, category="visual"),
    TestCase("q013", "What are Boeing's major business segments in the 2023 annual report?", {"report_type": "annual_report", "report_year": 2023}, category="annual"),
    TestCase("q014", "Where does Boeing discuss 737 MAX risks in annual reports?", {"report_type": "annual_report"}, category="risk"),
    TestCase("q015", "How did Boeing discuss COVID-19 impacts in the 2020 annual report?", {"report_type": "annual_report", "report_year": 2020}, category="annual"),
    TestCase("q016", "What does the 2021 annual report say about transparency or transformation?", {"report_type": "annual_report", "report_year": 2021}, category="annual"),
    TestCase("q017", "What does the 2022 annual report say about today, tomorrow and beyond?", {"report_type": "annual_report", "report_year": 2022}, category="annual"),
    TestCase("q018", "What does Boeing say about backlog in annual reports?", {"report_type": "annual_report"}, category="annual"),
    TestCase("q019", "What does Boeing say about liquidity in the 2021 annual report?", {"report_type": "annual_report", "report_year": 2021}, category="annual"),
    TestCase("q020", "What does Boeing say about cash flow in the 2022 annual report?", {"report_type": "annual_report", "report_year": 2022}, category="annual"),
    TestCase("q021", "Summarize Commercial Airplanes performance in the 2023 annual report.", {"report_type": "annual_report", "report_year": 2023}, category="annual"),
    TestCase("q022", "Summarize Defense, Space & Security discussion in the 2023 annual report.", {"report_type": "annual_report", "report_year": 2023}, category="annual"),
    TestCase("q023", "What does Boeing Global Services do according to the annual reports?", {"report_type": "annual_report"}, category="annual"),
    TestCase("q024", "What does Boeing say about supply chain constraints?", {"report_type": "annual_report"}, category="risk"),
    TestCase("q025", "What does Boeing say about pension or retirement plan obligations?", {"report_type": "annual_report"}, category="risk"),
    TestCase("q026", "What does Boeing say about regulatory or certification risks?", {"report_type": "annual_report"}, category="risk"),
    TestCase("q027", "What does Boeing say about aircraft production rates?", {"report_type": "annual_report"}, category="annual"),
    TestCase("q028", "What does Boeing say about debt in recent annual reports?", {"report_type": "annual_report", "report_year_min": 2020}, category="annual"),
    TestCase("q029", "Compare Boeing's annual report discussion of resilience in 2020 with forward together in 2021.", {"report_type": "annual_report", "report_year_min": 2020, "report_year_max": 2021}, category="comparison"),
    TestCase("q030", "What does Boeing say about product safety in sustainability reports?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q031", "What does Boeing say about governance in sustainability or environmental reports?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q032", "What does Boeing say about community engagement or social impact?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q033", "What does Boeing say about STEM education or future workforce programs?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q034", "What does Boeing say about greenhouse gas emissions?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q035", "What does Boeing say about water consumption?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q036", "What does Boeing say about solid waste or landfill reduction?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q037", "What does Boeing say about renewable electricity?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q038", "What does Boeing say about Scope 1 and Scope 2 emissions?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q039", "What does Boeing say about climate risk?", {}, category="mixed"),
    TestCase("q040", "What does Boeing say about safety culture?", {}, category="mixed"),
    TestCase("q041", "Find table evidence about environmental reduction goals.", {"content_type": "table", "report_type": "sustainability_report"}, category="table"),
    TestCase("q042", "Find table evidence about annual financial performance or revenue.", {"content_type": "table", "report_type": "annual_report"}, category="table"),
    TestCase("q043", "What does Boeing say about the UN Sustainable Development Goals?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q044", "What does Boeing say about employees or workforce in sustainability reports?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q045", "What does Boeing say about diversity, equity, inclusion, or belonging?", {"report_type": "sustainability_report"}, category="sustainability"),
    TestCase("q046", "What does Boeing say about operational highlights in older annual reports?", {"report_type": "annual_report", "report_year_max": 2017}, category="annual"),
    TestCase("q047", "What does Boeing say about creating or launching its second century?", {"report_type": "annual_report", "report_year_min": 2015, "report_year_max": 2016}, category="annual"),
    TestCase("q048", "What does Boeing say about the future being built here?", {"report_type": "annual_report", "report_year": 2018}, category="annual"),
    TestCase("q049", "What does Boeing say about resilience and resolve?", {"report_type": "annual_report", "report_year": 2020}, category="annual"),
    TestCase("q050", "Across all documents, what are the strongest cited themes about environmental responsibility?", {}, category="mixed"),
]


def post_query(case: TestCase) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE}/query",
        json={"question": case.question, "filters": case.filters, "top_k": case.top_k},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def mechanical_checks(case: TestCase, response: dict[str, Any]) -> dict[str, Any]:
    answer = response.get("answer") or ""
    sources = response.get("sources") or []
    cited_numbers = sorted({int(num) for num in re.findall(r"\[(\d+)\]", answer)})
    source_count = len(sources)
    citation_numbers_in_range = all(1 <= num <= source_count for num in cited_numbers)
    filters_ok = True
    filter_violations: list[str] = []
    for source in sources:
        for key, expected in case.filters.items():
            if expected in (None, ""):
                continue
            if key == "report_year_min":
                if source.get("report_year") is not None and source.get("report_year") < expected:
                    filters_ok = False
                    filter_violations.append(f"{source.get('citation_label')} year<{expected}")
            elif key == "report_year_max":
                if source.get("report_year") is not None and source.get("report_year") > expected:
                    filters_ok = False
                    filter_violations.append(f"{source.get('citation_label')} year>{expected}")
            elif key in {"report_type", "content_type", "report_year", "document_id"}:
                if source.get(key) != expected:
                    filters_ok = False
                    filter_violations.append(
                        f"{source.get('citation_label')} {key}={source.get(key)!r} expected {expected!r}"
                    )

    return {
        "answer_nonempty": len(answer.strip()) >= 80,
        "source_count": source_count,
        "has_sources": source_count > 0,
        "has_inline_citations": bool(cited_numbers),
        "cited_numbers": cited_numbers,
        "citation_numbers_in_range": citation_numbers_in_range,
        "filters_ok": filters_ok,
        "filter_violations": filter_violations,
    }


def judge_response(client: OpenAI, model: str, case: TestCase, response: dict[str, Any]) -> dict[str, Any]:
    sources = response.get("sources") or []
    evidence = "\n\n".join(
        f"[{idx}] {src.get('citation_label')}\n{src.get('text', '')[:1800]}"
        for idx, src in enumerate(sources, start=1)
    )
    prompt = f"""
You are grading a RAG answer against retrieved evidence.

Question:
{case.question}

Answer:
{response.get("answer", "")}

Evidence:
{evidence}

Return strict JSON only with:
- faithfulness: number 0-1, whether answer claims are supported by evidence
- relevance: number 0-1, whether evidence answers the question
- citation_use: number 0-1, whether citations are used appropriately and refer to supporting evidence
- completeness: number 0-1, whether answer is sufficiently complete given evidence
- overall: number 0-1
- verdict: one of "pass", "review", "fail"
- unsupported_claims: array of short strings
- notes: short string

Be strict. If the evidence is weak or does not support the answer, mark review or fail.
"""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a strict evidence-grounded RAG evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=1800,
        timeout=90,
    )
    raw = completion.choices[0].message.content or "{}"
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return {"faithfulness": 0, "relevance": 0, "citation_use": 0, "completeness": 0, "overall": 0, "verdict": "fail", "unsupported_claims": ["judge returned non-json"], "notes": raw[:300]}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"faithfulness": 0, "relevance": 0, "citation_use": 0, "completeness": 0, "overall": 0, "verdict": "fail", "unsupported_claims": ["judge json parse failed"], "notes": raw[:300]}


def status_from_scores(mechanical: dict[str, Any], judge: dict[str, Any]) -> str:
    if not mechanical["answer_nonempty"] or not mechanical["has_sources"] or not mechanical["citation_numbers_in_range"] or not mechanical["filters_ok"]:
        return "fail"
    if not mechanical["has_inline_citations"]:
        return "review"
    if float(judge.get("overall", 0)) < 0.65 or judge.get("verdict") == "fail":
        return "fail"
    if float(judge.get("overall", 0)) < 0.78 or judge.get("verdict") == "review":
        return "review"
    return "pass"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out-dir", type=Path, default=Path("evals/results"))
    args = parser.parse_args()

    from boeing_rag.config import get_settings

    settings = get_settings()
    client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)
    model = settings.nebius_chat_model or "MiniMaxAI/MiniMax-M2.5"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jsonl_path = args.out_dir / f"rag_eval_50_{stamp}.jsonl"
    md_path = args.out_dir / f"rag_eval_50_{stamp}.md"

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(TEST_CASES[: args.limit], start=1):
        started = time.time()
        print(f"[{idx:02d}/{args.limit}] {case.id}: {case.question}", flush=True)
        try:
            response = post_query(case)
            mechanical = mechanical_checks(case, response)
            judge = judge_response(client, model, case, response)
            final_status = status_from_scores(mechanical, judge)
            row = {
                "case": case.__dict__,
                "response": response,
                "mechanical": mechanical,
                "judge": judge,
                "final_status": final_status,
                "elapsed_seconds": round(time.time() - started, 2),
            }
        except Exception as exc:
            row = {
                "case": case.__dict__,
                "response": None,
                "mechanical": {},
                "judge": {"overall": 0, "verdict": "fail", "notes": str(exc)},
                "final_status": "fail",
                "elapsed_seconds": round(time.time() - started, 2),
            }
        results.append(row)
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_summary(md_path, results, jsonl_path)
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {md_path}")


def write_summary(path: Path, results: list[dict[str, Any]], jsonl_path: Path) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result["final_status"]] = counts.get(result["final_status"], 0) + 1
    overall_scores = [float(r["judge"].get("overall", 0)) for r in results]
    faithfulness = [float(r["judge"].get("faithfulness", 0)) for r in results]
    relevance = [float(r["judge"].get("relevance", 0)) for r in results]
    citation_use = [float(r["judge"].get("citation_use", 0)) for r in results]
    completeness = [float(r["judge"].get("completeness", 0)) for r in results]

    lines = [
        "# RAG Evaluation Summary",
        "",
        f"- Cases: {len(results)}",
        f"- Pass: {counts.get('pass', 0)}",
        f"- Review: {counts.get('review', 0)}",
        f"- Fail: {counts.get('fail', 0)}",
        f"- Mean overall: {statistics.mean(overall_scores):.3f}",
        f"- Mean faithfulness: {statistics.mean(faithfulness):.3f}",
        f"- Mean relevance: {statistics.mean(relevance):.3f}",
        f"- Mean citation use: {statistics.mean(citation_use):.3f}",
        f"- Mean completeness: {statistics.mean(completeness):.3f}",
        f"- Detailed JSONL: `{jsonl_path}`",
        "",
        "## Weak Cases",
        "",
    ]
    weak = [r for r in results if r["final_status"] != "pass"]
    if not weak:
        lines.append("No review/fail cases.")
    else:
        for result in weak:
            case = result["case"]
            judge = result["judge"]
            mech = result["mechanical"]
            lines.extend(
                [
                    f"### {case['id']} - {result['final_status'].upper()}",
                    f"- Question: {case['question']}",
                    f"- Filters: `{case['filters']}`",
                    f"- Overall: {judge.get('overall')}",
                    f"- Faithfulness: {judge.get('faithfulness')}",
                    f"- Relevance: {judge.get('relevance')}",
                    f"- Citation use: {judge.get('citation_use')}",
                    f"- Completeness: {judge.get('completeness')}",
                    f"- Mechanical: `{mech}`",
                    f"- Unsupported claims: `{judge.get('unsupported_claims')}`",
                    f"- Notes: {judge.get('notes')}",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
