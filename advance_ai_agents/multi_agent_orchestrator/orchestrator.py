"""Multi-agent orchestrator on LangGraph: one expensive orchestrator, many cheap parallel workers.

    START -> plan        (Kimi K3.1 Pro splits the goal into independent subtasks)
          -> worker x N  (Inkling 2 Small or a cheaper model, all in parallel via Send)
          -> review      (Kimi K3.1 Pro accepts each output or sends it back with feedback)
               -- revise --> worker (only the weak tasks; a "fast" task escalates to the standard worker)
               -- accept --> synthesize (Kimi K3.1 Pro writes the final deliverable) -> END

The orchestrator never does the legwork. It spends its tokens on the three
steps where judgment matters, so most of the tokens are billed at worker prices.
"""

from __future__ import annotations

import operator
import re
import time
from typing import Annotated, Iterator, Literal, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

import prompts
from models import (
    FAST_WORKER_MODEL,
    ORCHESTRATOR_REASONING,
    WORKER_MODEL,
    WORKER_REASONING,
    chat,
    cost_usd,
    resolve_orchestrator,
)
from tools import TOOLS, TOOLS_BY_NAME

MAX_TOOL_ROUNDS = 4  # model turns per worker that may call tools before it must answer


# ---------------------------------------------------------------- schemas


class Subtask(BaseModel):
    id: str = Field(description="Short unique kebab-case id, e.g. 'pricing-compare'")
    title: str = Field(description="A few words naming the subtask")
    brief: str = Field(description="Self-contained instructions: what to produce, scope, format and length")
    tier: Literal["fast", "standard"] = Field(description="fast for lookups and summaries, standard for analysis")


class TaskPlan(BaseModel):
    approach: str = Field(description="One or two sentences on how the work is split")
    tasks: list[Subtask]
    final_format: str = Field(description="Sections, length and tone of the final deliverable")


class Verdict(BaseModel):
    task_id: str
    decision: Literal["accept", "revise"]
    feedback: str = Field(default="", description="What to add, fix or remove. Empty when accepted.")


class Review(BaseModel):
    summary: str = Field(description="One or two sentences on the overall quality of the work")
    verdicts: list[Verdict]


# ---------------------------------------------------------------- state


class Settings(TypedDict):
    orchestrator: str
    worker: str  # "standard" tier, and every revision
    fast_worker: str  # "fast" tier, first attempt only
    max_tasks: int
    max_revisions: int  # review rounds that may send work back
    tools: bool


def _merge(left: dict | None, right: dict | None) -> dict:
    """Results are keyed by task id, so a revision replaces the earlier attempt."""
    return {**(left or {}), **(right or {})}


class OrchestratorState(TypedDict, total=False):
    goal: str
    settings: Settings
    plan: dict
    results: Annotated[dict, _merge]
    reviews: Annotated[list, operator.add]
    revisions: list
    review_round: int
    final: str
    ledger: Annotated[list, operator.add]  # one record per model call


class WorkerInput(TypedDict):
    goal: str
    task: dict
    model: str
    attempt: int
    escalated: bool
    feedback: str
    previous: str
    tools: bool


def make_settings(
    orchestrator: str | None = None,
    worker: str = WORKER_MODEL,
    fast_worker: str = FAST_WORKER_MODEL,
    max_tasks: int = 5,
    max_revisions: int = 1,
    tools: bool = True,
) -> Settings:
    return {
        "orchestrator": orchestrator or resolve_orchestrator(),
        "worker": worker,
        "fast_worker": fast_worker,
        "max_tasks": max(1, min(max_tasks, 8)),
        "max_revisions": max(0, max_revisions),
        "tools": tools,
    }


# ---------------------------------------------------------------- helpers


def _text(msg: BaseMessage | None) -> str:
    if msg is None:
        return ""
    content = msg.content
    if isinstance(content, list):
        content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    # Some open models inline their reasoning; the answer is what follows it.
    return re.sub(r"(?s)<think>.*?</think>", "", content or "").strip()


def _usage(role: str, model: str, msg: BaseMessage | None, seconds: float, task_id: str | None = None) -> dict:
    u = getattr(msg, "usage_metadata", None) or {}
    tokens_in, tokens_out = u.get("input_tokens", 0), u.get("output_tokens", 0)
    return {
        "role": role,
        "model": model,
        "task_id": task_id,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "reasoning_tokens": (u.get("output_token_details") or {}).get("reasoning", 0),
        "seconds": round(seconds, 2),
        "cost": cost_usd(model, tokens_in, tokens_out),
    }


