import os
import re

import httpx
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

CF_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
MAX_CONTENT_CHARS = 12_000


def get_client(account_id: str, api_token: str) -> OpenAI:
    return OpenAI(
        api_key=api_token,
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
    )


def fetch_page_text(url: str) -> str:
    """Fetch a webpage and return its plain text (strips HTML tags)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; WebpageAnalyzer/1.0)"}
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
    resp.raise_for_status()
    text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CONTENT_CHARS]


def analyze(url: str, content: str, focus: str, client: OpenAI) -> str:
    system = (
        "You are an expert web content analyst. "
        "Analyze the provided webpage content and give structured, actionable insights. "
        "Use markdown with headers and bullet points."
    )

    prompts = {
        "Summary & Key Points": (
            f"Analyze this webpage ({url}) and provide:\n"
            "## Summary\nA 3-sentence overview of what this page is about.\n\n"
            "## Key Points\n5 most important takeaways from the content.\n\n"
            "## Target Audience\nWho this page is written for.\n\n"
            "## Tone\nThe writing tone and style used."
        ),
        "SEO Analysis": (
            f"Perform an SEO analysis of this webpage ({url}) and provide:\n"
            "## Primary Keywords\nThe main keywords this page seems to target.\n\n"
            "## Content Quality\nIs the content comprehensive and valuable?\n\n"
            "## Readability\nHow readable is the content (grade level, sentence length)?\n\n"
            "## SEO Recommendations\nTop 5 improvements to boost search rankings."
        ),
        "Competitive Intelligence": (
            f"Analyze this webpage ({url}) from a competitive intelligence perspective:\n"
            "## Value Proposition\nWhat unique value does this page/product offer?\n\n"
            "## Strengths\nWhat this page does well.\n\n"
            "## Weaknesses\nGaps or areas that could be improved.\n\n"
            "## Opportunities\nHow a competitor could differentiate."
        ),
        "Content Gaps": (
            f"Review this webpage ({url}) and identify:\n"
            "## What's Covered\nMain topics addressed.\n\n"
            "## Missing Topics\nImportant related topics not mentioned.\n\n"
            "## Questions Left Unanswered\nQuestions a reader might still have.\n\n"
            "## Suggested Additions\nContent that would make this page more complete."
        ),
    }

    user_msg = f"{prompts[focus]}\n\n---\nPage content:\n{content}"

    response = client.chat.completions.create(
        model=CF_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=1500,
    )
    return response.choices[0].message.content


# ── UI ────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Webpage Analyzer Agent", page_icon="🔍", layout="wide")

st.title("🔍 Webpage Analyzer Agent")
st.caption(
    "Paste any URL and get instant AI-powered analysis using "
    "**Llama 3.3 70B on Cloudflare Workers AI**."
)

with st.sidebar:
    st.header("🔑 Cloudflare Credentials")
    account_id = st.text_input(
        "Account ID",
        value=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
        help="dash.cloudflare.com → right sidebar",
    )
    api_token = st.text_input(
        "API Token",
        type="password",
        value=os.getenv("CLOUDFLARE_API_TOKEN", ""),
        help="My Profile → API Tokens → Workers AI template",
    )

col1, col2 = st.columns([3, 1])
with col1:
    url = st.text_input(
        "Webpage URL",
        placeholder="https://example.com/blog/some-article",
    )
with col2:
    focus = st.selectbox(
        "Analysis Type",
        ["Summary & Key Points", "SEO Analysis", "Competitive Intelligence", "Content Gaps"],
    )

if st.button("🔍 Analyse", type="primary", use_container_width=True):
    if not account_id or not api_token:
        st.error("Enter your Cloudflare credentials in the sidebar.")
    elif not url.strip():
        st.error("Enter a URL to analyse.")
    else:
        with st.spinner(f"Fetching and analysing {url}…"):
            try:
                content = fetch_page_text(url.strip())
                client = get_client(account_id, api_token)
                result = analyze(url.strip(), content, focus, client)
                st.markdown("---")
                st.markdown(result)
                with st.expander("📄 Raw page content used"):
                    st.text(content[:2000] + ("…" if len(content) > 2000 else ""))
            except httpx.HTTPStatusError as e:
                st.error(f"Could not fetch page: HTTP {e.response.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
