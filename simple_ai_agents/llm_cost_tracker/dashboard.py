"""Inspect local metadata; chart only requests with known configured-rate costs."""

import os
import sqlite3
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from tracker import load_rows


def render() -> None:
    """Render local request totals and charts, preserving unknown-cost records."""
    load_dotenv(Path(__file__).with_name(".env"))
    st.set_page_config(page_title="LLM Cost Tracker", layout="wide")
    st.title("LLM Cost Tracker")
    st.caption("Configured-rate estimates, not invoices. The demo uses synthetic prices and usage.")
    path = st.text_input("SQLite database", os.getenv("LLM_COST_DB", ".data/demo.sqlite3"))
    try:
        rows = load_rows(Path(path))
    except (sqlite3.Error, ValueError, OSError):
        st.info("No readable request database. Run `uv run python main.py --demo` first.")
        return
    if not rows:
        st.info("No requests recorded yet.")
        return
    frame = pd.DataFrame(rows)
    provider = st.selectbox("Provider", ["All", *sorted(frame["provider"].unique())])
    if provider != "All":
        frame = frame[frame["provider"] == provider]
    known = frame[frame["estimated_cost_usd"].notna()].copy()
    total = sum((Decimal(value) for value in known["estimated_cost_usd"]), Decimal(0))
    left, middle, right = st.columns(3)
    left.metric("Requests", len(frame))
    middle.metric("Estimated cost (known requests)", f"${total:.8f}" if len(known) else "Unknown")
    right.metric("Unknown-cost requests", len(frame) - len(known))
    st.caption(
        "Unknown prices/usage and failed requests are excluded from cost totals, never zeroed."
    )
    if len(known):
        known["estimated_cost_usd"] = known["estimated_cost_usd"].map(float)
        known["date"] = pd.to_datetime(known["timestamp"], utc=True).dt.strftime("%Y-%m-%d")
        known["provider_model"] = known["provider"] + " / " + known["model"]
        for group, label in [
            ("date", "Cost over time (UTC)"),
            ("provider_model", "Cost by provider and requested model"),
            ("tag", "Cost by tag"),
        ]:
            st.subheader(label)
            values = known.groupby(group, as_index=False)["estimated_cost_usd"].sum()
            st.bar_chart(values.set_index(group))
    st.subheader("Request metadata")
    st.dataframe(frame.drop(columns=["id"]), hide_index=True)
    st.caption(
        "Latency includes SDK retries. No prompts, generated text or credentials are stored."
    )


if __name__ == "__main__":
    render()