def _structured(model: str, schema: type[BaseModel], system: str, user: str, role: str):
    """Structured output through tool calling (Kimi supports tools but not JSON mode). One retry."""
    llm = chat(model, temperature=0.2, max_tokens=16000, reasoning_effort=ORCHESTRATOR_REASONING)
    llm = llm.with_structured_output(schema, method="function_calling", include_raw=True)
    ledger, error = [], None
    for _ in range(2):
        started = time.time()
        out = llm.invoke([SystemMessage(system), HumanMessage(user)])
        raw = out["raw"]
        ledger.append(_usage(role, model, raw, time.time() - started))
        if out["parsed"] is not None:
            return out["parsed"], ledger
        finish = raw.response_metadata.get("finish_reason")
        error = out["parsing_error"] or f"finish_reason={finish}, reply={_text(raw)[:300]!r}"
    raise RuntimeError(f"{role}: the orchestrator didn't return a valid {schema.__name__}: {error}")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "task"


def _clean_tasks(tasks: list[Subtask], limit: int) -> list[dict]:
    seen, out = set(), []
    for t in tasks[:limit]:
        tid = _slug(t.id or t.title)
        while tid in seen:
            tid += "-2"
        seen.add(tid)
        out.append({**t.model_dump(), "id": tid})
    return out


def _worker_input(
    state: OrchestratorState, task: dict, feedback: str = "", previous: str = "", attempt: int = 1
) -> WorkerInput:
    s = state["settings"]
    # Fast tasks start on the cheapest model. Anything sent back goes to the standard worker.
    fast_first_try = task["tier"] == "fast" and attempt == 1
    model = s["fast_worker"] if fast_first_try else s["worker"]
    return {
        "goal": state["goal"],
        "task": task,
        "model": model,
        "attempt": attempt,
        "escalated": task["tier"] == "fast" and attempt > 1 and s["worker"] != s["fast_worker"],
        "feedback": feedback,
        "previous": previous,
        "tools": s["tools"],
    }


def _outputs_for_review(tasks: list[dict], results: dict) -> str:
    blocks = []
    for t in tasks:
        r = results.get(t["id"], {})
        blocks.append(
            f"### Task {t['id']}: {t['title']}\n"
            f"Brief: {t['brief']}\n"
            f"Status: {r.get('status', 'missing')}\n"
            f"Output:\n{r.get('output') or '(no output)'}"
        )
    return "\n\n---\n\n".join(blocks)


def _outputs_for_synthesis(tasks: list[dict], results: dict) -> str:
    blocks = []
    for t in tasks:
        r = results.get(t["id"], {})
        body = r.get("output") if r.get("status") == "done" else "(this part failed; cover it briefly yourself)"
        blocks.append(f"### {t['title']}\n{body}")
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------- nodes


def plan(state: OrchestratorState) -> dict:
    s = state["settings"]
    get_stream_writer()({"event": "planning", "model": s["orchestrator"]})
    system = prompts.PLAN_SYSTEM.format(
        max_tasks=s["max_tasks"],
        tools_note=prompts.TOOLS_ON if s["tools"] else prompts.TOOLS_OFF,
    )
    parsed, ledger = _structured(s["orchestrator"], TaskPlan, system, state["goal"], "plan")
    return {
        "plan": {
            "approach": parsed.approach,
            "final_format": parsed.final_format,
            "tasks": _clean_tasks(parsed.tasks, s["max_tasks"]),
        },
        "review_round": 0,
        "ledger": ledger,
    }


def dispatch(state: OrchestratorState):
    tasks = state["plan"]["tasks"]
    if not tasks:
        return "synthesize"
    return [Send("worker", _worker_input(state, t)) for t in tasks]


