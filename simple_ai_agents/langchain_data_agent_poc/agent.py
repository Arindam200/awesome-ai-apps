"""LangGraph NL-to-SQL data agent PoC using Nebius through LangChain."""
from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_nebius import ChatNebius
from langgraph.graph import END, StateGraph

from config import DEFAULT_DOMAIN, DOMAINS
from dataset import DemoDataset
from sql_safety import validate_select_sql
from visualization import suggest_chart

load_dotenv()

DEFAULT_MODEL = os.getenv("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B")


class DataAgentState(TypedDict, total=False):
    question: str
    history: list[tuple[str, str]]
    standalone_question: str
    domain: str
    sql: str
    validated_sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    answer: str
    chart: dict[str, str] | None
    error: str | None


class DataAgent:
    """A compact data-agent pipeline: route, write SQL, validate, execute, answer."""

    def __init__(self, dataset: DemoDataset | None = None, verbose: bool = False) -> None:
        self.dataset = dataset or DemoDataset()
        self.verbose = verbose
        self.llm = ChatNebius(
            model=DEFAULT_MODEL,
            api_key=os.environ["NEBIUS_API_KEY"],
            temperature=0,
        )
        self.graph = self._build_graph()

    def query(
        self,
        question: str,
        history: list[tuple[str, str]] | None = None,
    ) -> DataAgentState:
        return self.graph.invoke({"question": question, "history": history or []})

    def _build_graph(self):
        graph = StateGraph(DataAgentState)
        graph.add_node("rewrite", self._rewrite_question)
        graph.add_node("route", self._route_question)
        graph.add_node("write_sql", self._write_sql)
        graph.add_node("validate_sql", self._validate_sql)
        graph.add_node("execute_sql", self._execute_sql)
        graph.add_node("answer", self._answer)

        graph.set_entry_point("rewrite")
        graph.add_edge("rewrite", "route")
        graph.add_edge("route", "write_sql")
        graph.add_edge("write_sql", "validate_sql")
        graph.add_edge("validate_sql", "execute_sql")
        graph.add_edge("execute_sql", "answer")
        graph.add_edge("answer", END)
        return graph.compile()

    def _rewrite_question(self, state: DataAgentState) -> dict[str, Any]:
        question = state["question"]
        history = state.get("history", [])
        if not history:
            return {"standalone_question": question}

        history_text = _format_history(history[-6:])
        messages = [
            SystemMessage(
                content=(
                    "Rewrite the user's latest data question into a standalone question. "
                    "Keep metrics, filters, time windows, and entities. Return only the rewritten question."
                )
            ),
            HumanMessage(content=f"Conversation:\n{history_text}\n\nLatest question: {question}"),
        ]
        try:
            rewritten = self.llm.invoke(messages).content.strip()
        except Exception:
            rewritten = question
        return {"standalone_question": rewritten or question}

    def _route_question(self, state: DataAgentState) -> dict[str, Any]:
        question = state.get("standalone_question") or state["question"]
        domain_descriptions = "\n".join(
            f"- {name}: {domain.description}" for name, domain in DOMAINS.items()
        )
        messages = [
            SystemMessage(
                content=(
                    "Choose the best data domain for a natural language analytics question. "
                    "Return exactly one domain name from the list."
                )
            ),
            HumanMessage(content=f"Domains:\n{domain_descriptions}\n\nQuestion: {question}"),
        ]
        try:
            raw_domain = self.llm.invoke(messages).content.strip().lower()
        except Exception:
            raw_domain = ""

        domain = _pick_domain(raw_domain) or _keyword_domain(question) or DEFAULT_DOMAIN
        return {"domain": domain}

    def _write_sql(self, state: DataAgentState) -> dict[str, Any]:
        question = state.get("standalone_question") or state["question"]
        domain = DOMAINS[state["domain"]]
        schema = self.dataset.schema_text(domain.tables)
        messages = [
            SystemMessage(
                content=(
                    "You write safe SQLite SELECT queries for a demo analytics database. "
                    "Return only SQL. Do not include markdown, comments, explanations, writes, or multiple statements. "
                    "Use SUM(quantity * unit_price) when the user asks for revenue."
                )
            ),
            HumanMessage(
                content=(
                    f"Domain: {domain.name}\n"
                    f"Allowed tables: {', '.join(domain.tables)}\n\n"
                    f"Schema:\n{schema}\n\n"
                    f"Question: {question}"
                )
            ),
        ]
        sql = self.llm.invoke(messages).content
        return {"sql": _extract_sql(sql)}

    def _validate_sql(self, state: DataAgentState) -> dict[str, Any]:
        domain = DOMAINS[state["domain"]]
        result = validate_select_sql(state.get("sql", ""), set(domain.tables))
        if not result.ok:
            return {"error": result.error, "validated_sql": ""}
        return {"validated_sql": result.sql, "error": None}

    def _execute_sql(self, state: DataAgentState) -> dict[str, Any]:
        if state.get("error"):
            return {"rows": [], "columns": [], "chart": None}

        try:
            result = self.dataset.execute(state["validated_sql"])
        except Exception as exc:
            return {"error": f"Query failed: {exc}", "rows": [], "columns": [], "chart": None}

        chart = suggest_chart(result.rows)
        return {"rows": result.rows, "columns": result.columns, "chart": chart}

    def _answer(self, state: DataAgentState) -> dict[str, Any]:
        question = state.get("standalone_question") or state["question"]
        if state.get("error"):
            return {
                "answer": (
                    "I could not run a safe query for that request. "
                    f"Reason: {state['error']}"
                )
            }

        row_count = len(state.get("rows", []))
        rows_json = json.dumps(state.get("rows", [])[:20], indent=2)
        messages = [
            SystemMessage(
                content=(
                    "You are a concise data analyst. Answer from the SQL result only. "
                    "Mention the SQL result size and call out if the result is empty. "
                    "Do not invent numbers."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {question}\n"
                    f"SQL: {state.get('validated_sql')}\n"
                    f"Rows returned: {row_count}\n"
                    f"Result JSON:\n{rows_json}"
                )
            ),
        ]
        try:
            answer = self.llm.invoke(messages).content.strip()
        except Exception:
            answer = _fallback_answer(row_count, state.get("rows", []))
        return {"answer": answer}


def _format_history(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"{role}: {content}" for role, content in history)


def _pick_domain(text: str) -> str | None:
    for domain in DOMAINS:
        if re.search(rf"\b{re.escape(domain)}\b", text, re.IGNORECASE):
            return domain
    return None


def _keyword_domain(question: str) -> str | None:
    lowered = question.lower()
    support_words = {"ticket", "tickets", "support", "priority", "resolution", "refund", "damaged"}
    sales_words = {"revenue", "sales", "orders", "products", "inventory", "channel", "region"}
    if any(word in lowered for word in support_words):
        return "support"
    if any(word in lowered for word in sales_words):
        return "sales"
    return None


def _extract_sql(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\b(with|select)\b", cleaned, re.IGNORECASE)
    if match:
        cleaned = cleaned[match.start() :]
    return cleaned.strip()


def _fallback_answer(row_count: int, rows: list[dict[str, Any]]) -> str:
    if row_count == 0:
        return "The query ran successfully but returned no rows."
    return f"The query returned {row_count} rows. First row: {rows[0]}"

