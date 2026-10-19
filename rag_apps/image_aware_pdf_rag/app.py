"""Streamlit UI for the image-aware PDF RAG example.

Run from rag_apps/image_aware_pdf_rag:
    uv run streamlit run app.py

Uses the project's existing ingestion, chunking, vision, embeddings, FAISS,
Groq chat, and Groq vision modules.
"""

from __future__ import annotations

import hashlib
import html
import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Multimodal PDF RAG",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import after page configuration so Streamlit can show useful errors if a
# project dependency or local module is missing.
try:
    from markdown_utils import clean_markdown_response
    from ingestion import ingest_pdf
    from chunking import chunk_pages
    from vision import describe_pdf_pages
    from embeddings.local import LocalEmbeddingModel
    from vectorstores.faiss_store import FAISSVectorStore
    from interfaces.vector_store import VectorDocument
    from retrieval.retriever import PDFRetriever
    from providers.groq_chat import GroqChatModel
    from providers.groq_vision import GroqVisionModel
    import logging

    logger = logging.getLogger(__name__)
except Exception as exc:
    st.error(
        "The app could not import one of the project modules. Run Streamlit "
        "from the `image_aware_pdf_rag` directory and check the module names "
        "and dependencies."
    )
    st.exception(exc)
    st.stop()


