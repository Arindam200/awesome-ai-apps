"""The baseline: a default Deep Agent with the same model, tools and task, and no healing layer.

No failure sorting, no output contracts, no failure report, no tool-fixer, no repair_tool,
and Deep Agents' default harness profile. An observer middleware records tool calls for
the log and changes nothing: errors still go wherever Deep Agents sends them.

Import this module in its own process. healing.agent registers a harness profile for the
"openai" provider, and that must not leak into the baseline."""
from __future__ import annotations

import json

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import StructuredTool

from config import make_model
from healing.healer import _LOAD_LOCK, _content, _plain, _trim
from healing.recorder import Recorder
from tools import TOOLS, load_tool

PLAIN_PROMPT = """You build monthly LLM cost reports from a provider's billing API.

For a report: fetch_usage(month) -> summarize_usage(path) -> fetch_pricing for every model in
the summary -> export_report with one row per model (its usage totals plus its three prices).
Then answer in 2-4 short lines: total cost, the most expensive model, and the CSV path.
Use only numbers that tools returned. Never invent results."""


class Observer(AgentMiddleware):
    """Records tool calls and their outcome. Re-raises errors unchanged."""

    def __init__(self, rec: Recorder):
        super().__init__()
        self.rec = rec

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        name, args = call["name"], _plain(call.get("args", {}))
        if name not in TOOLS:
            self.rec.emit("other_tool", agent="agent", name=name, args=_trim(json.dumps(args), 200))
            out = handler(request)
            self.rec.emit("other_tool_result", agent="agent", name=name, result=_trim(_content(out), 300))
            return out
        self.rec.emit("tool_call", agent="agent", name=name, args=args)
        try:
            out = handler(request)
        except Exception as exc:
            self.rec.emit("tool_raise", agent="agent", name=name, error=_trim(f"{type(exc).__name__}: {exc}", 240))
            raise
        status = getattr(out, "status", "success")
        kind = "tool_ok" if status != "error" else "tool_error_msg"
        self.rec.emit(kind, agent="agent", name=name, result=_trim(_content(out), 300))
        return out


def plain_tools() -> list[StructuredTool]:
    def make(name: str):
        def run(**kwargs):
            with _LOAD_LOCK:                 # same safe reload as the healing agent
                func = load_tool(name)
            return json.dumps(func(**_plain(kwargs)))
        return StructuredTool.from_function(func=run, name=name, description=TOOLS[name]["description"],
                                            args_schema=TOOLS[name]["args"])
    return [make(n) for n in TOOLS]


def build_plain_agent(rec: Recorder):
    return create_deep_agent(model=make_model(), tools=plain_tools(), system_prompt=PLAIN_PROMPT,
                             middleware=[Observer(rec)], name="agent")
