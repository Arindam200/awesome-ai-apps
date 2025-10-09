import os

from dotenv import load_dotenv
import asyncio
import base64
import main as validator_main
import nest_asyncio
import streamlit as st
nest_asyncio.apply()

st.set_page_config(page_title="Startup Idea Validator Agent", layout="wide")

load_dotenv()


with open("./assets/adk.png", "rb") as adk_file:
    adk_base64 = base64.b64encode(adk_file.read()).decode()

with open("./assets/tavily.png", "rb") as tavily_file:
    tavily_base64 = base64.b64encode(tavily_file.read()).decode()

    # Create title with embedded images
    title_html = f"""
    <div style="display: flex;  width: 100%; ">
        <h1 style="margin: 0; padding: 0; font-size: 2.5rem; font-weight: bold;">
            <span style="font-size:2.5rem;">🏢</span> Startup Idea Validator with
            <img src="data:image/png;base64,{adk_base64}" style="height: 80px; vertical-align: middle; bottom: 10px;"/>
            <span style="">Google ADK</span> &
            <img src="data:image/png;base64,{tavily_base64}" style="height: 60px; vertical-align: middle; bottom: 5px;"/>
        </h1>
    </div>
    """
    st.markdown(title_html, unsafe_allow_html=True)
st.markdown("**Discover the perfect startup ideas with AI-powered validation and comprehensive analysis capabilities**")

with st.sidebar:
    st.image("./assets/Nebius.png", width=150)
    nebius_key = st.text_input("Enter your Nebius API key", value=os.getenv("NEBIUS_API_KEY", ""), type="password")

    tavily_key = st.text_input("Enter your Tavily API key", value=os.getenv("TAVILY_API_KEY", ""), type="password")

    if st.button("Save Keys", use_container_width=True):
        if nebius_key:
            os.environ["NEBIUS_API_KEY"] = nebius_key
        if tavily_key:
            os.environ["TAVILY_API_KEY"] = tavily_key
        st.success("API keys saved successfully!")
    st.markdown("---")
    st.header("About")
    st.markdown(
        """
        This application is powered by a set of advanced AI agents for startup idea validation and analysis:
        - **Idea Clarifier**: Refines and clarifies your startup idea.
        - **Market Researcher**: Analyzes market potential, size, and customer segments.
        - **Competitor Analyst**: Evaluates competitors and market positioning.
        - **Report Generator**: Synthesizes all findings into a comprehensive validation report.

        Each stage leverages state-of-the-art language models and tools to provide actionable, data-driven insights.
        """
    )
    st.markdown("---")
    st.markdown(
        "Developed with ❤️ by [Arindam Majumder](https://www.youtube.com/c/Arindam_1729)"
    )

idea = st.chat_input("Type your message...")

# Async runner for validation using nest_asyncio
def run_validation_sync(idea):

    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(validator_main.run_validation(idea))
        return result
    except Exception as e:
        return f"Error: {e}"

if idea:
    with st.spinner("Validating your startup idea. Please wait..."):
        summary = run_validation_sync(idea)
        st.markdown("---")
        # st.markdown("## 📝 Validation Report")
        st.markdown(summary)