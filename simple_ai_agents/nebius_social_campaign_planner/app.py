"""Nebius-powered social campaign planner."""

from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langchain_nebius import ChatNebius

load_dotenv()

DEFAULT_MODEL = "zai-org/GLM-4.5-Air"


def build_campaign_prompt(
    product: str,
    audience: str,
    goal: str,
    channels: list[str],
    tone: str,
) -> str:
    """Build a structured prompt for a launch-ready social campaign."""
    channel_list = ", ".join(channels)
    return f"""
You are a senior social strategist. Build a practical social campaign for this
product using the requested channels.

Product:
{product}

Audience:
{audience}

Goal:
{goal}

Channels:
{channel_list}

Tone:
{tone}

Return valid JSON with these keys:
- positioning: one concise paragraph
- content_pillars: array of 4 pillar objects with name and angle
- posts: array of 6 objects with channel, hook, body, cta, and rationale
- seven_day_calendar: array of 7 objects with day, channel, post_theme, and task
- review_checklist: array of short safety and quality checks before publishing

Keep post bodies publishable, specific, and free of placeholders.
""".strip()


def parse_json_response(content: str) -> dict[str, Any]:
    """Parse JSON even when the model wraps it in Markdown fences."""
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    if text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return json.loads(text)


def generate_campaign(
    api_key: str,
    model: str,
    temperature: float,
    product: str,
    audience: str,
    goal: str,
    channels: list[str],
    tone: str,
) -> dict[str, Any]:
    """Call Nebius and return the parsed campaign plan."""
    llm = ChatNebius(api_key=api_key, model=model, temperature=temperature)
    prompt = build_campaign_prompt(product, audience, goal, channels, tone)
    response = llm.invoke(prompt)
    content = str(response.content)
    return parse_json_response(content)


def render_posts(posts: list[dict[str, Any]]) -> None:
    """Render generated social posts."""
    for post in posts:
        with st.container(border=True):
            st.caption(str(post.get("channel", "Channel")))
            st.subheader(str(post.get("hook", "Post")))
            st.write(str(post.get("body", "")))
            st.markdown(f"**CTA:** {post.get('cta', '')}")
            st.caption(str(post.get("rationale", "")))


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(page_title="Nebius Social Campaign Planner", page_icon="📣")
    st.title("Nebius Social Campaign Planner")
    st.write(
        "Turn a product brief into channel-specific posts, content pillars, "
        "and a 7-day launch calendar powered by Nebius."
    )

    with st.sidebar:
        st.header("Nebius")
        api_key = st.text_input(
            "NEBIUS_API_KEY",
            value=os.getenv("NEBIUS_API_KEY", ""),
            type="password",
        )
        model = st.text_input("Model", value=DEFAULT_MODEL)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.55, 0.05)

    with st.form("campaign_form"):
        product = st.text_area(
            "Product or launch brief",
            value=(
                "A developer tool that helps teams review pull requests faster "
                "with AI-generated risk summaries."
            ),
            height=120,
        )
        audience = st.text_input(
            "Target audience",
            value="Engineering managers and senior developers at SaaS teams",
        )
        goal = st.text_input(
            "Campaign goal",
            value="Drive waitlist signups for a private beta",
        )
        channels = st.multiselect(
            "Channels",
            ["X/Twitter", "LinkedIn", "Reddit", "Newsletter", "Product Hunt"],
            default=["X/Twitter", "LinkedIn", "Newsletter"],
        )
        tone = st.selectbox(
            "Tone",
            ["Clear and practical", "Founder-led", "Technical", "Playful"],
        )
        submitted = st.form_submit_button("Generate Campaign")

    if submitted:
        if not api_key:
            st.error("Add NEBIUS_API_KEY to generate a campaign.")
            return
        if not channels:
            st.error("Select at least 1 channel.")
            return

        with st.spinner("Generating campaign with Nebius..."):
            try:
                campaign = generate_campaign(
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    product=product,
                    audience=audience,
                    goal=goal,
                    channels=channels,
                    tone=tone,
                )
            except (json.JSONDecodeError, ValueError) as error:
                st.error(f"Nebius returned invalid JSON: {error}")
                return
            except Exception as error:  # noqa: BLE001
                st.error(f"Campaign generation failed: {error}")
                return

        st.header("Positioning")
        st.write(str(campaign.get("positioning", "")))

        st.header("Content Pillars")
        for pillar in campaign.get("content_pillars", []):
            st.markdown(
                f"- **{pillar.get('name', 'Pillar')}**: {pillar.get('angle', '')}"
            )

        st.header("Generated Posts")
        render_posts(campaign.get("posts", []))

        st.header("7-Day Calendar")
        st.dataframe(campaign.get("seven_day_calendar", []), use_container_width=True)

        st.header("Review Checklist")
        for item in campaign.get("review_checklist", []):
            st.checkbox(str(item), value=False)


if __name__ == "__main__":
    main()
