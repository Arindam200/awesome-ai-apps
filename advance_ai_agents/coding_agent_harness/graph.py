"""Coding Agent Harness — LangGraph workflow with human-gated file edits.

Flow:
    START -> planner -> explorer -> coder
        -> (diffs proposed?) -> diff_review [interrupt] -> apply_diffs -> tester
        -> (no diffs)        -> tester
    tester -> (tests pass or max iterations) -> END
           -> (otherwise) -> coder

The diff_review node pauses the graph with LangGraph's `interrupt()` and
hands the pending change queue to the caller (CLI or Streamlit). The caller
resumes with `Command(resume={"decisions": {...}})` carrying per-diff
approve/reject decisions. Only approved diffs ever touch the disk.
"""
from __future__ import annotations

import operator
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_nebius import ChatNebius
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from sandbox import run_pytest_in_sandbox
from tools import (
    WORKSPACE_ROOT,
    build_file_diff,
    list_dir,
    list_workspace_tree,
    propose_edit,
    read_file,
)

load_dotenv()

DEFAULT_MODEL = os.getenv("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B")
DEFAULT_MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "4"))

MAX_TOOL_ROUNDS = 8


class AgentState(TypedDict, total=False):
    objective: str
    plan: str
    workspace_context: str
    pending_diffs: list[dict]  # proposed file changes awaiting human review
    diffs_to_apply: list[dict]  # approved diffs, consumed by apply_diffs
    applied_diffs: Annotated[list[dict], operator.add]
    review_feedback: str  # rejection reasons, fed back to the coder
    test_results: Annotated[list[dict], operator.add]
    last_test_passed: bool
    iteration: int
    max_iterations: int
    status: str  # running | awaiting_review | done | failed


def _llm(temperature: float = 0.2) -> ChatNebius:
    return ChatNebius(
        model=DEFAULT_MODEL,
        api_key=os.environ["NEBIUS_API_KEY"],
        temperature=temperature,
    )


def _run_tool_loop(llm_with_tools, messages: list, handlers: dict) -> str:
    """Minimal tool-calling loop; returns the model's final text answer."""
    for _ in range(MAX_TOOL_ROUNDS):
        ai: AIMessage = llm_with_tools.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            return ai.content if isinstance(ai.content, str) else str(ai.content)
        for call in ai.tool_calls:
            handler = handlers.get(call["name"])
            try:
                content = (
                    handler(call["args"])
                    if handler
                    else f"ERROR: unknown tool {call['name']!r}"
                )
            except Exception as exc:
                content = f"ERROR: {exc}"
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
    messages.append(
        HumanMessage(content="Stop using tools and give your final answer now.")
    )
    final: AIMessage = llm_with_tools.invoke(messages)
    return final.content if isinstance(final.content, str) else str(final.content)


# --- Nodes -------------------------------------------------------------------

PLANNER_PROMPT = """You are the planning lead of a small coding team.
Given an objective and the workspace file layout, write a short numbered
plan (3-6 steps) for how the team should approach it: what to inspect,
what to change, and how to verify. Be concrete; name real files. Output
only the plan."""


def planner_node(state: AgentState) -> dict:
    response = _llm().invoke(
        [
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(
                content=(
                    f"Objective: {state['objective']}\n\n"
                    f"Workspace layout:\n{list_workspace_tree()}"
                )
            ),
        ]
    )
    return {
        "plan": response.content,
        "status": "running",
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", DEFAULT_MAX_ITERATIONS),
    }


EXPLORER_PROMPT = """You are the codebase explorer of a small coding team.
Use list_dir and read_file to inspect the workspace. Never guess at file
contents — read them. When you have seen everything relevant to the
objective, produce a briefing for the coder: for each relevant file, its
path, its role, and the exact functions/lines that matter, including any
suspected bugs. Do not propose code yet."""


def explorer_node(state: AgentState) -> dict:
    llm = _llm().bind_tools([list_dir, read_file])
    handlers = {
        "list_dir": lambda args: list_dir.invoke(args),
        "read_file": lambda args: read_file.invoke(args),
    }
    briefing = _run_tool_loop(
        llm,
        [
            SystemMessage(content=EXPLORER_PROMPT),
            HumanMessage(
                content=f"Objective: {state['objective']}\n\nPlan:\n{state.get('plan', '')}"
            ),
        ],
        handlers,
    )
    return {"workspace_context": briefing}


CODER_PROMPT = """You are the software engineer of a small coding team.
You cannot write to disk directly. Instead, call propose_edit with the
COMPLETE new content of each file you want to change; a human reviews
each proposed diff before it is applied. Keep every change minimal and
scoped to the objective. Never edit test files unless the objective says
to. Use read_file if you need to re-check current content. When you have
proposed all needed edits, stop calling tools and summarize what you
proposed and why in 2-3 sentences."""


