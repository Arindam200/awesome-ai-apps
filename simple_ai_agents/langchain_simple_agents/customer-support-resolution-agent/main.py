from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


ROOT = Path(__file__).parent
DATA = ROOT / "data"


class SupportResolution(BaseModel):
    ticket_id: str
    priority: str
    category: str
    customer_sentiment: str
    facts_found: list[str]
    recommended_actions: list[str]
    approval_required: bool
    approval_reason: str
    customer_reply: str
    internal_note: str
    audit_trail: list[str] = Field(default_factory=list)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


@tool
def search_knowledge_base(query: str) -> str:
    """Search support knowledge base articles."""
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    articles = read_json(DATA / "kb.json")
    scored = []
    for article in articles:
        text = f"{article['title']} {article['text']}".lower()
        score = sum(1 for term in query_terms if term in text)
        if score:
            scored.append((score, article))
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    return json.dumps([item for _, item in ranked[:5]], indent=2)


@tool
def lookup_order(order_id: str) -> str:
    """Look up order state, inventory, shipping, and payment events."""
    orders = read_json(DATA / "orders.json")
    matches = [item for item in orders if item["order_id"].lower() == order_id.lower()]
    return json.dumps(matches, indent=2)


@tool
def draft_refund_or_replacement(action: str, order_id: str, reason: str) -> str:
    """Draft a refund/replacement recommendation. This does not execute the action."""
    return json.dumps(
        {
            "action": action,
            "order_id": order_id,
            "reason": reason,
            "execution_status": "draft_only_requires_human_or_workflow_approval",
        }
    )


TOOLS = [search_knowledge_base, lookup_order, draft_refund_or_replacement]

SYSTEM = """You are a production customer support resolution agent.
Use tools before deciding. Never claim a refund, replacement, or shipment was executed.
The customer_reply must not say "I escalated", "I processed", "you will receive",
or promise a tracking/refund time unless a tool confirms execution. Use wording like
"I recommend", "I can request", or "our team should" for draft-only actions.
Return compact JSON only:
{
  "ticket_id": "...",
  "priority": "low|normal|high|urgent",
  "category": "...",
  "customer_sentiment": "...",
  "facts_found": ["..."],
  "recommended_actions": ["..."],
  "approval_required": true,
  "approval_reason": "...",
  "customer_reply": "empathetic reply ready to send",
  "internal_note": "concise note for CRM",
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
        temperature=0.2,
        max_tokens=2400,
    ).bind_tools(TOOLS)


def run_agent(ticket: dict[str, Any]) -> SupportResolution:
    llm = build_llm()
    tools = {item.name: item for item in TOOLS}
    messages: list[Any] = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Resolve this support ticket:\n{json.dumps(ticket)}"),
    ]
    audit = []
    for _ in range(6):
        response = llm.invoke(messages)
        messages.append(response)
        if not isinstance(response, AIMessage) or not response.tool_calls:
            content = response.content if isinstance(response.content, str) else json.dumps(response.content)
            if not content.strip():
                messages.append(HumanMessage(content="Return the final support resolution as the requested JSON object now."))
                continue
            result = SupportResolution.model_validate_json(extract_json(content))
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
    parser = argparse.ArgumentParser(description="Nebius + LangChain support resolution agent.")
    parser.add_argument("--ticket", type=Path, default=DATA / "ticket.json")
    args = parser.parse_args()
    print(run_agent(read_json(args.ticket)).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
