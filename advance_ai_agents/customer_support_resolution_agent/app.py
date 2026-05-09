"""Streamlit chat UI for the customer support resolution agent."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from agent import build_agent

ROOT = Path(__file__).parent
ORDERS_PATH = ROOT / "data" / "orders.json"
TICKETS_PATH = ROOT / "data" / "tickets.json"

st.set_page_config(page_title="NimbusCart Support", page_icon="🛟", layout="wide")
st.title("🛟 NimbusCart: Customer Support Resolution Agent")
st.caption("LangChain · Nebius Token Factory · FAISS")

with st.sidebar:
    st.header("Demo data")
    st.subheader("Sample orders")
    orders = json.loads(ORDERS_PATH.read_text())
    for oid, o in orders.items():
        st.markdown(f"**{oid}** — {o['status']} — `{o['customer_email']}`")

    st.divider()
    st.subheader("Tickets opened this session")
    tickets = json.loads(TICKETS_PATH.read_text())
    if not tickets:
        st.caption("No tickets yet.")
    else:
        for t in tickets[-10:]:
            st.markdown(
                f"- **{t['ticket_id']}** ({t['priority']}) — {t['summary']}"
            )

    if st.button("Reset conversation"):
        st.session_state.pop("messages", None)
        st.session_state.pop("history", None)
        st.rerun()


if "agent" not in st.session_state:
    st.session_state.agent = build_agent(verbose=False)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Ask about an order, refund, shipping, or your account…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Looking it up…"):
            turn_messages = st.session_state.history + [("human", prompt)]
            result = st.session_state.agent.invoke({"messages": turn_messages})
            answer = result["messages"][-1].content
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.history.extend([("human", prompt), ("ai", answer)])
    st.rerun()
