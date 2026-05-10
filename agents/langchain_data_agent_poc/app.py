"""Streamlit UI for the data agent PoC."""
from __future__ import annotations

import os

from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import streamlit as st

from agent import DataAgent
from config import DOMAINS
from dataset import DemoDataset

load_dotenv()


def _render_result(result: dict) -> None:
    if result.get("domain"):
        st.caption(f"Domain: {result['domain']}")
    if result.get("validated_sql"):
        with st.expander("SQL"):
            st.code(result["validated_sql"], language="sql")

    rows = result.get("rows") or []
    if rows:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, hide_index=True)
        chart = result.get("chart")
        if chart:
            fig = _build_chart(frame, chart)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)


def _build_chart(frame: pd.DataFrame, chart: dict):
    x = chart.get("x")
    y = chart.get("y")
    if not x or not y or x not in frame.columns or y not in frame.columns:
        return None

    frame = frame.copy()
    frame[y] = pd.to_numeric(frame[y], errors="coerce")
    title = chart.get("title") or f"{y} by {x}"
    if chart.get("type") == "line":
        return px.line(frame, x=x, y=y, markers=True, title=title)
    return px.bar(frame, x=x, y=y, title=title)


st.set_page_config(page_title="Retail Data Agent", page_icon=":bar_chart:", layout="wide")
st.title("Retail Data Agent")
st.caption("LangChain + LangGraph + Nebius + SQLite + Streamlit")

dataset = DemoDataset()

with st.sidebar:
    st.header("Dataset")
    for domain in DOMAINS.values():
        with st.expander(f"{domain.name.title()} domain", expanded=domain.name == "sales"):
            st.write(domain.description)
            st.caption("Tables: " + ", ".join(domain.tables))
            for question in domain.sample_questions:
                if st.button(question, key=f"sample-{domain.name}-{question}"):
                    st.session_state.pending_prompt = question

    st.divider()
    st.header("Tables")
    for table_name in sorted(dataset.table_names):
        with st.expander(table_name):
            st.dataframe(pd.DataFrame(dataset.preview(table_name, limit=5)), hide_index=True)

    if st.button("Reset conversation"):
        st.session_state.pop("messages", None)
        st.session_state.pop("history", None)
        st.session_state.pop("agent", None)
        st.rerun()

if not os.getenv("NEBIUS_API_KEY"):
    st.info("Set NEBIUS_API_KEY in .env before asking questions.")
    st.stop()

if "agent" not in st.session_state:
    st.session_state.agent = DataAgent(dataset=dataset)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("result"):
            _render_result(message["result"])

prompt = st.session_state.pop("pending_prompt", None) or st.chat_input(
    "Ask about revenue, orders, inventory, or support tickets"
)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying the demo warehouse..."):
            result = st.session_state.agent.query(prompt, history=st.session_state.history)
            st.markdown(result["answer"])
            _render_result(result)

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "result": result}
    )
    st.session_state.history.extend([("human", prompt), ("ai", result["answer"])])
    st.rerun()
