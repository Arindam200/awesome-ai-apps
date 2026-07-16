"""Streamlit UI for the Diff-Stack Code Agent."""
from __future__ import annotations

import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph import DEFAULT_MAX_ITERATIONS, build_graph

load_dotenv()

st.set_page_config(page_title="Diff Stack Code Agent", page_icon="🗂️", layout="wide")

# The compiled graph and its checkpointer must survive Streamlit reruns —
# a fresh InMemorySaver per rerun would silently drop every checkpoint.
if "graph" not in st.session_state:
    st.session_state.checkpointer = InMemorySaver()
    st.session_state.graph = build_graph(checkpointer=st.session_state.checkpointer)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "run_started" not in st.session_state:
    st.session_state.run_started = False
if "pending_review" not in st.session_state:
    st.session_state.pending_review = None  # the interrupt payload, if paused
if "final_state" not in st.session_state:
    st.session_state.final_state = None

config = {"configurable": {"thread_id": st.session_state.thread_id}}


def drive(invoke_arg) -> None:
    """Single choke point for graph.invoke — both the first call and every
    Command(resume=...) go through here, and this is the only place that
    checks whether the graph paused on an interrupt."""
    with st.spinner("Agents working… (explore → propose diffs → test)"):
        result = st.session_state.graph.invoke(invoke_arg, config)
    if "__interrupt__" in result:
        st.session_state.pending_review = result["__interrupt__"][0].value
        st.session_state.final_state = None
    else:
        st.session_state.pending_review = None
        st.session_state.final_state = result


# --- Sidebar -----------------------------------------------------------------

with st.sidebar:
    st.title("🗂️ Diff Stack Code Agent")
    st.markdown(
        "A LangGraph coding crew — planner, explorer, coder, tester — where "
        "the coder can only **propose diffs**. Every proposed change lands on "
        "a diff stack that *you* review. Approved diffs are written to "
        "`workspace/`; rejected ones go back to the coder with your reason."
    )
    st.divider()
    missing = [k for k in ("NEBIUS_API_KEY", "E2B_API_KEY") if not os.getenv(k)]
    if missing:
        st.error(f"Missing in .env: {', '.join(missing)}")
    else:
        st.success("API keys loaded")
    st.caption(f"Model: `{os.getenv('NEBIUS_MODEL', 'Qwen/Qwen3-30B-A3B')}`")
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}`")
    st.divider()
    st.markdown(
        "Reset the sample project between runs with:\n"
        "```bash\ngit restore workspace/\n```"
    )

# --- Run controls --------------------------------------------------------------

st.subheader("Objective")
objective = st.text_area(
    "What should the coding crew do?",
    value=(
        "Fix the failing pytest suite. Users report bugs in cart.py: a discount "
        "compounds when applied twice, removing a missing item crashes, and the "
        "total ignores quantities. Fix ONLY cart.py — never edit a test."
    ),
    height=100,
    label_visibility="collapsed",
)

col_start, col_reset = st.columns([1, 1])
with col_start:
    start_clicked = st.button(
        "▶️ Start run",
        type="primary",
        disabled=st.session_state.run_started or bool(missing),
    )
with col_reset:
    if st.button("🔄 New run"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.run_started = False
        st.session_state.pending_review = None
        st.session_state.final_state = None
        st.rerun()

if start_clicked and objective.strip():
    st.session_state.run_started = True
    drive(
        {
            "objective": objective.strip(),
            "iteration": 0,
            "max_iterations": int(os.getenv("MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS)),
        }
    )
    st.rerun()

# --- Progress context (plan, test history) -----------------------------------

if st.session_state.run_started:
    snapshot = st.session_state.graph.get_state(config)
    values = snapshot.values if snapshot else {}
    if values.get("plan"):
        with st.expander("📋 Plan", expanded=False):
            st.markdown(values["plan"])
    for tr in values.get("test_results", []):
        with st.expander(
            f"🧪 Test run — iteration {tr['iteration']} — {tr['summary']}",
            expanded=False,
        ):
            st.code(tr["stdout"], language="text")

# --- Diff stack review gate ----------------------------------------------------
# Widget interactions inside this block trigger Streamlit reruns but must NOT
# re-invoke the graph; only the Submit button calls drive() with the resume.

if st.session_state.pending_review:
    payload = st.session_state.pending_review
    st.subheader(f"👀 Review the diff stack (iteration {payload['iteration'] + 1})")
    st.caption(
        "Approve a diff to apply it to disk. Reject it (with a reason) to send "
        "it back to the coder for revision."
    )
    decisions = {}
    for diff in payload["diffs"]:
        with st.expander(f"`{diff['file_path']}` — {diff['rationale']}", expanded=True):
            st.code(diff["unified_diff"], language="diff")
            action = st.radio(
                "Decision",
                options=["approve", "reject"],
                key=f"decision_{diff['diff_id']}",
                horizontal=True,
            )
            reason = ""
            if action == "reject":
                reason = st.text_input(
                    "Reason (fed back to the coder)",
                    key=f"reason_{diff['diff_id']}",
                )
            decisions[diff["diff_id"]] = {"action": action, "reason": reason}

    if st.button("✅ Submit review", type="primary"):
        drive(Command(resume={"decisions": decisions}))
        st.rerun()

# --- Final result ---------------------------------------------------------------

if st.session_state.final_state:
    state = st.session_state.final_state
    if state.get("last_test_passed"):
        st.success(
            f"✅ All tests passing after {state.get('iteration', 0)} iteration(s)."
        )
    else:
        st.error(
            f"❌ Stopped after {state.get('iteration', 0)} iteration(s); "
            "tests still failing. Start a new run or raise MAX_ITERATIONS."
        )
    if state.get("applied_diffs"):
        st.subheader("📜 Applied diffs")
        for diff in state["applied_diffs"]:
            with st.expander(
                f"`{diff['file_path']}` (iteration {diff['iteration'] + 1}) — {diff['rationale']}"
            ):
                st.code(diff["unified_diff"], language="diff")
