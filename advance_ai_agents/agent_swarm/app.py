"""Streamlit UI: watch Kimi K3.1 Pro run a swarm of cheap workers, live.

uv run streamlit run app.py
"""

from __future__ import annotations

import time

import streamlit as st

from models import (
    FAST_WORKER_MODEL,
    ORCHESTRATOR_FALLBACKS,
    ORCHESTRATOR_MODEL,
    WORKER_MODEL,
    WORKER_OPTIONS,
    available,
    catalog,
    label,
    price,
    resolve_orchestrator,
)
from swarm import cost_summary, make_settings, run

EXAMPLES = {
    "Database decision": (
        "Compare Postgres, SQLite, DuckDB, MongoDB and ClickHouse for a solo developer building a SaaS "
        "analytics dashboard. Recommend one and explain when to switch."
    ),
    "Launch plan": (
        "Plan a one-week launch for an open-source CLI that turns screenshots into Markdown docs: "
        "channels, content calendar, launch-day checklist and success metrics."
    ),
    "Science explainer": (
        "Explain how CRISPR gene editing works, its approved medical uses so far, and the open ethical "
        "debates, for a smart high-school student."
    ),
}

STATUS = {
    "queued": ":gray[queued]",
    "running": ":blue[running]",
    "done": ":green[done]",
    "revising": ":orange[sent back]",
    "error": ":red[failed]",
    "empty": ":red[empty]",
}

st.set_page_config(page_title="Agent Swarm", page_icon=":material/hub:", layout="wide")


def model_select(title: str, options: list[str], default: str, key: str) -> str:
    options = options or [default]
    index = options.index(default) if default in options else 0
    return st.selectbox(
        title,
        options,
        index=index,
        key=key,
        format_func=lambda m: f"{label(m)}  (${price(m)[0]:.2f} / ${price(m)[1]:.2f})",
    )


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Swarm settings")
    try:
        live = bool(catalog())
    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    st.caption(
        "Prices are USD per 1M input / output tokens, "
        + ("live from Token Factory." if live else "from the built-in table (catalog unreachable).")
    )
    orch_options = available([ORCHESTRATOR_MODEL, *ORCHESTRATOR_FALLBACKS])
    orchestrator = model_select("Orchestrator", orch_options, resolve_orchestrator(), "orch")
    worker_options = available(WORKER_OPTIONS)
    worker = model_select("Standard worker", worker_options, WORKER_MODEL, "worker")
    fast_worker = model_select("Fast worker", worker_options, FAST_WORKER_MODEL, "fast")
    max_tasks = st.slider("Max subtasks", 2, 8, 5)
    max_revisions = st.slider("Review rounds", 0, 2, 1, help="How many times Kimi may send work back")
    tools = st.toggle("Worker tools (Wikipedia, fetch URL)", value=True)
    st.divider()
    st.caption(
        "Kimi plans, reviews and writes the final answer. Workers do everything else in parallel. "
        "Fast-tier tasks start on the fast worker; anything sent back is redone on the standard worker."
    )

# ---------------------------------------------------------------- header

st.title("Agent Swarm")
st.markdown(
    f"**{label(orchestrator)}** plans the work, reviews it and writes the answer. "
    f"**{label(worker)}** and **{label(fast_worker)}** do the work in parallel. "
    "Built with LangGraph on [Nebius Token Factory](https://dub.sh/nebius)."
)

if "goal" not in st.session_state:
    st.session_state.goal = EXAMPLES["Database decision"]
cols = st.columns(len(EXAMPLES) + 2)
for col, (name, text) in zip(cols, EXAMPLES.items()):
    if col.button(name, width="stretch"):
        st.session_state.goal = text
goal = st.text_area("Goal", key="goal", height=100)
start = st.button("Run the swarm", type="primary", disabled=not goal.strip())

# ---------------------------------------------------------------- rendering


def new_view() -> dict:
    return {"stage": "plan", "plan": None, "workers": {}, "reviews": [], "final": "", "ledger": [], "elapsed": 0.0}


STAGES = [
    ("plan", "Plan"),
    ("workers", "Workers"),
    ("review", "Review"),
    ("synthesize", "Synthesize"),
    ("done", "Done"),
]


def render_header(ph, view: dict, orchestrator: str) -> None:
    with ph.container():
        order = [s for s, _ in STAGES]
        current = order.index(view["stage"])
        st.markdown(
            "  →  ".join(
                f"**:violet[{name}]**" if i == current else (f":green[{name}]" if i < current else f":gray[{name}]")
                for i, (_, name) in enumerate(STAGES)
            )
        )
        c = cost_summary(view["ledger"], orchestrator)
        m = st.columns(5)
        m[0].metric("Workers", len(view["workers"]))
        m[1].metric("Model calls", len(view["ledger"]))
        m[2].metric("Tokens", f"{c['tokens']:,}")
        m[3].metric("Cost", f"${c['total']:.4f}")
        m[4].metric(
            f"Same tokens on {label(orchestrator)}",
            f"${c['all_orchestrator_total']:.4f}",
            delta=f"-{c['savings_pct']:.0f}%" if c["total"] else None,
            delta_color="inverse",
        )


def render_plan(ph, view: dict) -> None:
    plan = view["plan"]
    if not plan:
        return
    with ph.container(border=True):
        st.markdown(f"**Plan** · {plan['approach']}")
        st.caption(f"Final deliverable: {plan['final_format']}")