def worker(inp: WorkerInput) -> dict:
    write = get_stream_writer()
    task, model = inp["task"], inp["model"]
    tid = task["id"]
    write({"event": "worker_start", "task_id": tid, "model": model, "attempt": inp["attempt"]})

    started, ledger = time.time(), []
    try:
        output, tool_calls = _run_worker(inp, ledger, write)
        status = "done" if output else "empty"
    except Exception as e:  # one failed worker shouldn't sink the run; review will retry it
        output, tool_calls, status = f"Worker error: {type(e).__name__}: {e}", 0, "error"

    result = {
        "task_id": tid,
        "title": task["title"],
        "tier": task["tier"],
        "model": model,
        "attempt": inp["attempt"],
        "escalated": inp["escalated"],
        "status": status,
        "output": output,
        "tool_calls": tool_calls,
        "seconds": round(time.time() - started, 1),
        "cost": sum(r["cost"] for r in ledger),
    }
    return {"results": {tid: result}, "ledger": ledger}


def _run_worker(inp: WorkerInput, ledger: list, write) -> tuple[str, int]:
    task, model = inp["task"], inp["model"]
    llm = chat(model, temperature=0.4, max_tokens=12000, reasoning_effort=WORKER_REASONING)
    user = prompts.WORKER_TASK.format(goal=inp["goal"], title=task["title"], brief=task["brief"])
    if inp["feedback"]:
        user += prompts.WORKER_REVISION.format(feedback=inp["feedback"], previous=inp["previous"] or "(empty)")
    system = prompts.WORKER_SYSTEM.format(
        tools_note=prompts.WORKER_TOOLS_ON if inp["tools"] else prompts.WORKER_TOOLS_OFF
    )
    messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(user)]
    runnable = llm.bind_tools(TOOLS) if inp["tools"] else llm

    tool_calls, ai = 0, None
    for step in range(MAX_TOOL_ROUNDS + 1):
        if inp["tools"] and step == MAX_TOOL_ROUNDS:
            # Out of tool budget: keep the tool schema (the history has tool calls) but forbid using it.
            runnable = llm.bind_tools(TOOLS, tool_choice="none")
            messages.append(HumanMessage("You've used your tool budget. Write your final answer now."))
        started = time.time()
        ai = runnable.invoke(messages)
        ledger.append(_usage("worker", model, ai, time.time() - started, task["id"]))
        messages.append(ai)
        if not getattr(ai, "tool_calls", None):
            break
        for call in ai.tool_calls:
            tool_calls += 1
            write({"event": "tool_call", "task_id": task["id"], "tool": call["name"], "args": call["args"]})
            tool = TOOLS_BY_NAME.get(call["name"])
            try:
                result = tool.invoke(call["args"]) if tool else f"Unknown tool: {call['name']}"
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    text = _text(ai)
    if not text and not getattr(ai, "tool_calls", None):
        # A reasoning model can spend its whole budget thinking and return nothing. Retry once, briefly.
        messages.pop()
        retry = chat(model, temperature=0.4, max_tokens=12000, reasoning_effort="low")
        if inp["tools"]:
            retry = retry.bind_tools(TOOLS, tool_choice="none")
        started = time.time()
        ai = retry.invoke(messages + [HumanMessage("Write your answer now. Keep your reasoning short.")])
        ledger.append(_usage("worker", model, ai, time.time() - started, task["id"]))
        text = _text(ai)
    return text, tool_calls


def review(state: OrchestratorState) -> dict:
    s = state["settings"]
    round_no = state.get("review_round", 0)
    if round_no >= s["max_revisions"]:
        return {"revisions": []}  # no revision budget left, nothing to act on

    get_stream_writer()({"event": "reviewing", "round": round_no + 1, "model": s["orchestrator"]})
    tasks, results = state["plan"]["tasks"], state["results"]
    user = prompts.REVIEW_TASK.format(
        goal=state["goal"],
        approach=state["plan"]["approach"],
        outputs=_outputs_for_review(tasks, results),
    )
    parsed, ledger = _structured(s["orchestrator"], Review, prompts.REVIEW_SYSTEM, user, "review")

    known = {t["id"] for t in tasks}
    revisions = {
        v.task_id: v.feedback or "Rework this so it fully meets the brief."
        for v in parsed.verdicts
        if v.decision == "revise" and v.task_id in known
    }
    for tid, r in results.items():  # failed or empty work always goes back, whatever the verdict
        if r["status"] != "done":
            revisions.setdefault(tid, "Your previous attempt failed or came back empty. Complete the brief.")

    return {
        "reviews": [
            {"round": round_no + 1, "summary": parsed.summary, "verdicts": [v.model_dump() for v in parsed.verdicts]}
        ],
        "revisions": [{"task_id": k, "feedback": v} for k, v in revisions.items()],
        "review_round": round_no + 1,
        "ledger": ledger,
    }


