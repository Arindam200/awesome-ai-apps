"""Optional visual review UI for the Coding Agent Harness."""
from __future__ import annotations

import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from demo_data import DEMO_BUGGY_CART, DEMO_DIFF, DEMO_OBJECTIVE
from graph import DEFAULT_MAX_ITERATIONS, build_graph

load_dotenv()

st.set_page_config(
    page_title="Coding Agent Harness",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --ink: var(--text-color);
        --muted: color-mix(in srgb, var(--text-color) 62%, transparent);
        --line: color-mix(in srgb, var(--text-color) 20%, transparent);
        --panel: var(--secondary-background-color);
        --accent: #ff5c5c;
        --accent-soft: rgba(255, 92, 92, 0.12);
        --green: #48d597;
    }
    html, body, [class*="css"] { font-family: "DM Sans", sans-serif; }
    code, pre, [data-testid="stCodeBlock"] { font-family: "IBM Plex Mono", monospace; }
    .block-container { max-width: 1320px; padding-top: 2.6rem; padding-bottom: 4rem; }
    [data-testid="stSidebar"] { border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    h1, h2, h3 { letter-spacing: -0.035em; }
    .eyebrow {
        color: var(--accent); font: 500 0.74rem/1 "IBM Plex Mono", monospace;
        letter-spacing: 0.13em; text-transform: uppercase; margin-bottom: 0.8rem;
    }
    .hero-title {
        color: var(--ink); font-size: clamp(2.4rem, 5vw, 4.6rem); line-height: 0.98;
        letter-spacing: -0.065em; font-weight: 700; max-width: 900px; margin: 0;
    }
    .hero-copy {
        color: var(--muted); font-size: 1.12rem; line-height: 1.65;
        max-width: 730px; margin: 1.25rem 0 2rem;
    }
    .status-line {
        display: flex; align-items: center; gap: 0.55rem; color: var(--muted);
        font: 500 0.78rem/1.4 "IBM Plex Mono", monospace; margin-bottom: 1rem;
    }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
    .agent-step {
        min-height: 118px; padding: 1rem; border-top: 2px solid var(--line);
        background: linear-gradient(180deg, rgba(255,255,255,0.025), transparent);
    }
    .agent-step strong { color: var(--ink); display: block; font-size: 0.95rem; margin: 0.4rem 0; }
    .agent-step span { color: var(--muted); font-size: 0.8rem; line-height: 1.4; }
    .agent-step.review { border-color: var(--accent); background: var(--accent-soft); }
    .step-no { color: var(--muted); font: 500 0.7rem/1 "IBM Plex Mono", monospace; }
    .ticket {
        border: 1px solid var(--line); background: var(--panel); padding: 1.2rem 1.3rem;
        border-radius: 8px; margin-top: 0.25rem;
    }
    .ticket-id { color: var(--accent); font: 500 0.72rem/1 "IBM Plex Mono", monospace; }
    .ticket h3 { font-size: 1.15rem; margin: 0.75rem 0 0.55rem; }
    .ticket p { color: var(--muted); font-size: 0.88rem; line-height: 1.5; margin: 0; }
    .failure-row {
        display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.8rem 0;
        border-bottom: 1px solid var(--line); color: var(--ink); font-size: 0.87rem;
    }
    .failure-row:last-child { border-bottom: 0; }
    .failure-mark { color: var(--accent); font-family: "IBM Plex Mono", monospace; }
    div[data-testid="stMetric"] {
        border-top: 1px solid var(--line); padding-top: 0.8rem;
    }
    div[data-testid="stMetric"] label { color: var(--muted); }
    div[data-testid="stMetricValue"] {
        font-family: "IBM Plex Mono", monospace; font-size: 1.65rem;
        white-space: nowrap; overflow: visible;
    }
    .stButton > button { border-radius: 6px; min-height: 46px; font-weight: 600; }
    div[data-testid="stCodeBlock"] { border: 1px solid var(--line); border-radius: 7px; }
    div[data-testid="stTabs"] button { font-weight: 600; }
    .sidebar-brand { font-size: 1.25rem; font-weight: 700; letter-spacing: -0.03em; }
    .sidebar-copy { color: var(--muted); font-size: 0.86rem; line-height: 1.55; }
    </style>
    """,
    unsafe_allow_html=True,
)

# The graph and checkpointer must survive Streamlit reruns. A fresh
# InMemorySaver would silently drop every checkpoint at the review gate.
if "graph" not in st.session_state:
    st.session_state.checkpointer = InMemorySaver()
    st.session_state.graph = build_graph(checkpointer=st.session_state.checkpointer)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "run_started" not in st.session_state:
    st.session_state.run_started = False
if "pending_review" not in st.session_state:
    st.session_state.pending_review = None
if "final_state" not in st.session_state:
    st.session_state.final_state = None

config = {"configurable": {"thread_id": st.session_state.thread_id}}
missing = [key for key in ("NEBIUS_API_KEY", "E2B_API_KEY") if not os.getenv(key)]


def drive(invoke_arg) -> None:
    """Invoke or resume the graph and capture an interrupt or final state."""
    with st.spinner("Crew is exploring the repo and preparing a patch…"):
        result = st.session_state.graph.invoke(invoke_arg, config)
    if "__interrupt__" in result:
        st.session_state.pending_review = result["__interrupt__"][0].value
        st.session_state.final_state = None
    else:
        st.session_state.pending_review = None
        st.session_state.final_state = result


def reset_run() -> None:
    """Start a fresh checkpoint thread without touching the demo workspace."""
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.run_started = False
    st.session_state.pending_review = None
    st.session_state.final_state = None


with st.sidebar:
    st.markdown('<div class="sidebar-brand">Code Harness</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sidebar-copy">A coding crew with a hard boundary: the model '
        "can propose code, but only you can apply it.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    run_label = "Awaiting your review" if st.session_state.pending_review else (
        "Run in progress" if st.session_state.run_started and not st.session_state.final_state
        else "Ready for a ticket"
    )
    st.markdown(
        f'<div class="status-line"><span class="status-dot"></span>{run_label}</div>',
        unsafe_allow_html=True,
    )
    if missing:
        st.error(f"Add to `.env`: {', '.join(missing)}")
    else:
        st.success("Nebius + E2B connected")
    st.caption(f"Model · `{os.getenv('NEBIUS_MODEL', 'Qwen/Qwen3-30B-A3B')}`")
    st.caption(f"Thread · `{st.session_state.thread_id[:8]}`")

    st.divider()
    st.markdown("**Safety boundary**")
    st.caption("The coder has no file-write tool. Only approved diffs reach `workspace/`.")
    with st.expander("Reset the sample repo"):
        st.code("git restore workspace/", language="bash")

st.markdown('<div class="eyebrow">Human-gated coding harness</div>', unsafe_allow_html=True)
st.markdown(
    '<h1 class="hero-title">Review AI code before it touches disk.</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="hero-copy">Give a four-agent crew a real bug ticket. It can inspect, '
    "plan, and propose a patch, but execution stops at a review gate you control. "
    "Approve good code, reject weak code with a reason, then verify it in an isolated sandbox.</p>",
    unsafe_allow_html=True,
)

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("Seeded test suite", "3 failing")
metric_2.metric("Files in scope", "1 of 2")
metric_3.metric("Approval gates", "Every diff")
metric_4.metric("Test environment", "E2B sandbox")

st.markdown("### The handoff")
steps = [
    ("01", "Planner", "Turns the ticket into a scoped implementation plan."),
    ("02", "Explorer", "Reads the real workspace and finds the failure points."),
    ("03", "Coder", "Produces a unified diff. It cannot write the file."),
    ("04", "You", "Approve the patch or reject it with precise feedback."),
    ("05", "Tester", "Runs pytest in E2B and loops back if anything fails."),
]
for column, (number, title, copy) in zip(st.columns(5), steps):
    review_class = " review" if title == "You" else ""
    column.markdown(
        f'<div class="agent-step{review_class}"><div class="step-no">{number}</div>'
        f"<strong>{title}</strong><span>{copy}</span></div>",
        unsafe_allow_html=True,
    )

st.divider()
run_col, ticket_col = st.columns([1.65, 1], gap="large")
with run_col:
    st.markdown("### Run the seeded ticket")
    objective = st.text_area(
        "Ticket objective",
        value=DEMO_OBJECTIVE,
        height=126,
        help="The sample workspace intentionally starts with three bugs.",
    )
    action_col, reset_col = st.columns([1.6, 1])
    with action_col:
        start_clicked = st.button(
            "Start agent run",
            type="primary",
            disabled=st.session_state.run_started or bool(missing),
            use_container_width=True,
        )
    with reset_col:
        if st.button("New thread", use_container_width=True):
            reset_run()
            st.rerun()
    if missing:
        st.caption("Add both API keys to `.env` to enable the live run. The demo below works without them.")

with ticket_col:
    st.markdown(
        """
        <div class="ticket">
            <div class="ticket-id">CART-104 · BUG</div>
            <h3>Cart totals are wrong in production</h3>
            <p>Fix implementation behavior without changing the contract encoded by the tests.</p>
            <div class="failure-row"><span class="failure-mark">FAIL</span><span>Quantity 3 × $2.50 returns $2.50, expected $7.50</span></div>
            <div class="failure-row"><span class="failure-mark">FAIL</span><span>Removing a missing SKU raises KeyError</span></div>
            <div class="failure-row"><span class="failure-mark">FAIL</span><span>Applying 10% twice becomes a 20% discount</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

# Live progress and review gate appear directly below the ticket once a run starts.
if st.session_state.run_started:
    st.divider()
    st.markdown("## Live run")
    snapshot = st.session_state.graph.get_state(config)
    values = snapshot.values if snapshot else {}
    if values.get("plan"):
        with st.expander("Implementation plan", expanded=True):
            st.markdown(values["plan"])
    for test_result in values.get("test_results", []):
        with st.expander(
            f"Test run · iteration {test_result['iteration']} · {test_result['summary']}",
            expanded=False,
        ):
            st.code(test_result["stdout"], language="text")

if st.session_state.pending_review:
    payload = st.session_state.pending_review
    st.warning("Execution paused. Nothing below has been written to disk.")
    st.subheader(f"Review proposed changes · iteration {payload['iteration'] + 1}")
    decisions = {}
    for diff in payload["diffs"]:
        with st.expander(f"{diff['file_path']} · {diff['rationale']}", expanded=True):
            st.code(diff["unified_diff"], language="diff")
            action = st.radio(
                "Decision",
                options=["approve", "reject"],
                format_func=lambda value: "Approve patch" if value == "approve" else "Request changes",
                key=f"decision_{diff['diff_id']}",
                horizontal=True,
            )
            reason = ""
            if action == "reject":
                reason = st.text_input(
                    "What should the coder change?",
                    placeholder="Example: preserve the public method signature",
                    key=f"reason_{diff['diff_id']}",
                )
            decisions[diff["diff_id"]] = {"action": action, "reason": reason}

    if st.button("Submit review and resume", type="primary"):
        drive(Command(resume={"decisions": decisions}))
        st.rerun()

if st.session_state.final_state:
    state = st.session_state.final_state
    if state.get("last_test_passed"):
        st.success(f"All 5 tests pass after {state.get('iteration', 0)} iteration(s).")
    else:
        st.error(
            f"Stopped after {state.get('iteration', 0)} iteration(s); tests still fail. "
            "Start a new run or raise MAX_ITERATIONS."
        )
    if state.get("applied_diffs"):
        st.subheader("Applied diffs")
        for diff in state["applied_diffs"]:
            with st.expander(
                f"{diff['file_path']} · iteration {diff['iteration'] + 1} · {diff['rationale']}"
            ):
                st.code(diff["unified_diff"], language="diff")

st.divider()
st.markdown("## See the use case before spending a token")
st.caption("This preview uses the real seeded bug and representative patch. It never invokes a model or changes a file.")

workspace_tab, review_tab, contract_tab = st.tabs(
    ["Buggy workspace", "Review-gate preview", "Safety contract"]
)

with workspace_tab:
    source_col, failures_col = st.columns([1.25, 1], gap="large")
    with source_col:
        st.markdown("#### `workspace/cart.py`")
        st.code(DEMO_BUGGY_CART, language="python", line_numbers=True)
    with failures_col:
        st.markdown("#### Baseline: 3 failed, 2 passed")
        st.code(
            """FAILED test_total_respects_quantity
  assert 2.5 == 7.5

FAILED test_remove_missing_item_is_noop
  KeyError: 'banana'

FAILED test_discount_applied_once
  assert 8.0 == 9.0

3 failed, 2 passed in 0.05s""",
            language="text",
        )

with review_tab:
    st.markdown("#### Proposed patch · `cart.py`")
    st.caption("The graph would pause here. The workspace is still unchanged.")
    st.code(DEMO_DIFF, language="diff", line_numbers=True)
    preview_choice = st.radio(
        "Your decision",
        ["Approve patch", "Request changes"],
        horizontal=True,
        key="preview_decision",
    )
    if preview_choice == "Request changes":
        st.text_input(
            "Feedback sent back to the coder",
            value="Keep remove_item as a silent no-op and preserve the public API.",
        )
        st.info("The coder receives this constraint and must propose a new diff. No code is applied.")
    else:
        st.success("Next: apply this diff, run all 5 tests in E2B, and loop back if one fails.")

with contract_tab:
    contract_1, contract_2, contract_3 = st.columns(3)
    contract_1.markdown("**Model proposes**\n\nThe coder returns complete file content, which is converted into a unified diff.")
    contract_2.markdown("**Human authorizes**\n\nLangGraph interrupts before the only node that can write to the workspace.")
    contract_3.markdown("**Sandbox verifies**\n\nApproved code is copied into E2B and tested away from the host machine.")
