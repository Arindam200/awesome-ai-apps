import streamlit as st
import asyncio
import os
import logging
import nest_asyncio
import base64
from dotenv import load_dotenv
from job_agents import run_analysis
from mcp_server import wait_for_initialization, get_mcp_server

nest_asyncio.apply()
load_dotenv()

logger = logging.getLogger(__name__)

# Set page config
st.set_page_config(
    page_title="LinkedIn Profile Analyzer",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = ""
if 'is_analyzing' not in st.session_state:
    st.session_state.is_analyzing = False

async def analyze_profile(linkedin_url: str):
    try:
        if not await wait_for_initialization():
            st.error("Failed to initialize MCP server")
            return
            
        result = await run_analysis(get_mcp_server(), linkedin_url)
        st.session_state.analysis_result = result
    except Exception as e:
        logger.error(f"Error analyzing LinkedIn profile: {str(e)}")
        st.error(f"Error analyzing LinkedIn profile: {str(e)}")
    finally:
        st.session_state.is_analyzing = False

def main():
    # Load and encode images
    with open("./assets/bright-data-logo.png", "rb") as bright_data_file:
        bright_data_base64 = base64.b64encode(bright_data_file.read()).decode()       
    
    # Create title with embedded images
    title_html = f"""
    <div style="display: flex; align-items: center; gap: 0px; margin: 0; padding: 0;">
        <h1 style="margin: 0; padding: 0;">
        Job Searcher Agent with 
        <img src="data:image/png;base64,{bright_data_base64}" style="height: 110px; margin: 0; padding: 0;"/>
        </h1>
    </div>
    """
    st.markdown(title_html, unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.image("./assets/Nebius.png", width=150)
        api_key = st.text_input("Enter your API key", type="password")
        st.divider()
        
        st.subheader("Enter LinkedIn Profile URL")
        linkedin_url = st.text_input("LinkedIn URL", placeholder="https://www.linkedin.com/in/username/")
        
        if st.button("Analyze Profile", type="primary", disabled=st.session_state.is_analyzing):
            if not linkedin_url:
                st.error("Please enter a LinkedIn profile URL")
                return
            if not api_key:
                st.error("Please enter your API key")
                return

            st.session_state.is_analyzing = True
            st.session_state.analysis_result = ""
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(analyze_profile(linkedin_url))
            finally:
                loop.close()

    # Results section
    if st.session_state.analysis_result:
        st.subheader("Analysis Results")
        st.markdown(st.session_state.analysis_result)

    # Loading state
    if st.session_state.is_analyzing:
        st.markdown("---")
        with st.spinner("Analyzing profile... This may take a few minutes."):
            st.empty()

if __name__ == "__main__":
    main()