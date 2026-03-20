import os
import re

import streamlit as st

from agents import run_due_diligence

st.set_page_config(
    page_title="Due Diligence Agent",
    page_icon="🏢",
    layout="wide",
)

st.title("Due Diligence Agent")
st.markdown(
    "A multi-stage AI pipeline powered by **AG2** that researches a company across "
    "6 dimensions: team, investors, press, financials, tech stack, and social signals."
)

with st.sidebar:
    st.header("Configuration")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()

    st.header("About")
    st.markdown(
        """
    This agent runs a 4-stage pipeline using AG2 ConversableAgents:
    1. **Seed Crawler** - Extracts company profile from URL
    2. **6 Specialist Agents** - Research team, investors, press, financials, tech, social (in parallel)
    3. **Validator** - Cross-checks for contradictions and gaps
    4. **Synthesis** - Produces a final due diligence report
    """
    )

company_url = st.text_input(
    "Company URL",
    placeholder="https://example.com",
    help="Enter the company website URL to research",
)

if st.button("Run Due Diligence", type="primary", disabled=not company_url):
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    with st.status("Running due diligence pipeline...", expanded=True) as status:
        status.write("**Stage 1:** Crawling company website for initial profile...")

        try:
            output_dir, report = run_due_diligence(company_url)

            status.write("**Stage 2:** Running 6 specialist agents in parallel...")
            status.write("**Stage 3:** Validating collected data...")
            status.write("**Stage 4:** Synthesizing final report...")
            status.update(label="Due diligence complete!", state="complete")
        except Exception as e:
            status.update(label="Pipeline failed", state="error")
            st.error(f"An error occurred: {e}")
            st.stop()

    st.success(f"Report saved to `{output_dir}/`")

    # Clean up markdown fences if present
    cleaned_report = re.sub(r"^```(?:[a-zA-Z]*)?\n?", "", report)
    cleaned_report = re.sub(r"\n?```$", "", cleaned_report)
    st.markdown(cleaned_report, unsafe_allow_html=True)
