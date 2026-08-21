from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping

import streamlit as st
from dotenv import load_dotenv

from create_sample_pdf import SAMPLE_VISUAL_DESCRIPTIONS, build_sample_pdf
from rag import (
    ExtractiveAnswerGenerator,
    ImageAwarePdfRag,
    OpenAIAnswerGenerator,
    OpenAIVisionDescriber,
    PdfValidationError,
)

load_dotenv()

st.set_page_config(page_title="PageLens PDF RAG", page_icon="PDF", layout="wide")


def _build_pipeline(api_key: str, use_vision: bool) -> ImageAwarePdfRag:
    vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
    answer_model = os.getenv("OPENAI_ANSWER_MODEL", "gpt-4.1-mini")
    vision = OpenAIVisionDescriber(api_key, vision_model) if api_key and use_vision else None
    answerer = (
        OpenAIAnswerGenerator(api_key, answer_model) if api_key else ExtractiveAnswerGenerator()
    )
    return ImageAwarePdfRag(vision_describer=vision, answer_generator=answerer)


def _select_document(
    uploaded_file: st.runtime.uploaded_file_manager.UploadedFile | None,
) -> tuple[str, bytes, Mapping[int, str] | None] | None:
    if uploaded_file is not None:
        return uploaded_file.name, uploaded_file.getvalue(), None
    return st.session_state.get("sample_document")


st.title("PageLens PDF RAG")

with st.sidebar:
    st.subheader("Model")
    api_key = st.text_input(
        "OpenAI API key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
    )
    use_vision = st.checkbox("Describe page visuals", value=bool(api_key), disabled=not api_key)
    top_k = st.slider("Evidence pages", min_value=1, max_value=5, value=3)
    mode = "OpenAI vision + answer" if api_key else "Offline extractive"
    st.caption(mode)

upload_col, sample_col = st.columns([3, 1])
with upload_col:
    uploaded_file = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
with sample_col:
    if st.button("Load sample", use_container_width=True):
        st.session_state["sample_document"] = (
            "sample_report.pdf",
            build_sample_pdf(),
            SAMPLE_VISUAL_DESCRIPTIONS,
        )

document = _select_document(uploaded_file)
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
