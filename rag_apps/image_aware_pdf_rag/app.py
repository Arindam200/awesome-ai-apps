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

      /* Theme design tokens follow Streamlit's active theme. */
      .stApp {
        --app-bg: var(--background-color);
        --text-primary: var(--text-color);
        --text-secondary: color-mix(in srgb, var(--text-color) 80%, var(--background-color));
        --text-muted: color-mix(in srgb, var(--text-color) 65%, var(--background-color));
        --card-bg: var(--secondary-background-color);
        --card-border: color-mix(in srgb, var(--text-color) 14%, var(--secondary-background-color));
        --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04), 0 2px 4px -2px rgba(0, 0, 0, 0.04);
        --metric-bg: var(--background-color);
        --metric-border: var(--card-border);
        --btn-bg: var(--secondary-background-color);
        --btn-text: var(--text-color);
        --btn-border: color-mix(in srgb, var(--text-color) 28%, var(--secondary-background-color));
        --btn-hover-bg: color-mix(in srgb, var(--secondary-background-color) 92%, var(--text-color));
        --btn-hover-border: color-mix(in srgb, var(--text-color) 40%, var(--secondary-background-color));
        --uploader-bg: var(--secondary-background-color);
        --uploader-border: var(--btn-border);
        --citation-bg: var(--secondary-background-color);
        background: var(--app-bg) !important;
        color: var(--text-primary) !important;
      }

      /* Base App Typography */
      html, body, p, h1, h2, h3, h4, h5, h6, input, textarea, select, label {
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
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' 1 !important;
        font-feature-settings: 'liga' 1 !important;
        -webkit-font-smoothing: antialiased !important;
      }
      
      /* Make Streamlit top navbar transparent and integrate seamlessly */
      header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none;
        z-index: 100;
        height: 2.75rem;
      }
      
      header[data-testid="stHeader"] > * {
        pointer-events: auto;
      }

      header[data-testid="stHeader"] button, 
      header[data-testid="stHeader"] [data-testid="stToolbarActions"],
      header[data-testid="stHeader"] svg {
        color: var(--text-primary) !important;
        fill: var(--text-primary) !important;
      }

      .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
      }

      /* Hero Header */
      .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #31104b 100%);
        border-radius: 20px;
        padding: 24px 32px;
        color: #ffffff;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 20px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25), 0 8px 10px -6px rgba(15, 23, 42, 0.2);
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.1);
      }

      .hero-title-area {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .hero-badge-icon {
        font-size: 2.2rem;
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(8px);
        width: 58px;
        height: 58px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.2);
      }

      .hero-title {
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.15;
        margin: 0;
        background: linear-gradient(to right, #ffffff, #c7d2fe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }

      .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 4px;
        font-weight: 400;
      }

      .hero-tags {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }

      .hero-tag {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #e2e8f0;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      /* Section Cards */
      .ui-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: var(--card-shadow);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }

      .ui-card:hover {
        box-shadow: 0 8px 16px -2px rgba(0, 0, 0, 0.15);
      }

      .ui-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.01em;
      }

      /* Status Metrics */
      .metric-badge {
        background: var(--metric-bg);
        border: 1px solid var(--metric-border);
        border-radius: 10px;
        padding: 8px 12px;
        margin: 6px 0;
        font-size: 0.88rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: var(--text-secondary);
      }

      .metric-badge b {
        color: var(--text-primary);
        font-weight: 600;
      }

      /* Chat Bubbles */
      .chat-user-msg {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: #ffffff !important;
        border-radius: 14px 14px 2px 14px;
        padding: 12px 16px;
        margin: 12px 0 12px auto;
        max-width: 85%;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
        font-size: 0.95rem;
        line-height: 1.5;
      }

      [class*="st-key-chat-assistant-msg-"] {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 14px 14px 14px 2px;
        padding: 16px 18px;
        margin: 12px auto 12px 0;
        max-width: 95%;
        box-shadow: var(--card-shadow);
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.6;
      }

      /* Buttons & Inputs - ensures high contrast in both dark and light system themes */
      div.stButton > button,
      div.stDownloadButton > button {
        background-color: var(--btn-bg) !important;
        color: var(--btn-text) !important;
        border: 1px solid var(--btn-border) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
      }

      div.stButton > button * {
        color: inherit !important;
      }

      div.stButton > button:hover,
      div.stDownloadButton > button:hover {
        background-color: var(--btn-hover-bg) !important;
        border-color: var(--btn-hover-border) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15) !important;
      }

      div.stButton > button[kind="primary"],
      div.stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
        border: none !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4) !important;
      }

      div.stButton > button[kind="primary"] *,
      div.stButton > button[data-testid="baseButton-primary"] * {
        color: #ffffff !important;
      }

      div.stButton > button[kind="primary"]:hover,
      div.stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%) !important;
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.5) !important;
        color: #ffffff !important;
      }

      div.stButton > button:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
        transform: none !important;
        box-shadow: none !important;
      }

      /* Ensure columns maintain proper container backgrounds on wide layouts */
      [data-testid="column"] {
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 18px !important;
        padding: 22px 20px !important;
        box-shadow: var(--card-shadow) !important;
        color: var(--text-primary) !important;
      }

      /* Clean, responsive file uploader */
      [data-testid="stFileUploader"] {
        background: var(--uploader-bg) !important;
        border: 2px dashed var(--uploader-border) !important;
        border-radius: 16px !important;
        padding: 10px 14px !important;
        transition: all 0.2s ease !important;
      }

      [data-testid="stFileUploader"]:hover {
        border-color: #6366f1 !important;
      }

      [data-testid="stFileUploaderDropzone"] {
        padding: 16px !important;
        border: none !important;
        background: transparent !important;
        text-align: center !important;
      }

      /* Hide broken icon font ligature text like raw 'upload' text */
      [data-testid="stFileUploaderDropzone"] [data-testid="stIconMaterial"],
      [data-testid="stFileUploaderDropzone"] svg + span:empty,
      [data-testid="stFileUploaderDropzone"] span.material-symbols-rounded,
      [data-testid="stFileUploaderDropzone"] span.material-icons {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
      }

      [data-testid="stFileUploaderDropzone"] button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 8px 18px !important;
        background: var(--btn-bg) !important;
        color: var(--btn-text) !important;
        border: 1px solid var(--btn-border) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
        margin: 6px auto !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
      }

      [data-testid="stFileUploaderDropzoneInstructions"] {
        font-size: 0.82rem !important;
        color: var(--text-muted) !important;
        text-align: center !important;
        margin-top: 6px !important;
      }

      /* Expander header styling */
      [data-testid="stExpander"] {
        border: 1px solid var(--card-border) !important;
        border-radius: 12px !important;
        background: var(--card-bg) !important;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
      }

      [data-testid="stExpander"] summary {
        padding: 10px 14px !important;
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
      }

      [data-testid="stExpander"] summary:hover {
        color: #6366f1 !important;
      }

      /* Citations Card */
      .citation-card {
        background: var(--citation-bg);
        border: 1px solid var(--card-border);
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 8px 0;
      }

      /* Page viewer styling */
      .viewer-box {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 16px;
        box-shadow: var(--card-shadow);
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Cached resources ----------
@st.cache_resource(show_spinner="Loading local embedding model…")
def get_embedding_model() -> LocalEmbeddingModel:
    return LocalEmbeddingModel()


def get_vector_store() -> FAISSVectorStore:
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = FAISSVectorStore()
    return st.session_state.vector_store


@st.cache_resource
def get_chat_model(model_name: str, api_key: str | None = None) -> GroqChatModel:
    load_dotenv(override=True)
    key = api_key or os.getenv("GROQ_API_KEY")
    return GroqChatModel(model=model_name, api_key=key)


@st.cache_resource
def get_vision_model(model_name: str, api_key: str | None = None) -> GroqVisionModel:
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
    "index_status": None,  # None, "inspected", "text_only", "complete", "partial_visual_failure", "failed"
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------- Helpers ----------
def page_number(page: Any) -> int:
    return int(getattr(page, "page_number", 1))


def page_image(page: Any) -> bytes | None:
    image_bytes = getattr(page, "image_png", None)
    return image_bytes if isinstance(image_bytes, bytes) and image_bytes else None


def page_text(page: Any) -> str:
    return str(getattr(page, "text", "") or "").strip()


def set_question_input(question: str) -> None:
    st.session_state.question_input = question


def object_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_vector(vector: Any) -> list[float]:
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
    embedding = normalize_vector(embedding_model.embed_documents([text]))
    document = VectorDocument(
        id=item_id,
        text=text,
        embedding=embedding,
        metadata=metadata,
    )
    store.add_documents([document])


def format_history_for_prompt(history: list[dict[str, str]]) -> list[dict[str, str]]:
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
        "- If the question references a specific chart (e.g. Chart 1.1) or page, verify that the evidence matches that exact chart/page.\n"
        "- Do not confuse or substitute different charts (e.g., Chart 1.1 vs Chart 1.2).\n"
        "- Include [Page N] citations for claims supported by the evidence.\n"
        "- Format your answer cleanly in standard Markdown without empty bold tags (do not output **    ** or blank bold syntax)."
    )
    messages = format_history_for_prompt(st.session_state.chat_history)
    messages.append({"role": "user", "content": prompt})
    raw_answer = chat_model.generate(messages)
    cleaned_answer = clean_markdown_response(str(raw_answer))
    return cleaned_answer, evidence


