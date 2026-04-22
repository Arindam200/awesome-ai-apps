"""Streamlit UI for the Context Engineering Pipeline."""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from runner import FORMATS, TASKS, load_eval, load_prompt, run_all

load_dotenv()

st.set_page_config(page_title="Context Engineering Pipeline", layout="wide")
st.title("Context Engineering Pipeline")
st.caption("Compare XML vs JSON vs Markdown prompt formats on accuracy, latency, and tokens — powered by Nebius Token Factory.")

with st.sidebar:
    st.header("Run Configuration")
    model = st.selectbox(
        "Nebius model",
        [
            "Qwen/Qwen3-30B-A3B",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "deepseek-ai/DeepSeek-V3",
        ],
        index=0,
    )
    selected_tasks = st.multiselect("Tasks", list(TASKS), default=list(TASKS))
    selected_formats = st.multiselect("Formats", FORMATS, default=FORMATS)
    limit = st.slider("Items per task (for speed)", 2, 20, 10)

    has_key = bool(os.environ.get("NEBIUS_API_KEY"))
    if not has_key:
        st.error("NEBIUS_API_KEY not set. Add it to a .env file.")

    run_btn = st.button(
        "▶ Run evaluation",
        type="primary",
        disabled=not (has_key and selected_tasks and selected_formats),
        use_container_width=True,
    )

tab_results, tab_prompts, tab_data = st.tabs(["Results", "Prompts", "Eval Data"])

with tab_prompts:
    colf = st.columns(3)
    for i, fmt in enumerate(FORMATS):
        with colf[i]:
            st.subheader(fmt.upper())
            task_pick = st.selectbox(f"Task ({fmt})", list(TASKS), key=f"task_{fmt}")
            st.code(load_prompt(task_pick, fmt), language=fmt if fmt != "markdown" else "markdown")

with tab_data:
    for task in TASKS:
        st.subheader(task)
        st.dataframe(pd.DataFrame(load_eval(task)), use_container_width=True)

with tab_results:
    if run_btn:
        progress = st.progress(0.0, text="Starting…")
        status = st.empty()
        total_units = len(selected_tasks) * len(selected_formats) * limit
        done_units = {"n": 0}

        def _cb(task: str, fmt: str, done: int, total: int) -> None:
            done_units["n"] += 1
            frac = min(done_units["n"] / total_units, 1.0)
            progress.progress(frac, text=f"[{task}/{fmt}] {done}/{total}")

        with st.spinner("Calling Nebius…"):
            results = run_all(
                model=model,
                tasks=selected_tasks,
                formats=selected_formats,
                limit=limit,
                on_progress=_cb,
            )
        progress.empty()
        status.success(f"Done — {len(results)} runs")

        summary_df = pd.DataFrame([r.summary() for r in results])
        st.subheader("Summary")
        st.dataframe(summary_df, use_container_width=True)

        st.subheader("Accuracy by format")
        pivot = summary_df.pivot(index="format", columns="task", values="accuracy")
        st.bar_chart(pivot)

        if "field_accuracy" in summary_df.columns:
            st.subheader("Field-level accuracy (extraction) / label accuracy (classification)")
            st.bar_chart(summary_df.pivot(index="format", columns="task", values="field_accuracy"))

        st.subheader("Tokens used")
        tok_df = summary_df[["task", "format", "prompt_tokens", "completion_tokens"]]
        st.dataframe(tok_df, use_container_width=True)

        st.subheader("Per-item results")
        for r in results:
            with st.expander(f"{r.task} / {r.fmt} — acc {r.accuracy:.0%}"):
                rows = []
                for it in r.items:
                    rows.append({
                        "correct": "✅" if it["grade"]["correct"] else "❌",
                        "input": it["input"][:80] + ("…" if len(it["input"]) > 80 else ""),
                        "expected": it["expected"],
                        "raw_output": it["raw"][:200],
                        "latency_ms": round(it["latency_ms"], 0),
                        "error": it["error"] or "",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("Configure the run in the sidebar and click ▶ Run evaluation.")