def after_review(state: OrchestratorState):
    revisions = state.get("revisions") or []
    if not revisions:
        return "synthesize"
    by_id = {t["id"]: t for t in state["plan"]["tasks"]}
    sends = []
    for rev in revisions:
        prev = state["results"][rev["task_id"]]
        sends.append(
            Send(
                "worker",
                _worker_input(state, by_id[rev["task_id"]], rev["feedback"], prev["output"], prev["attempt"] + 1),
            )
        )
    return sends


def synthesize(state: OrchestratorState) -> dict:
    s = state["settings"]
    model = s["orchestrator"]
    write = get_stream_writer()
    write({"event": "synthesizing", "model": model})
    user = prompts.SYNTH_TASK.format(
        goal=state["goal"],
        final_format=state["plan"]["final_format"],
        outputs=_outputs_for_synthesis(state["plan"]["tasks"], state.get("results", {})),
    )
    llm = chat(model, temperature=0.4, max_tokens=16000, reasoning_effort=ORCHESTRATOR_REASONING)
    started, full = time.time(), None
    for chunk in llm.stream([SystemMessage(prompts.SYNTH_SYSTEM), HumanMessage(user)]):
        full = chunk if full is None else full + chunk
        delta = _text(chunk)
        if delta:
            write({"event": "final_delta", "text": delta})
    return {"final": _text(full), "ledger": [_usage("synthesize", model, full, time.time() - started)]}


# ---------------------------------------------------------------- graph


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("plan", plan)
    g.add_node("worker", worker)
    g.add_node("review", review)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", dispatch, ["worker", "synthesize"])
    g.add_edge("worker", "review")  # runs once, after every parallel worker has finished
    g.add_conditional_edges("review", after_review, ["worker", "synthesize"])
    g.add_edge("synthesize", END)
    return g.compile()


GRAPH = build_graph()


def run(goal: str, settings: Settings, max_concurrency: int = 8) -> Iterator[dict]:
    """Run the graph and yield flat events for a UI. The last event is {"event": "done", "state": ...}."""
    state: dict = {}
    config = {"max_concurrency": max_concurrency, "recursion_limit": 50}
    stream = GRAPH.stream({"goal": goal, "settings": settings}, config, stream_mode=["custom", "updates", "values"])
    for mode, data in stream:
        if mode == "custom":
            yield data
        elif mode == "values":
            state = data
        else:
            for node, update in data.items():
                if not update:
                    continue
                if node == "plan":
                    yield {"event": "plan", "plan": update["plan"]}
                elif node == "worker":
                    for result in update["results"].values():
                        yield {"event": "worker_done", "result": result}
                elif node == "review" and update.get("reviews"):
                    yield {"event": "review", "review": update["reviews"][-1], "revisions": update["revisions"]}
                elif node == "synthesize":
                    yield {"event": "final", "text": update["final"]}
                if update.get("ledger"):
                    yield {"event": "usage", "records": update["ledger"]}
    yield {"event": "done", "state": state}


def cost_summary(ledger: list[dict], orchestrator: str) -> dict:
    """What the run cost, and what the worker tokens would have cost on the orchestrator."""
    by_model: dict[str, dict] = {}
    for r in ledger:
        m = by_model.setdefault(r["model"], {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        m["calls"] += 1
        m["input_tokens"] += r["input_tokens"]
        m["output_tokens"] += r["output_tokens"]
        m["cost"] += r["cost"]
    worker_recs = [r for r in ledger if r["role"] == "worker"]
    total = sum(r["cost"] for r in ledger)
    worker_cost = sum(r["cost"] for r in worker_recs)
    worker_on_orch = sum(cost_usd(orchestrator, r["input_tokens"], r["output_tokens"]) for r in worker_recs)
    all_orch = total - worker_cost + worker_on_orch
    return {
        "total": total,
        "orchestrator_cost": total - worker_cost,
        "worker_cost": worker_cost,
        "all_orchestrator_total": all_orch,
        "savings_pct": (1 - total / all_orch) * 100 if all_orch else 0.0,
        "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in ledger),
        "worker_token_share": (
            sum(r["input_tokens"] + r["output_tokens"] for r in worker_recs)
            / max(1, sum(r["input_tokens"] + r["output_tokens"] for r in ledger))
            * 100
        ),
        "by_model": by_model,
    }
