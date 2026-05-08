from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB_PATH = DATA / "ops.sqlite"


class DataOpsReport(BaseModel):
    question: str
    executive_summary: str
    anomaly_found: bool
    evidence: list[str]
    root_cause_hypothesis: str
    recommended_actions: list[str]
    sql_used: list[str]
    confidence: str
    audit_trail: list[str] = Field(default_factory=list)


def ensure_db() -> None:
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for table, csv_name in [("events", "events.csv"), ("pipeline_runs", "pipeline_runs.csv")]:
            rows = list(csv.DictReader((DATA / csv_name).open()))
            columns = rows[0].keys()
            conn.execute(f"CREATE TABLE {table} ({', '.join(f'{col} TEXT' for col in columns)})")
            for row in rows:
                placeholders = ", ".join("?" for _ in columns)
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [row[col] for col in columns],
                )
        conn.commit()
    finally:
        conn.close()


@tool
def describe_schema() -> str:
    """Describe available read-only SQLite tables and columns."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        schema = {}
        for table in ["events", "pipeline_runs"]:
            schema[table] = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        return json.dumps(schema, indent=2)
    finally:
        conn.close()


@tool
def run_readonly_sql(sql: str) -> str:
    """Run a read-only SELECT query against the local ops database."""
    normalized = sql.strip()
    lowered = normalized.lower()
    if ";" in normalized:
        return "Rejected: multiple statements are not allowed."
    if "--" in normalized or "/*" in normalized or "*/" in normalized:
        return "Rejected: SQL comments are not allowed."
    if not re.match(r"^\s*select\b", lowered):
        return "Rejected: only SELECT queries are allowed."
    forbidden = r"\b(insert|update|delete|drop|alter|attach|pragma|create|replace|vacuum)\b"
    if re.search(forbidden, lowered):
        return "Rejected: query contains a forbidden SQL keyword."
    ensure_db()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute(sql).fetchmany(50)]
        return json.dumps(rows, indent=2)
    finally:
        conn.close()


@tool
def list_pipeline_changes(date: str) -> str:
    """List pipeline runs and code changes for a date."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM pipeline_runs WHERE date = ? ORDER BY pipeline", (date,)
            )
        ]
        return json.dumps(rows, indent=2)
    finally:
        conn.close()


TOOLS = [describe_schema, run_readonly_sql, list_pipeline_changes]

SYSTEM = """You are a data quality operations agent.
Use tools to inspect schema, query data, and correlate pipeline changes.
Only recommend actions; do not mutate data. Return compact JSON only:
{
  "question": "...",
  "executive_summary": "...",
  "anomaly_found": true,
  "evidence": ["..."],
  "root_cause_hypothesis": "...",
  "recommended_actions": ["..."],
  "sql_used": ["..."],
  "confidence": "low|medium|high",
  "audit_trail": ["tools/evidence used"]
}
"""


def build_llm() -> Any:
    load_dotenv(ROOT / ".env")
    load_dotenv()
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("Set NEBIUS_API_KEY in the environment or this folder's .env file.")
    return ChatOpenAI(
        api_key=key,
        base_url="https://api.studio.nebius.ai/v1/",
        model=os.getenv("NEBIUS_MODEL", "moonshotai/Kimi-K2.5"),
        temperature=0.1,
        max_tokens=2600,
    ).bind_tools(TOOLS)


def run_agent(question: str) -> DataOpsReport:
    llm = build_llm()
    tools = {item.name: item for item in TOOLS}
    messages: list[Any] = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=question),
    ]
    audit = []
    for _ in range(8):
        response = llm.invoke(messages)
        messages.append(response)
        if not isinstance(response, AIMessage) or not response.tool_calls:
            content = response.content if isinstance(response.content, str) else json.dumps(response.content)
            if not content.strip():
                messages.append(HumanMessage(content="Return the final data quality report as the requested JSON object now."))
                continue
            result = DataOpsReport.model_validate_json(extract_json(content))
            result.audit_trail = result.audit_trail + audit
            return result
        for call in response.tool_calls:
            tool_name = call["name"]
            if tool_name not in tools:
                allowed = ", ".join(tools)
                messages.append(
                    ToolMessage(
                        content=f"Unknown tool '{tool_name}'. Choose only one of these tools: {allowed}.",
                        tool_call_id=call["id"],
                    )
                )
                continue
            output = tools[tool_name].invoke(call["args"])
            audit.append(f"{call['name']}({call['args']})")
            messages.append(ToolMessage(content=output, tool_call_id=call["id"]))
    raise RuntimeError("Agent did not converge after tool loop.")


def extract_json(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Model response did not contain JSON: {cleaned[:300]}")
    return match.group(0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Nebius + LangChain data quality ops agent.")
    parser.add_argument(
        "--question",
        default="Why did web accepted events drop on 2026-05-07, and what should DataOps do next?",
    )
    args = parser.parse_args()
    print(run_agent(args.question).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
