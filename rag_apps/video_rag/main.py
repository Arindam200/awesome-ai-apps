"""Streamlit UI for Video RAG: Gemini native multimodal embeddings + Weaviate + Nebius."""

from __future__ import annotations

import os
import re
import tempfile

import streamlit as st
from dotenv import load_dotenv

from ingest import ingest_video
from rag import ask

load_dotenv()


def check_env() -> list[str]:
    required = ["NEBIUS_API_KEY", "GEMINI_API_KEY"]
    return [k for k in required if not os.getenv(k)]


def ts_to_seconds(ts: str) -> int:
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def main() -> None:
    st.set_page_config(page_title="Video RAG (Gemini + Weaviate + Nebius)", layout="wide")
    st.title("Video RAG")
    st.caption("Native multimodal video search with Gemini embeddings, Weaviate, and Nebius Token Factory.")

    missing = check_env()
    if missing:
        st.error(f"Missing environment variables: {', '.join(missing)}")
        st.stop()

    for key, default in {
        "video_id": None,
        "video_path": None,
        "ingested": False,
        "messages": [],
        "last_seek": 0,
        "model_id": "Qwen/Qwen3-235B-A22B",
    }.items():
        st.session_state.setdefault(key, default)

    with st.sidebar:
        st.header("Ingest")
        st.session_state.model_id = st.selectbox(
            "Answer model",
            ["Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3", "meta-llama/Meta-Llama-3.1-70B-Instruct"],
            index=0,
        )
        clip_sec = st.slider("Clip length (sec)", 10.0, 60.0, 20.0, step=5.0)
        top_k = st.slider("Top-K clips", 3, 15, 8)
        uploaded = st.file_uploader("Upload video", type=["mp4", "mov", "mkv", "webm"])

        if uploaded and st.button("Ingest video", type="primary"):
            suffix = os.path.splitext(uploaded.name)[1] or ".mp4"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.getbuffer())
            tmp.close()
            st.session_state.video_path = tmp.name
            with st.spinner("Splitting into clips and embedding with Gemini... this can take a few minutes."):
                stats = ingest_video(tmp.name, clip_sec=clip_sec)
            st.session_state.video_id = stats["video_id"]
            st.session_state.ingested = True
            st.session_state.messages = []
            st.success(f"Indexed {stats['clips']} clips (video_id={stats['video_id']}).")

    col_video, col_chat = st.columns([1, 1])

    with col_video:
        st.subheader("Video")
        if st.session_state.video_path:
            st.video(st.session_state.video_path, start_time=st.session_state.last_seek)
        else:
            st.info("Upload and ingest a video to begin.")

    with col_chat:
        st.subheader("Ask the video")
        if not st.session_state.ingested:
            st.info("Ingest a video first.")
            return

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        query = st.chat_input("Ask about what is said or shown...")
        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("Retrieving and answering..."):
                    answer, hits = ask(
                        query,
                        video_id=st.session_state.video_id,
                        top_k=top_k,
                        model_id=st.session_state.model_id,
                    )
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

                timestamps = re.findall(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", answer)
                unique_ts = []
                for t in timestamps:
                    if t not in unique_ts:
                        unique_ts.append(t)
                if unique_ts:
                    st.caption("Jump to:")
                    cols = st.columns(min(len(unique_ts), 6))
                    for i, ts in enumerate(unique_ts[:12]):
                        if cols[i % len(cols)].button(ts, key=f"seek_{len(st.session_state.messages)}_{i}"):
                            st.session_state.last_seek = ts_to_seconds(ts)
                            st.rerun()

                with st.expander("Retrieved clips"):
                    for h in hits:
                        st.markdown(f"- **[{h['timestamp']}]** score `{h['score']}` — `{h['clip_path']}`")


if __name__ == "__main__":
    main()
