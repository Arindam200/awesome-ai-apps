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


class IncidentPlan(BaseModel):
    incident_id: str
    severity: str
    likely_cause: str
    confidence: str
    customer_impact: str
    immediate_actions: list[str]
    validation_steps: list[str]
    rollback_or_mitigation: str
    comms_update: str
    owners_to_page: list[str]
    audit_trail: list[str]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


@tool
def search_logs(service: str, query: str = "") -> str:
    """Search recent service logs. Use this before deciding cause or mitigation."""
    rows = []
    for line in (DATA / "logs.jsonl").read_text().splitlines():
        item = json.loads(line)
        if item["service"] == service and (not query or query.lower() in item["message"].lower()):
            rows.append(item)
    return json.dumps(rows[-12:], indent=2)


@tool
def lookup_runbook(service: str) -> str:
    """Return the incident runbook for a service."""
    runbooks = read_json(DATA / "runbooks.json")
    matches = [item for item in runbooks if item["service"] == service]
    return json.dumps(matches, indent=2)


@tool
def lookup_recent_deploys(service: str) -> str:
    """Return recent deploys and feature changes for a service."""
    deploys = read_json(DATA / "deploys.json")
    matches = [item for item in deploys if item["service"] == service]
    return json.dumps(matches, indent=2)


@tool
def draft_status_update(summary: str, action: str, eta: str) -> str:
    """Draft a customer/internal status update. Does not send anything."""
    return f"Status draft: {summary} Current action: {action} Next update: {eta}."


TOOLS = [search_logs, lookup_runbook, lookup_recent_deploys, draft_status_update]

SYSTEM = """You are an incident commander agent for production systems.
Use tools to gather evidence before recommending action. Prefer reversible mitigation.
Do not claim an action was executed. Return compact JSON only with this schema:
{
  "incident_id": "...",
  "severity": "sev1|sev2|sev3",
  "likely_cause": "...",
  "confidence": "low|medium|high",
  "customer_impact": "...",
  "immediate_actions": ["..."],
  "validation_steps": ["..."],
  "rollback_or_mitigation": "...",
  "comms_update": "...",
  "owners_to_page": ["..."],
  "audit_trail": ["which tools/evidence were used"]
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
        max_tokens=2400,
    ).bind_tools(TOOLS)


def run_agent(alert: dict[str, Any]) -> IncidentPlan:
    llm = build_llm()
    tool_map = {item.name: item for item in TOOLS}
    messages: list[Any] = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Investigate this alert and produce an incident plan:\n{json.dumps(alert)}"),
    ]
    audit = []
    for _ in range(6):
        response = llm.invoke(messages)
        messages.append(response)
        if not isinstance(response, AIMessage) or not response.tool_calls:
            content = response.content if isinstance(response.content, str) else json.dumps(response.content)
            if not content.strip():
                messages.append(HumanMessage(content="Return the final incident plan as the requested JSON object now."))
                continue
            plan = IncidentPlan.model_validate_json(extract_json(content))
            plan.audit_trail = plan.audit_trail + audit
            return plan
        for call in response.tool_calls:
            tool_name = call["name"]
            if tool_name not in tool_map:
                allowed = ", ".join(tool_map)
                messages.append(
                    ToolMessage(
                        content=f"Unknown tool '{tool_name}'. Choose only one of these tools: {allowed}.",
                        tool_call_id=call["id"],
                    )
                )
                continue
            output = tool_map[tool_name].invoke(call["args"])
            audit.append(f"{tool_name}({call['args']})")
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
    parser = argparse.ArgumentParser(description="Nebius + LangChain incident response agent.")
    parser.add_argument("--alert", type=Path, default=DATA / "alert.json")
    args = parser.parse_args()
    plan = run_agent(read_json(args.alert))
    print(plan.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
