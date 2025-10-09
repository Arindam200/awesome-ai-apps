import os
import re

from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, Settings, VectorStoreIndex
from llama_index.embeddings.nebius import NebiusEmbedding
from llama_index.llms.nebius import NebiusLLM
import base64
import io
import shutil
import streamlit as st
import tempfile
load_dotenv()

def run_rag_completion(
    documents,
    query_text: str,
    embedding_model: str = "BAAI/bge-en-icl",
    generative_model: str = "Qwen/Qwen3-235B-A22B"
) -> str:
    """Run RAG completion using Nebius models."""
    llm = NebiusLLM(
        model=generative_model,
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    embed_model = NebiusEmbedding(
        model_name=embedding_model,
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    Settings.llm = llm
    Settings.embed_model = embed_model

    index = VectorStoreIndex.from_documents(documents)
    response = index.as_query_engine(similarity_top_k=5).query(query_text)

    return str(response)

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

def format_reasoning_response(thinking_content):
    """Format assistant content by removing think tags."""
    return (
        thinking_content.replace("<think>\n\n</think>", "")
        .replace("<think>", "")
        .replace("</think>", "")
    )

def display_assistant_message(content):
    """Display assistant message with thinking content if present."""
    pattern = r"<think>(.*?)</think>"
    think_match = re.search(pattern, content, re.DOTALL)
    if think_match:
        think_content = think_match.group(0)
        response_content = content.replace(think_content, "")
        think_content = format_reasoning_response(think_content)
        with st.expander("Thinking complete!"):
            st.markdown(think_content)
        st.markdown(response_content)
    else:
        st.markdown(content)

def main():
    st.set_page_config(page_title="Nebius RAG Chat", layout="wide")

    # Initialize session states
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "docs_loaded" not in st.session_state:
        st.session_state.docs_loaded = False
    if "temp_dir" not in st.session_state:
        st.session_state.temp_dir = None
    if "current_pdf" not in st.session_state:
        st.session_state.current_pdf = None

    # Header with title and buttons
    col1, col2 = st.columns([4, 1])
    with col1:
        # Convert images to base64
        with open("./assets/Qwen.png", "rb") as qwen_file:
            qwen_base64 = base64.b64encode(qwen_file.read()).decode()
        with open("./assets/LlamaIndex.png", "rb") as llama_file:
            llama_base64 = base64.b64encode(llama_file.read()).decode()

        # Create title with embedded images
        title_html = f"""
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1 style="margin: 0;">RAG Chat with Qwen3
            <img src="data:image/png;base64,{qwen_base64}" style="height: 40px; margin: 0;">
            and LlamaIndex
            <img src="data:image/png;base64,{llama_base64}" style="height: 40px; margin: 0;">
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

    st.caption("Powered by Nebius AI")

    # Sidebar for configuration
    with st.sidebar:
        st.image("./assets/Nebius.png", width=150)

        # Model selection
        generative_model = st.selectbox(
            "Generative Model",
            ["Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3"],
            index=0
        )

        st.divider()

        # PDF file upload
        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type="pdf",
            accept_multiple_files=False
        )

        # Handle PDF upload and processing
        if uploaded_file is not None:
            if uploaded_file != st.session_state.current_pdf:
                st.session_state.current_pdf = uploaded_file
                try:
                    if not os.getenv("NEBIUS_API_KEY"):
                        st.error("Missing Nebius API key")
                        st.stop()

                    # Create temporary directory for the PDF
                    if st.session_state.temp_dir:
                        shutil.rmtree(st.session_state.temp_dir)
                    st.session_state.temp_dir = tempfile.mkdtemp()

                    # Save uploaded PDF to temp directory
                    file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner("Loading PDF..."):
                        # Load documents from temp directory
                        documents = SimpleDirectoryReader(st.session_state.temp_dir).load_data()
                        st.session_state.docs_loaded = True
                        st.session_state.documents = documents
                        st.success("✓ PDF loaded successfully")

                        # Display PDF preview
                        display_pdf_preview(uploaded_file)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_assistant_message(message["content"])
            else:
                st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your PDF..."):
        if not st.session_state.docs_loaded:
            st.error("Please upload a PDF first")
            st.stop()

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = run_rag_completion(
                        st.session_state.documents,
                        prompt,
                        "BAAI/bge-en-icl",  # Fixed embedding model
                        generative_model
                    )
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    display_assistant_message(response)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()