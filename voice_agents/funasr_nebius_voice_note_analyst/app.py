import hashlib
import json
from pathlib import Path
from typing import Any

import streamlit as st

from voice_note_analyst.clients import (
    FunASRClient,
    NebiusBriefClient,
    ProviderError,
    build_transcriptions_url,
)
from voice_note_analyst.models import VoiceNoteBrief
from voice_note_analyst.settings import (
    load_funasr_settings,
    load_nebius_api_key,
    load_nebius_settings,
)


APP_DIR = Path(__file__).resolve().parent
AUDIO_TYPES = ["wav", "mp3", "m4a", "flac", "ogg", "webm"]
LANGUAGES = {
    "Auto detect": "auto",
    "Chinese": "zh",
    "Cantonese": "yue",
    "English": "en",
    "Japanese": "ja",
    "Korean": "ko",
}


st.set_page_config(
    page_title="FunASR + Nebius Voice Note Analyst",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --paper: #f7f8f5;
        --surface: #ffffff;
        --ink: #17211f;
        --muted: #586461;
        --line: #d8ddda;
        --teal: #006b64;
        --red: #b83a32;
    }
    [data-testid="stAppViewContainer"] {
        background: var(--paper);
        color: var(--ink);
    }
    [data-testid="stHeader"] {
        background: var(--paper);
        min-height: 0;
        height: 0;
    }
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"],
    [data-testid="stDecoration"] {
        display: none !important;
    }
    .block-container {
        max-width: 1240px;
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
    }
    h1, h2, h3, p, label, button, input, textarea {
        letter-spacing: 0 !important;
    }
    h1 {
        color: var(--ink);
        font-size: 2rem !important;
        line-height: 1.2 !important;
        text-align: center;
    }
    h2, h3 {
        color: var(--ink);
        font-size: 1.1rem !important;
        line-height: 1.35 !important;
    }
    [data-testid="stImage"] img {
        max-height: 72px;
        width: auto;
        object-fit: contain;
    }
    [data-testid="stImage"] button {
        display: none !important;
    }
    [data-testid="stHorizontalBlock"] {
        gap: 1.5rem;
    }
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-baseweb="input"],
    [data-baseweb="select"] > div,
    textarea,
    button {
        border-radius: 6px !important;
    }
    [data-testid="stButton"] button p {
        white-space: nowrap;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: var(--surface);
        border-color: var(--line);
        border-radius: 6px;
    }
    [data-testid="stTextArea"] textarea,
    [data-testid="stTextInput"] input {
        background: var(--surface);
        color: var(--ink);
    }
    [data-testid="stText"],
    [data-testid="stText"] * {
        font-family: inherit !important;
        overflow-wrap: anywhere !important;
        white-space: pre-wrap !important;
        word-break: break-word;
    }
    [data-testid="stButton"] button[kind="primary"] {
        background: var(--teal);
        border-color: var(--teal);
    }
    [data-testid="stDownloadButton"] button {
        border-color: var(--teal);
        color: var(--teal);
    }
    [data-testid="stAlert"] {
        border-radius: 6px;
    }
    hr {
        border-color: var(--line);
    }
    @media (max-width: 640px) {
        .block-container {
            padding: 0.75rem 1rem 2rem;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        [data-testid="stImage"] img {
            max-height: 44px;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 0.75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _reset_analysis_state() -> None:
    for key in (
        "transcript_editor",
        "detected_language",
        "brief",
        "transcribed_audio_fingerprint",
    ):
        st.session_state.pop(key, None)


def _clear_brief() -> None:
    st.session_state["brief"] = None


def _clear_transcription() -> None:
    st.session_state["transcript_editor"] = ""
    st.session_state["detected_language"] = None
    st.session_state["brief"] = None
    st.session_state["transcribed_audio_fingerprint"] = None


def _audio_payload(uploaded: Any, recorded: Any) -> tuple[bytes, str, str | None] | None:
    selected = uploaded if uploaded is not None else recorded
    if selected is None:
        return None
    filename = getattr(selected, "name", None) or "recording.wav"
    content_type = getattr(selected, "type", None)
    return selected.getvalue(), filename, content_type


def _render_brief(brief: VoiceNoteBrief) -> None:
    st.subheader("Brief")
    st.markdown("**Summary**")
    st.text(brief.summary)

    st.markdown("**Key points**")
    for point in brief.key_points:
        st.text(f"- {point}")

    st.markdown("**Action items**")
    if brief.action_items:
        for index, item in enumerate(brief.action_items, start=1):
            st.text(
                f"{index}. {item.task}\n"
                f"Owner: {item.owner or 'Not specified'}\n"
                f"Due: {item.due or 'Not specified'}"
            )
    else:
        st.write("No action items")

    st.markdown("**Follow-up message**")
    st.text(brief.follow_up_message)
    serialized = json.dumps(brief.model_dump(mode="json"), ensure_ascii=False, indent=2)
    st.download_button(
        "Download brief",
        data=serialized,
        file_name="voice-note-brief.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )


try:
    funasr_settings = load_funasr_settings()
except ValueError as exc:
    st.error(str(exc))
    st.stop()
nebius_api_key = load_nebius_api_key()

for state_key, initial_value in (
    ("transcript_editor", ""),
    ("detected_language", None),
    ("brief", None),
    ("transcribed_audio_fingerprint", None),
    ("funasr_status", "not checked"),
):
    if state_key not in st.session_state:
        st.session_state[state_key] = initial_value

funasr_logo, app_title, nebius_logo = st.columns(
    [1, 5, 1],
    vertical_alignment="center",
)
with funasr_logo:
    st.image(str(APP_DIR / "assets" / "funasr-logo.png"), width=112)
with app_title:
    st.title("FunASR + Nebius Voice Note Analyst")
with nebius_logo:
    st.image(str(APP_DIR / "assets" / "nebius.png"), width=92)

st.divider()
transcription_column, analysis_column = st.columns([1, 1], gap="large")

with transcription_column:
    st.subheader("1. Transcription")
    recorded_audio = st.audio_input("Record a voice note")
    uploaded_audio = st.file_uploader("Upload audio", type=AUDIO_TYPES)
    selected_language = st.selectbox("Language", list(LANGUAGES))
    audio_payload = _audio_payload(uploaded_audio, recorded_audio)
    audio_fingerprint = (
        hashlib.sha256(audio_payload[0]).hexdigest() if audio_payload is not None else None
    )
    previous_fingerprint = st.session_state["transcribed_audio_fingerprint"]
    if previous_fingerprint is not None and previous_fingerprint != audio_fingerprint:
        _clear_transcription()
    endpoint_status = st.empty()
    endpoint = build_transcriptions_url(funasr_settings.funasr_base_url)
    endpoint_status.caption(
        f"ASR endpoint: {endpoint} | Status: {st.session_state['funasr_status']}"
    )

    if audio_payload is not None:
        audio_bytes, _, content_type = audio_payload
        st.audio(audio_bytes, format=content_type)

    transcribe_clicked = st.button(
        "Transcribe",
        type="primary",
        icon=":material/transcribe:",
        disabled=audio_payload is None,
        width="stretch",
    )
    if transcribe_clicked and audio_payload is not None:
        audio_bytes, filename, _ = audio_payload
        _clear_transcription()
        try:
            with st.spinner("Transcribing"):
                with FunASRClient(
                    base_url=funasr_settings.funasr_base_url,
                    model=funasr_settings.funasr_model,
                    api_key=funasr_settings.funasr_api_key,
                    timeout_seconds=funasr_settings.funasr_timeout_seconds,
                ) as client:
                    transcription = client.transcribe(
                        audio_bytes,
                        filename=filename,
                        language=LANGUAGES[selected_language],
                    )
            st.session_state["transcript_editor"] = transcription.text
            st.session_state["detected_language"] = transcription.language
            st.session_state["brief"] = None
            st.session_state["transcribed_audio_fingerprint"] = audio_fingerprint
            st.session_state["funasr_status"] = "ready"
            endpoint_status.caption(f"ASR endpoint: {endpoint} | Status: ready")
        except (ValueError, ProviderError) as exc:
            st.session_state["funasr_status"] = "error"
            endpoint_status.caption(f"ASR endpoint: {endpoint} | Status: error")
            st.error(str(exc))

with analysis_column:
    analysis_title, reset_column = st.columns([3, 1], vertical_alignment="center")
    with analysis_title:
        st.subheader("2. Transcript and brief")
    with reset_column:
        if st.button(
            "Reset",
            icon=":material/restart_alt:",
            help="Reset transcript and brief",
            width="stretch",
        ):
            _reset_analysis_state()
            st.rerun()

    transcript = st.text_area(
        "Transcript",
        key="transcript_editor",
        height=220,
        on_change=_clear_brief,
    )
    if st.session_state["detected_language"]:
        st.caption(f"Detected language: {st.session_state['detected_language']}")
    if transcript.strip():
        st.download_button(
            "Download transcript",
            data=transcript,
            file_name="transcript.txt",
            mime="text/plain",
            icon=":material/download:",
            width="stretch",
        )

    entered_nebius_key = st.text_input(
        "Nebius API key (optional)",
        type="password",
        value="",
        autocomplete="off",
    )
    active_nebius_key = entered_nebius_key.strip() or nebius_api_key
    generate_clicked = st.button(
        "Generate brief",
        icon=":material/auto_awesome:",
        disabled=not transcript.strip() or not active_nebius_key,
        width="stretch",
    )
    if generate_clicked:
        try:
            nebius_settings = load_nebius_settings()
            with st.spinner("Generating brief"):
                with NebiusBriefClient(
                    api_key=active_nebius_key,
                    base_url=nebius_settings.nebius_base_url,
                    model=nebius_settings.nebius_model,
                    timeout_seconds=nebius_settings.nebius_timeout_seconds,
                ) as brief_client:
                    generated_brief = brief_client.create_brief(transcript)
            st.session_state["brief"] = generated_brief.model_dump(mode="json")
        except (ValueError, ProviderError) as exc:
            st.error(str(exc))

    if st.session_state["brief"] is not None:
        _render_brief(VoiceNoteBrief.model_validate(st.session_state["brief"]))
