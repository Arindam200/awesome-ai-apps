"""Streamlit UI: pick or upload a patient, run the agent, see how the result was reached.

    streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from early_warning import SAMPLES, generate, run_agent
from early_warning.agent import DISCLAIMER
from early_warning.models import VITAL_INFO, VITALS, patient_from_dict
from early_warning.signals import baseline

load_dotenv()
st.set_page_config(page_title="Clinical Early-Warning Agent", layout="wide")

LEVEL_COLOR = {"Stable": "#15803d", "Watch": "#b45309", "Warning": "#c2410c", "Critical": "#b91c1c"}

with st.sidebar:
    st.header("Patient")
    mode = st.radio("Source", ["Sample patient", "Upload JSON"], label_visibility="collapsed")
    patient = None
    if mode == "Sample patient":
        name = st.selectbox("Sample", list(SAMPLES), index=list(SAMPLES).index("early_sepsis"),
                            format_func=lambda k: SAMPLES[k]["label"])
        patient = generate(name)
    else:
        upload = st.file_uploader("Patient JSON", type="json", help="See the README for the format.")
        if upload is not None:
            try:
                patient = patient_from_dict(json.load(upload))
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
                st.error(f"Could not read that file: {e}")

    st.header("Agent")
    api_key = st.text_input("Gemini API key", value=os.getenv("GEMINI_API_KEY", ""), type="password",
                            help="Leave empty to run offline: same tools, template explanation.")
    model = st.text_input("Model", value=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    offline = st.toggle("Offline (no LLM)", value=not api_key)
    run = st.button("Assess patient", type="primary", disabled=patient is None, use_container_width=True)

st.title("Clinical Early-Warning Agent")
st.caption("NEWS2 · qSOFA · personal baseline · trend — every number from a tested tool, explained by Gemini.")

if patient is None:
    st.info("Choose a sample patient or upload one in the sidebar.")
    st.stop()

st.subheader(patient.label)
st.write(f"Conditions: {', '.join(patient.conditions) or '—'} · {len(patient.readings)} readings · "
         f"NEWS2 SpO2 scale {patient.spo2_scale}")

if run:
    with st.spinner("The agent is calling its tools…"):
        st.session_state["result"] = (patient.id, run_agent(patient, api_key=api_key, model=model, offline=offline))

stored = st.session_state.get("result")
# Until the agent is run, show the tools' own assessment right away (instant, no API call).
result = stored[1] if stored and stored[0] == patient.id else run_agent(patient, offline=True)

if result:
    a, e = result.assessment, result.explanation
    color = LEVEL_COLOR[a["level"]]
    st.markdown(
        f"<div style='padding:14px 18px;border-radius:12px;background:{color}14;border:1px solid {color}55'>"
        f"<span style='font-size:28px;font-weight:700;color:{color}'>{a['level']}</span>"
        f"<span style='margin-left:12px;color:{color}'>score {a['score']}/100 · {a['urgency']}</span></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NEWS2", f"{a['news2']['total']} ({a['news2']['band']})")
    c2.metric("qSOFA", f"{a['qsofa']['score']}/3", "sepsis flag" if a["qsofa"]["sepsis_flag"] else None, delta_color="inverse")
    c3.metric("Off personal baseline", ", ".join(a["flagged_baselines"]) or "none")
    c4.metric("Drifting", ", ".join(a["flagged_trends"]) or "none")

    heading = f" · Gemini ({result.model})" if result.source == "gemini" else " · tools only (press Assess patient for the agent)"
    st.markdown("#### Assessment" + heading)
    st.write(e["clinician_summary"])
    for finding in e.get("key_findings", []):
        st.markdown(f"- {finding}")
    if e.get("patient_message"):
        st.markdown(f"**For the patient:** {e['patient_message']}")
    if result.note:
        st.warning(result.note)

    st.markdown("#### Contributing factors")
    if a["factors"]:
        st.dataframe(pd.DataFrame(a["factors"])[["points", "detail"]], hide_index=True, use_container_width=True)
    else:
        st.write("None — within this patient's own normal range.")

    if result.trace:
        with st.expander(f"Agent trace · {len(result.trace)} tool calls"):
            for call in result.trace:
                st.markdown(f"**{call['tool']}** {call['args'] or ''}")
                st.json(call["result"], expanded=False)

st.markdown("#### Last 12 hours against this patient's own normal")
st.caption("Solid: readings. Dashed: this patient's personal normal (7-day median, excluding the last 6 h).")
recent = [r for r in patient.readings if r.ts >= patient.latest.ts - timedelta(hours=12)]
cols = st.columns(len(VITALS))
for col, vital in zip(cols, VITALS, strict=True):
    info = VITAL_INFO[vital]
    frame = pd.DataFrame({"time": [r.ts for r in recent], "value": [r.get(vital) for r in recent]})
    line = alt.Chart(frame).mark_line(strokeWidth=1.5).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format="%H:%M", tickCount=4)),
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("time:T", format="%H:%M"), alt.Tooltip("value:Q", title=info["label"])],
    )
    b = baseline(patient.readings, vital)
    chart = line
    if b:
        chart = line + alt.Chart(pd.DataFrame({"normal": [b["mean"]]})).mark_rule(strokeDash=[4, 4], color="#64748b").encode(y="normal:Q")
    col.caption(f"{info['label']} ({info['unit']})")
    col.altair_chart(chart.properties(height=170), use_container_width=True)

st.caption(DISCLAIMER)