# ---------- Styling ----------
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
      @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

      /* Clean Light & Lavender Theme Tokens */
      :root {
        --bg-main: #f8fafc;
        --panel-bg: #ffffff;
        --border-subtle: #e2e8f0;
        --border-hover: #cbd5e1;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --text-subtle: #94a3b8;
        --purple-primary: #7c3aed;
        --purple-hover: #6d28d9;
        --purple-light: #f5f3ff;
        --purple-tint: #ede9fe;
        --purple-border: #ddd6fe;
        --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
      }

      .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
      }

      html, body, [class*="css"], p, h1, h2, h3, h4, h5, h6, input, textarea, select, label {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
      }

      /* Streamlit icon preservation */
      [data-testid*="stIcon"],
      [data-testid*="Icon"],
      [data-testid="stExpanderToggleIcon"],
      span.material-symbols-rounded,
      span.material-icons,
      [data-testid="stExpander"] summary span:first-child {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 20px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
      }

      header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none;
        z-index: 100;
        height: 2.25rem;
      }

      header[data-testid="stHeader"] > * {
        pointer-events: auto;
      }

      .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
      }

      /* Compact Clean Top Header */
      .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        padding: 12px 18px;
        background: #ffffff;
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: var(--shadow-sm);
      }

      .app-header-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .app-header-icon {
        width: 36px;
        height: 36px;
        background: var(--purple-light);
        border: 1px solid var(--purple-border);
        border-radius: 9px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
      }

      .app-header-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--text-main);
        letter-spacing: -0.02em;
        line-height: 1.2;
      }

      .app-header-subtitle {
        font-size: 0.82rem;
        color: var(--text-muted);
        margin-top: 2px;
      }

      .app-header-capabilities {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .capability-pill {
        background: var(--purple-light);
        border: 1px solid var(--purple-border);
        color: #5b21b6;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 5px;
      }

      /* Three Column Layout Styling */
      [data-testid="column"] {
        background: #ffffff !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 14px !important;
        padding: 16px 18px !important;
        box-shadow: var(--shadow-sm) !important;
        height: 100%;
      }

      .panel-heading {
        font-size: 0.96rem;
        font-weight: 700;
        color: var(--text-main);
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.01em;
      }

      /* Compact Metric Rows */
      .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 10px;
        background: #f8fafc;
        border: 1px solid var(--border-subtle);
        border-radius: 8px;
        margin-bottom: 6px;
        font-size: 0.82rem;
        color: var(--text-muted);
      }

      .metric-row b {
        color: var(--text-main);
        font-weight: 600;
      }

      /* Chat Bubbles */
      .chat-user-row {
        background: var(--purple-light);
        border: 1px solid var(--purple-border);
        border-radius: 12px;
        padding: 12px 14px;
        margin: 10px 0;
        color: #2e1065;
        font-size: 0.9rem;
        line-height: 1.5;
      }

      .chat-user-label {
        font-size: 0.76rem;
        font-weight: 700;
        color: #7c3aed;
        margin-bottom: 4px;
      }

      [class*="st-key-chat-assistant-msg-"] {
        background: #ffffff !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        margin: 10px 0 !important;
        box-shadow: var(--shadow-sm) !important;
        color: var(--text-main) !important;
        font-size: 0.9rem !important;
        line-height: 1.6 !important;
      }

      /* Buttons - Purple Accent */
      div.stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        letter-spacing: -0.01em !important;
        transition: all 0.15s ease !important;
        padding: 0.4rem 0.85rem !important;
        box-shadow: none !important;
      }

      div.stButton > button[kind="primary"],
      div.stButton > button[data-testid="baseButton-primary"] {
        background: var(--purple-primary) !important;
        border: 1px solid var(--purple-primary) !important;
        color: #ffffff !important;
      }

      div.stButton > button[kind="primary"]:hover,
      div.stButton > button[data-testid="baseButton-primary"]:hover {
        background: var(--purple-hover) !important;
        border-color: var(--purple-hover) !important;
      }

      div.stButton > button[kind="secondary"],
      div.stButton > button[data-testid="baseButton-secondary"] {
        background: #ffffff !important;
        border: 1px solid var(--border-subtle) !important;
        color: var(--text-main) !important;
      }

      div.stButton > button[kind="secondary"]:hover,
      div.stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #f8fafc !important;
        border-color: var(--border-hover) !important;
        color: var(--purple-primary) !important;
      }

      /* File Uploader */
      [data-testid="stFileUploader"] {
        background: #fcfcfd !important;
        border: 1px dashed var(--border-hover) !important;
        border-radius: 10px !important;
        padding: 8px !important;
      }

      [data-testid="stFileUploaderDropzone"] {
        padding: 10px !important;
      }

      /* Thumbnail strip item active state */
      .active-thumbnail {
        border: 2px solid var(--purple-primary) !important;
        border-radius: 6px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Cached resources ----------
@st.cache_resource(show_spinner="Loading local embedding model…")
def get_embedding_model() -> LocalEmbeddingModel:
    """Load and cache the local Sentence-Transformers embedding model."""
    return LocalEmbeddingModel()


def get_vector_store() -> FAISSVectorStore:
    """Retrieve or initialize the session-scoped FAISS vector store instance."""
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = FAISSVectorStore()
    return st.session_state.vector_store


@st.cache_resource
def get_chat_model(model_name: str, api_key: str | None = None) -> GroqChatModel:
    """Load and cache the Groq chat model instance."""
    load_dotenv(override=True)
    key = api_key or os.getenv("GROQ_API_KEY")
    return GroqChatModel(model=model_name, api_key=key)


@st.cache_resource
def get_vision_model(model_name: str, api_key: str | None = None) -> GroqVisionModel:
    """Load and cache the Groq multimodal vision model instance."""
    load_dotenv(override=True)
    key = api_key or os.getenv("GROQ_API_KEY")
    return GroqVisionModel(model=model_name, api_key=key)


# ---------- Session state ----------
defaults = {
    "pdf_hash": None,
    "pdf_name": None,
    "pages": [],
    "chunks": [],
    "visual_descriptions": [],
    "index_ready": False,
    "index_source": None,
    "chat_history": [],
    "cited_page": 1,
    "processing_error": None,
    "indexed_items": 0,
    "text_chunks_indexed": 0,
    "visual_pages_succeeded": [],
    "visual_pages_failed": [],
    "visual_pages_errors": {},
    "index_status": None,  # None, "inspected", "text_only", "complete", "partial_visual_failure", "failed"
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------- Helpers ----------
def page_number(page: Any) -> int:
    """Extract page number integer from a page object."""
    return int(getattr(page, "page_number", 1))


def page_image(page: Any) -> bytes | None:
    """Extract rendered PNG bytes from a page object if present."""
    image_bytes = getattr(page, "image_png", None)
    return image_bytes if isinstance(image_bytes, bytes) and image_bytes else None


def page_text(page: Any) -> str:
    """Extract trimmed text content from a page object."""
    return str(getattr(page, "text", "") or "").strip()


def set_question_input(question: str) -> None:
    """Set the pre-populated question text into Streamlit session state."""
    st.session_state.question_input = question


def object_value(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve attribute or dict key value with a fallback default."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_vector(vector: Any) -> list[float]:
    """Convert embedding outputs from ndarrays or nested lists into float lists."""
    # Sentence Transformers wrappers commonly return a list or NumPy array.
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    if vector and isinstance(vector[0], (list, tuple)):
        vector = vector[0]
    return [float(value) for value in vector]


def add_to_index(
    store: FAISSVectorStore,
    embedding_model: LocalEmbeddingModel,
    text: str,
    metadata: dict[str, Any],
    item_id: str,
) -> None:
    """Embed and index a single text or visual description into FAISS."""
    embedding = normalize_vector(embedding_model.embed_documents([text]))
    document = VectorDocument(
        id=item_id,
        text=text,
        embedding=embedding,
        metadata=metadata,
    )
    store.add_documents([document])


def format_history_for_prompt(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Format recent chat history into structured prompt messages."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert PDF question-answering assistant.\n"
                "Rules:\n"
                "1. Answer strictly using the provided PDF evidence.\n"
                "2. When a question asks about a specific chart (e.g. Chart 1.1) or page, locate the evidence for that exact chart/page.\n"
                "   Never substitute a similarly named chart or different page (e.g. do not substitute Chart 1.2 for Chart 1.1).\n"
                "3. Cite supporting pages using [Page N].\n"
                "4. Do not invent chart labels, line colors, or numbers."
            ),
        }
    ]
    messages.extend(history[-8:])
    return messages


def retrieve_evidence(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve top-k relevant text and visual evidence items from the vector index."""
    source_id = st.session_state.index_source
    if not st.session_state.index_ready or not source_id:
        return []
    embedder = get_embedding_model()
    store = get_vector_store()

    retriever = PDFRetriever(embeddings=embedder, vector_store=store)
    raw_evidence = retriever.retrieve(query=query, top_k=top_k, source_id=source_id)

    evidence = []
    for idx, item in enumerate(raw_evidence, start=1):
        record = {
            "page_number": int(item.page_number),
            "text": str(item.text),
            "content_type": str(item.content_type),
            "source": str(item.source),
            "score": 0.0,
        }
        evidence.append(record)
        snippet = item.text[:120].replace('\n', ' ')
        logger.info(
            "Retrieved evidence: page=%d, type=%s",
            item.page_number,
            item.content_type,
        )
        logger.debug(
            "Retrieved evidence #%d snippet: %s",
            idx,
            snippet,
        )

    return evidence


def answer_question(query: str, chat_model: GroqChatModel) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve evidence and generate a cited response to the user query."""
    evidence = retrieve_evidence(query)
    if not evidence:
        return (
            "I couldn't retrieve evidence from the document. Please upload a PDF and build the search index first.",
            [],
        )

    evidence_text = "\n\n".join(
        f"[Page {item['page_number']} | {item['content_type']}]\n{item['text']}"
        for item in evidence
    )
    prompt = (
        f"Question: {query}\n\n"
        f"Retrieved PDF evidence:\n{evidence_text}\n\n"
        "Instructions:\n"
        "- Answer the question using only the retrieved evidence above.\n"
        "- Provide a concise, clear answer first, followed by key takeaways as a short bulleted list when useful.\n"
        "- If the question references a specific chart (e.g. Chart 1.1) or page, verify that the evidence matches that exact chart/page.\n"
        "- Do not confuse or substitute different charts (e.g., Chart 1.1 vs Chart 1.2).\n"
        "- Include inline page citations such as [Page N] for claims supported by the evidence.\n"
        "- Format your answer cleanly in standard Markdown without empty bold tags (do not output **    ** or blank bold syntax)."
    )
    messages = format_history_for_prompt(st.session_state.chat_history)
    messages.append({"role": "user", "content": prompt})
    raw_answer = chat_model.generate(messages)
    cleaned_answer = clean_markdown_response(str(raw_answer))
    return cleaned_answer, evidence


def set_cited_page(number: int) -> None:
    """Clamp and update the active cited page preview number in session state."""
    total = len(st.session_state.pages)
    if total:
        st.session_state.cited_page = max(1, min(number, total))


# ---------- Header ----------
st.markdown(
    """
    <div class="app-header">
      <div class="app-header-left">
        <div class="app-header-icon">📑</div>
        <div>
          <div class="app-header-title">Multimodal PDF RAG</div>
          <div class="app-header-subtitle">Ask questions about text, charts, tables and diagrams in your PDF</div>
        </div>
      </div>
      <div class="app-header-capabilities">
        <div class="capability-pill"><span>📄</span> Understands text</div>
        <div class="capability-pill"><span>📊</span> Reads charts and tables</div>
        <div class="capability-pill"><span>🔍</span> Interprets diagrams</div>
        <div class="capability-pill"><span>🎯</span> Cites supporting pages</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- Main layout: Three columns (22% / 46% / 32%) ----------
col_left, col_center, col_right = st.columns([0.22, 0.46, 0.32], gap="medium")


# COLUMN A: PDF Upload and Settings (22%)
with col_left:
    st.markdown('<div class="panel-heading">📂 Upload PDF</div>', unsafe_allow_html=True)

    if "pdf_uploader_version" not in st.session_state:
        st.session_state.pdf_uploader_version = 0

    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        help="Upload a PDF with text, charts, tables, or diagrams.",
        label_visibility="collapsed",
        key=f"pdf_uploader_{st.session_state.pdf_uploader_version}",
    )

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.getvalue()
        current_hash = hashlib.sha256(pdf_bytes).hexdigest()
        file_size_mb = len(pdf_bytes) / (1024 * 1024)

        # Compact file row with remove/replace
        c_fname, c_del = st.columns([4, 1])
        with c_fname:
            st.markdown(
                f'<div class="metric-row"><span>📄 <b>{html.escape(uploaded_file.name[:18])}{"…" if len(uploaded_file.name) > 18 else ""}</b></span>'
                f'<span style="font-size:0.75rem; color:#64748b;">{file_size_mb:.2f} MB</span></div>',
                unsafe_allow_html=True,
            )
        with c_del:
            if st.button("✕", help="Remove or replace file", key="remove_pdf_btn", use_container_width=True):
                if st.session_state.index_source:
                    get_vector_store().delete_source(st.session_state.index_source)
                st.session_state.pdf_hash = None
                st.session_state.pdf_name = None
                st.session_state.pages = []
                st.session_state.chunks = []
                st.session_state.visual_descriptions = []
                st.session_state.index_ready = False
                st.session_state.index_source = None
                st.session_state.chat_history = []
                st.session_state.last_evidence = []
                st.session_state.last_question = None
                st.session_state.cited_page = 1
                st.session_state.visual_pages_succeeded = []
                st.session_state.visual_pages_failed = []
                st.session_state.visual_pages_errors = {}
                st.session_state.index_status = None
                st.session_state.pdf_uploader_version += 1
                st.rerun()

        if current_hash != st.session_state.pdf_hash:
            if st.session_state.index_source:
                get_vector_store().delete_source(st.session_state.index_source)
            st.session_state.pdf_hash = current_hash
            st.session_state.pdf_name = uploaded_file.name
            st.session_state.pages = []
            st.session_state.chunks = []
            st.session_state.visual_descriptions = []
            st.session_state.index_ready = False
            st.session_state.index_source = None
            st.session_state.chat_history = []
            st.session_state.last_evidence = []
            st.session_state.last_question = None
            st.session_state.cited_page = 1
            st.session_state.indexed_items = 0
            st.session_state.processing_error = None
            st.session_state.visual_pages_succeeded = []
            st.session_state.visual_pages_failed = []
            st.session_state.visual_pages_errors = {}
            st.session_state.index_status = None

            # Automatic ingestion of uploaded PDF
            try:
                with st.spinner("Extracting pages and text chunks…"):
                    pages = ingest_pdf(pdf_bytes)
                    if not pages:
                        raise ValueError("No pages were found in this PDF.")
                    st.session_state.pages = pages
                    chunk_result = chunk_pages(pages)
                    st.session_state.chunks = list(
                        object_value(chunk_result, "chunks", []) or []
                    )
                    st.session_state.index_status = "inspected"
                    st.session_state.visual_pages_succeeded = []
                    st.session_state.visual_pages_failed = []
            except Exception as exc:
                st.session_state.processing_error = str(exc)
                st.session_state.pages = []
                st.session_state.chunks = []
                st.session_state.index_status = "failed"

    if st.session_state.processing_error:
        st.error(f"Processing error: {st.session_state.processing_error}")

    pages = st.session_state.pages
    chunks = st.session_state.chunks
    rendered_visuals = sum(1 for page in pages if page_image(page))

    # Section B: Processing status
    st.markdown('<div class="panel-heading" style="margin-top:14px;">⚡ Processing Status</div>', unsafe_allow_html=True)
    if pages:
        status_text = "Pending Index"
        status_color = "#64748b"
        if st.session_state.index_ready:
            if st.session_state.index_status == "complete":
                status_text = "Text + Visuals"
                status_color = "#16a34a"
            elif st.session_state.index_status == "partial_visual_failure":
                status_text = "Partial Visuals"
                status_color = "#d97706"
            elif st.session_state.index_status == "text_only":
                status_text = "Text Only"
                status_color = "#2563eb"
            elif st.session_state.index_status == "failed":
                status_text = "Visual Analysis Failed"
                status_color = "#dc2626"
            else:
                status_text = "Text + Visuals"
                status_color = "#16a34a"

        st.markdown(
            f'<div class="metric-row"><span>📄 Pages</span><b>{len(pages)}</b></div>'
            f'<div class="metric-row"><span>✂️ Text Chunks</span><b>{len(chunks)}</b></div>'
            f'<div class="metric-row"><span>🖼️ Visual Regions</span><b>{rendered_visuals}</b></div>'
            f'<div class="metric-row"><span>⚡ Status</span><b style="color:{status_color};">{status_text}</b></div>',
            unsafe_allow_html=True,
        )

        if st.session_state.index_ready or st.session_state.index_status in {"failed", "partial_visual_failure"}:
            succ_pages = st.session_state.get("visual_pages_succeeded", [])
            fail_pages = st.session_state.get("visual_pages_failed", [])
            err_dict = st.session_state.get("visual_pages_errors", {})

            if succ_pages:
                st.caption(f"✅ Visuals indexed: Pages {', '.join(str(p) for p in succ_pages)}")
            if fail_pages:
                with st.expander(f"⚠️ Visual issues ({len(fail_pages)} pages)", expanded=False):
                    for fp in fail_pages:
                        reason = err_dict.get(fp, "Unknown error")
                        st.markdown(f"**Page {fp}:** `{html.escape(reason[:120])}`")

        if not st.session_state.index_ready and st.session_state.index_status == "inspected":
            if st.button("🚀 Index Document", type="primary", use_container_width=True):
                if not os.getenv("GROQ_API_KEY"):
                    st.error("GROQ_API_KEY is missing. Check your `.env`.")
                else:
                    try:
                        with st.spinner("Embedding text and indexing visual descriptions…"):
                            embedder = get_embedding_model()
                            vision_model = get_vision_model(os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"))
                            store = get_vector_store()

                            if st.session_state.index_source:
                                store.delete_source(st.session_state.index_source)

                            index_source = st.session_state.pdf_hash
                            st.session_state.index_source = index_source
                            indexed_count = 0
                            text_indexed_count = 0

                            for i, chunk in enumerate(chunks):
                                chunk_text = str(object_value(chunk, "text", "") or "").strip()
                                if not chunk_text:
                                    continue
                                pnum = int(object_value(chunk, "page_number", 1))
                                add_to_index(
                                    store,
                                    embedder,
                                    chunk_text,
                                    {
                                        "page_number": pnum,
                                        "content_type": "text",
                                        "source": st.session_state.pdf_name or "uploaded PDF",
                                        "source_id": index_source,
                                        "chunk_index": int(object_value(chunk, "chunk_index", i)),
                                    },
                                    f"{index_source}:text:{i}",
                                )
                                indexed_count += 1
                                text_indexed_count += 1

                            st.session_state.text_chunks_indexed = text_indexed_count

                            pages_with_images = [p for p in pages if page_image(p)]
                            descriptions = []
                            succeeded_pages = []
                            failed_pages_dict: dict[int, str] = {}
                            fatal_auth_error = False

                            for i, page in enumerate(pages_with_images, start=1):
                                if fatal_auth_error:
                                    break
                                pnum = page_number(page)
                                try:
                                    result = describe_pdf_pages([page], vision_model)
                                    for description in result:
                                        desc_text = str(
                                            object_value(description, "description", "") or ""
                                        ).strip()
                                        if not desc_text:
                                            failed_pages_dict[pnum] = "Empty description"
                                            continue
                                        descriptions.append(description)
                                        succeeded_pages.append(pnum)
                                        add_to_index(
                                            store,
                                            embedder,
                                            f"Visual description of page {pnum}: {desc_text}",
                                            {
                                                "page_number": pnum,
                                                "content_type": "visual_description",
                                                "source": st.session_state.pdf_name or "uploaded PDF",
                                                "source_id": index_source,
                                            },
                                            f"{index_source}:visual:{pnum}:{len(descriptions)}",
                                        )
                                        indexed_count += 1
                                except Exception as exc:
                                    err_str = str(exc)
                                    failed_pages_dict[pnum] = err_str
                                    if "401" in err_str or "invalid_api_key" in err_str.lower():
                                        st.error("Invalid Groq API Key.")
                                        fatal_auth_error = True
                                        break

                            st.session_state.visual_descriptions = descriptions
                            st.session_state.index_source = index_source
                            st.session_state.indexed_items = indexed_count
                            st.session_state.visual_pages_succeeded = sorted(list(set(succeeded_pages)))
                            st.session_state.visual_pages_failed = sorted(list(failed_pages_dict.keys()))
                            st.session_state.visual_pages_errors = dict(failed_pages_dict)
                            st.session_state.index_ready = indexed_count > 0
                            succeeded_page_numbers = set(succeeded_pages)
                            all_visual_pages_failed = bool(pages_with_images) and all(
                                page_number(page) in failed_pages_dict
                                and page_number(page) not in succeeded_page_numbers
                                for page in pages_with_images
                            )

                            if indexed_count == 0:
                                st.session_state.index_status = "failed"
                            elif all_visual_pages_failed:
                                st.session_state.index_status = "failed"
                            elif len(failed_pages_dict) == 0 and len(descriptions) > 0:
                                st.session_state.index_status = "complete"
                            elif len(descriptions) > 0:
                                st.session_state.index_status = "partial_visual_failure"
                            else:
                                st.session_state.index_status = "text_only"
                            st.rerun()
                    except Exception as exc:
                        st.session_state.index_status = "failed"
                        st.error(f"Index creation failed: {exc}")
    else:
        st.markdown('<div class="metric-row"><span>Upload a PDF to view metrics</span></div>', unsafe_allow_html=True)

    # Section C: Model & Settings
    st.markdown('<div class="panel-heading" style="margin-top:14px;">⚙️ Model & Settings</div>', unsafe_allow_html=True)
    chat_model_name = st.selectbox(
        "LLM Provider",
        options=["openai/gpt-oss-20b"],
        index=0,
        help="Groq LLM provider for fast answering.",
    )
    st.selectbox(
        "Embedding Provider",
        options=["Local MiniLM-L6-v2 (CPU)"],
        index=0,
        help="Local dense embeddings via Sentence Transformers.",
    )
    st.selectbox(
        "Vision Provider",
        options=[os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")],
        index=0,
        help="Multimodal vision model for chart analysis.",
    )

    if st.button("🔄 Reprocess PDF", use_container_width=True):
        if not uploaded_file:
            st.warning("Please upload a PDF first.")
        else:
            st.session_state.index_ready = False
            st.session_state.index_status = "inspected"
            st.session_state.visual_descriptions = []
            st.session_state.chat_history = []
            st.session_state.last_evidence = []
            st.rerun()


# COLUMN B: Question and Answer Workspace (46%)
with col_center:
    st.markdown('<div class="panel-heading">Ask a question about your PDF</div>', unsafe_allow_html=True)

    with st.form("ask_question_form", clear_on_submit=False):
        query = st.text_input(
            "Question",
            placeholder="Ask about the document, a chart, table or diagram...",
            label_visibility="collapsed",
            key="question_input",
            disabled=not st.session_state.index_ready,
        )
        ask_col, clear_col = st.columns([4, 1.2])
        with ask_col:
            ask_clicked = st.form_submit_button(
                "Ask Question",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.index_ready,
            )
        with clear_col:
            clear_clicked = st.form_submit_button("Clear", use_container_width=True)

    if clear_clicked:
        st.session_state.chat_history = []
        st.session_state.last_evidence = []
        st.session_state.last_question = None
        st.rerun()

    # Try an example section with the 4 exact requested examples
    st.markdown('<div style="font-size:0.78rem; color:#64748b; font-weight:600; margin: 4px 0 6px 0;">Try an example:</div>', unsafe_allow_html=True)
    example_questions = [
        "What is the main contribution of this paper?",
        "What does the chart on page 5 show?",
        "Explain the architecture diagram on page 3.",
        "What are the key results in the table on page 8?",
    ]
    ex_row1 = st.columns(2)
    ex_row2 = st.columns(2)
    for idx, ex_text in enumerate(example_questions):
        target_col = ex_row1[idx] if idx < 2 else ex_row2[idx - 2]
        with target_col:
            st.button(
                ex_text,
                key=f"ex_btn_{idx}",
                use_container_width=True,
                disabled=not st.session_state.index_ready,
                on_click=set_question_input,
                args=(ex_text,),
            )

    if ask_clicked:
        question = (st.session_state.question_input or "").strip()
        if not question:
            st.warning("Please enter a question.")
        else:
            try:
                with st.spinner("Formulating grounded response…"):
                    chat_model = get_chat_model(chat_model_name)
                    answer, evidence = answer_question(question, chat_model)
                st.session_state.chat_history.append({"role": "user", "content": question})
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.session_state.chat_history = st.session_state.chat_history[-20:]
                st.session_state.last_evidence = evidence
                st.session_state.last_question = question
                if evidence:
                    set_cited_page(int(evidence[0]["page_number"]))
            except Exception as exc:
                st.error("Question answering failed.")
                st.exception(exc)

    # Render Conversation History
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            content = html.escape(str(message["content"]))
            st.markdown(
                f'<div class="chat-user-row"><div class="chat-user-label">You</div>{content}</div>',
                unsafe_allow_html=True,
            )
        else:
            assistant_content = clean_markdown_response(str(message["content"]))
            with st.container(key=f"chat-assistant-msg-{i}"):
                st.markdown('<b style="color:#7c3aed; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.04em;">AI Response</b>', unsafe_allow_html=True)
                st.markdown(assistant_content)

    # Cited sources section at the bottom of the answer
    last_evidence = st.session_state.get("last_evidence", [])
    if last_evidence:
        st.markdown('<div class="panel-heading" style="margin-top:16px;">📚 Cited Sources</div>', unsafe_allow_html=True)
        seen_pages: set[int] = set()
        for item in last_evidence:
            pnum = int(item["page_number"])
            if pnum in seen_pages:
                continue
            seen_pages.add(pnum)
            preview = next(
                (p for p in pages if page_number(p) == pnum), None
            )
            c_thumb, c_info, c_action = st.columns([1, 3.2, 1.2])
            with c_thumb:
                if preview and page_image(preview):
                    st.image(page_image(preview), use_container_width=True)
                else:
                    st.caption(f"Page {pnum}")
            with c_info:
                ctype = "Visual Region" if item['content_type'] == "visual_description" else "Text Section"
                st.markdown(f"**Page {pnum}** · <span style='color:#7c3aed; font-size:0.78rem; font-weight:600;'>{ctype}</span>", unsafe_allow_html=True)
                st.caption(item["text"][:140] + ("…" if len(item["text"]) > 140 else ""))
            with c_action:
                if st.button("View page", key=f"btn_cite_view_{pnum}", use_container_width=True):
                    set_cited_page(pnum)
                    st.rerun()


# COLUMN C: Cited PDF Page Preview (32%)
with col_right:
    current_pages = st.session_state.pages
    total_pages = len(current_pages)
    selected_page = st.session_state.cited_page

    st.markdown('<div class="panel-heading">📖 Cited Page</div>', unsafe_allow_html=True)

    nav_prev, nav_center, nav_next = st.columns([0.6, 2.0, 0.6])
    with nav_center:
        st.markdown(
            f'<div style="text-align:center; font-weight:600; font-size:0.85rem; color:#0f172a; padding-top:4px;">'
            f'Page {selected_page} of {max(1, total_pages)}</div>',
            unsafe_allow_html=True,
        )
    with nav_prev:
        if st.button("◀", key="prev_page_c", disabled=not current_pages or selected_page <= 1, use_container_width=True):
            set_cited_page(selected_page - 1)
            st.rerun()
    with nav_next:
        if st.button("▶", key="next_page_c", disabled=not current_pages or selected_page >= total_pages, use_container_width=True):
            set_cited_page(selected_page + 1)
            st.rerun()

    if current_pages:
        selected = next(
            (p for p in current_pages if page_number(p) == selected_page),
            current_pages[0],
        )
        image_bytes = page_image(selected)
        if image_bytes:
            st.image(image_bytes, use_container_width=True)
        else:
            st.info(f"No visual preview available for page {selected_page}.")
            extracted_text = page_text(selected)
            st.markdown("**Extracted text**")
            st.text(extracted_text or "No extracted text available for this page.")

        # Compact horizontal strip of nearby page thumbnails
        st.markdown('<div style="font-size:0.76rem; font-weight:600; color:#64748b; margin-top:12px; margin-bottom:6px;">Nearby Pages</div>', unsafe_allow_html=True)
        thumbnail_pages = current_pages[
            max(0, selected_page - 3) : min(total_pages, selected_page + 2)
        ]
        thumb_cols = st.columns(min(5, max(1, len(thumbnail_pages))))
        for idx, page in enumerate(thumbnail_pages):
            with thumb_cols[idx % len(thumb_cols)]:
                pnum = page_number(page)
                t_img = page_image(page)
                if t_img:
                    st.image(t_img, use_container_width=True)
                is_selected = (pnum == selected_page)
                if st.button(
                    f"P.{pnum}",
                    key=f"th_{pnum}",
                    type="primary" if is_selected else "secondary",
                    use_container_width=True,
                ):
                    set_cited_page(pnum)
                    st.rerun()
    else:
        st.info("Upload and index a PDF to preview cited pages and diagrams.")
