import os
import time
import re
import streamlit as st

from dotenv import load_dotenv
from app.agents import save_to_db
from app.agents import (
    run_smartcrawler,
    run_searchscraper,
    research_agent,
    gtm_agent,
    channel_agent,
    fetch_all_data,
    fetch_reports_by_url,
    assemble_cached_combined,
    extract_company_name,
)


load_dotenv("api.env")

st.set_page_config(
    page_title="Smart GTM Agent", layout="wide", initial_sidebar_state="expanded"
)


# ================= UI Styling =================
st.markdown(
    """
<style>
.stApp { background-color: #0E1117; color: #FAFAFA; }
.main-header { font-size: 2.8rem; color: #00D4B1; text-align: center; font-weight: 800; margin-bottom: 0.2rem; letter-spacing: -0.5px; }
.sub-header { text-align: center; color: #888; margin-bottom: 2.5rem; font-size: 1.1rem; }
.stButton>button { width: 100%; background-color: #555555; color: #FAFAFA; border: none; padding: 0.8rem 1rem; border-radius: 8px; font-weight: 600; font-size: 1rem; margin-top: 1rem; }
.stButton>button:hover { background-color: #777777; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
.stTextInput>div>div>input { background-color: #262730; color: #FAFAFA; border: 1px solid #393946; border-radius: 8px; padding: 0.8rem; }
.stTextInput>div>div>input:focus { border-color: #00D4B1; box-shadow: 0 0 0 2px rgba(0, 212, 177, 0.2); }
.css-1d391kg, .css-1d391kg>div { background-color: #0E1117 !important; border-right: 1px solid #262730; }
.css-1d391kg h1,h2,h3,h4,h5,h6,p,label { color: #FAFAFA !important; }
.stProgress > div > div > div > div { background-color: #00D4B1; }
.streamlit-expanderHeader { background-color: #262730; color: #FAFAFA; border-radius: 8px; font-weight: 600; }
.streamlit-expanderContent { background-color: #1A1D25; border-radius: 0 0 8px 8px; }
.card { background-color: #262730; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00D4B1; }
.stRadio > div { background-color: #262730; padding: 1rem; border-radius: 8px; }
label { font-weight: 600 !important; margin-bottom: 0.5rem; display: block; color: #CCC !important; }
.main-title { font-size: 40px; font-weight: bold; display: flex; align-items: center; }
.main-title img { height: 50px; margin-left: 20px; vertical-align: middle; }
.subtitle { font-size: 20px; color: #AAAAAA; }
</style>
<div class="header">
  <div class="main-title">
    Smart GTM Agent With
    <img src="https://scrapegraphai.com/scrapegraphai_logo.svg" alt="ScrapeGraphAI Logo">
    <span style="margin-left:40px;">&</span>
    <img src="https://langchain-ai.github.io/langgraph/static/wordmark_dark.svg" alt="LangGraph Logo">
  </div>
  <div class="subtitle"> Professional market intelligence </div>
  <br>
</div>
""",
    unsafe_allow_html=True,
)


with st.sidebar:
    st.image("./assets/nebius.png", width=150)
    nebius_key = st.text_input(
        "Enter your Nebius API key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
    )
    smartcrawler_key = st.text_input(
        "Smartcrawler Key", value=os.getenv("SMARTCRAWLER_API_KEY", ""), type="password"
    )

    if st.button("💾 Save Keys"):
        st.session_state["NEBIUS_API_KEY"] = nebius_key
        st.session_state["SMARTCRAWLER_API_KEY"] = smartcrawler_key
    if nebius_key or smartcrawler_key:
        st.success("Keys saved for this session")

    st.markdown("---")
    st.subheader("History")
    try:
        recent = fetch_all_data()
        if recent:
            for rid, url, feature, created_at in recent[:2]:
                st.caption(f"{created_at} · {feature} · {url}")
        else:
            st.caption("No history yet.")
    except Exception:
        st.caption("History unavailable.")
    selected_feature = st.selectbox(
        "Selected Feature", ["None", "Research", "Go-to-Market", "Channel"]
    )
    st.markdown(
        """
    <div style='padding: 1rem; background-color: #262730; border-radius: 8px;'>
      <h4 style='margin-top: 0; color: #00D4B1;'>About</h4>
      <ul style='color: #AAA; margin-bottom: 0; padding-left: 1.2rem;'>
        <li><strong>Research:</strong> Company profile & competitors</li>
        <li><strong>GTM Strategy:</strong> Market size & opportunities</li>
        <li><strong>Channel:</strong> Partners & distribution insights</li>
        <li><strong>SmartCrawler:</strong> Automated data collection</li>
        <li><strong>LangGraph:</strong> Structured AI reasoning</li>
        <li><strong>Nebius:</strong> Fast & scalable execution</li>
      </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )

company = st.text_input(
    "🏢 **Company URL**", placeholder="e.g., https://www.studio1hq.com/..."
)
col_run1, col_run2 = st.columns([3, 2])
with col_run1:
    run_analysis = st.button("🚀 Analyze Company")
with col_run2:
    force_fresh = st.toggle(
        "Force fresh run", value=False, help="Bypass cached DB content and call APIs"
    )
entity_label = extract_company_name(company) if company else ""


# ================= Main Logic =================
if run_analysis and company:
    text_output = ""
    if selected_feature.lower() == "none":
        st.warning(
            "⚠️ Please select a valid feature (Research, Go-to-Market, or Channel) before running analysis."
        )
    else:
        # Try using cached DB content first unless forced fresh
        cached_combined = None if force_fresh else assemble_cached_combined(company)
        if cached_combined:
            st.info(
                "Using cached results from database. Disable 'Force fresh run' to save costs."
            )
            st.markdown(cached_combined, unsafe_allow_html=True)
            text_output = cached_combined
            combined_context = cached_combined
        else:
            # ---- Running SmartCrawler ----
            with st.status("🕷️ Running SmartCrawler...") as status:
                scrawler_result = run_smartcrawler(company)
                st.markdown(scrawler_result, unsafe_allow_html=True)
                status.text("✅ SmartCrawler completed! Saved to DB.")
                save_to_db(company, "smartcrawler", scrawler_result)

            # ---- Running SearchScraper ----
            with st.status("🔍 Running SearchScraper...") as status:
                search_result = run_searchscraper(company)
                st.markdown(search_result, unsafe_allow_html=True)
                status.text("✅ SearchScraper completed! Saved to DB.")
                save_to_db(company, "searchscraper", search_result)

            text_output = scrawler_result + "\n\n" + search_result
            combined_context = text_output

        if selected_feature.lower() == "research":
            st.markdown("## 📊 Research Agent Insights")
            try:
                response = research_agent.invoke(
                    {"messages": [("user", combined_context)]}
                )
                st.markdown(response["messages"][-1].content)
            except Exception as e:
                st.error(f"Research Agent failed: {e}")

        elif selected_feature.lower() == "go-to-market":
            st.markdown("## 🚀 GTM Agent Insights")
            try:
                response = gtm_agent.invoke({"messages": [("user", combined_context)]})
                st.markdown(response["messages"][-1].content)
            except Exception as e:
                st.error(f"GTM Agent failed: {e}")

        elif selected_feature.lower() == "channel":
            st.markdown("## 📡 Channel Agent Insights")
            try:
                response = channel_agent.invoke(
                    {"messages": [("user", combined_context)]}
                )
                st.markdown(response["messages"][-1].content)
            except Exception as e:
                st.error(f"Channel Agent failed: {e}")

        st.success(f"✅ Analysis of {company} completed successfully!")
