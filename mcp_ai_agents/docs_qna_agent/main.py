# Standard library imports
import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
import asyncio
import streamlit as st
load_dotenv()

DEFAULT_SERVER_URL = "https://docs.studio.nebius.com/mcp"

# --- Function to run the MCP agent ---
async def run_mcp_agent(url: str, query: str, api_key: str) -> str:
    """Run the MCP agent and return the response content."""
    mcp_tools = MCPTools(url=url, transport="streamable-http")
    await mcp_tools.connect()
    agent = Agent(
        model=Nebius(id="deepseek-ai/DeepSeek-V3-0324", api_key=api_key),
        tools=[mcp_tools],
    )
    response = await agent.arun(query)
    await mcp_tools.close()
    return response.content


# --- Streamlit App Configuration ---
st.set_page_config(page_title="Talk to Your Docs", page_icon="📚", layout="wide")

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Layout: Title and Clear Chat Button ---
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1 style="margin: 0;">📚 Talk to Your Docs</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- Sidebar: Logo, API Key, Doc URL, Example Questions ---
with st.sidebar:
    try:
        st.image("./assets/Nebius.png", width=150)
    except Exception:
        st.markdown("### 🤖 Nebius AI")

    nebius_api_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius API key",
    )
    st.divider()
    doc_url = st.text_input(
        "Documentation URL",
        value=DEFAULT_SERVER_URL,
        help="Enter the URL of the documentation you want to query",
    )
    st.divider()
    st.markdown("### 💡 Example Questions")
    example_questions = [
        "How to create an Agent with Google ADK & Nebius?",
        "How to fine-tune your custom model?",
        "How to get structured output from our text models?",
        "How to use the Nebius API?",
    ]
    for question in example_questions:
        if st.button(
            question, key=f"example_{hash(question)}", use_container_width=True
        ):
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()


# --- Display Chat Messages ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Chat Input ---
prompt = st.chat_input("Ask a question about the documentation...")

# --- Determine Prompt Source (Chat Input or Example Button) ---
if st.session_state.messages:
    last_message = st.session_state.messages[-1]
    if last_message["role"] == "user":
        if (
            len(st.session_state.messages) == 1
            or st.session_state.messages[-2]["role"] != "assistant"
        ):
            prompt = last_message["content"]

# --- Handle User Prompt ---
if prompt:
    if not nebius_api_key:
        st.error("Please enter your Nebius API key in the sidebar.")
        st.stop()

    # Add user message to chat history if not already present
    if not (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and st.session_state.messages[-1]["content"] == prompt
    ):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    # Display assistant response
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                response_text = asyncio.run(
                    run_mcp_agent(doc_url, prompt, nebius_api_key)
                )
            if response_text:
                st.markdown(response_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response_text}
                )
            else:
                error_message = "No response received from the agent."
                st.error(error_message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_message}
                )
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message}
            )