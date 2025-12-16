"""
YouTube Trend Analysis Agent with Memori, Agno (Nebius), and YouTube scraping.

Streamlit app:
- Sidebar: API keys + YouTube channel URL + "Ingest channel into Memori" button.
- Main: Chat interface to ask about trends and get new video ideas.

This app uses:
- Nebius (via both the OpenAI SDK and Agno's Nebius model) for LLM reasoning.
- yt-dlp to scrape YouTube channel/playlist videos.
- Memori to store and search your channel's video history.
"""

import base64
import os

import streamlit as st
from agno.agent import Agent
from agno.models.nebius import Nebius
from dotenv import load_dotenv

from core import fetch_exa_trends, ingest_channel_into_memori


def _load_inline_image(path: str, height_px: int) -> str:
    """Return an inline <img> tag for a local PNG, or empty string on failure."""
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return (
            f"<img src='data:image/png;base64,{encoded}' "
            f"style='height:{height_px}px; width:auto; display:inline-block; "
            f"vertical-align:middle; margin:0 8px;' alt='Logo'>"
        )
    except Exception:
        return ""


def main():
    load_dotenv()

    # Page config
    st.set_page_config(
        page_title="YouTube Trend Analysis Agent",
        layout="wide",
    )

    # Branded title with Memori logo (reusing the pattern from AI Consultant Agent)
    memori_img_inline = _load_inline_image(
        "assets/Memori_Logo.png",
        height_px=85,
    )
    title_html = f"""
<div style='display:flex; align-items:center; width:120%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.2rem; font-weight:800; display:flex; align-items:center; gap:10px;'>
    <span>YouTube Trend Analysis Agent with</span>
    {memori_img_inline}
  </h1>
</div>
"""
    st.markdown(title_html, unsafe_allow_html=True)

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # Memori/OpenAI client will be initialized lazily when needed.

    # Sidebar
    with st.sidebar:
        st.subheader("🔑 API Keys & Channel")

        # Nebius logo above the Nebius API key field
        try:
            st.image("assets/Nebius_Logo.png", width=120)
        except Exception:
            # Non-fatal if the logo is missing
            pass

        nebius_api_key_input = st.text_input(
            "Nebius API Key",
            value=os.getenv("NEBIUS_API_KEY", ""),
            type="password",
            help="Your Nebius API key (used for both Memori and Agno).",
        )

        exa_api_key_input = st.text_input(
            "Exa API Key (optional)",
            value=os.getenv("EXA_API_KEY", ""),
            type="password",
            help="Used to fetch external web trends via Exa AI when suggesting new ideas.",
        )

        memori_api_key_input = st.text_input(
            "Memori API Key (optional)",
            value=os.getenv("MEMORI_API_KEY", ""),
            type="password",
            help="Used for Memori Advanced Augmentation and higher quotas.",
        )

        channel_url_input = st.text_input(
            "YouTube channel / playlist URL",
            placeholder="https://www.youtube.com/@YourChannel",
        )

        if st.button("Save Settings"):
            if nebius_api_key_input:
                os.environ["NEBIUS_API_KEY"] = nebius_api_key_input
            if exa_api_key_input:
                os.environ["EXA_API_KEY"] = exa_api_key_input
            if memori_api_key_input:
                os.environ["MEMORI_API_KEY"] = memori_api_key_input

            st.success("✅ API keys saved for this session.")

        st.markdown("---")

        if st.button("Ingest channel into Memori"):
            if not os.getenv("NEBIUS_API_KEY"):
                st.warning("NEBIUS_API_KEY is required before ingestion.")
            elif not channel_url_input.strip():
                st.warning("Please enter a YouTube channel or playlist URL.")
            else:
                with st.spinner(
                    "📥 Scraping channel and ingesting videos into Memori…"
                ):
                    count = ingest_channel_into_memori(channel_url_input.strip())
                st.success(f"✅ Ingested {count} video(s) into Memori.")

        st.markdown("---")
        st.markdown("### 💡 About")
        st.markdown(
            """
            This agent:

            - Scrapes your **YouTube channel** directly from YouTube using yt-dlp.
            - Stores video metadata & summaries in **Memori**.
            - Uses **Exa** and your channel info stored in **Memori** to surface trends and new video ideas.
            """
        )

    # Get keys for main app logic
    nebius_key = os.getenv("NEBIUS_API_KEY", "")
    if not nebius_key:
        st.warning(
            "⚠️ Please enter your Nebius API key in the sidebar to start chatting!"
        )
        st.stop()

    # Initialize Nebius model for the advisor (once)
    if "nebius_model" not in st.session_state:
        try:
            st.session_state.nebius_model = Nebius(
                id=os.getenv(
                    "YOUTUBE_TREND_MODEL",
                    "moonshotai/Kimi-K2-Instruct",
                ),
                api_key=nebius_key,
            )
        except Exception as e:
            st.error(f"Failed to initialize Nebius model: {e}")
            st.stop()

    # Display chat history
    st.markdown(
        "<h2 style='margin-top:0;'>YouTube Trend Chat</h2>",
        unsafe_allow_html=True,
    )
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    prompt = st.chat_input("Ask about your channel trends or new video ideas…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤔 Analyzing your channel memories…"):
                try:
                    # Build context from Memori (if available) and from cached channel videos
                    memori_context = ""
                    mem = st.session_state.get("memori")
                    if mem is not None and hasattr(mem, "search"):
                        try:
                            results = mem.search(prompt, limit=5)
                            if results:
                                memori_context = (
                                    "\n\nRelevant snippets from your channel history:\n"
                                    + "\n".join(f"- {r}" for r in results)
                                )
                        except Exception as e:
                            st.warning(f"Memori search issue: {e}")

                    videos = st.session_state.get("channel_videos") or []
                    video_summaries = ""
                    if videos:
                        video_summaries_lines = []
                        for v in videos[:10]:
                            title = v.get("title") or "Untitled video"
                            topics = v.get("topics") or []
                            topics_str = ", ".join(topics) if topics else "N/A"
                            views = v.get("views") or "Unknown"
                            desc = v.get("description") or ""
                            if len(desc) > 120:
                                desc_snip = desc[:120].rstrip() + "…"
                            else:
                                desc_snip = desc
                            video_summaries_lines.append(
                                f"- {title} | topics: {topics_str} | views: {views} | desc: {desc_snip}"
                            )
                        video_summaries = (
                            "\n\nRecent videos on this channel:\n"
                            + "\n".join(video_summaries_lines)
                        )

                    channel_name = (
                        st.session_state.get("channel_title") or "this YouTube channel"
                    )

                    exa_trends = ""
                    # Fetch or reuse Exa-based trend context, if Exa is configured
                    if os.getenv("EXA_API_KEY") and videos:
                        if "exa_trends" in st.session_state:
                            exa_trends = st.session_state["exa_trends"]
                        else:
                            exa_trends = fetch_exa_trends(channel_name, videos)
                            st.session_state["exa_trends"] = exa_trends

                    full_prompt = f"""You are a YouTube strategy assistant analyzing the channel '{channel_name}'.

You have access to a memory store of the user's past videos (titles, topics, views).
Use that memory to:
- Identify topics and formats that perform well on the channel.
- Suggest concrete, fresh video ideas aligned with those trends.
- Optionally point out gaps or under-explored themes.

Always be specific and actionable (titles, angles, hooks, examples), but ONLY answer what the user actually asks.
Do NOT provide long, generic strategy plans unless the user explicitly asks for them.

User question:
{prompt}

Memory context (may be partial):
{memori_context}

Channel metadata from recent scraped videos (titles, topics, views):
{video_summaries}

External web trends for this niche (may be partial):
{exa_trends}
"""

                    advisor = Agent(
                        name="YouTube Trend Advisor",
                        model=st.session_state.nebius_model,
                        markdown=True,
                    )

                    result = advisor.run(full_prompt)
                    response_text = (
                        str(result.content)
                        if hasattr(result, "content")
                        else str(result)
                    )

                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    st.markdown(response_text)
                except Exception as e:
                    err = f"❌ Error generating answer: {e}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": err}
                    )
                    st.error(err)


if __name__ == "__main__":
    main()
