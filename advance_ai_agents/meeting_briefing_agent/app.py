"""Briefing Room — Streamlit UI for the pre-meeting intel agent."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from graph import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MODEL,
    TavilySearchError,
    build_graph,
    build_model,
    build_search,
    initial_state,
)

ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_FILE)

st.set_page_config(page_title="Briefing Room — Pre-Meeting Intel Agent", layout="wide")


def _exception_chain_contains(error: Exception, error_type: type[Exception]) -> bool:
    """Return whether an exception or one of its causes has the requested type."""
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, error_type):
            return True
        current = current.__cause__ or current.__context__
    return False


def _is_authentication_error(error: Exception) -> bool:
    """Recognize authentication failures across OpenAI-compatible clients."""
    current: BaseException | None = error
    while current is not None:
        message = str(current).lower()
        status_code = getattr(current, "status_code", None)
        if status_code == 401 or "authenticate" in message or "unauthorized" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


def _merge_stream_update(state: dict, update: dict) -> dict:
    """Merge streamed updates without replacing previously collected evidence."""
    non_evidence = {
        key: value for key, value in update.items() if key != "evidence"
    }
    merged = {**state, **non_evidence}
    if "evidence" in update:
        merged["evidence"] = [
            *state.get("evidence", []),
            *update.get("evidence", []),
        ]
    return merged


MODEL_CHOICES = [
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "Qwen/Qwen3.5-397B-A17B",
    "deepseek-ai/DeepSeek-V4-Pro",
    "zai-org/GLM-5.2",
]

NODE_LABELS = {
    "plan": "🧭 Planning research questions",
    "research": "🔎 Searching the web with Tavily",
    "reflect": "🧐 Checking coverage for gaps",
    "write": "✍️ Writing the brief",
}

st.title("🗂️ Briefing Room")
st.markdown(
    "Give it a **company** (and optionally an **attendee**) and get a one-page, "
    "cited pre-meeting brief: what to know, what to ask, and what to avoid. "
    "Built with **LangGraph**, **Tavily**, and **Nebius Token Factory**."
)

# --------------------------------------------------------------------------- #
# Sidebar — configuration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Configuration")
    env_nebius_key = os.getenv("NEBIUS_API_KEY", "").strip()
    env_tavily_key = os.getenv("TAVILY_API_KEY", "").strip()

    # Keep .env authoritative while preserving the original editable,
    # password-masked sidebar fields.
    if env_nebius_key:
        st.session_state.nebius_api_key = env_nebius_key
    if env_tavily_key:
        st.session_state.tavily_api_key = env_tavily_key

    nebius_key = st.text_input(
        "Nebius API Key",
        key="nebius_api_key",
        type="password",
        help="Nebius Token Factory key (loaded from .env when configured).",
    )
    tavily_key = st.text_input(
        "Tavily API Key",
        key="tavily_api_key",
        type="password",
        help="Tavily key (loaded from .env when configured).",
    )
    model = st.selectbox(
        "Model (via Nebius Token Factory)",
        MODEL_CHOICES,
        index=MODEL_CHOICES.index(
            os.getenv("NEBIUS_MODEL", DEFAULT_MODEL))
        if os.getenv("NEBIUS_MODEL", DEFAULT_MODEL) in MODEL_CHOICES
        else 0,
    )
    max_iterations = st.slider(
        "Max research passes",
        min_value=1,
        max_value=3,
        value=DEFAULT_MAX_ITERATIONS,
        help="How many reflect→research loops the graph may take before writing.",
    )
    st.divider()
    st.caption(
        "Tip: set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` to watch "
        "every graph step live in LangSmith."
    )

# --------------------------------------------------------------------------- #
# Main inputs
# --------------------------------------------------------------------------- #
col1, col2 = st.columns(2)
with col1:
    company = st.text_input("Company *", placeholder="e.g. LangChain")
with col2:
    attendee = st.text_input(
        "Attendee (optional)",
        placeholder="e.g. Harrison Chase, CEO",
    )
user_context = st.text_area(
    "Your context / goal (optional)",
    placeholder=(
        "e.g. We sell observability tooling and want to pitch a partnership."
    ),
    height=80,
)

run = st.button(
    "🚀 Generate brief",
    type="primary",
    disabled=not company.strip(),
)

if "result" not in st.session_state:
    st.session_state.result = None

if run:
    nebius_key = nebius_key.strip()
    tavily_key = tavily_key.strip()
    if not nebius_key or not tavily_key:
        st.error("Please provide both the Nebius and Tavily API keys (sidebar or .env).")
        st.stop()

    llm = build_model(
        model=model,
        base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=nebius_key,
    )
    search = build_search(api_key=tavily_key)
    graph = build_graph(llm, search)
    state = initial_state(
        company=company,
        attendee=attendee,
        user_context=user_context,
        max_iterations=max_iterations,
    )

    progress = st.status("Starting the briefing graph…", expanded=True)
    final_state = dict(state)
    try:
        for chunk in graph.stream(state, stream_mode="updates"):
            for node, update in chunk.items():
                final_state = _merge_stream_update(final_state, update)
                label = NODE_LABELS.get(node, node)
                if node == "plan":
                    progress.write(
                        f"{label} — "
                        f"{len(update.get('sub_questions', []))} questions queued"
                    )
                elif node == "research":
                    progress.write(
                        f"{label} — "
                        f"{len(update.get('evidence', []))} new sources"
                    )
                elif node == "reflect":
                    gaps = update.get("gaps", [])
                    note = (
                        f"gaps found, looping back ({len(gaps)} follow-ups)"
                        if gaps
                        else "coverage looks good"
                    )
                    progress.write(f"{label} — {note}")
                elif node == "write":
                    progress.write(f"{label}")
        progress.update(label="✅ Brief ready", state="complete", expanded=False)
    except Exception as error:
        progress.update(label="❌ Run failed", state="error")
        if _exception_chain_contains(error, TavilySearchError):
            if _is_authentication_error(error):
                st.error(
                    "Tavily authentication failed. Re-enter a valid Tavily API key "
                    "in the sidebar, then try again."
                )
            else:
                st.error(f"Tavily search failed: {error}")
        elif _is_authentication_error(error):
            st.error(
                "Nebius authentication failed. Re-enter a valid Nebius Token "
                "Factory API key in the sidebar, then try again."
            )
        else:
            st.error(f"The graph run failed: {error}")
        st.stop()

    st.session_state.result = final_state

# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
result = st.session_state.result
if result and result.get("brief"):
    brief_tab, evidence_tab = st.tabs(
        [
            "📄 Brief",
            f"🔬 Evidence ({len(result.get('evidence', []))} sources)",
        ]
    )
    with brief_tab:
        st.markdown(result["brief"])
        st.download_button(
            "⬇️ Download brief (Markdown)",
            data=result["brief"],
            file_name=(
                f"briefing_{result['company'].lower().replace(' ', '_')}.md"
            ),
            mime="text/markdown",
        )
    with evidence_tab:
        rows = [
            {
                "#": index,
                "Question": evidence["question"],
                "Title": evidence["title"],
                "URL": evidence["url"],
            }
            for index, evidence in enumerate(
                result.get("evidence", []),
                start=1,
            )
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
elif not run:
    st.info(
        "Enter a company above and hit **Generate brief**. The agent will plan "
        "research questions, search the web, reflect on gaps, and write a cited brief."
    )
