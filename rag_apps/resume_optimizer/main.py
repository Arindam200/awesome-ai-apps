import os

from PyPDF2 import PdfReader
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
    job_title: str,
    job_description: str,
    embedding_model: str = "BAAI/bge-en-icl",
    generative_model: str = "Qwen/Qwen3-235B-A22B"
) -> str:
    """Run RAG completion using Nebius models for resume optimization."""
    try:
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

        # Step 1: Analyze the resume
        analysis_prompt = f"""
        Analyze this resume in detail. Focus on:
        1. Key skills and expertise
        2. Professional experience and achievements
        3. Education and certifications
        4. Notable projects or accomplishments
        5. Career progression and gaps

        Provide a concise analysis in bullet points.
        """

        index = VectorStoreIndex.from_documents(documents)
        resume_analysis = index.as_query_engine(similarity_top_k=5).query(analysis_prompt)

        # Step 2: Generate optimization suggestions
        optimization_prompt = f"""
        Based on the resume analysis and job requirements, provide specific, actionable improvements.

        Resume Analysis:
        {resume_analysis}

        Job Title: {job_title}
        Job Description: {job_description}

        Optimization Request: {query_text}

        Provide a direct, structured response in this exact format:

        ## Key Findings
        • [2-3 bullet points highlighting main alignment and gaps]

        ## Specific Improvements
        • [3-5 bullet points with concrete suggestions]
        • Each bullet should start with a strong action verb
        • Include specific examples where possible

        ## Action Items
        • [2-3 specific, immediate steps to take]
        • Each item should be clear and implementable

        Keep all points concise and actionable. Do not include any thinking process or analysis.
        """

        optimization_suggestions = index.as_query_engine(similarity_top_k=5).query(optimization_prompt)

        return str(optimization_suggestions)
    except Exception as e:
        raise

def display_pdf_preview(pdf_file):
    """Display PDF preview in the sidebar."""
    try:
        st.sidebar.subheader("Resume Preview")
        base64_pdf = base64.b64encode(pdf_file.getvalue()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
        st.sidebar.markdown(pdf_display, unsafe_allow_html=True)
        return True
    except Exception as e:
        st.sidebar.error(f"Error previewing PDF: {str(e)}")
        return False

def main():
    st.set_page_config(page_title="Resume Optimizer", layout="wide")

    # Initialize session states
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "docs_loaded" not in st.session_state:
        st.session_state.docs_loaded = False
    if "temp_dir" not in st.session_state:
        st.session_state.temp_dir = None
    if "current_pdf" not in st.session_state:
        st.session_state.current_pdf = None

    # Header
    st.title("📝 Resume Optimizer")
    st.caption("Powered by Nebius AI")

    # Sidebar for configuration
    with st.sidebar:
        st.image("./Nebius.png", width=150)

        # Model selection
        generative_model = st.selectbox(
            "Generative Model",
            ["Qwen/Qwen3-235B-A22B", "deepseek-ai/DeepSeek-V3"],
            index=0
        )

        st.divider()

        # Resume upload
        st.subheader("Upload Resume")
        uploaded_file = st.file_uploader(
            "Choose your resume (PDF)",
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

                    with st.spinner("Loading Resume..."):
                        documents = SimpleDirectoryReader(st.session_state.temp_dir).load_data()
                        st.session_state.docs_loaded = True
                        st.session_state.documents = documents
                        st.success("✓ Resume loaded successfully")
                        display_pdf_preview(uploaded_file)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Job Information")
        job_title = st.text_input("Job Title")
        job_description = st.text_area("Job Description", height=200)

        st.subheader("Optimization Options")
        optimization_type = st.selectbox(
            "Select Optimization Type",
            [
                "ATS Keyword Optimizer",
                "Experience Section Enhancer",
                "Skills Hierarchy Creator",
                "Professional Summary Crafter",
                "Education Optimizer",
                "Technical Skills Showcase",
                "Career Gap Framing"
            ]
        )

        if st.button("Optimize Resume"):
            if not st.session_state.docs_loaded:
                st.error("Please upload your resume first")
                st.stop()
            if not job_title or not job_description:
                st.error("Please provide both job title and description")
                st.stop()

            # Generate optimization prompt based on selection
            prompts = {
                "ATS Keyword Optimizer": "Identify and optimize ATS keywords. Focus on exact matches and semantic variations from the job description.",
                "Experience Section Enhancer": "Enhance experience section to align with job requirements. Focus on quantifiable achievements.",
                "Skills Hierarchy Creator": "Organize skills based on job requirements. Identify gaps and development opportunities.",
                "Professional Summary Crafter": "Create a targeted professional summary highlighting relevant experience and skills.",
                "Education Optimizer": "Optimize education section to emphasize relevant qualifications for this position.",
                "Technical Skills Showcase": "Organize technical skills based on job requirements. Highlight key competencies.",
                "Career Gap Framing": "Address career gaps professionally. Focus on growth and relevant experience."
            }

            with st.spinner("Analyzing resume and generating suggestions..."):
                try:
                    response = run_rag_completion(
                        st.session_state.documents,
                        prompts[optimization_type],
                        job_title,
                        job_description,
                        "BAAI/bge-en-icl",
                        generative_model
                    )
                    # Remove think tags from response
                    response = response.replace("<think>", "").replace("</think>", "")
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            st.divider()

    with col2:
        st.subheader("Optimization Results")
        for message in st.session_state.messages:
            st.markdown(message["content"])

if __name__ == "__main__":
    main()