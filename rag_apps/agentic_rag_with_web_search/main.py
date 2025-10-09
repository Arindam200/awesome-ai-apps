import os

from crews import crew
from dotenv import load_dotenv
from operator import ne
from qdrant_tool import load_pdf_to_qdrant
import base64
import shutil
import streamlit as st
import tempfile
load_dotenv()

st.set_page_config(page_title="Agentic RAG", layout="wide")

# Ensure session state variables are initialized
if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = None
if "docs_loaded" not in st.session_state:
    st.session_state.docs_loaded = False
if "messages" not in st.session_state:
    st.session_state.messages = []

def display_pdf_preview(pdf_file):
    """Display PDF preview in the sidebar."""
    try:
        # Display PDF info
        st.sidebar.subheader("PDF Preview")

        # Convert PDF to base64 for display
        base64_pdf = base64.b64encode(pdf_file.getvalue()).decode('utf-8')

        # Display PDF using HTML iframe
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
        st.sidebar.markdown(pdf_display, unsafe_allow_html=True)

        return True
    except Exception as e:
        st.sidebar.error(f"Error previewing PDF: {str(e)}")
        return False

# Load the knowledge base: Comment after first run as the knowledge base is already loaded

col1, col2 = st.columns([4, 1])
with col1:
    # Convert images to base64
    with open("./assets/qdrant-logo.svg", "rb") as qdrant_file:
        qdrant_base64 = base64.b64encode(qdrant_file.read()).decode()

    with open("./assets/exa-logo.png", "rb") as exa_file:
        exa_base64 = base64.b64encode(exa_file.read()).decode()

    with open("./assets/crewai-logo.png", "rb") as crew_file:
        crew_base64 = base64.b64encode(crew_file.read()).decode()

    with open("./assets/Nebius.png", "rb") as nebius_file:
        nebius_base64 = base64.b64encode(nebius_file.read()).decode()

    # Create title with embedded images
    title_html = f"""
        <div style="display: flex; align-items: center; gap: 10px;">
          <div>
            <h1 style="margin: 0;">
             Agentic RAG with Web Search
            </h1>
            <h2 style="margin: 0; font-size: 1.2em; color: #555;">
             powered by <img src="data:image/png;base64,{crew_base64}" style="height: 44px; margin: 1; top: -20px;">
            </h2>
            </div>
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

with st.sidebar:

    st.image("./assets/qdrant-logo.svg", width=180)

    qdrant_api_key = st.text_input(
        "Qdrant API Key",
        value=os.getenv("QDRANT_API_KEY", ""),
        type="password",
        help="Your Qdrant API key",
    )

    qdrant_url = st.text_input(
        "Qdrant URL",
        value=os.getenv("QDRANT_URL", ""),
        type="password",
        help="Your Qdrant URL",
    )

    st.divider()

    st.image("./assets/exa-logo.png", width=100)

    exa_api_key = st.text_input(
        "Exa API Key",
        value=os.getenv("EXA_API_KEY", ""),
        type="password",
        help="Your Exa API key",
    )

    st.divider()

    # PDF file upload
    st.subheader("Upload PDF")
    uploaded_file = st.file_uploader(
        "Choose a PDF file", type="pdf", accept_multiple_files=False
    )

    # Handle PDF upload and processing
    if uploaded_file is not None:
        if uploaded_file != st.session_state.current_pdf:
            st.session_state.current_pdf = uploaded_file
            try:
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
                try:
                    print(f"Loading PDF to Qdrant: {file_path}")
                    load_pdf_to_qdrant(file_path)
                    print("PDF loaded to Qdrant")
                except Exception as e:
                    st.error(f"Error loading PDF to Qdrant: {str(e)}")
                st.success("✓ PDF loaded successfully")

            except Exception as e:
                st.error(f"Error: {str(e)}")
        # Always show preview
        display_pdf_preview(uploaded_file)

    st.markdown("---")

query = st.chat_input("Ask about your PDF...", width=1000)
if query:
    if not st.session_state.docs_loaded:
        st.warning("Please upload a PDF file first.")
    else:
        # Add user message
        response = crew.kickoff(inputs={"query": query})
        # st.markdown("#### Answer \n", unsafe_allow_html=True)
        st.markdown(response.raw, unsafe_allow_html=True)
        # answer = ""
        # answer_placeholder = st.empty()
        # for event in response:
        #     if hasattr(event, "raw") and event.raw:
        #         answer += event.raw
        #         answer_placeholder.markdown(answer, unsafe_allow_html=True)


# if __name__ == "__main__":
# response = agentic_rag_response(["https://modelcontextprotocol.io/docs/learn/architecture.md"], "Tell me about MCP primitives that clients can expose.")
# pprint_run_response(response, markdown=True)