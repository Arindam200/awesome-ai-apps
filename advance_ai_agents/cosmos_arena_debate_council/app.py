"""Cosmos Arena - Debate Council (Streamlit UI).

Streams a LangGraph-orchestrated debate turn by turn: each council member's
argument appears in its own color-coded card under the round it belongs to, and
the Arbiter's verdict lands in a highlighted panel at the end. The engine hands
the UI clean, structured turns (see cosmos_council.py), so there is no report
parsing here -- the UI just renders what each member actually said.
"""

import base64
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from cosmos_council import (
    DEFAULT_MODEL,
    MEMBERS,
    build_debate_graph,
    build_model,
    initial_state,
)

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

st.set_page_config(
    page_title="Cosmos Arena · Debate Council",
    page_icon="🪐",
    layout="centered",
)

# --- Council look: speaker -> (avatar, caption, accent color) ---------------
STYLE = {
    "proponent": ("🟢", "FOR the motion", "#16a34a"),
    "opponent": ("🔴", "AGAINST the motion", "#dc2626"),
    "pragmatist": ("🟡", "Independent reality check", "#d97706"),
    "judge": ("⚖️", "The verdict", "#8b5cf6"),
}


def meta(speaker: str) -> tuple[str, str, str, str]:
    avatar, caption, color = STYLE.get(speaker, ("🗳️", "Statement", "#64748b"))
    name = MEMBERS.get(speaker, {}).get("name", speaker.title())
    return name, avatar, caption, color


# --- Session state ----------------------------------------------------------
st.session_state.setdefault("debate", None)
st.session_state.setdefault("motion", "")


# --- Styling ----------------------------------------------------------------
st.markdown(
    """
    <style>
    .resolution { background: linear-gradient(135deg, #0b1220 0%, #1e293b 100%);
        border: 1px solid #334155; border-radius: 14px; padding: 18px 22px;
        margin: 8px 0 14px; }
    .resolution .lbl { color: #74B71B; font-size: 12px; font-weight: 800;
        letter-spacing: 2px; }
    .resolution .txt { color: #e2e8f0; font-size: 20px; font-weight: 600;
        line-height: 1.45; margin-top: 6px; }
    .member { border: 1px solid #2a2a3a; border-radius: 12px; padding: 14px 10px;
        text-align: center; height: 100%; background: #11131a; }
    .member .ava { font-size: 26px; }
    .member .nm { font-weight: 700; margin-top: 6px; font-size: 15px; }
    .member .rl { color: #94a3b8; font-size: 11px; margin-top: 3px; line-height: 1.3; }
    .round-pill { display: inline-block; background: #74B71B; color: #0a0a0a;
        font-weight: 800; letter-spacing: 1px; padding: 5px 16px; border-radius: 999px;
        font-size: 13px; margin: 20px 0 6px; }
    .speaker { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .speaker .ava { font-size: 22px; }
    .speaker .nm { font-weight: 700; font-size: 17px; }
    .speaker .badge { padding: 3px 12px; border-radius: 999px; font-size: 12px;
        font-weight: 600; }
    .speaker .state { color: #94a3b8; font-size: 12px; margin-left: auto;
        font-style: italic; }
    .turn-body { min-height: 24px; }
    div[class*="st-key-card-proponent"] { border-left: 5px solid #16a34a !important;
        background: rgba(22,163,74,0.05) !important; }
    div[class*="st-key-card-opponent"] { border-left: 5px solid #dc2626 !important;
        background: rgba(220,38,38,0.05) !important; }
    div[class*="st-key-card-pragmatist"] { border-left: 5px solid #d97706 !important;
        background: rgba(217,119,6,0.05) !important; }
    div[class*="st-key-card-judge"] { border-left: 5px solid #8b5cf6 !important;
        background: rgba(139,92,246,0.07) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Header with NVIDIA logo ------------------------------------------------
def _logo(name: str) -> str:
    path = APP_DIR / "assets" / name
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode()


nvidia_b64 = _logo("nvidia-color.png")
nvidia_img = (
    f'<img src="data:image/png;base64,{nvidia_b64}" style="height:52px;">'
    if nvidia_b64
    else ""
)
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:12px;">
        {nvidia_img}
        <h1 style="margin:0; line-height:1.1;">
            <span style="color:#74B71B;">Cosmos Arena</span> · Debate Council
        </h1>
    </div>
    <p style="color:#94a3b8; margin:6px 0 0;">
        A multi-agent debate council orchestrated with <b>LangGraph</b> and
        powered by <b>NVIDIA Cosmos</b> on <b>Nebius Token Factory</b>.
    </p>
    """,
    unsafe_allow_html=True,
)


