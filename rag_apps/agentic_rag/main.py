from typing import Iterator
import os

from agno.agent import Agent, RunResponseEvent
from agno.embedder.openai import OpenAIEmbedder
from agno.knowledge.url import UrlKnowledge
from agno.models.openai import OpenAIChat
from agno.utils.pprint import pprint_run_response
from agno.vectordb.lancedb import LanceDb, SearchType
from dotenv import load_dotenv
from tkinter.ttk import Style
from turtle import width
import shutil
load_dotenv()
import streamlit as st
import base64

from phoenix.otel import register

# Set environment variables for Arize Phoenix
os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={os.getenv('ARIZE_PHOENIX_API_KEY')}"
os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "https://app.phoenix.arize.com"

# Configure the Phoenix tracer
tracer_provider = register(
    project_name="default",
    auto_instrument=True,  # Automatically use the installed OpenInference instrumentation
)


st.set_page_config(page_title="Agentic RAG", layout="wide")


def load_knowledge_base(urls: list[str] = None):
    """
    Returns the knowledge base for the agent.
    This function is used to load the knowledge base from a URL.
    """
    knowledge_base = UrlKnowledge(
        urls=urls or [],
        vector_db=LanceDb(
            table_name="mcp-docs-knowledge-base",
            uri="tmp/lancedb",
            search_type=SearchType.vector,
            embedder=OpenAIEmbedder(id="text-embedding-3-small"),
        ),
    )
    knowledge_base.load()
    return knowledge_base


# Load the knowledge base: Comment after first run as the knowledge base is already loaded
def agentic_rag_response(
    urls: list[str] = None, query: str = ""
) -> Iterator[RunResponseEvent]:
    knowledge_base = load_knowledge_base(urls)

    agent = Agent(
        model=OpenAIChat(id="gpt-5-2025-08-07"),
        knowledge=knowledge_base,
        search_knowledge=True,
        # show_tool_calls=True,
        markdown=True,
    )

    response: Iterator[RunResponseEvent] = agent.run(query, stream=True)

    return response


col1, col2 = st.columns([4, 1])
with col1:
    title_html = f"""
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1 style="margin: 0;">
             Agentic RAG with Agno & GPT-5
            </h1>
        </div>
        """
    st.markdown(title_html, unsafe_allow_html=True)

with col2:
        if st.button("🔄 Reset KB"):
            st.session_state.docs_loaded = False
            if 'loaded_urls' in st.session_state:
                del st.session_state['loaded_urls']
            st.success("Knowledge base reset!")
            st.rerun()

with st.sidebar:
    st.markdown("### 🧠 Knowledge Base URLs")
    if "urls" not in st.session_state:
        st.session_state.urls = [""]

    col1, col2 = st.columns([4, 1])
    with col1:
        for i, url in enumerate(st.session_state.urls):
            st.session_state.urls[i] = col1.text_input(
                f"URL {i+1}", value=url, key=f"url_{i}", label_visibility="collapsed"
            )
    # Add button in the last column
    if col2.button("➕"):
        if st.session_state.urls and st.session_state.urls[-1].strip() != "":
            st.session_state.urls.append("")

    # Remove empty strings and duplicates
    urls = [u for u in st.session_state.urls if u.strip()]
    urls = list(dict.fromkeys(urls))  # Remove duplicates, preserve order

    if st.button("Load Knowledge Base"):
        if urls:
            with st.spinner("Loading knowledge base... This may take a moment."):
                try:
                    # Actually load the knowledge base with the provided URLs
                    knowledge_base = load_knowledge_base(urls)
                    st.session_state.docs_loaded = True
                    st.session_state.loaded_urls = urls.copy()  # Store the loaded URLs
                    st.success(f"Knowledge base loaded successfully with {len(urls)} URL(s)!")
                except Exception as e:
                    st.error(f"Error loading knowledge base: {str(e)}")
                    st.session_state.docs_loaded = False
        else:
            st.warning("Please add at least one URL to the knowledge base.")

    # Display currently loaded URLs if any
    if st.session_state.get('docs_loaded', False) and st.session_state.get('loaded_urls'):
        st.markdown("**📚 Currently Loaded URLs:**")
        for i, url in enumerate(st.session_state.loaded_urls, 1):
            st.markdown(f"{i}. {url}")

    st.markdown("---")

query = st.chat_input("Ask a question", width=1000)
if query:
    # Check if knowledge base is loaded
    if not st.session_state.get('docs_loaded', False):
        st.warning(
            "Please load the knowledge base first by adding URLs and clicking 'Load Knowledge Base'."
        )
    elif not st.session_state.get('loaded_urls'):
        st.warning(
            "No URLs are currently loaded in the knowledge base. Please add URLs and load the knowledge base."
        )
    else:
        # Use the loaded URLs from session state
        loaded_urls = st.session_state.loaded_urls
        response = agentic_rag_response(loaded_urls, query)
        st.markdown("#### Answer", unsafe_allow_html=True)
        answer = ""
        answer_placeholder = st.empty()
        for content in response:
            if hasattr(content, 'event') and content.event == "RunResponseContent":
                answer += content.content
                answer_placeholder.markdown(answer, unsafe_allow_html=True)


# if __name__ == "__main__":
# response = agentic_rag_response(["https://modelcontextprotocol.io/docs/learn/architecture.md"], "Tell me about MCP primitives that clients can expose.")
# pprint_run_response(response, markdown=True)