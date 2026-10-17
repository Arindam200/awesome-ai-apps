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
    from ingestion import ingest_pdf
    from chunking import chunk_pages
    from vision import describe_pdf_pages
    from embeddings.local import LocalEmbeddingModel
    from vectorstores.faiss_store import FAISSVectorStore
    from interfaces.vector_store import VectorDocument
    from providers.groq_chat import GroqChatModel
    from providers.groq_vision import GroqVisionModel
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
      .stApp {
        background: linear-gradient(135deg, #f6f8ff 0%, #fbfcff 48%, #f2f6ff 100%);
        color: #101735;
      }
      .block-container { padding-top: 1.25rem; padding-bottom: 1rem; max-width: 100%; }
      h1, h2, h3 { color: #101735; letter-spacing: -0.025em; }
      .hero {
        padding: 8px 4px 18px 4px;
        display: flex; align-items: center; justify-content: space-between; gap: 18px;
      }
      .hero-title { font-size: 2.25rem; font-weight: 800; line-height: 1.05; }
      .hero-subtitle { color: #5a6380; font-size: 1.05rem; margin-top: 8px; }
      .feature-strip {
        background: #edf3ff; border: 1px solid #e0e9ff; border-radius: 16px;
        padding: 17px; color: #39496f; display: flex; gap: 18px;
        justify-content: space-around; flex-wrap: wrap; font-size: .9rem;
      }
      .panel {
        background: rgba(255,255,255,.86); border: 1px solid #e3e9f5;
        border-radius: 15px; padding: 15px; min-height: 180px;
      }
      .metric {
        border: 1px solid #e1e8f6; background: #f7f9ff; border-radius: 11px;
        padding: 10px 12px; margin: 6px 0; font-size: .93rem;
      }
      .chat-user {
        background: #ecebff; border: 1px solid #e1dfff; border-radius: 12px;
        padding: 14px 16px; margin: 12px 0;
      }
      .chat-assistant {
        background: #f8faff; border: 1px solid #e7ebf6; border-radius: 12px;
        padding: 16px; margin: 10px 0;
      }
      .citation {
        border: 1px solid #dfe6f5; border-radius: 12px; background: #fff;
        padding: 12px; margin: 8px 0;
      }
      div.stButton > button {
        border-radius: 10px; border: 1px solid #dce3f4; font-weight: 600;
      }
      div.stButton > button[kind="primary"] {
        background: #625cf6; border-color: #625cf6; color: white;
      }
      [data-testid="stFileUploader"] {
        background: rgba(255,255,255,.75); border: 1px dashed #b9c8e6;
        border-radius: 12px; padding: 8px;
      }
      .small-muted { color: #6b7590; font-size: .82rem; }
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
def get_chat_model(model_name: str) -> GroqChatModel:
    # The provider implementation should accept model=...; if yours uses a
    # different constructor argument, adjust this line to match groq_chat.py.
    return GroqChatModel(model=model_name)


@st.cache_resource
def get_vision_model(model_name: str) -> GroqVisionModel:
    return GroqVisionModel(model=model_name)


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
                "You are a helpful assistant answering questions about an uploaded PDF. "
                "Use only the supplied evidence. If evidence is insufficient, say so. "
                "Cite supporting pages using [Page N]. Distinguish information explicitly "
                "shown in a chart or diagram from your own interpretation. Do not invent "
                "numbers, chart labels, or claims."
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
    query_embedding = normalize_vector(embedder.embed_query(query))
    store = get_vector_store()
    candidate_limit = top_k
    results = []
    while True:
        candidates = store.search(query_embedding, top_k=candidate_limit)
        results = [
            result
            for result in candidates
            if (object_value(result, "metadata", {}) or {}).get("source_id")
            == source_id
        ]
        if len(results) >= top_k or len(candidates) < candidate_limit:
            break
        candidate_limit *= 2

    evidence = []
    for result in results[:top_k]:
        metadata = object_value(result, "metadata", {}) or {}
        evidence.append(
            {
                "page_number": int(metadata.get("page_number", 1)),
                "text": str(object_value(result, "text", "")),
                "content_type": metadata.get("content_type", "text"),
                "source": metadata.get("source", st.session_state.pdf_name or "uploaded PDF"),
                "score": object_value(result, "score"),
            }
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
        "Answer clearly and concisely. Use bullet points for key findings when useful. "
        "Include [Page N] citations for claims supported by the evidence. If the evidence "
        "does not answer the question, state what is missing."
    )
    messages = format_history_for_prompt(st.session_state.chat_history)
    messages.append({"role": "user", "content": prompt})
    answer = chat_model.generate(messages)
    return str(answer), evidence


def set_cited_page(number: int) -> None:
    total = len(st.session_state.pages)
    if total:
        st.session_state.cited_page = max(1, min(number, total))


# ---------- Header ----------
st.markdown(
    """
    <div class="hero">
      <div>
        <div class="hero-title">📄 Multimodal PDF RAG</div>
        <div class="hero-subtitle">Ask questions about text, charts, tables and diagrams in your PDF</div>
      </div>
      <div class="feature-strip">
        <span>▧ Understands text</span>
        <span>▥ Reads charts &amp; tables</span>
        <span>♧ Interprets diagrams</span>
        <span>⌕ Cites pages with evidence</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- Three-column dashboard ----------
left, center, right = st.columns([0.95, 2.1, 1.45], gap="medium")


# LEFT: upload, processing and settings
with left:
    st.markdown("### 1. Upload PDF")
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
            f'<div class="metric">📕 <b>{html.escape(uploaded_file.name)}</b><br>'
            f'<span class="small-muted">{len(pdf_bytes) / (1024 * 1024):.2f} MB</span></div>',
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

        if st.button("Inspect PDF pages", use_container_width=True):
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
                    st.session_state.processing_error = None
                    st.session_state.cited_page = 1
            except Exception as exc:
                st.session_state.processing_error = str(exc)
                st.session_state.pages = []
                st.session_state.chunks = []
                st.session_state.index_ready = False

    if st.session_state.processing_error:
        st.error(f"PDF processing failed: {st.session_state.processing_error}")

    pages = st.session_state.pages
    chunks = st.session_state.chunks
    text_pages = sum(1 for page in pages if page_text(page))
    rendered_pages = sum(1 for page in pages if page_image(page))

    st.markdown("### 2. Processing")
    if pages:
        st.success("PDF processed successfully!")
        st.markdown(f'<div class="metric">✣ Pages: <b>{len(pages)}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric">✣ Text chunks: <b>{len(chunks)}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric">▧ Page images rendered: <b>{rendered_pages}</b></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="metric">⌘ Index: <b>{"Created (text + visuals)" if st.session_state.index_ready else "Not built yet"}</b></div>',
            unsafe_allow_html=True,
        )
        no_text_pages = [
            page_number(page) for page in pages if not page_text(page)
        ]
        if no_text_pages:
            st.warning(
                "Some pages have no selectable text: "
                + ", ".join(map(str, no_text_pages[:12]))
                + (", …" if len(no_text_pages) > 12 else "")
                + ". OCR is not automatically performed by this app."
            )
    else:
        st.info("Upload a PDF, then choose **Inspect PDF pages**.")

    st.markdown("---")
    st.markdown("### 3. Model & Settings")
    chat_model_name = st.selectbox(
        "LLM Provider",
        options=["openai/gpt-oss-20b"],
        index=0,
        help="Groq model IDs are configured in providers/groq_chat.py.",
    )
    vision_model_name = st.selectbox(
        "Vision Provider",
        options=[os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")],
        help="Groq model ID configured in providers/groq_vision.py.",
    )
    st.selectbox(
        "Embedding Provider",
        options=["Local Sentence Transformers (all-MiniLM-L6-v2)"],
        help="Embeddings run locally after the model is downloaded.",
    )
    offline_mode = st.toggle(
        "Use local / offline mode (if available)",
        value=False,
        help="Local embeddings are used. Groq chat and vision still require an internet connection and GROQ_API_KEY.",
    )
    if offline_mode:
        st.info(
            "Local embeddings are enabled, but full offline question answering is not "
            "available unless you configure a local chat and vision provider."
        )

    if st.button("↻ Reprocess PDF", use_container_width=True, type="primary"):
        if uploaded_file is None:
            st.warning("Upload a PDF first.")
        else:
            st.session_state.index_ready = False
            st.session_state.visual_descriptions = []
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")
    st.caption("API key: " + ("configured" if os.getenv("GROQ_API_KEY") else "missing"))
    if not os.getenv("GROQ_API_KEY"):
        st.warning("Set GROQ_API_KEY in your `.env` file to enable Groq chat and vision.")


# CENTER: index building, questions and chat
with center:
    st.markdown("### Ask a question about your PDF")

    if pages and not st.session_state.index_ready:
        st.info(
            "Your PDF has been inspected. Build the search index to search both "
            "extracted text and visual descriptions."
        )
        if st.button("Build search index", type="primary", use_container_width=True):
            if not os.getenv("GROQ_API_KEY"):
                st.error("GROQ_API_KEY is missing. Add it to `.env` before building the visual index.")
            else:
                try:
                    with st.spinner("Building index: embedding text and describing page visuals…"):
                        embedder = get_embedding_model()
                        vision_model = get_vision_model(vision_model_name)
                        store = get_vector_store()

                        # Remove the previous document's vectors before re-indexing.
                        if st.session_state.index_source:
                            store.delete_source(st.session_state.index_source)

                        index_source = st.session_state.pdf_hash
                        st.session_state.index_source = index_source
                        indexed_count = 0

                        # Index text chunks, retaining source page metadata.
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

                        # Describe page images, one page at a time to reduce rate-limit risk.
                        descriptions = []
                        pages_with_images = [page for page in pages if page_image(page)]
                        progress = st.progress(0.0, text="Describing page visuals…")
                        for i, page in enumerate(pages_with_images):
                            try:
                                result = describe_pdf_pages([page], vision_model)
                                for description in result:
                                    desc_text = str(
                                        object_value(description, "description", "") or ""
                                    ).strip()
                                    if not desc_text:
                                        continue
                                    pnum = int(object_value(description, "page_number", page_number(page)))
                                    descriptions.append(description)
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
                                # A single page failing should not discard the text index.
                                st.warning(f"Could not describe page {page_number(page)}: {exc}")
                            progress.progress(
                                (i + 1) / max(1, len(pages_with_images)),
                                text=f"Describing page visuals… ({i + 1}/{len(pages_with_images)})",
                            )
                        progress.empty()

                        st.session_state.visual_descriptions = descriptions
                        st.session_state.index_source = index_source
                        st.session_state.indexed_items = indexed_count
                        st.session_state.index_ready = indexed_count > 0
                        if st.session_state.index_ready:
                            st.success(
                                f"Index created successfully: {indexed_count} searchable items "
                                f"({len(chunks)} text chunks available; "
                                f"{len(descriptions)} visual descriptions indexed)."
                            )
                        else:
                            st.error("No searchable text or visual descriptions were indexed.")
                except Exception as exc:
                    st.error("Index creation failed. Check the provider configuration and module APIs.")
                    st.exception(exc)

    query = st.text_input(
        "Ask anything about the document (text, charts, tables, diagrams)…",
        placeholder="Ask anything about the document (text, charts, tables, diagrams)…",
        label_visibility="collapsed",
        key="question_input",
        disabled=not st.session_state.index_ready,
    )
    st.caption("Try these example questions:")
    examples = [
        "What is the main contribution of this paper?",
        "What does the chart on page 5 show?",
        "Explain the architecture diagram on page 3.",
        "What are the key results in the table?",
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

    ask_col, clear_col = st.columns([4, 1])
    with ask_col:
        ask_clicked = st.button(
            "➤ Ask question",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.index_ready,
        )
    with clear_col:
        if st.button("Clear chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.last_evidence = []
            st.session_state.last_question = None
            st.rerun()

    if ask_clicked:
        question = (st.session_state.question_input or "").strip()
        if not question:
            st.warning("Enter a question first.")
        else:
            try:
                with st.spinner("Retrieving evidence and generating an answer…"):
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

    # Render conversation history.
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            content = html.escape(str(message["content"]))
            st.markdown(
                f'<div class="chat-user">👤 {content}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="chat-assistant">🤖</div>',
                unsafe_allow_html=True,
            )
            st.markdown(str(message["content"]))

    # Evidence cards for the most recent answer.
    last_evidence = st.session_state.get("last_evidence", [])
    if last_evidence:
        st.markdown("#### Cited Sources")
        seen_pages: set[int] = set()
        for item in last_evidence:
            pnum = int(item["page_number"])
            if pnum in seen_pages:
                continue
            seen_pages.add(pnum)
            preview = next(
                (page for page in pages if page_number(page) == pnum), None
            )
            c1, c2 = st.columns([1, 4])
            with c1:
                if preview and page_image(preview):
                    st.image(page_image(preview), use_container_width=True)
                else:
                    st.caption(f"Page {pnum}")
            with c2:
                st.markdown(f"**Page {pnum}** · {item['content_type']}")
                st.caption(item["text"][:260] + ("…" if len(item["text"]) > 260 else ""))
                if st.button(f"View Page {pnum} →", key=f"view_citation_{pnum}"):
                    set_cited_page(pnum)
                    st.rerun()


# RIGHT: cited page viewer
with right:
    current_pages = st.session_state.pages
    total_pages = len(current_pages)
    selected_page = st.session_state.cited_page

    nav_left, title_col, nav_right = st.columns([0.55, 2.3, 0.55])
    with title_col:
        st.markdown(f"### Cited Page: {selected_page}")
    with nav_left:
        if st.button("‹", key="prev_page", disabled=not current_pages or selected_page <= 1):
            set_cited_page(selected_page - 1)
            st.rerun()
    with nav_right:
        if st.button("›", key="next_page", disabled=not current_pages or selected_page >= total_pages):
            set_cited_page(selected_page + 1)
            st.rerun()

    st.caption(f"Page {selected_page} / {total_pages}" if total_pages else "Upload a PDF to preview pages.")

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
            with st.expander("View extracted page text"):
                st.write(extracted_text)
        else:
            st.caption("No selectable text was extracted from this page.")

        st.markdown("#### Page thumbnails")
        # Streamlit has no built-in horizontally scrolling thumbnail carousel;
        # this compact grid provides page navigation with the same functionality.
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
                    str(pnum),
                    key=f"thumbnail_{pnum}",
                    type="primary" if pnum == selected_page else "secondary",
                    use_container_width=True,
                ):
                    set_cited_page(pnum)
                    st.rerun()
    else:
        st.info("Your cited PDF page will appear here after upload and inspection.")

st.markdown("---")
st.caption(
    "Multimodal PDF RAG · Page citations are based on retrieved indexed evidence. "
    "Scanned PDFs may require OCR, which is not included by default."
)