def coder_node(state: AgentState) -> dict:
    iteration = state.get("iteration", 0)
    collected: list[dict] = []

    def handle_propose(args: dict) -> str:
        diff = build_file_diff(
            file_path=args["file_path"],
            new_content=args["new_content"],
            rationale=args.get("rationale", ""),
            iteration=iteration,
        )
        collected.append(diff)
        return f"Diff {diff['diff_id']} for {diff['file_path']} queued for human review."

    llm = _llm().bind_tools([read_file, propose_edit])
    handlers = {
        "read_file": lambda args: read_file.invoke(args),
        "propose_edit": handle_propose,
    }

    briefing = [
        f"Objective: {state['objective']}",
        f"Plan:\n{state.get('plan', '')}",
        f"Explorer briefing:\n{state.get('workspace_context', '')}",
    ]
    if state.get("applied_diffs"):
        applied = ", ".join(
            f"{d['file_path']} (diff {d['diff_id']})" for d in state["applied_diffs"]
        )
        briefing.append(f"Already applied in earlier rounds: {applied}")
    if state.get("test_results"):
        last = state["test_results"][-1]
        briefing.append(
            f"Latest test run ({last['summary']}):\n{last['stdout']}"
        )
    if state.get("review_feedback"):
        briefing.append(
            "The human reviewer REJECTED some of your previous diffs. Address "
            f"this feedback in your revised proposals:\n{state['review_feedback']}"
        )

    _run_tool_loop(
        llm,
        [SystemMessage(content=CODER_PROMPT), HumanMessage(content="\n\n".join(briefing))],
        handlers,
    )
    return {"pending_diffs": collected, "review_feedback": ""}


def diff_review_node(state: AgentState) -> dict:
    """Human-in-the-loop gate. One interrupt() per invocation, no side effects
    before it — the node re-runs from the top on every resume."""
    pending = state.get("pending_diffs", [])
    if not pending:
        return {"diffs_to_apply": []}

    decision = interrupt(
        {
            "type": "diff_review",
            "iteration": state.get("iteration", 0),
            "diffs": [
                {k: d[k] for k in ("diff_id", "file_path", "unified_diff", "rationale")}
                for d in pending
            ],
        }
    )

    decisions = (decision or {}).get("decisions", {})
    approved, rejected_notes = [], []
    for diff in pending:
        choice = decisions.get(diff["diff_id"], {})
        if choice.get("action") == "approve":
            approved.append(diff)
        else:
            reason = choice.get("reason") or "no reason given"
            rejected_notes.append(f"- {diff['file_path']}: {reason}")

    return {
        "diffs_to_apply": approved,
        "pending_diffs": [],
        "review_feedback": "\n".join(rejected_notes),
    }


def apply_diffs_node(state: AgentState) -> dict:
    """The only place that writes to the workspace. Runs after the interrupt
    has resolved, so it is never re-executed by interrupt replay."""
    applied = []
    for diff in state.get("diffs_to_apply", []):
        target = WORKSPACE_ROOT / diff["file_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(diff["new_content"])
        applied.append(
            {
                "diff_id": diff["diff_id"],
                "file_path": diff["file_path"],
                "unified_diff": diff["unified_diff"],
                "rationale": diff["rationale"],
                "iteration": diff["proposed_at_iteration"],
            }
        )
    return {"applied_diffs": applied, "diffs_to_apply": []}


def tester_node(state: AgentState) -> dict:
    result = run_pytest_in_sandbox(WORKSPACE_ROOT, "tests")
    iteration = state.get("iteration", 0) + 1
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    if result["passed"]:
        status = "done"
    elif iteration >= max_iterations:
        status = "failed"
    else:
        status = "running"
    return {
        "test_results": [{**result, "iteration": iteration}],
        "last_test_passed": result["passed"],
        "iteration": iteration,
        "status": status,
    }


# --- Routing -----------------------------------------------------------------

def route_after_coder(state: AgentState) -> str:
    return "diff_review" if state.get("pending_diffs") else "tester"


def route_after_tester(state: AgentState) -> str:
    if state.get("last_test_passed"):
        return END
    if state.get("iteration", 0) >= state.get("max_iterations", DEFAULT_MAX_ITERATIONS):
        return END
    return "coder"


def build_graph(checkpointer):
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("explorer", explorer_node)
    graph.add_node("coder", coder_node)
    graph.add_node("diff_review", diff_review_node)
    graph.add_node("apply_diffs", apply_diffs_node)
    graph.add_node("tester", tester_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "explorer")
    graph.add_edge("explorer", "coder")
    graph.add_conditional_edges(
        "coder", route_after_coder, {"diff_review": "diff_review", "tester": "tester"}
    )
    graph.add_edge("diff_review", "apply_diffs")
    graph.add_edge("apply_diffs", "tester")
    graph.add_conditional_edges(
        "tester", route_after_tester, {"coder": "coder", END: END}
    )

    # A checkpointer is required for interrupt()/resume to work at all.
    return graph.compile(checkpointer=checkpointer)
