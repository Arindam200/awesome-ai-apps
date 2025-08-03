"""
Candilyzer: AI-powered candidate analyzer for elite technical hiring.

This Streamlit application leverages the Agno AI Agent Orchestration Framework to conduct
forensic-level multi-candidate and single-candidate analysis using verified GitHub and LinkedIn data.

Agents are powered by Nebius and enhanced with Agno’s GitHubTools, ExaTools, ThinkingTools,
and ReasoningTools — enabling strict, professional-grade hiring decisions with full traceability.
"""

import re
import yaml
import streamlit as st

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.github import GithubTools
from agno.tools.exa import ExaTools
from agno.tools.thinking import ThinkingTools
from agno.tools.reasoning import ReasoningTools

# Set wide layout
st.set_page_config(layout="wide")

# Load YAML prompts
@st.cache_data
def load_yaml(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        st.error("❌ YAML prompt file not found.")
        st.stop()
    except yaml.YAMLError as e:
        st.error(f"❌ YAML parsing error: {e}")
        st.stop()

data = load_yaml("hiring_prompts.yaml")
description_multi = data.get("description_for_multi_candidates", "")
instructions_multi = data.get("instructions_for_multi_candidates", "")
description_single = data.get("description_for_single_candidate", "")
instructions_single = data.get("instructions_for_single_candidate", "")

# Header
st.markdown("""
    <div style="text-align:center;">
        <h1 style="font-size: 2.8rem;">🧠 Candilyzer</h1>
        <p style="font-size:1.1rem;">Elite GitHub + LinkedIn Candidate Analyzer for Tech Hiring</p>
    </div>
""", unsafe_allow_html=True)

# Session state init
for key in ["Nebius_api_key",  "model_id", "github_api_key", "exa_api_key"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# Sidebar
st.sidebar.title("🔑 API Keys & Navigation")
st.sidebar.markdown("### Enter API Keys")
st.session_state.Nebius_api_key = st.sidebar.text_input("Nebius API Key", value=st.session_state.Nebius_api_key, type="password")
st.session_state.model_id = st.sidebar.text_input("Model ID", value=st.session_state.model_id)
st.session_state.github_api_key = st.sidebar.text_input("GitHub API Key", value=st.session_state.github_api_key, type="password")
st.session_state.exa_api_key = st.sidebar.text_input("Exa API Key", value=st.session_state.exa_api_key, type="password")
st.sidebar.markdown("---")
page = st.sidebar.radio("Select Page", ("Multi-Candidate Analyzer", "Single Candidate Analyzer"))

# ---------------- Multi-Candidate Analyzer ---------------- #
if page == "Multi-Candidate Analyzer":
    st.header("Multi-Candidate Analyzer 🕵️‍♂️")
    st.markdown("Enter multiple GitHub usernames (one per line) and a target job role.")

    with st.form("multi_candidate_form"):
        github_usernames = st.text_area("GitHub Usernames (one per line)", placeholder="username1\nusername2\n...")
        job_role = st.text_input("Target Job Role", placeholder="e.g. Backend Engineer")
        submit = st.form_submit_button("Analyze Candidates")

    if submit:
        if not github_usernames or not job_role:
            st.error("❌ Please enter both usernames and job role.")
        elif not all([st.session_state.Nebius_api_key, st.session_state.github_api_key, st.session_state.exa_api_key, st.session_state.model_id]):
            st.error("❌ Please enter all API keys and model info in the sidebar.")
        else:
            usernames = [u.strip() for u in github_usernames.split("\n") if u.strip()]
            if not usernames:
                st.error("❌ Enter at least one valid GitHub username.")
            else:
                agent = Agent(
                    description=description_multi,
                    instructions=instructions_multi,
                    model=Nebius(
                        id=st.session_state.model_id,
                        api_key=st.session_state.Nebius_api_key,
                    ),
                    name="StrictCandidateEvaluator",
                    tools=[
                        ThinkingTools(think=True, instructions="Strict GitHub candidate evaluation"),
                        GithubTools(access_token=st.session_state.github_api_key),
                        ExaTools(api_key=st.session_state.exa_api_key, include_domains=["github.com"], type="keyword"),
                        ReasoningTools(add_instructions=True)
                    ],
                    markdown=True,
                    show_tool_calls=True
                )

                st.markdown("### 🔎 Evaluation in Progress...")
                with st.spinner("Running detailed analysis..."):
                    query = f"Evaluate GitHub candidates for role '{job_role}': {', '.join(usernames)}"
                    stream = agent.run(query, stream=True)

                    output = ""
                    block = st.empty()
                    for chunk in stream:
                        if hasattr(chunk, "content") and isinstance(chunk.content, str):
                            output += chunk.content
                            block.markdown(output, unsafe_allow_html=True)

# ---------------- Single Candidate Analyzer ---------------- #
elif page == "Single Candidate Analyzer":
    st.header("Single Candidate Analyzer")
    st.markdown("Analyze GitHub and optional LinkedIn profiles for a role.")

    with st.form("single_candidate_form"):
        col1, col2 = st.columns(2)
        with col1:
            github_username = st.text_input("GitHub Username", placeholder="e.g. Toufiq")
            linkedin_url = st.text_input("LinkedIn Profile (Optional)", placeholder="https://linkedin.com/in/...")
        with col2:
            job_role = st.text_input("Job Role", placeholder="e.g. ML Engineer")
        submit_button = st.form_submit_button("Analyze Candidate 🔥")

    if submit_button:
        if not github_username or not job_role:
            st.error("GitHub username and job role are required.")
        elif not all([st.session_state.Nebius_api_key, st.session_state.github_api_key, st.session_state.exa_api_key, st.session_state.model_id]):
            st.error("❌ Please enter all API keys and model info.")
        else:
            try:
                agent = Agent(
                    model=Nebius(
                        id=st.session_state.model_id,
                        api_key=st.session_state.Nebius_api_key,
                    ),
                    name="Candilyzer",
                    tools=[
                        ThinkingTools(add_instructions=True),
                        GithubTools(access_token=st.session_state.github_api_key),
                        ExaTools(
                            api_key=st.session_state.exa_api_key,
                            include_domains=["linkedin.com", "github.com"],
                            type="keyword",
                            text_length_limit=2000,
                            show_results=True
                        ),
                        ReasoningTools(add_instructions=True)
                    ],
                    description=description_single,
                    instructions=instructions_single,
                    markdown=True,
                    show_tool_calls=True,
                    add_datetime_to_instructions=True
                )

                st.markdown("### 🤖 AI Evaluation in Progress...")
                with st.spinner("Analyzing candidate..."):
                    input_text = f"GitHub: {github_username}, Role: {job_role}"
                    if linkedin_url:
                        input_text += f", LinkedIn: {linkedin_url}"

                    response_stream = agent.run(
                        f"Analyze candidate for {job_role}. {input_text}. Provide score and detailed report.",
                        stream=True
                    )

                    full_response = ""
                    placeholder = st.empty()
                    for chunk in response_stream:
                        if hasattr(chunk, "content") and isinstance(chunk.content, str):
                            full_response += chunk.content
                            placeholder.markdown(full_response, unsafe_allow_html=True)

                    match = re.search(r"\b([1-9]?\d|100)/100\b", full_response)
                    if match:
                        score = int(match.group(1))
                        st.success(f"🎯 Candidate Score: {score}/100")

            except (ValueError, KeyError, ConnectionError) as e:
                st.error(f"❌ Known error: {e}")
            except Exception as e:
                st.error("❌ Unexpected error occurred.")
                st.exception(e)

