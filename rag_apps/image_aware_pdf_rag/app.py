from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping

import streamlit as st
from dotenv import load_dotenv

from create_sample_pdf import SAMPLE_VISUAL_DESCRIPTIONS, build_sample_pdf
from rag import (
    DEFAULT_NEBIUS_BASE_URL,
    DEFAULT_NEBIUS_TIMEOUT_SECONDS,
    ExtractiveAnswerGenerator,
    ImageAwarePdfRag,
    NebiusAnswerGenerator,
    NebiusVisionDescriber,
    PdfValidationError,
)

load_dotenv()

st.set_page_config(page_title="PageLens PDF RAG", page_icon="PDF", layout="wide")


def _configured_timeout() -> float:
    """Read the provider timeout while keeping an invalid env value harmless."""
    try:
        return max(
            1.0,
            float(os.getenv("NEBIUS_TIMEOUT_SECONDS", str(DEFAULT_NEBIUS_TIMEOUT_SECONDS))),
        )
    except ValueError:
        return DEFAULT_NEBIUS_TIMEOUT_SECONDS


def _build_pipeline(api_key: str, use_vision: bool) -> ImageAwarePdfRag:
    """Build an offline or Nebius-backed pipeline from the current settings."""
    base_url = os.getenv("NEBIUS_BASE_URL", DEFAULT_NEBIUS_BASE_URL)
    vision_model = os.getenv("NEBIUS_VISION_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct")
    answer_model = os.getenv("NEBIUS_ANSWER_MODEL", "Qwen/Qwen3-235B-A22B")
    timeout = _configured_timeout()
    vision = (
        NebiusVisionDescriber(api_key, vision_model, base_url, timeout)
        if api_key and use_vision
        else None
    )
    answerer = (
        NebiusAnswerGenerator(api_key, answer_model, base_url, timeout)
        if api_key
        else ExtractiveAnswerGenerator()
    )
    return ImageAwarePdfRag(vision_describer=vision, answer_generator=answerer)


def _select_document(
    uploaded_file: st.runtime.uploaded_file_manager.UploadedFile | None,
    source: str,
) -> tuple[str, bytes, Mapping[int, str] | None] | None:
    """Select exactly one document source, even when Streamlit retains uploads."""
    if source == "sample":
        return st.session_state.get("sample_document")
    if uploaded_file is not None:
        return uploaded_file.name, uploaded_file.getvalue(), None
    return None


def _load_sample() -> None:
    """Store the bundled sample and switch the active source to it."""
    st.session_state["sample_document"] = (
        "sample_report.pdf",
        build_sample_pdf(),
        SAMPLE_VISUAL_DESCRIPTIONS,
    )
    st.session_state["document_source"] = "sample"


st.title("PageLens PDF RAG")

with st.sidebar:
    st.subheader("Model")
    api_key = st.text_input(
        "Nebius API key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
    )
    use_vision = st.checkbox("Describe page visuals", value=bool(api_key), disabled=not api_key)
    top_k = st.slider("Evidence pages", min_value=1, max_value=5, value=3)
    st.session_state.setdefault("document_source", "upload")
    source = st.radio(
        "Document source",
        options=("upload", "sample"),
        format_func=lambda value: "Upload PDF" if value == "upload" else "Bundled sample",
        key="document_source",
    )
    if api_key:
        mode = "Nebius vision + answer" if use_vision else "Nebius text-only answer"
    else:
        mode = "Offline extractive"
    st.caption(mode)

upload_col, sample_col = st.columns([3, 1])
with upload_col:
    uploaded_file = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
with sample_col:
    st.button("Load sample", use_container_width=True, on_click=_load_sample)

document = _select_document(uploaded_file, source)
if document is not None:
    file_name, pdf_bytes, visual_descriptions = document
    fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
    st.caption(f"Selected: {file_name} ({len(pdf_bytes) / 1024:.1f} KB)")
    if st.button("Index document", type="primary"):
        pipeline = _build_pipeline(api_key, use_vision)
        try:
            with st.spinner("Rendering and indexing pages..."):
                pages = pipeline.index_pdf(pdf_bytes, visual_descriptions)
        except PdfValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
        else:
            st.session_state["pipeline"] = pipeline
            st.session_state["fingerprint"] = fingerprint
            st.success(f"Indexed {len(pages)} pages")

pipeline: ImageAwarePdfRag | None = st.session_state.get("pipeline")
is_current_document = document is not None and st.session_state.get("fingerprint") == fingerprint

st.divider()
with st.form("question_form"):
    question = st.text_input(
        "Question", placeholder="Which quarter had the highest activation rate?"
    )
    submitted = st.form_submit_button(
        "Ask",
        type="primary",
        disabled=pipeline is None or not is_current_document,
    )

if submitted and pipeline is not None:
    try:
        with st.spinner("Retrieving page evidence..."):
            answer = pipeline.ask(question, top_k=top_k)
    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error(f"Question failed: {exc}")
    else:
        st.subheader("Answer")
        st.markdown(answer.text)
        st.subheader("Evidence")
        if not answer.hits:
            st.info("No matching page evidence was found.")
        for hit in answer.hits:
            label = f"Page {hit.page_number} - score {hit.score:.3f}"
            with st.expander(label, expanded=hit == answer.hits[0]):
                preview_col, evidence_col = st.columns([1, 1])
                with preview_col:
                    st.image(hit.evidence.image_png, caption=f"Page {hit.page_number}")
                with evidence_col:
                    if hit.evidence.visual_description:
                        st.markdown("**Visual evidence**")
                        st.write(hit.evidence.visual_description)
                    if hit.evidence.text:
                        st.markdown("**Extracted text**")
                        st.text(hit.evidence.text[:2500])

if pipeline is None or not is_current_document:
    st.caption("Index the selected PDF to enable questions.")
