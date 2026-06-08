"""Streamlit UI for the Nebius travel planner."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import DEFAULT_MODEL, build_agent

load_dotenv()


def _secret_or_env(name: str, default: str = "") -> str:
    env_value = os.getenv(name, default)
    try:
        return st.secrets.get(name, env_value)
    except Exception:  # noqa: BLE001 - Streamlit raises when secrets are absent.
        return env_value


def _compose_trip_prompt(
    *,
    destination: str,
    origin: str,
    start: date,
    end: date,
    travelers: int,
    budget: float,
    currency: str,
    style: str,
    interests: list[str],
    constraints: str,
) -> str:
    nights = max((end - start).days, 0)
    days = nights + 1
    interest_text = ", ".join(interests) if interests else "local highlights"
    budget_text = f"{budget:,.0f} {currency}" if budget > 0 else "not specified"
    constraint_text = constraints.strip() or "No hard constraints."
    origin_text = origin.strip() or "not specified"
    return f"""Build a travel plan with these details:

Destination: {destination}
Origin: {origin_text}
Dates: {start.isoformat()} to {end.isoformat()} ({days} days, {nights} nights)
Travelers: {travelers}
Budget ceiling: {budget_text}
Preferred currency: {currency}
Travel style: {style}
Interests: {interest_text}
Constraints: {constraint_text}