def set_cited_page(number: int) -> None:
    total = len(st.session_state.pages)
    if total:
        st.session_state.cited_page = max(1, min(number, total))


# ---------- Header ----------
st.markdown(
    """
    <div class="hero-container">
      <div class="hero-title-area">
        <div class="hero-badge-icon">📄</div>
        <div>
          <h1 class="hero-title">Multimodal PDF RAG</h1>
          <div class="hero-subtitle">Intelligent document intelligence across text, charts, diagrams &amp; tables</div>
        </div>
      </div>
      <div class="hero-tags">
        <div class="hero-tag"><span>📝</span> Rich Text Extraction</div>
        <div class="hero-tag"><span>📊</span> Vision-Aware Charts</div>
        <div class="hero-tag"><span>🔍</span> FAISS Dense Retrieval</div>
        <div class="hero-tag"><span>🎯</span> Page-Level Citations</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- Three-column dashboard ----------
left, center, right = st.columns([1.0, 2.0, 1.4], gap="large")


# LEFT: upload, processing and settings
with left:
    st.markdown('<div class="ui-card-title">📁 1. Upload Document</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drag and drop a PDF here",
        type=["pdf"],
        help="Upload a PDF with selectable text, charts, tables, or diagrams.",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.getvalue()
        current_hash = hashlib.sha256(pdf_bytes).hexdigest()
        st.markdown(
            f'<div class="metric-badge"><span>📕 <b>{html.escape(uploaded_file.name)}</b></span>'
            f'<span style="color:#64748b; font-size:0.8rem;">{len(pdf_bytes) / (1024 * 1024):.2f} MB</span></div>',
            unsafe_allow_html=True,
        )
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

        if st.button("🔍 Inspect PDF Pages", use_container_width=True, type="primary"):
            try:
                with st.spinner("Extracting text and rendering PDF pages…"):
                    pages = ingest_pdf(pdf_bytes)
                    if not pages:
                        raise ValueError("No pages were found in this PDF.")
                    st.session_state.pages = pages
                    chunk_result = chunk_pages(pages)
                    st.session_state.chunks = list(
                        object_value(chunk_result, "chunks", []) or []
                    )
                    st.session_state.index_ready = False
                    st.session_state.index_status = "inspected"
                    st.session_state.visual_pages_succeeded = []
                    st.session_state.visual_pages_failed = []
                    st.session_state.processing_error = None
                    st.session_state.cited_page = 1
            except Exception as exc:
                st.session_state.processing_error = str(exc)
                st.session_state.pages = []
                st.session_state.chunks = []
                st.session_state.index_ready = False
                st.session_state.index_status = "failed"

    if st.session_state.processing_error:
        st.error(f"PDF processing failed: {st.session_state.processing_error}")

    pages = st.session_state.pages
    chunks = st.session_state.chunks
    text_pages = sum(1 for page in pages if page_text(page))
    rendered_pages = sum(1 for page in pages if page_image(page))

    st.markdown('<div class="ui-card-title" style="margin-top:14px;">⚡ 2. Document Status</div>', unsafe_allow_html=True)
    if pages:
        status_label = "Not Built"
        status_color = "#e11d48"
        if st.session_state.index_ready:
            if st.session_state.index_status == "complete":
                status_label = "Active (Text + Vision)"
                status_color = "#16a34a"
            elif st.session_state.index_status == "partial_visual_failure":
                status_label = "Active (Partial Vision)"
                status_color = "#d97706"
            elif st.session_state.index_status == "text_only":
                status_label = "Active (Text Only)"
                status_color = "#2563eb"
            else:
                status_label = "Active"
                status_color = "#16a34a"
        elif st.session_state.index_status == "inspected":
            status_label = "Inspected (Ready to Index)"
            status_color = "#6366f1"
        elif st.session_state.index_status == "failed":
            status_label = "Index Failed"
            status_color = "#dc2626"

        st.markdown(
            f'<div class="metric-badge"><span>📑 Total Pages</span><b>{len(pages)}</b></div>'
            f'<div class="metric-badge"><span>✂️ Text Chunks</span><b>{len(chunks)}</b></div>'
            f'<div class="metric-badge"><span>🖼️ Rendered Visuals</span><b>{rendered_pages}</b></div>'
            f'<div class="metric-badge"><span>⚡ Index State</span>'
            f'<b style="color:{status_color};">{status_label}</b></div>',
            unsafe_allow_html=True,
        )

        if st.session_state.visual_pages_failed:
            st.warning(
                f"Visual analysis failed on page(s): {', '.join(map(str, st.session_state.visual_pages_failed))}. "
                "Text search remains functional for all extracted pages."
            )

        no_text_pages = [
            page_number(page) for page in pages if not page_text(page)
        ]
        if no_text_pages:
            st.info(
                "Pages without text: "
                + ", ".join(map(str, no_text_pages[:8]))
                + (", …" if len(no_text_pages) > 8 else "")
                + ". Visual RAG will analyze these with multimodal vision."
            )
    else:
        st.info("Upload a PDF document to begin inspecting pages.")

    st.markdown("---")
    st.markdown('<div class="ui-card-title">⚙️ 3. Settings & Models</div>', unsafe_allow_html=True)
    chat_model_name = st.selectbox(
        "Chat Model (Groq)",
        options=["openai/gpt-oss-20b"],
        index=0,
        help="Fast inference with Groq.",
    )
    vision_model_name = st.selectbox(
        "Vision Model (Groq)",
        options=[os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")],
        help="Multimodal model for diagrams and figures.",
    )
    st.selectbox(
        "Embedding Provider",
        options=["Local MiniLM-L6-v2 (HuggingFace)"],
        help="Dense local embeddings running efficiently on CPU.",
    )

    if st.button("🔄 Reset Document & Chat", use_container_width=True):
        if uploaded_file is None:
            st.warning("No PDF uploaded.")
        else:
            st.session_state.index_ready = False
            st.session_state.visual_descriptions = []
            st.session_state.chat_history = []
            st.session_state.last_evidence = []
            st.rerun()

    st.markdown("---")
    has_groq_key = bool(os.getenv("GROQ_API_KEY"))
    st.markdown(
        f'<div style="font-size:0.82rem; color:{ "#16a34a" if has_groq_key else "#e11d48" }; font-weight:600;">'
        f'● Groq API Key: {"Connected" if has_groq_key else "Missing from .env"}</div>',
        unsafe_allow_html=True,
    )


# CENTER: index building, questions and chat
with center:
    st.markdown('<div class="ui-card-title">💬 Document Q&A & Research</div>', unsafe_allow_html=True)

    if pages and not st.session_state.index_ready:
        st.info("Your PDF pages are loaded. Click below to construct the multimodal search index.")
        if st.button("🚀 Build Search Index (Embeddings + Vision)", type="primary", use_container_width=True):
            if not os.getenv("GROQ_API_KEY"):
                st.error("GROQ_API_KEY is missing. Add it to `.env` before building the visual index.")
            else:
                try:
                    with st.spinner("Building index: embedding text chunks and generating visual analyses…"):
                        embedder = get_embedding_model()
                        vision_model = get_vision_model(vision_model_name)
                        store = get_vector_store()

                        if st.session_state.index_source:
                            store.delete_source(st.session_state.index_source)

                        index_source = st.session_state.pdf_hash
                        st.session_state.index_source = index_source
                        indexed_count = 0
                        text_indexed_count = 0

                        # Step 1: Index text chunks
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

                        # Step 2: Describe page images
                        pages_with_images = [
                            page for page in pages
                            if page_image(page)
                        ]

                        descriptions = []
                        succeeded_pages = []
                        failed_pages_dict: dict[int, str] = {}
                        progress = st.progress(0.0, text="Describing page visuals…")
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
                                        failed_pages_dict[pnum] = "Empty description returned"
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
                                if "401" in err_str or "invalid_api_key" in err_str.lower() or "authentication failed" in err_str.lower():
                                    st.error("❌ Invalid Groq API Key! Please verify GROQ_API_KEY in your `.env` file.")
                                    fatal_auth_error = True
                                    break
                                else:
                                    st.warning(f"Vision failed on PDF page {pnum}: {exc}")

                            progress.progress(
                                i / max(1, len(pages_with_images)),
                                text=f"Analyzing visuals ({i}/{len(pages_with_images)})",
                            )
                        progress.empty()

                        st.session_state.visual_descriptions = descriptions
                        st.session_state.index_source = index_source
                        st.session_state.indexed_items = indexed_count
                        st.session_state.visual_pages_succeeded = sorted(list(set(succeeded_pages)))
                        st.session_state.visual_pages_failed = sorted(list(failed_pages_dict.keys()))
                        st.session_state.index_ready = indexed_count > 0

                        if indexed_count == 0:
                            st.session_state.index_status = "failed"
                            st.error("No searchable content was indexed.")
                        elif len(failed_pages_dict) == 0 and len(descriptions) > 0:
                            st.session_state.index_status = "complete"
                            st.success(
                                f"✓ Index fully ready with {indexed_count} items ({text_indexed_count} text chunks, {len(descriptions)} visual analyses)."
                            )
                        elif len(descriptions) > 0:
                            st.session_state.index_status = "partial_visual_failure"
                            st.warning(
                                f"✓ Index ready with partial visual coverage ({indexed_count} total items: "
                                f"{text_indexed_count} text chunks, {len(descriptions)} visual analyses across {len(st.session_state.visual_pages_succeeded)} pages; "
                                f"failed on pages {st.session_state.visual_pages_failed})."
                            )
                        else:
                            st.session_state.index_status = "text_only"
                            st.info(
                                f"✓ Text-only index ready with {text_indexed_count} text chunks (visual analysis was unavailable or failed)."
                            )
                except Exception as exc:
                    st.session_state.index_status = "failed"
                    st.error("Index creation failed. Please check your credentials and logs.")
                    st.exception(exc)

    # QA Submission Form: Wrapping in st.form eliminates double-click and window collapse issues
    with st.form("ask_question_form", clear_on_submit=False):
        query = st.text_input(
            "Ask a question about text, charts, diagrams, or numbers in your PDF…",
            placeholder="e.g., What does the system architecture diagram illustrate?",
            label_visibility="collapsed",
            key="question_input",
            disabled=not st.session_state.index_ready,
        )
        ask_col, clear_col = st.columns([4, 1.2])
        with ask_col:
            ask_clicked = st.form_submit_button(
                "✨ Ask Question",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.index_ready,
            )
        with clear_col:
            clear_clicked = st.form_submit_button(
                "🗑️ Clear",
                use_container_width=True,
            )

    if clear_clicked:
        st.session_state.chat_history = []
        st.session_state.last_evidence = []
        st.session_state.last_question = None
        st.rerun()

    st.markdown('<div style="font-size:0.8rem; color:#64748b; font-weight:600; margin: 4px 0 6px 0;">Suggested Questions:</div>', unsafe_allow_html=True)
    examples = [
        "What is the main architecture described?",
        "What do the key charts or diagrams show?",
        "Summarize the technical results & tables.",
        "What are the main components and flow?",
    ]
    example_cols = st.columns(2)
    for i, example in enumerate(examples):
        with example_cols[i % 2]:
            st.button(
                example,
                key=f"example_{i}",
                use_container_width=True,
                disabled=not st.session_state.index_ready,
                on_click=set_question_input,
                args=(example,),
            )

    if ask_clicked:
        question = (st.session_state.question_input or "").strip()
        if not question:
            st.warning("Please type a question.")
        else:
            try:
                with st.spinner("Searching document & formulating verified answer…"):
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

    # Render conversation history with modern styling
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            content = html.escape(str(message["content"]))
            st.markdown(
                f'<div class="chat-user-msg"><b>You</b><br>{content}</div>',
                unsafe_allow_html=True,
            )
        else:
            assistant_content = clean_markdown_response(str(message["content"]))
            with st.container(key=f"chat-assistant-msg-{i}"):
                st.markdown('<b style="color:#4f46e5;">🤖 Assistant</b>', unsafe_allow_html=True)
                st.markdown(assistant_content)

    # Cited sources section
    last_evidence = st.session_state.get("last_evidence", [])
    if last_evidence:
        st.markdown('<div class="ui-card-title" style="margin-top:20px;">📚 Supporting Citations & Evidence</div>', unsafe_allow_html=True)
        seen_pages: set[int] = set()
        for item in last_evidence:
            pnum = int(item["page_number"])
            if pnum in seen_pages:
                continue
            seen_pages.add(pnum)
            preview = next(
                (page for page in pages if page_number(page) == pnum), None
            )
            c1, c2 = st.columns([1, 3.5])
            with c1:
                if preview and page_image(preview):
                    st.image(page_image(preview), use_container_width=True)
                else:
                    st.caption(f"Page {pnum}")
            with c2:
                ctype = "Visual Diagram" if item['content_type'] == "visual_description" else "Text Block"
                st.markdown(f"**Page {pnum}** · <span style='color:#6366f1; font-weight:600;'>{ctype}</span>", unsafe_allow_html=True)
                st.caption(item["text"][:260] + ("…" if len(item["text"]) > 260 else ""))
                if st.button(f"🔎 Jump to Page {pnum}", key=f"view_citation_{pnum}"):
                    set_cited_page(pnum)
                    st.rerun()


# RIGHT: cited page viewer
with right:
    current_pages = st.session_state.pages
    total_pages = len(current_pages)
    selected_page = st.session_state.cited_page

    st.markdown('<div class="ui-card-title">📖 Document Inspector</div>', unsafe_allow_html=True)

    nav_left, title_col, nav_right = st.columns([0.6, 2.0, 0.6])
    with title_col:
        st.markdown(
            f'<div style="text-align:center; font-weight:700; color:var(--text-primary); padding-top:4px;">'
            f'Page {selected_page} of {max(1, total_pages)}</div>',
            unsafe_allow_html=True,
        )
    with nav_left:
        if st.button("◀", key="prev_page", disabled=not current_pages or selected_page <= 1, use_container_width=True):
            set_cited_page(selected_page - 1)
            st.rerun()
    with nav_right:
        if st.button("▶", key="next_page", disabled=not current_pages or selected_page >= total_pages, use_container_width=True):
            set_cited_page(selected_page + 1)
            st.rerun()

    if current_pages:
        selected = next(
            (page for page in current_pages if page_number(page) == selected_page),
            current_pages[0],
        )
        image_bytes = page_image(selected)
        if image_bytes:
            st.image(image_bytes, use_container_width=True)
        else:
            st.warning("No rendered image is available for this page.")
        extracted_text = page_text(selected)
        if extracted_text:
            with st.expander("Extracted Page Text", expanded=False):
                st.text_area("Extracted Text", extracted_text, height=180, disabled=True, label_visibility="collapsed")
        else:
            st.caption("No raw text on this page.")

        st.markdown('<div style="font-weight:700; font-size:0.9rem; margin-top:16px; margin-bottom:8px; color:#334155;">Thumbnail Gallery</div>', unsafe_allow_html=True)
        thumbnail_pages = current_pages[
            max(0, selected_page - 3) : min(total_pages, selected_page + 2)
        ]
        thumb_cols = st.columns(min(5, max(1, len(thumbnail_pages))))
        for i, page in enumerate(thumbnail_pages):
            with thumb_cols[i % len(thumb_cols)]:
                pnum = page_number(page)
                img = page_image(page)
                if img:
                    st.image(img, use_container_width=True)
                if st.button(
                    f"P.{pnum}",
                    key=f"thumbnail_{pnum}",
                    type="primary" if pnum == selected_page else "secondary",
                    use_container_width=True,
                ):
                    set_cited_page(pnum)
                    st.rerun()
    else:
        st.info("Upload and inspect a PDF to view pages, diagrams, and citation highlights.")

st.markdown("---")
st.markdown(
    '<div style="text-align:center; color:#94a3b8; font-size:0.8rem;">'
    'Multimodal PDF RAG · Grounded answering with FAISS, Groq Vision &amp; Local Dense Embeddings'
    '</div>',
    unsafe_allow_html=True,
)