# --- Rendering primitives ---------------------------------------------------
def speaker_header(speaker: str, state: str = "") -> str:
    name, avatar, caption, color = meta(speaker)
    state_html = f'<span class="state">{state}</span>' if state else ""
    return (
        f'<div class="speaker"><span class="ava">{avatar}</span>'
        f'<span class="nm">{name}</span>'
        f'<span class="badge" style="background:{color}26;color:{color};">{caption}</span>'
        f"{state_html}</div>"
    )


def stream_text(slot, text: str, chunk: int = 6, delay: float = 0.01) -> None:
    """Type text into a placeholder for a live feel, then settle on markdown."""
    text = text or "_(no statement returned)_"
    words = text.split(" ")
    shown = ""
    for i in range(0, len(words), chunk):
        shown += " ".join(words[i:i + chunk]) + " "
        slot.markdown(shown)
        time.sleep(delay)
    slot.markdown(text)


class Card:
    """A stable, color-coded card for one speaker, opened before its content."""

    def __init__(self, speaker: str, index: int):
        self.speaker = speaker
        self.box = st.container(border=True, key=f"card-{speaker}-{index}")
        with self.box:
            self.header = st.empty()
            self.body = st.empty()
            self.reasoning = st.empty()
        self.header.markdown(speaker_header(speaker, "weighing the arguments…"),
                             unsafe_allow_html=True)
        self.body.markdown(
            '<div class="turn-body" style="color:#94a3b8;">Taking the floor…</div>',
            unsafe_allow_html=True,
        )

    def complete(self, text: str, reasoning: str = "", live: bool = True) -> None:
        self.header.markdown(speaker_header(self.speaker), unsafe_allow_html=True)
        if live:
            stream_text(self.body, text)
        else:
            self.body.markdown(text or "_(no statement returned)_")
        if reasoning:
            with self.reasoning.expander("🧠 Show reasoning"):
                st.markdown(reasoning)


def render_motion(motion: str) -> None:
    st.markdown(
        f'<div class="resolution"><span class="lbl">THE MOTION</span>'
        f'<div class="txt">{motion}</div></div>',
        unsafe_allow_html=True,
    )


def render_roster(use_pragmatist: bool) -> None:
    speakers = ["proponent", "opponent"]
    if use_pragmatist:
        speakers.append("pragmatist")
    speakers.append("judge")
    for col, speaker in zip(st.columns(len(speakers)), speakers):
        name, avatar, caption, _ = meta(speaker)
        col.markdown(
            f'<div class="member"><div class="ava">{avatar}</div>'
            f'<div class="nm">{name}</div><div class="rl">{caption}</div></div>',
            unsafe_allow_html=True,
        )


def section_header(speaker: str, rnd: int, last_round: list[int]) -> None:
    """Emit the round pill / section title that precedes a speaker, if needed."""
    if speaker in ("proponent", "opponent") and rnd != last_round[0]:
        last_round[0] = rnd
        st.markdown(f'<span class="round-pill">ROUND {rnd}</span>',
                    unsafe_allow_html=True)
    elif speaker == "pragmatist":
        st.markdown("#### 🔍 Independent Reality Check")
    elif speaker == "judge":
        st.markdown("### ⚖️ The Arbiter's Verdict")


def plan_speakers(rounds: int, use_pragmatist: bool) -> list[tuple[str, int]]:
    """The deterministic order in which council members take the floor."""
    order: list[tuple[str, int]] = []
    for rnd in range(1, rounds + 1):
        order.append(("proponent", rnd))
        order.append(("opponent", rnd))
    if use_pragmatist:
        order.append(("pragmatist", 0))
    order.append(("judge", 0))
    return order


# --- Running the debate -----------------------------------------------------
def run_debate(graph, motion: str, plan: list[tuple[str, int]]) -> dict:
    render_motion(motion)
    render_roster(any(s == "pragmatist" for s, _ in plan))
    st.markdown("### 🎙️ The Debate Floor")

    status = st.status("The council is convening…", expanded=True)
    last_round = [0]
    turns: list[tuple[str, int, str, str]] = []

    def open_card(idx: int) -> Card:
        speaker, rnd = plan[idx]
        section_header(speaker, rnd, last_round)
        name = meta(speaker)[0]
        status.update(label=f"{name} is taking the floor…")
        return Card(speaker, idx)

    idx = 0
    card = open_card(idx)
    for update in graph.stream(
        initial_state(motion), config={"recursion_limit": 60}, stream_mode="updates"
    ):
        delta = next(iter(update.values()))
        new_turns = delta.get("transcript") if isinstance(delta, dict) else None
        if not new_turns:  # e.g. the increment_round bookkeeping step
            continue
        turn = new_turns[-1]
        card.complete(turn["text"], turn["reasoning"], live=True)
        turns.append((turn["speaker"], turn["round"], turn["text"], turn["reasoning"]))
        idx += 1
        if idx < len(plan):
            card = open_card(idx)

    status.update(label="Debate concluded.", state="complete", expanded=False)
    return {"motion": motion, "turns": turns}


