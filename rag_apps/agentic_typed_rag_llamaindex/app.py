"""Streamlit interface for typed, cited, self-refusing RAG on Nebius."""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path, PurePath

import streamlit as st
from dotenv import load_dotenv

from agent import (
    Answer,
    DEFAULT_MODEL,
    RagDependencies,
    answer_question,
    resolve_model_name,
)
from rag import (
    DEFAULT_EMBEDDING_MODEL,
    KnowledgeBase,
    build_embed_model,
    fetch_url_text,
    ingest_document,
)


load_dotenv()

ASSETS_DIR = Path(__file__).parent / "assets"
LLAMAINDEX_LOGO = ASSETS_DIR / "llamaindex-color.png"
NEBIUS_LOGO = ASSETS_DIR / "nebius-logo.svg"

st.set_page_config(
    page_title="Agentic Typed RAG",
    page_icon=str(LLAMAINDEX_LOGO),
    layout="wide",
    initial_sidebar_state="expanded",
)

EMBEDDING_MODELS = [
    DEFAULT_EMBEDDING_MODEL,
    "BAAI/bge-en-icl",
    "intfloat/e5-mistral-7b-instruct",
]

LEGACY_DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"


def inject_styles() -> None:
    """Keep the UI close to native Streamlit with a focused dark theme."""
    st.markdown(
        """
        <style>
        :root { color-scheme: dark; }

        .stApp {
            background: #0e1117;
        }

        [data-testid="stHeader"] {
            background: rgba(14, 17, 23, 0.88);
            backdrop-filter: blur(10px);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1120px;
            padding-top: 3rem;
            padding-bottom: 7rem;
        }

        [data-testid="stSidebar"] {
            background: #262730;
            border-right: 1px solid #3a3c47;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 2rem;
        }

        [data-testid="stSidebar"] hr {
            border-color: #444651;
            margin: 1.5rem 0;
        }

        h1, h2, h3 {
            letter-spacing: -0.025em;
        }

        .brand-header {
            margin: 0 0 0.35rem;
            width: 100%;
        }

        .brand-header h1 {
            align-items: center;
            color: #f5f5f7;
            display: flex;
            flex-wrap: wrap;
            font-size: clamp(1.55rem, 3vw, 2.35rem);
            font-weight: 750;
            gap: 0.35rem 0.55rem;
            justify-content: flex-start;
            line-height: 1.2;
            margin: 0;
        }

        .brand-header .llama-brand {
            align-items: center;
            color: #7dd3fc;
            display: inline-flex;
            gap: 0.35rem;
            white-space: nowrap;
        }

        .brand-header .llama-logo {
            display: block;
            height: 0.95em;
            margin: 0;
            width: auto;
        }

        .brand-header .nebius {
            color: #dfff4f;
        }

        .api-status {
            align-items: center;
            border: 1px solid #3a3c47;
            border-radius: 10px;
            display: flex;
            gap: 0.75rem;
            margin: 1rem 0 0.25rem;
            padding: 0.85rem 0.95rem;
        }

        .api-status--connected {
            background: linear-gradient(135deg, rgba(223, 255, 79, 0.12), rgba(223, 255, 79, 0.04));
            border-color: rgba(223, 255, 79, 0.35);
        }

        .api-status--missing {
            background: rgba(255, 193, 7, 0.08);
            border-color: rgba(255, 193, 7, 0.35);
        }

        .api-status-dot {
            background: #dfff4f;
            border-radius: 50%;
            box-shadow: 0 0 0 4px rgba(223, 255, 79, 0.18);
            flex-shrink: 0;
            height: 10px;
            width: 10px;
        }

        .api-status--missing .api-status-dot {
            background: #ffc107;
            box-shadow: 0 0 0 4px rgba(255, 193, 7, 0.18);
        }

        .api-status-copy {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
            min-width: 0;
        }

        .api-status-copy strong {
            color: #f5f5f7;
            font-size: 0.92rem;
            font-weight: 650;
            line-height: 1.2;
        }

        .api-status-copy span {
            color: #9ba1ad;
            font-size: 0.78rem;
            line-height: 1.35;
        }

        .api-status-copy code {
            color: #dfff4f;
            font-size: 0.76rem;
        }

        .brand-subtitle {
            color: #9ba1ad;
            font-size: 1rem;
            line-height: 1.55;
            margin: 0;
            max-width: 720px;
            text-align: center;
        }

        .section-kicker {
            color: #8d94a1;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin-bottom: -0.6rem;
            text-transform: uppercase;
        }

        [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #151922;
            border: 1px solid #303440 !important;
            border-radius: 10px !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: #10141b;
            border-color: #414653;
            border-radius: 8px;
        }

        [data-testid="stTextInputRootElement"],
        [data-baseweb="select"] > div {
            background: #10141b !important;
            border-color: #3b404d !important;
        }

        .stButton > button {
            border-radius: 8px;
            font-weight: 650;
            min-height: 2.75rem;
        }

        .stButton > button[kind="primary"] {
            background: #dfff4f;
            border-color: #dfff4f;
            color: #11151b;
        }

        .stButton > button[kind="primary"]:hover {
            background: #ebff86;
            border-color: #ebff86;
            color: #11151b;
        }

        .stButton > button:disabled,
        .stButton > button:disabled:hover {
            background: #343842;
            border-color: #343842;
            color: #777e8b;
            cursor: not-allowed;
            opacity: 1;
        }

        [data-testid="stAlert"],
        [data-testid="stExpander"],
        [data-testid="stChatMessage"] {
            border-radius: 8px;
        }

        [data-testid="stChatMessage"] {
            background: #151922;
            border: 1px solid #2c303b;
            padding: 0.25rem 0.55rem;
        }

        [data-testid="stChatInput"] {
            background: #262730;
            border-color: #414450;
            border-radius: 22px;
        }

        [data-testid="stProgress"] > div > div > div > div {
            background: #7dd3fc;
        }

        .source-row {
            align-items: center;
            border-top: 1px solid #2e323d;
            color: #c7cad1;
            display: flex;
            font-size: 0.9rem;
            justify-content: space-between;
            padding: 0.7rem 0;
        }

        .source-row:first-child {
            border-top: 0;
        }

        .source-row span:last-child {
            color: #8f96a3;
            font-size: 0.8rem;
        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] {
                padding-top: 1.8rem;
            }

            .brand-header h1 {
                font-size: 1.85rem;
            }

            .brand-header .llama-logo {
                height: 0.9em;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def image_data_uri(path: Path) -> str:
    """Return a local PNG as an embeddable data URI."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def run_async(awaitable):
    """Run one async operation from Streamlit's synchronous script."""
    return asyncio.run(awaitable)


def build_knowledge_base(files, docs_url: str, embedding_model: str):
    """Build a fresh knowledge base from the current source selection."""
    kb = KnowledgeBase(build_embed_model(embedding_model))
    indexed = []

    for uploaded_file in files:
        source = PurePath(uploaded_file.name).name
        chunk_count = ingest_document(kb, source, uploaded_file.getvalue())
        indexed.append((source, chunk_count))

    if docs_url:
        text = fetch_url_text(docs_url)
        chunk_count = kb.add_document(docs_url, text)
        indexed.append((docs_url, chunk_count))

    return kb, indexed


def render_welcome() -> None:
    """Intro copy shown in the main panel before the first chat message."""
    st.markdown(
        """
        ### Ask questions over your documents with validated citations

        Upload PDFs or add a documentation URL from the sidebar, then build a
        knowledge base. The agent retrieves evidence before answering and returns a
        typed `Answer` with exact source quotes, chunk IDs, and a confidence score.

        **What you get in chat**
        - Grounded answers with verbatim citations from indexed chunks
        - A confidence score for each response
        - An explicit refusal when retrieval is too weak or citations fail validation

        **Getting started**
        1. Add your Nebius API key in the sidebar
        2. Upload documents or paste a docs URL
        3. Click **Build knowledge base**
        4. Ask an in-corpus question below
        """
    )


def render_answer(answer: Answer) -> None:
    """Render either a grounded answer or an explicit refusal."""
    if answer.answered:
        st.markdown(answer.text)
        st.progress(answer.confidence)
        st.caption(f"Grounding confidence · {answer.confidence:.0%}")

        if answer.citations:
            st.markdown("#### Sources")
            for citation in answer.citations:
                label = f"{citation.source} · {citation.chunk_id}"
                with st.expander(label):
                    st.code(citation.quoted_span, language=None)
    else:
        st.warning(answer.text, icon="🛑")
        st.progress(answer.confidence)
        st.caption(f"Best retrieval similarity · {answer.confidence:.0%}")


if "rag_kb" not in st.session_state:
    st.session_state.rag_kb = None
if "indexed_sources" not in st.session_state:
    st.session_state.indexed_sources = []
if "answer_history" not in st.session_state:
    st.session_state.answer_history = []

resolved_model = resolve_model_name()
if "answer_model" not in st.session_state:
    st.session_state.answer_model = resolved_model
elif "_migrated_answer_model_default" not in st.session_state:
    if (
        st.session_state.answer_model == LEGACY_DEFAULT_MODEL
        and not os.getenv("RAG_MODEL", "").strip()
    ):
        st.session_state.answer_model = resolved_model
    st.session_state._migrated_answer_model_default = DEFAULT_MODEL
elif (
    os.getenv("RAG_MODEL", "").strip()
    and st.session_state.answer_model != resolved_model
):
    st.session_state.answer_model = resolved_model

inject_styles()

title_col, clear_col = st.columns([4, 1])
with title_col:
    st.markdown(
        f"""
        <div class="brand-header">
            <h1>
                <span>Agentic Typed RAG with</span>
                <span class="llama-brand">
                    <img class="llama-logo" src="{image_data_uri(LLAMAINDEX_LOGO)}" alt="">
                    LlamaIndex
                </span>
                <span>&amp;</span>
                <span class="nebius">Nebius</span>
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
with clear_col:
    if st.session_state.answer_history and st.button(
        "Clear chat", use_container_width=True
    ):
        st.session_state.answer_history = []
        st.rerun()

st.caption("Powered by Nebius AI · Typed answers with validated citations")

with st.sidebar:
    st.image(str(NEBIUS_LOGO), width=150)

    api_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Create a key at tokenfactory.nebius.com",
    )
    if api_key:
        os.environ["NEBIUS_API_KEY"] = api_key

    st.divider()
    st.subheader("Model settings")

    model_name = st.text_input(
        "Answer model",
        key="answer_model",
        help=f"Default: {DEFAULT_MODEL}. Any Nebius Token Factory chat model with tool calling.",
    )

    default_embedding = os.getenv("RAG_EMBEDDING_MODEL", "").strip()
    embedding_options = EMBEDDING_MODELS.copy()
    if default_embedding and default_embedding not in embedding_options:
        embedding_options.insert(0, default_embedding)

    embedding_model = st.selectbox(
        "Embedding model",
        embedding_options,
        index=embedding_options.index(default_embedding) if default_embedding else 0,
    )
    min_relevance = st.slider(
        "Refusal threshold",
        min_value=0.05,
        max_value=0.80,
        value=0.30,
        step=0.01,
        help="The agent refuses questions below this retrieval score.",
    )

    st.divider()
    st.subheader("Knowledge base")

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "pptx", "xlsx"],
        accept_multiple_files=True,
        help="PDFs parse locally. Office formats require LibreOffice.",
    )

    docs_url = (
        st.text_input(
            "Documentation URL",
            placeholder="https://docs.example.com",
            help="Optional. HTML and plain-text pages up to 2 MB are supported.",
        )
        or ""
    ).strip()

    build_clicked = st.button(
        "Build knowledge base",
        type="primary",
        disabled=not uploaded_files and not docs_url,
        use_container_width=True,
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected")

    if st.session_state.rag_kb is not None:
        kb = st.session_state.rag_kb
        metric_a, metric_b = st.columns(2)
        metric_a.metric("Sources", len(st.session_state.indexed_sources))
        metric_b.metric("Chunks", kb.count)
        st.caption(f"Embedding model: {kb.embedding_name}")

        if st.session_state.indexed_sources:
            with st.expander(
                f"Indexed sources · {len(st.session_state.indexed_sources)}",
                expanded=True,
            ):
                for source, chunks in st.session_state.indexed_sources:
                    st.markdown(
                        f'<div class="source-row"><span>{source}</span>'
                        f"<span>{chunks} chunks</span></div>",
                        unsafe_allow_html=True,
                    )

        if st.button("Reset knowledge base", use_container_width=True):
            st.session_state.rag_kb = None
            st.session_state.indexed_sources = []
            st.session_state.answer_history = []
            st.rerun()
    else:
        st.caption("Upload a document or add a URL, then build your knowledge base.")

if build_clicked:
    if not os.getenv("NEBIUS_API_KEY"):
        st.error("Add your Nebius API key in the sidebar before building.")
    else:
        with st.status("Building knowledge base…", expanded=True) as status:
            try:
                st.write("Extracting and chunking source content…")
                kb, indexed_sources = build_knowledge_base(
                    uploaded_files or [], docs_url, embedding_model
                )
                st.write("Generating embeddings with Nebius…")
            except Exception as exc:
                status.update(label="Indexing failed", state="error")
                st.error(f"Could not build the knowledge base: {exc}")
            else:
                st.session_state.rag_kb = kb
                st.session_state.indexed_sources = indexed_sources
                st.session_state.answer_history = []
                status.update(label="Knowledge base ready", state="complete")
                st.rerun()

if st.session_state.answer_history:
    for item in st.session_state.answer_history:
        with st.chat_message("user"):
            st.markdown(item["question"])
        with st.chat_message("assistant"):
            render_answer(Answer.model_validate(item["answer"]))

question = st.chat_input(
    "Ask a question about your indexed sources…",
    disabled=st.session_state.rag_kb is None,
)

if question:
    if not os.getenv("NEBIUS_API_KEY"):
        st.error("Add your Nebius API key in the sidebar before asking a question.")
    else:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving and validating evidence…"):
                deps = RagDependencies(
                    kb=st.session_state.rag_kb,
                    min_relevance=min_relevance,
                    top_k=6,
                )
                try:
                    selected_model = (model_name or "").strip() or resolve_model_name()
                    answer = run_async(
                        answer_question(question, deps, model=selected_model)
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.session_state.answer_history.append(
                        {"question": question, "answer": answer.model_dump()}
                    )
                    st.rerun()
elif not st.session_state.answer_history:
    render_welcome()
