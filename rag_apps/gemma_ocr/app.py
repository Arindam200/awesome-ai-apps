import os
from openai import OpenAI
import streamlit as st
import os
from dotenv import load_dotenv
import tempfile
import shutil
import base64
import io
import re
import mimetypes
from openai import OpenAI
import base64
import os
import tempfile
from PIL import Image
import fitz  # PyMuPDF for PDF to image

load_dotenv()

st.set_page_config(page_title="Gemma 3 OCR", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "docs_loaded" not in st.session_state:
    st.session_state.docs_loaded = False
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = None
if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None

col1, col2 = st.columns([4, 1])
with col1:
    # Convert images to base64
    with open("./assets/gemma.png", "rb") as gemma_file:
        gemma_base64 = base64.b64encode(gemma_file.read()).decode()

    # Create title with embedded images
    title_html = f"""
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1 style="margin: 0;">
            <img src="data:image/png;base64,{gemma_base64}" style="height: 56px; margin: 0;">
             <span style="color: #2E96FF;"> Gemma 3 </span> OCR with Nebius AI Studio
            </h1>
        </div>
        """
    st.markdown(title_html, unsafe_allow_html=True)
with col2:
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.docs_loaded = False
        if st.session_state.temp_dir:
            shutil.rmtree(st.session_state.temp_dir)
            st.session_state.temp_dir = None
        st.session_state.current_pdf = None
        st.rerun()

# Sidebar for configuration
with st.sidebar:
    st.image("./assets/Nebius.png", width=150)

    # Model selection
    nebius_api_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius API key",
    )

    st.divider()

    # PDF or Image file upload
    st.subheader("Upload PDF or Image")
    uploaded_file = st.file_uploader(
        "Choose a PDF, JPG, or PNG file",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=False,
    )

    def display_file_preview(file):
        if file is None:
            return
        file_type = file.type
        if file_type == "application/pdf":
            # Display PDF preview
            st.sidebar.subheader("PDF Preview")
            base64_pdf = base64.b64encode(file.getvalue()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
            st.sidebar.markdown(pdf_display, unsafe_allow_html=True)
        elif file_type in ["image/png", "image/jpeg", "image/jpg"]:
            st.sidebar.subheader("Image Preview")
            st.sidebar.image(file, use_container_width=True)
        else:
            st.sidebar.info("Unsupported file type for preview.")

    def ocr(file, api_key):
        file_type = file.type
        file_bytes = file.getvalue()
        client = OpenAI(
            base_url="https://api.studio.nebius.com/v1/",
            api_key=api_key or os.environ.get("NEBIUS_API_KEY"),
        )
        if file_type in ["image/png", "image/jpeg", "image/jpg"]:
            b64_data = base64.b64encode(file_bytes).decode()
            mime = file_type
            with st.spinner("Extracting text from image..."):
                try:
                    response = client.chat.completions.create(
                        model="google/gemma-3-27b-it",
                        max_tokens=512,
                        temperature=0.5,
                        top_p=0.9,
                        extra_body={"top_k": 50},
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Extract the Details and use Tables where applicable",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime};base64,{b64_data}"
                                        },
                                    },
                                ],
                            }
                        ],
                    )
                    return (
                        response.choices[0].message.content
                        if hasattr(response.choices[0].message, "content")
                        else str(response)
                    )
                except Exception as e:
                    return f"OCR API call failed: {e}"
        elif file_type == "application/pdf":
            # Process all pages
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp_pdf:
                    tmp_pdf.write(file_bytes)
                    tmp_pdf.flush()
                    doc = fitz.open(tmp_pdf.name)
                    num_pages = doc.page_count
                    results = []
                    progress = st.progress(0, text="Processing PDF pages...")
                    for i in range(num_pages):
                        page = doc.load_page(i)
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        b64_data = base64.b64encode(img_bytes).decode()
                        mime = "image/png"
                        try:
                            response = client.chat.completions.create(
                                model="google/gemma-3-27b-it",
                                # max_tokens=512,
                                temperature=0.5,
                                top_p=0.9,
                                extra_body={"top_k": 50},
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "Extract the Details in a Table",
                                            },
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": f"data:{mime};base64,{b64_data}"
                                                },
                                            },
                                        ],
                                    }
                                ],
                            )
                            text = (
                                response.choices[0].message.content
                                if hasattr(response.choices[0].message, "content")
                                else str(response)
                            )
                        except Exception as e:
                            text = f"OCR API call failed on page {i+1}: {e}"
                        results.append(f"### Page {i+1}\n" + text)
                        progress.progress(
                            (i + 1) / num_pages,
                            text=f"Processed {i+1} of {num_pages} pages...",
                        )
                    progress.empty()
                    return "\n\n".join(results)
            except Exception as e:
                return f"PDF to image conversion failed: {e}"
        else:
            return "Unsupported file type for OCR."

    # Handle file upload and processing
    if uploaded_file is not None:
        if uploaded_file != st.session_state.current_pdf:
            st.session_state.current_pdf = uploaded_file
            try:
                if not os.getenv("NEBIUS_API_KEY"):
                    st.error("Missing Nebius API key")
                    st.stop()

                # Create temporary directory for the file
                if st.session_state.temp_dir:
                    shutil.rmtree(st.session_state.temp_dir)
                st.session_state.temp_dir = tempfile.mkdtemp()

                # Save uploaded file to temp directory
                file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                st.session_state.docs_loaded = True
                st.session_state.current_file = uploaded_file
                if uploaded_file.type == "application/pdf":
                    st.success("✓ PDF loaded successfully")
                else:
                    st.success("✓ Image loaded successfully")

            except Exception as e:
                st.error(f"Error: {str(e)}")
        # Always show preview
        display_file_preview(uploaded_file)
        # OCR button
        if st.button("🔍 Extract Text (OCR)"):
            extracted_text = ocr(uploaded_file, nebius_api_key)
            st.session_state.extracted_text = extracted_text

# In the main section (center), after the columns:
if "extracted_text" in st.session_state:
    st.markdown("### Extracted Text")
    st.markdown(st.session_state.extracted_text)
