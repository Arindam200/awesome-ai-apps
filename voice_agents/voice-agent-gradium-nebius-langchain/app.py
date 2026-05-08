from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from voice_pitch_coach.async_utils import run_async
from voice_pitch_coach.coach import NebiusPitchCoach
from voice_pitch_coach.gradium_audio import GradiumAudio
from voice_pitch_coach.settings import load_settings


st.set_page_config(page_title="PitchLoop Voice Coach", page_icon="🎙️", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --ink: oklch(0.21 0.02 250);
        --muted: oklch(0.48 0.03 250);
        --line: oklch(0.88 0.02 250);
        --paper: oklch(0.98 0.01 250);
        --panel: oklch(0.94 0.015 250);
        --blue: oklch(0.48 0.16 245);
        --green: oklch(0.60 0.13 155);
      }
      .main .block-container { padding-top: 2.2rem; max-width: 1180px; }
      .hero {
        border: 1px solid var(--line);
        background: linear-gradient(135deg, var(--paper), var(--panel));
        border-radius: 8px;
        padding: 32px;
        margin-bottom: 24px;
      }
      .hero h1 { color: var(--ink); font-size: 2.4rem; line-height: 1.05; margin: 0 0 10px; }
      .hero p { color: var(--muted); font-size: 1.02rem; max-width: 66ch; margin: 0; }
      .metric-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 18px;
        background: var(--paper);
      }
      .score { color: var(--blue); font-size: 2rem; font-weight: 750; }
      .small-label { color: var(--muted); font-size: .82rem; text-transform: uppercase; }
      div[data-testid="stButton"] button {
        border-radius: 6px;
        border: 1px solid oklch(0.50 0.15 245);
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_clients() -> tuple[GradiumAudio, NebiusPitchCoach]:
    settings = load_settings()
    return (
        GradiumAudio(
            api_key=settings.gradium_api_key,
            base_url=settings.gradium_base_url,
            voice_id=settings.gradium_voice_id,
        ),
        NebiusPitchCoach(api_key=settings.nebius_api_key, model=settings.nebius_model),
    )


def init_state() -> None:
    st.session_state.setdefault("turns", [])
    st.session_state.setdefault("next_question", "Give me your 45-second opening pitch.")


init_state()

st.markdown(
    """
    <div class="hero">
      <h1>PitchLoop Voice Coach</h1>
      <p>Practice a spoken pitch, interview answer, demo intro, or sales response. Gradium transcribes and speaks, while Nebius and LangChain coach the next turn.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Practice Setup")
    scenario = st.selectbox(
        "Scenario",
        ["startup pitch", "job interview", "product demo intro", "sales discovery", "conference talk"],
    )
    audience = st.text_input("Audience", value="early-stage investors")
    goal = st.text_area(
        "Goal",
        value="make the idea clear, sound credible, and earn a follow-up conversation",
        height=90,
    )
    st.caption("Free-tier friendly tip: keep recordings around 30-60 seconds.")
    if st.button("Reset session", use_container_width=True):
        st.session_state.turns = []
        st.session_state.next_question = "Give me your 45-second opening pitch."
        st.rerun()

left, right = st.columns([0.92, 1.08], gap="large")

with left:
    st.subheader("Coach Prompt")
    st.info(st.session_state.next_question)
    audio_value = st.audio_input("Record your answer", sample_rate=16000)
    uploaded = st.file_uploader("Or upload a WAV file", type=["wav"])
    audio_bytes = audio_value.getvalue() if audio_value is not None else None
    if uploaded is not None:
        audio_bytes = uploaded.getvalue()
        st.audio(audio_bytes, format="audio/wav")

    analyze = st.button("Analyze Voice Turn", type="primary", use_container_width=True)

with right:
    st.subheader("Session")
    if not st.session_state.turns:
        st.write("Your coaching turns will appear here after the first recording.")
    for idx, turn in enumerate(reversed(st.session_state.turns), start=1):
        result = turn["result"]
        with st.expander(f"Turn {len(st.session_state.turns) - idx + 1}: {result.overall_score}/100", expanded=idx == 1):
            st.markdown(f'<div class="score">{result.overall_score}/100</div>', unsafe_allow_html=True)
            cols = st.columns(5)
            for col, (label, value) in zip(cols, result.scores.model_dump().items()):
                col.metric(label.replace("_", " ").title(), value)
            st.write("**Transcript summary**")
            st.write(result.transcript_summary)
            st.write("**Strengths**")
            st.write("\n".join(f"- {item}" for item in result.strengths))
            st.write("**Improve next**")
            st.write("\n".join(f"- {item}" for item in result.improvements))
            st.write("**Tighter version**")
            st.write(result.suggested_rewrite)
            st.write("**Next question**")
            st.write(result.next_question)
            st.write("**Practice drill**")
            st.write(result.practice_drill)
            if turn.get("audio_path") and Path(turn["audio_path"]).exists():
                st.audio(Path(turn["audio_path"]).read_bytes(), format="audio/wav")

if analyze:
    if not audio_bytes:
        st.error("Record or upload a WAV file first.")
    else:
        try:
            gradium_audio, coach = get_clients()
            with st.status("Working through the voice turn...", expanded=True) as status:
                st.write("Transcribing with Gradium STT")
                transcript = run_async(gradium_audio.transcribe_wav(audio_bytes))
                if not transcript:
                    raise RuntimeError("Gradium returned an empty transcript.")

                st.write("Coaching with LangChain + Nebius")
                result = coach.analyze(
                    transcript=transcript,
                    scenario=scenario,
                    audience=audience,
                    goal=goal,
                    previous_question=st.session_state.next_question,
                )

                st.write("Creating spoken feedback with Gradium TTS")
                filename = f"coach-feedback-{datetime.now().strftime('%Y%m%d-%H%M%S')}.wav"
                audio_path = run_async(
                    gradium_audio.speak_to_file(
                        f"{result.spoken_feedback} {result.next_question}",
                        Path("outputs") / filename,
                    )
                )
                status.update(label="Coaching turn complete", state="complete", expanded=False)

            st.session_state.turns.append(
                {"transcript": transcript, "result": result, "audio_path": audio_path}
            )
            st.session_state.next_question = result.next_question
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