Please research the destination, check weather, estimate the budget, and return:
1. Key assumptions
2. Best base neighborhood or area
3. Weather and packing notes
4. Day-by-day itinerary
5. Food and local transport suggestions
6. Budget breakdown against the budget ceiling
7. Risks, booking cautions, and next follow-up questions
"""


def _sample_prompts() -> dict[str, str]:
    return {
        "Tokyo first-timer": (
            "Plan a 5-day first trip to Tokyo in October for two people. "
            "We like food markets, design shops, train-friendly days, and one "
            "easy day trip. Keep it standard comfort and show costs in USD."
        ),
        "Lisbon remote-work week": (
            "Create a 7-day Lisbon plan for one remote worker in May. I need "
            "good cafe neighborhoods, low-stress evenings, a weekend Sintra day, "
            "and budget estimates in EUR."
        ),
        "Family Kerala route": (
            "Build a 6-day Kerala itinerary for a family of four from Bengaluru. "
            "Prioritize nature, low travel fatigue, monsoon-aware planning, and "
            "show a budget in INR."
        ),
    }


st.set_page_config(page_title="VoyageCompass", page_icon=":airplane:", layout="wide")
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 6.5rem;
    }
    h1 {
        padding-bottom: 0.1rem;
    }
    h3 {
        padding-top: 0.5rem;
    }
    [data-testid="stForm"] {
        border: 1px solid rgba(49, 51, 63, 0.16);
        border-radius: 8px;
        padding: 0.85rem 1.1rem 1rem;
    }
    div[data-testid="stForm"]:has(input[aria-label="Ask for a trip plan or a follow-up refinement..."]) {
        position: fixed;
        left: 300px;
        right: 0;
        top: auto;
        bottom: 0;
        z-index: 999;
        width: calc(100vw - 300px) !important;
        max-width: none !important;
        box-sizing: border-box;
        height: auto !important;
        min-height: 0 !important;
        background: var(--background-color);
        border-top: 1px solid rgba(49, 51, 63, 0.12);
        border-left: 0;
        border-right: 0;
        border-bottom: 0;
        border-radius: 0;
        padding: 0.75rem max(5rem, 8vw) 0.85rem;
    }
    @media (max-width: 760px) {
        div[data-testid="stForm"]:has(input[aria-label="Ask for a trip plan or a follow-up refinement..."]) {
            left: 0;
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("VoyageCompass Travel Planner")
st.caption("Streamlit + LangChain + Nebius ChatNebius")

with st.sidebar:
    st.header("Nebius")
    sidebar_api_key = st.text_input(
        "API key",
        value="",
        type="password",
        help="Optional. Leave blank to use NEBIUS_API_KEY from .env or Streamlit secrets.",
    )
    api_key = sidebar_api_key or _secret_or_env("NEBIUS_API_KEY")
    model_name = st.text_input("Model", value=_secret_or_env("NEBIUS_MODEL", DEFAULT_MODEL))
    temperature = st.slider("Creativity", min_value=0.0, max_value=1.0, value=0.25, step=0.05)
    if api_key:
        st.success("Nebius API key found.")
    else:
        st.warning("Set NEBIUS_API_KEY to run the planner.")

    st.divider()
    st.header("Examples")
    for label, prompt in _sample_prompts().items():
        if st.button(label, use_container_width=True):
            st.session_state.pending_prompt = prompt

    st.divider()
    if st.button("Reset chat", use_container_width=True):
        for key in ("messages", "history", "agent", "agent_config", "pending_prompt"):
            st.session_state.pop(key, None)
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

with st.expander("Trip brief", expanded=True):
    with st.form("trip_brief"):
        destination_col, origin_col, style_col = st.columns([1.2, 1.0, 0.8])
        with destination_col:
            destination = st.text_input("Destination", value="Kyoto, Japan")
        with origin_col:
            origin = st.text_input("Origin", value="")
        with style_col:
            style = st.selectbox(
                "Travel style",
                ["budget", "standard", "comfort", "premium", "backpacker"],
                index=1,
            )

        today = date.today()
        default_start = today + timedelta(days=45)
        default_end = default_start + timedelta(days=4)
        date_col, end_col, traveler_col, currency_col, budget_col = st.columns(
            [1.0, 1.0, 0.8, 0.7, 1.0]
        )
        with date_col:
            start = st.date_input("Start date", value=default_start)
        with end_col:
            end = st.date_input("End date", value=default_end)
        with traveler_col:
            travelers = st.number_input("Travelers", min_value=1, max_value=12, value=2, step=1)
        with currency_col:
            currency = st.text_input("Currency", value="USD", max_chars=3).upper()
        with budget_col:
            budget = st.number_input("Budget ceiling", min_value=0.0, value=2500.0, step=100.0)

        interests_col, constraints_col = st.columns([1.0, 1.35])
        with interests_col:
            interests = st.multiselect(
                "Interests",
                [
                    "food",
                    "museums",
                    "nature",
                    "nightlife",
                    "shopping",
                    "history",
                    "family-friendly",
                    "day trips",
                    "remote work",
                    "wellness",
                ],
                default=["food", "history", "day trips"],
            )
        with constraints_col:
            constraints = st.text_area(
                "Constraints",
                placeholder="Mobility needs, dietary limits, pace, must-see places, avoidances...",
                height=72,
            )
        submitted = st.form_submit_button("Build itinerary", use_container_width=True)

if submitted:
    if end < start:
        st.error("End date must be on or after start date.")
    elif not destination.strip():
        st.error("Enter a destination.")
    else:
        st.session_state.pending_prompt = _compose_trip_prompt(
            destination=destination,
            origin=origin,
            start=start,
            end=end,
            travelers=int(travelers),
            budget=float(budget),
            currency=currency or "USD",
            style=style,
            interests=interests,
            constraints=constraints,
        )

st.divider()

if not api_key:
    st.info("Add a Nebius API key in the sidebar, .env, or Streamlit secrets.")
    if "pending_prompt" in st.session_state:
        st.warning(
            "Add a Nebius API key before building the itinerary. Your trip brief is ready to send."
        )
    with st.form("fixed_chat_bar_disabled", clear_on_submit=True):
        chat_col, send_col = st.columns([0.84, 0.16])
        with chat_col:
            st.text_input(
                "Ask for a trip plan or a follow-up refinement...",
                disabled=True,
                label_visibility="collapsed",
                placeholder="Ask for a trip plan or a follow-up refinement...",
            )
        with send_col:
            st.form_submit_button("Send", disabled=True, use_container_width=True)
else:
    agent_config = (model_name, float(temperature), bool(api_key))
    if (
        "agent" not in st.session_state
        or st.session_state.get("agent_config") != agent_config
    ):
        with st.spinner("Starting Nebius planner..."):
            st.session_state.agent = build_agent(
                api_key=api_key,
                model_name=model_name,
                temperature=float(temperature),
                debug=False,
            )
            st.session_state.agent_config = agent_config

    response_area = st.container(border=False)
    with response_area:
        if st.session_state.messages:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        else:
            st.info("Build an itinerary from the trip brief or ask a follow-up below.")

    manual_prompt = ""
    with st.form("fixed_chat_bar", clear_on_submit=True):
        chat_col, send_col = st.columns([0.84, 0.16])
        with chat_col:
            manual_prompt = st.text_input(
                "Ask for a trip plan or a follow-up refinement...",
                label_visibility="collapsed",
                placeholder="Ask for a trip plan or a follow-up refinement...",
            )
        with send_col:
            manual_submitted = st.form_submit_button("Send", use_container_width=True)

    prompt = st.session_state.pop("pending_prompt", None) or (
        manual_prompt if manual_submitted else None
    )
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        with response_area:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Researching and planning..."):
                    try:
                        turn_messages = st.session_state.history + [("human", prompt)]
                        result = st.session_state.agent.invoke({"messages": turn_messages})
                        answer = result["messages"][-1].content
                    except Exception as exc:  # noqa: BLE001
                        answer = f"Planner failed: {exc}"
                    st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.history.extend([("human", prompt), ("ai", answer)])
        st.rerun()