def render_workers(ph, view: dict) -> None:
    workers = list(view["workers"].values())
    if not workers:
        return
    with ph.container():
        per_row = 3
        for i in range(0, len(workers), per_row):
            cols = st.columns(per_row)
            for col, w in zip(cols, workers[i : i + per_row]):
                with col.container(border=True):
                    st.markdown(f"**{w['task']['title']}**")
                    st.markdown(
                        f"`{w['task']['tier']}` · {label(w['model'])} · attempt {w['attempt']} · {STATUS[w['status']]}"
                    )
                    if w.get("feedback") and w["status"] in ("revising", "running"):
                        st.caption(f"Kimi: {w['feedback'][:220]}")
                    if w.get("last_tool"):
                        st.caption(f"`{w['last_tool']}`")
                    r = w.get("result")
                    if r:
                        st.caption(f"{r['seconds']}s · {r['tool_calls']} tool calls · ${r['cost']:.4f}")
                        with st.expander("Output"):
                            st.markdown(r["output"])


def render_reviews(ph, view: dict) -> None:
    if not view["reviews"]:
        return
    with ph.container():
        for rv in view["reviews"]:
            with st.container(border=True):
                st.markdown(f"**Review {rv['round']}** · {rv['summary']}")
                for v in rv["verdicts"]:
                    if v["decision"] == "revise":
                        st.markdown(f":orange[revise] **{v['task_id']}**: {v['feedback']}")
                    else:
                        st.markdown(f":green[accept] **{v['task_id']}**")


def render_ledger(ph, view: dict, orchestrator: str) -> None:
    c = cost_summary(view["ledger"], orchestrator)
    rows = [
        {
            "Model": label(m),
            "Calls": d["calls"],
            "Input tokens": d["input_tokens"],
            "Output tokens": d["output_tokens"],
            "Cost (USD)": round(d["cost"], 5),
        }
        for m, d in sorted(c["by_model"].items(), key=lambda kv: -kv[1]["cost"])
    ]
    with ph.container():
        st.subheader("Cost ledger")
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(
            f"Workers handled {c['worker_token_share']:.0f}% of the tokens for ${c['worker_cost']:.4f}. "
            f"Run time {view['elapsed']:.0f}s."
        )


def apply(view: dict, ev: dict) -> None:
    kind = ev["event"]
    if kind == "plan":
        view["plan"] = ev["plan"]
        view["stage"] = "workers"
        for t in ev["plan"]["tasks"]:
            s = view["settings"]
            model = s["fast_worker"] if t["tier"] == "fast" else s["worker"]
            view["workers"][t["id"]] = {"task": t, "model": model, "attempt": 1, "status": "queued"}
    elif kind == "worker_start":
        w = view["workers"][ev["task_id"]]
        w.update(status="running", model=ev["model"], attempt=ev["attempt"], last_tool=None)
        view["stage"] = "workers"
    elif kind == "tool_call":
        arg = next(iter(ev["args"].values()), "")
        view["workers"][ev["task_id"]]["last_tool"] = f"{ev['tool']}({str(arg)[:60]!r})"
    elif kind == "worker_done":
        r = ev["result"]
        view["workers"][r["task_id"]].update(status=r["status"] if r["status"] != "done" else "done", result=r)
    elif kind == "reviewing":
        view["stage"] = "review"
    elif kind == "review":
        view["reviews"].append(ev["review"])
        for rev in ev["revisions"]:
            view["workers"][rev["task_id"]].update(status="revising", feedback=rev["feedback"])
    elif kind == "synthesizing":
        view["stage"] = "synthesize"
        view["final"] = ""
    elif kind == "final_delta":
        view["final"] += ev["text"]
    elif kind == "final":
        view["final"] = ev["text"]
    elif kind == "usage":
        view["ledger"].extend(ev["records"])
    elif kind == "done":
        view["stage"] = "done"


def render_all(view: dict, orchestrator: str, ph: dict) -> None:
    render_header(ph["header"], view, orchestrator)
    render_plan(ph["plan"], view)
    render_workers(ph["workers"], view)
    render_reviews(ph["reviews"], view)
    if view["final"]:
        with ph["final"].container():
            st.subheader("Final deliverable")
            st.markdown(view["final"])
    if view["stage"] == "done":
        render_ledger(ph["ledger"], view, orchestrator)


ph = {k: st.empty() for k in ("header", "plan", "workers", "reviews", "final", "ledger")}

if start:
    settings = make_settings(
        orchestrator=orchestrator,
        worker=worker,
        fast_worker=fast_worker,
        max_tasks=max_tasks,
        max_revisions=max_revisions,
        tools=tools,
    )
    view, started, last_paint = new_view(), time.time(), 0.0
    view["settings"] = settings
    render_all(view, orchestrator, ph)
    try:
        for ev in run(goal.strip(), settings):
            apply(view, ev)
            view["elapsed"] = time.time() - started
            # Final-answer tokens arrive fast; repaint at most ~8 times a second.
            if ev["event"] != "final_delta" or time.time() - last_paint > 0.12:
                render_all(view, orchestrator, ph)
                last_paint = time.time()
    except Exception as e:
        st.error(f"The swarm stopped: {type(e).__name__}: {e}")
    view["elapsed"] = time.time() - started
    render_all(view, orchestrator, ph)
    st.session_state.last = {"view": view, "orchestrator": orchestrator, "goal": goal}
elif "last" in st.session_state:
    last = st.session_state.last
    render_all(last["view"], last["orchestrator"], ph)

if "last" in st.session_state and st.session_state.last["view"]["final"]:
    st.download_button(
        "Download as Markdown",
        st.session_state.last["view"]["final"],
        file_name="swarm-report.md",
        mime="text/markdown",
    )
