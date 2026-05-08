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


class RiskItem(BaseModel):
    control_id: str
    severity: str
    finding: str
    evidence: str
    remediation: str


class VendorRiskReview(BaseModel):
    vendor: str
    decision: str
    summary: str
    risks: list[RiskItem]
    required_approvals: list[str]
    contract_redlines: list[str]
    go_live_conditions: list[str]
    audit_trail: list[str] = Field(default_factory=list)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


@tool
def search_policy_controls(query: str) -> str:
    """Search internal security/privacy control requirements."""
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    controls = read_json(DATA / "policy_controls.json")
    scored = []
    for control in controls:
        text = f"{control['id']} {control['title']} {control['requirement']}".lower()
        score = sum(1 for term in terms if term in text)
        if score:
            scored.append((score, control))
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    return json.dumps([item for _, item in ranked], indent=2)


@tool
def read_contract_excerpt() -> str:
    """Read the available vendor contract excerpt."""
    return (DATA / "contract_excerpt.txt").read_text()


@tool
def check_data_residency(hosting_region: str, data_types: list[str]) -> str:
    """Check simple regional transfer concern based on hosting and data sensitivity."""
    personal = {"email", "ip_address", "user_id"}.intersection(set(data_types))
    if hosting_region.lower() == "us only" and personal:
        return "Regional risk: US-only hosting with personal data requires transfer review for EU customers."
    return "No regional transfer issue found in this simple check."


TOOLS = [search_policy_controls, read_contract_excerpt, check_data_residency]

SYSTEM = """You are a vendor risk and compliance review agent.
Use tools for policy and contract evidence. Do not approve vendors unconditionally.
Return compact JSON only:
{
  "vendor": "...",
  "decision": "approve|approve_with_conditions|reject|needs_review",
  "summary": "...",
  "risks": [{"control_id":"...","severity":"low|medium|high","finding":"...","evidence":"...","remediation":"..."}],
  "required_approvals": ["..."],
  "contract_redlines": ["..."],
  "go_live_conditions": ["..."],
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


def run_agent(questionnaire: dict[str, Any]) -> VendorRiskReview:
    llm = build_llm()
    tools = {item.name: item for item in TOOLS}
    messages: list[Any] = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Review this vendor for production data use:\n{json.dumps(questionnaire)}"),
    ]
    audit = []
    for _ in range(7):
        response = llm.invoke(messages)
        messages.append(response)
        if not isinstance(response, AIMessage) or not response.tool_calls:
            content = response.content if isinstance(response.content, str) else json.dumps(response.content)
            if not content.strip():
                messages.append(HumanMessage(content="Return the final vendor risk review as the requested JSON object now."))
                continue
            result = VendorRiskReview.model_validate_json(extract_json(content))
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
    parser = argparse.ArgumentParser(description="Nebius + LangChain vendor risk agent.")
    parser.add_argument("--questionnaire", type=Path, default=DATA / "vendor_questionnaire.json")
    args = parser.parse_args()
    print(run_agent(read_json(args.questionnaire)).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
