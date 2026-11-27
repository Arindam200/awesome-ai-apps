"""Records every event of a run with its timestamp, and prints a readable live view.

The same events.jsonl feeds the terminal, the benchmark and the video replay,
so the video only ever shows what really happened.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax

from config import cost_usd

STYLE = {
    "task": "bold white", "tool": "cyan", "ok": "green", "fail": "bold red", "retry": "yellow",
    "classify": "magenta", "delegate": "bold magenta", "repair": "bold yellow",
    "rejected": "red", "rollback": "red", "verified": "bold green", "recovered": "bold green",
    "refused": "red", "done": "bold white", "file": "dim cyan",
}


class Recorder:
    def __init__(self, path: Path | None = None, live: bool = True, console: Console | None = None,
                 on_event=None):
        self.t0 = time.perf_counter()
        self.on_event = on_event        # optional callback, e.g. to stream events to the web page
        self.events: list[dict] = []
        self.path = path
        self.live = live
        self.console = console or Console(highlight=False, soft_wrap=True)
        self._fh = path.open("w", encoding="utf-8") if path else None
        self._streaming_agent: str | None = None   # who is printing tokens right now

    def elapsed(self) -> float:
        return round(time.perf_counter() - self.t0, 3)

    def emit(self, type_: str, **data: Any) -> dict:
        event = {"t": self.elapsed(), "type": type_, **data}
        self.events.append(event)
        if self._fh:
            self._fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        if self.live:
            self._print(event)
        if self.on_event:
            self.on_event(event)
        return event

    def close(self):
        if self._fh:
            self._fh.close()

    # ------------------------------------------------------------------ live view
    def _end_stream(self):
        if self._streaming_agent is not None:
            self.console.print()
            self._streaming_agent = None

    def _line(self, t: float, kind: str, text: str, agent: str = "agent"):
        self._end_stream()
        who = "fixer" if agent == "tool-fixer" else "agent"
        style = STYLE.get(kind, "white")
        self.console.print(f"[dim]{t:6.1f}s {who:<5}[/dim] [{style}]{kind:<9}[/{style}] {escape(text)}")

    def _print(self, e: dict):
        k, t = e["type"], e["t"]
        if k == "token":
            if self._streaming_agent != e["agent"]:
                self._end_stream()
                who = "fixer" if e["agent"] == "tool-fixer" else "agent"
                self.console.print(f"[dim]{t:6.1f}s {who:<5}[/dim] [white]says[/white]      ", end="")
                self._streaming_agent = e["agent"]
            self.console.print(escape(e["text"]).replace("\n", " "), end="", style="italic")
        elif k == "llm_end":
            if self._streaming_agent:
                self._end_stream()
        elif k == "run_start":
            self.console.rule(f"[bold]{escape(e['scenario'])}[/bold]")
            self._line(t, "task", e["task"])
        elif k == "tool_call":
            self._line(t, "tool", f"{e['name']}({_short(e['args'])})", e["agent"])
        elif k == "tool_ok":
            self._line(t, "ok", _short(e["result"], 110), e["agent"])
        elif k == "tool_error":
            self._line(t, "fail", f"{e['name']}: {e['error']}", e["agent"])
            self._line(t, "classify", f"{e['kind']}: {e['explanation']}", e["agent"])
        elif k in ("tool_raise", "tool_error_msg"):
            self._line(t, "fail", f"{e['name']}: {e.get('error') or e.get('result')}", e["agent"])
        elif k == "other_tool":
            self._line(t, "tool", f"{e['name']}({e['args']})", e["agent"])
        elif k == "other_tool_result":
            self._line(t, "ok", e["result"], e["agent"])
        elif k == "retry":
            self._line(t, "retry", f"{e['name']}: HTTP 429, waiting {e['wait']}s "
                                   f"(retry {e['attempt']}/{e['max']}), code untouched")
        elif k == "file_read":
            self._line(t, "file", f"read {e['path']}", e["agent"])
        elif k == "delegate":
            self._line(t, "delegate", f"task -> tool-fixer: {e['description']}")
        elif k == "delegate_done":
            self._line(t, "delegate", f"tool-fixer finished: {e['summary']}")
        elif k == "repair":
            self._line(t, "repair", f"attempt {e['attempt']}/{e['max']} on tools/{e['tool']}.py: {e['reason']}",
                       "tool-fixer")
        elif k == "patch":
            self._end_stream()
            self.console.print(Panel(Syntax(e["diff"].rstrip(), "diff", theme="ansi_dark"),
                                     title=f"patch for tools/{e['tool']}.py", expand=False, border_style="yellow"))
        elif k in ("verified", "rollback", "rejected", "refused"):
            self._line(t, k, e["message"], "tool-fixer")
        elif k == "recovered":
            self._line(t, "recovered", f"{e['name']} works again -> {_short(e['result'], 90)}")
        elif k == "final":
            self._line(t, "done", "final answer:")
            self.console.print(Panel(escape(e["answer"].strip()), border_style="white", expand=False))
        elif k == "run_end":
            u = e["usage"]
            self.console.print(
                f"[dim]{u['llm_calls']} model calls | {u['input']:,} input tokens "
                f"({u['cached']:,} cached) | {u['output']:,} output | ${e['cost_usd']:.4f} | "
                f"{e['seconds']:.1f}s[/dim]")

    # ------------------------------------------------------------------ totals
    def usage(self) -> dict:
        ends = [e for e in self.events if e["type"] == "llm_end"]
        u = {"llm_calls": len(ends), "input": 0, "cached": 0, "output": 0, "reasoning": 0}
        for e in ends:
            for key in ("input", "cached", "output", "reasoning"):
                u[key] += e[key]
        return u

    def cost(self) -> float:
        u = self.usage()
        return round(cost_usd(u["input"], u["cached"], u["output"]), 6)


class ModelEvents(BaseCallbackHandler):
    """LangChain callback: streams tokens and records per-call timing and usage."""

    def __init__(self, rec: Recorder):
        self.rec = rec
        self.calls: dict[str, dict] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kw):
        agent = (metadata or {}).get("lc_agent_name") or "agent"
        self.calls[str(run_id)] = {"agent": agent, "start": self.rec.elapsed(), "first": None}

    def on_llm_new_token(self, token, *, run_id, chunk=None, **kw):
        call = self.calls.get(str(run_id))
        if call is None or not token:
            return
        if call["first"] is None:
            call["first"] = self.rec.elapsed()
        self.rec.emit("token", agent=call["agent"], text=token)

    def on_llm_end(self, response, *, run_id, **kw):
        call = self.calls.pop(str(run_id), None)
        if call is None:
            return
        usage = {}
        for gens in response.generations:
            for g in gens:
                msg = getattr(g, "message", None)
                if msg is not None and getattr(msg, "usage_metadata", None):
                    usage = msg.usage_metadata
        end = self.rec.elapsed()
        details_in = usage.get("input_token_details") or {}
        details_out = usage.get("output_token_details") or {}
        self.rec.emit("llm_end", agent=call["agent"],
                      seconds=round(end - call["start"], 3),
                      ttft=round((call["first"] or end) - call["start"], 3),
                      input=usage.get("input_tokens", 0), cached=details_in.get("cache_read", 0) or 0,
                      output=usage.get("output_tokens", 0), reasoning=details_out.get("reasoning", 0) or 0)


def _short(obj, n: int = 80) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 3] + "..."
