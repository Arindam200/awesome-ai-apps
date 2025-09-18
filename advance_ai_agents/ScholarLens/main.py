import patch_sqlite
import json
import tempfile
import os
import streamlit as st
from summarization.overall_summary import extract_sections_with_titles, generate_metadata, arxiv, text_splitter
from search.find_Research_Paper import run_literature_review
from search.find_latest_Research_paper import run_literature_review_latest
from summarization.sectionSummarizer import summarize_section, summarizer_agent, LLM, Crew, Process
from comparision.ComparePapers import extract_text_from_pdf, chain
from io import BytesIO
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.agent import Agent
from rag.Agentic_Rag import embeddings, vector_db, PDFReader,Agent, Gemini

from utils.memory_Storage import memory,storage

# Initialize session state
if 'pdf_knowledge_base' not in st.session_state:
    st.session_state.pdf_knowledge_base = None
if 'agent' not in st.session_state:
    st.session_state.agent = None

import streamlit as st
from PIL import Image


st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #E5E3D4 0%, #764ba2 100%);
        color: #2c3e50;
        font-family: 'Inter', sans-serif;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .sidebar .sidebar-content {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.9), rgba(118, 75, 162, 0.9));
        backdrop-filter: blur(20px);
        border-right: 2px solid rgba(55, 55, 255, 0.2);
        box-shadow: 4px 0 20px rgba(0,0,0,0.2);
    }

    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 14px 28px;
        font-size: 16px;
        font-weight: 600;
        border-radius: 12px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stButton > button:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 12px 35px rgba(102, 126, 234, 0.4);
        background: linear-gradient(135deg, #5a67d8, #6b46c1);
    }

    .card {
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(20px);
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        margin-bottom: 30px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        color: white;
    }
    .card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
    .card:hover {
        transform: translateY(-8px);
        box-shadow: 0 25px 50px rgba(0,0,0,0.15);
    }
    .card-title {
        font-size: 24px;
        font-weight: 700;
        margin-bottom: 20px;
        color: #667eea;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .stExpander {
        background: rgba(0, 0, 0, 0.7);
        border: 2px solid rgba(102, 126, 234, 0.3);
        border-radius: 16px;
        margin-bottom: 16px;
        transition: all 0.3s ease;
        overflow: hidden;
        color: white;
    }
    .stExpander:hover {
        border-color: rgba(102, 126, 234, 0.3);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
        transform: translateY(-2px);
    }

    .stSelectbox > div > div {
        background: rgba(55, 25, 55, 0.9);
        border: 2px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    .stSelectbox > div > div:focus-within {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .stTextInput > div > div > input {
        background: rgba(55, 25, 55, 0.9);
        border: 2px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 16px;
        transition: all 0.3s ease;
    }
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .stFileUploader {
        background: rgba(55, 25, 55, 0.9);
        border: 2px dashed rgba(102, 126, 234, 0.3);
        border-radius: 16px;
        padding: 20px;
        transition: all 0.3s ease;
    }
    .stFileUploader:hover {
        border-color: #667eea;
        background: rgba(255, 255, 255, 0.95);
    }

    .hero-section {
        text-align: center;
        padding: 40px 20px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        margin-bottom: 30px;
        backdrop-filter: blur(10px);
    }
    .hero-title {
        font-size: 3rem;
        font-weight: 700;
        color: white;
        margin-bottom: 10px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: rgba(255, 255, 255, 0.9);
        margin-bottom: 0;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,255,255,0.7));
        padding: 20px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .chat-message {
        background: linear-gradient(135deg, #e8f4fd, #f1f8ff);
        padding: 16px 20px;
        border-radius: 16px;
        margin: 15px 0;
        border-left: 4px solid #667eea;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        font-size: 16px;
        line-height: 1.6;
    }

    .success-message {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        color: #155724;
        padding: 16px 20px;
        border-radius: 12px;
        border-left: 4px solid #28a745;
        margin: 15px 0;
    }

    .warning-message {
        background: linear-gradient(135deg, #fff3cd, #ffeaa7);
        color: #856404;
        padding: 16px 20px;
        border-radius: 12px;
        border-left: 4px solid #ffc107;
        margin: 15px 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.7);
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        border: 2px solid transparent;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-color: rgba(55, 25, 55, 0.9);
    }
    </style>
""", unsafe_allow_html=True)


# Set page title and favicon
st.set_page_config(
    page_title="ScholarLens",
    page_icon="🧠",
    layout="wide",
)

# Display logo and branding in sidebar
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <div style='background: linear-gradient(135deg, #667eea, #764ba2); 
                        width: 80px; height: 80px; border-radius: 50%; 
                        margin: 0 auto 15px; display: flex; align-items: center; 
                        justify-content: center; box-shadow: 0 8px 20px rgba(102,126,234,0.3);'>
                <span style='font-size: 2rem;'>🧠</span>
            </div>
            <h2 style='color: white; margin: 0; font-weight: 700; font-size: 1.8rem;'>ScholarLens</h2>
            <p style='color: rgba(255,255,255,0.8); margin: 5px 0 0; font-size: 0.9rem; font-weight: 500;'>AI-Powered Research Assistant</p>
            <div style='width: 50px; height: 3px; background: linear-gradient(90deg, #667eea, #764ba2); 
                        margin: 15px auto; border-radius: 2px;'></div>
        </div>
    """, unsafe_allow_html=True)

# Sidebar navigation
options = st.sidebar.selectbox(
    "Select a page", ["ArXiv Smart Search", "AI Paper Companion","RAG Chatbot", "Compare Research Papers"]
)

# Page 1: ArXiv Literature Review
if options == 'ArXiv Smart Search':
    st.markdown("""
        <div class='hero-section'>
            <h1 class='hero-title'>🔍 ArXiv Smart Search</h1>
            <p class='hero-subtitle'>Discover and summarize cutting-edge research papers from arXiv</p>
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
    
        topic = st.text_input("🔍 Research Topic", placeholder="e.g. Diffusion Models in Vision")
        num_papers = st.slider("📊 Papers to Analyze", 1, 10, 4)
        latest_papers = st.checkbox("🔥 Find Latest Papers")
        run_button = st.button("🚀 Start Search")

    if run_button:
        if not topic.strip():
            st.warning("Please enter a valid topic.")
        else:
            with st.spinner("🔎 Searching and summarizing papers..."):
                if latest_papers:
                    result = run_literature_review_latest(topic, num_papers=num_papers)
                else:
                    result = run_literature_review(topic, num_papers=num_papers)
                
                st.success("✅ Paper Search Complete!")

                # Display introduction in enhanced card
                st.markdown("""
                    <div class='card'>
                        <div class='card-title'>✨ Research Overview</div>
                        <div style='font-size: 16px; line-height: 1.6; color: #4a5568;'>
                """, unsafe_allow_html=True)
                st.write(result.get("introduction"))
                st.markdown("</div></div>", unsafe_allow_html=True)

                st.markdown("""
                    <div style='text-align: center; margin: 40px 0 30px;'>
                        <h2 style='color: #667eea; font-weight: 700; font-size: 2rem; margin: 0;'>📄 Research Papers</h2>
                        <div style='width: 100px; height: 3px; background: linear-gradient(90deg, #667eea, #764ba2); 
                                    margin: 10px auto; border-radius: 2px;'></div>
                    </div>
                """, unsafe_allow_html=True)
                papers = result.get("papers details", [])
                if not papers:
                    st.warning("No paper details found.")
                else:
                    for i, paper in enumerate(papers, 1):
                        with st.expander(f"📘 {i}. {paper.get('title', 'Untitled')}", expanded=False):
                            st.markdown(f"**🔗 Title:** [{paper.get('title')}]({paper.get('link')})")
                            st.markdown(f"**👥 Authors:** {paper.get('authors', 'N/A')}")
                            st.markdown(f"**❓ Problem:** {paper.get('problem', 'N/A')}")
                            st.markdown(f"**🚀 Contribution:** {paper.get('contribution', 'N/A')}")
                            st.markdown(f"**📝 Summary:** {paper.get('summary', 'N/A')}")

                st.download_button(
                    label="📥 Download Results as JSON",
                    data=json.dumps(result, indent=2),
                    file_name="literature_review.json",
                    mime="application/json"
                )

# Page 2: PDF Assistant (Summary, Sectional Summary, RAG Chatbot)
elif options == 'AI Paper Companion':
    st.markdown("""
        <div class='hero-section'>
            <h1 class='hero-title'>📚 AI Paper Companion</h1>
            <p class='hero-subtitle'>Intelligent analysis and summarization of research papers</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("""
            <div style='background: rgba(55,55,55,0.1); padding: 20px; border-radius: 16px; margin: 20px 0;'>
                <h3 style='color: white; margin: 0 0 15px; font-weight: 600;'>📎 Upload Paper</h3>
            </div>
        """, unsafe_allow_html=True)
        uploaded_file = st.file_uploader("📄 Choose PDF File", type=["pdf"])

    if uploaded_file is not None:
        st.success("PDF uploaded successfully!")
        text, index, sections = extract_sections_with_titles(uploaded_file)
        arxiv_id = index[0].replace("arXiv:", "").strip()

        tab1, tab2 = st.tabs(['⚡ Instant Glance', "📝Summary (Guru Mode)"])

        with tab1:
            st.markdown("""
                <div style='text-align: center; margin: 20px 0;'>
                    <h2 style='color: #667eea; font-weight: 700; font-size: 1.8rem; margin: 0;'>⚡ Instant Glance</h2>
                    <p style='color: #64748b; margin: 5px 0;'>Quick insights and key information</p>
                </div>
            """, unsafe_allow_html=True)
            chunks = text_splitter.split_text(text)
            paper_data = generate_metadata(chunks)

            # Wrap in card
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.subheader(f"🧾 Title: {paper_data['title']}")
            st.markdown(f"**🧠 Model:** {paper_data['model']}")
            st.markdown(f"**📊 Dataset:** {paper_data['dataset']}")
            st.markdown("### 📈 Evaluation Metrics:")
            for metric, value in paper_data["metrics"].items():
                st.markdown(f"- **{metric}**: {value}")

            summary = paper_data["summary"]
            st.markdown("### 📝 Summary")
            for key, val in summary.items():
                st.markdown(f"**{key}:** {val}")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("""
                <div style='text-align: center; margin: 20px 0;'>
                    <h2 style='color: #667eea; font-weight: 700; font-size: 1.8rem; margin: 0;'>📚 Guru Mode</h2>
                    <p style='color: #64748b; margin: 5px 0;'>Deep section-wise analysis</p>
                </div>
            """, unsafe_allow_html=True)
            section_titles = [
                "Abstract", "Introduction", "Related Work", "Background", "Methodology",
                "Experiments", "Results", "Discussion", "Conclusion", "Conclusions and future work"
            ]
            available_sections = [title for title in section_titles if sections.get(title)]
            if not available_sections:
                st.warning("No recognized sections found in the uploaded PDF.")
            else:
                selected_section = st.selectbox("📌 Choose a section to summarize", available_sections)
                task = summarize_section(sections[selected_section], selected_section)
                crew = Crew(agents=[summarizer_agent], tasks=[task], process=Process.sequential)

                with st.spinner("🔍 Summarizing..."):
                    result = crew.kickoff()
                    raw_output = result.raw.strip().strip('`')
                    if raw_output.startswith("json"):
                        raw_output = raw_output[4:].strip()
                    try:
                        summary_data = json.loads(raw_output)
                        # Wrap in card
                        st.markdown("<div class='card'><div class='card-title'>📝 Bullet-Point Summary:</div>", unsafe_allow_html=True)
                        for value in summary_data.values():
                            st.write(f"- {value}")
                        st.markdown("</div>", unsafe_allow_html=True)
                    except json.JSONDecodeError:
                        st.error("⚠️ Failed to parse JSON summary. Showing raw output:")
                        st.code(raw_output)




elif options == 'RAG Chatbot':
    with st.sidebar:
        st.markdown("## 📎 Upload Paper")
        uploaded_file = st.file_uploader("Upload Paper", type=["pdf"])

    if uploaded_file is not None:
        st.success("PDF uploaded successfully!")

        if 'pdf_temp_path' not in st.session_state:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                st.session_state.pdf_temp_path = tmp_file.name

    if st.button("Load Knowledge Base"):
        if 'pdf_temp_path' not in st.session_state:
            st.warning("Please upload a PDF first.")
        else:
            try:
                pdf_knowledge_base = PDFKnowledgeBase(
                    path=st.session_state.pdf_temp_path,
                    vector_db=vector_db,
                    reader=PDFReader(chunk=True)
                )
                pdf_knowledge_base.load(recreate=False, upsert=True)

                agent = Agent(
                    knowledge=pdf_knowledge_base,
                    model=Gemini(id="gemini-2.0-flash-lite"),
                    description="You are an AI with a memory.",
                    memory=memory,
                    storage=storage,
                    enable_user_memories=True,
                    add_history_to_messages=True,
                    num_history_runs=3,
                    session_id="my_chat_sessioin",
                    markdown=True,
                    
                )

                st.session_state.pdf_knowledge_base = pdf_knowledge_base
                st.session_state.agent = agent
                st.success("✅ Knowledge base loaded!")

            except Exception as e:
                st.error(f"❌ Failed to load knowledge base: {e}")

    if st.session_state.get('agent'):
        query = st.text_input("🤖 Ask Me Anything About This Paper,Please give clear instruction..")
        if query:
            with st.spinner("Thinking..."):
                response = st.session_state.agent.run(query)
                st.markdown("""
                    <div class='card'>
                        <div class='card-title'>🤖 AI Response</div>
                        <div style='color: white;'>
                """, unsafe_allow_html=True)
                st.write(response.content)
                st.markdown("</div></div>", unsafe_allow_html=True)
    
    if st.button("Clear Session"):
        st.session_state.clear()
        if 'pdf_temp_path' in st.session_state:
            os.unlink(st.session_state.pdf_temp_path)
        st.rerun()


# Page 3: Paper Comparison
else:
    st.markdown("""
        <div class='hero-section'>
            <h1 class='hero-title'>📈 Compare Papers</h1>
            <p class='hero-subtitle'>Side-by-side analysis of research methodologies and findings</p>
        </div>
    """, unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("📄 Upload 2-3 Research Papers (PDF)", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        if len(uploaded_files) < 2:
            st.warning("Please upload at least 2 PDFs.")
        elif len(uploaded_files) > 3:
            st.warning("Please upload no more than 3 PDFs.")
        else:
            with st.spinner("🔍 Extracting text from PDFs..."):
                pdf_texts = [extract_text_from_pdf(f) for f in uploaded_files]
            st.success("✅ Text extracted! Click below to compare.")

            if st.button("🔍 Generate Comparison"):
                with st.spinner("🧠 Analyzing and comparing papers..."):
                    try:
                        response = chain.run({
                            "paper1": pdf_texts[0][:6000],
                            "paper2": pdf_texts[1][:6000]
                        })
                        st.markdown("""
                            <div class='card'>
                                <div class='card-title'>📈 Comparative Analysis</div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"<div style='color: black;'>{response}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.markdown(f"""
                            <div class='warning-message'>
                                <strong>⚠️ Error:</strong> {str(e)}
                            </div>
                        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class='card' style='text-align: center; padding: 60px 30px;'>
                <div style='font-size: 4rem; margin-bottom: 20px;'>📄</div>
                <h3 style='color: #667eea; margin-bottom: 10px;'>Ready for Comparison</h3>
                <p style='color: #64748b; margin: 0;'>Upload 2-3 research papers to begin comparative analysis</p>
            </div>
        """, unsafe_allow_html=True)