def render_saved(debate: dict) -> None:
    render_motion(debate["motion"])
    render_roster(any(s == "pragmatist" for s, _, _, _ in debate["turns"]))
    st.markdown("### 🎙️ The Debate Floor")
    last_round = [0]
    for idx, (speaker, rnd, text, reasoning) in enumerate(debate["turns"]):
        section_header(speaker, rnd, last_round)
        Card(speaker, idx).complete(text, reasoning, live=False)


def download_button(debate: dict) -> None:
    parts = [f"# Cosmos Arena · Debate Council\n\n> {debate['motion']}\n"]
    for speaker, rnd, text, _ in debate["turns"]:
        name = meta(speaker)[0]
        tag = f" — Round {rnd}" if rnd else ""
        parts.append(f"## {name}{tag}\n\n{text}")
    st.download_button(
        "⬇️ Download debate (Markdown)",
        data="\n\n".join(parts),
        file_name="cosmos_arena_debate.md",
        mime="text/markdown",
        use_container_width=True,
    )


# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    nebius_logo = APP_DIR / "assets" / "Nebius.png"
    if nebius_logo.exists():
        st.image(str(nebius_logo), width=150)

    nebius_api_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius Token Factory API key.",
    )
    st.divider()
    st.subheader("Debate Settings")
    rounds = st.slider("Debate rounds", 1, 4, 2,
                       help="Round 1 is opening statements; later rounds are rebuttals.")
    use_pragmatist = st.toggle("Include The Pragmatist", value=True,
                               help="An independent member who stress-tests both sides.")
    model_name = st.text_input("Model", value=os.getenv("COSMOS_MODEL", DEFAULT_MODEL),
                               help="NVIDIA reasoning model served by Nebius Token Factory.")
    st.markdown("---")
    st.markdown("Made with ❤️ by Arindam Majumder")


# --- Motion input -----------------------------------------------------------
st.markdown(
    "Enter a **motion** and convene the council. Each member argues in turn, the "
    "rounds thread real rebuttals, and The Arbiter delivers a scored verdict."
)

EXAMPLES = [
    "This house believes AGI will arrive before 2035.",
    "This house believes remote work makes engineering teams more productive.",
]
for col, example in zip(st.columns(2), EXAMPLES):
    if col.button(example, use_container_width=True):
        st.session_state.motion = example
        st.rerun()

motion = st.text_area(
    "Debate motion",
    key="motion",
    placeholder="e.g. This house believes open-source AI models do more good than harm.",
    height=90,
)
run = st.button("🪐 Convene the Council", type="primary", use_container_width=True)


# --- Main flow --------------------------------------------------------------
if run:
    if not motion or not motion.strip():
        st.warning("Please enter a motion for the council to debate.")
        st.stop()
    api_key = nebius_api_key or os.getenv("NEBIUS_API_KEY")
    if not api_key:
        st.error("Missing Nebius API key. Add it in the sidebar.")
        st.stop()

    try:
        model = build_model(api_key=api_key, model=model_name)
        graph = build_debate_graph(model, rounds=rounds, use_pragmatist=use_pragmatist)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to initialize the council: {exc}")
        st.stop()

    try:
        plan = plan_speakers(rounds, use_pragmatist)
        debate = run_debate(graph, motion.strip(), plan)
        st.session_state.debate = debate
        download_button(debate)
    except Exception as exc:  # noqa: BLE001
        st.error(f"The debate failed: {exc}")
        st.stop()

elif st.session_state.debate:
    debate = st.session_state.debate
    render_saved(debate)
    download_button(debate)

else:
    st.markdown(
        """
This app stages a structured, multi-round debate as an explicit **LangGraph** state machine:

- 🟢 **The Advocate** argues *for* the motion; 🔴 **The Skeptic** argues *against* — rebutting each other every round.
- 🟡 **The Pragmatist** is an independent member who stress-tests both sides *(optional)*.
- ⚖️ **The Arbiter** scores the debate and delivers an impartial verdict.

Each member is its own graph node and model call, and every node reasons with
**`nvidia/Cosmos3-Super-Reasoner`** served by **Nebius Token Factory**.
"""
    )
