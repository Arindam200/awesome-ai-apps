"""
Job Search Agent with Memori
Streamlit interface for job search with memory capabilities
"""

import os
import base64
import streamlit as st
from memori import Memori
from dotenv import load_dotenv
from workflow import JobSearchConfig, process_job_search
from langchain_nebius import ChatNebius
from langchain_core.messages import HumanMessage
from resume_parser import extract_text_from_pdf, parse_resume

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Job Search Agent",
    layout="wide",
)

# Inline title with Memori and ExaAI logos
try:
    with open("./assets/Memori_Logo.png", "rb") as f:
        memori_png_base64 = base64.b64encode(f.read()).decode()
    memori_img_inline = (
        f"<img src='data:image/png;base64,{memori_png_base64}' "
        f"style='height:100px; width:auto; display:inline-block; vertical-align:middle; margin:0 8px;' alt='Memori Logo'>"
    )
except Exception:
    memori_img_inline = ""

try:
    with open("./assets/exa_logo.png", "rb") as f:
        exa_png_base64 = base64.b64encode(f.read()).decode()
    exa_img_inline = (
        f"<img src='data:image/png;base64,{exa_png_base64}' "
        f"style='height:80px; width:auto; display:inline-block; vertical-align:middle; margin:0 8px;' alt='ExaAI Logo'>"
    )
except Exception:
    exa_img_inline = ""

title_html = f"""
<div style='display:flex; align-items:center; width:120%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.2rem; font-weight:800; display:flex; align-items:center; gap:10px;'>
    <span>Job Search Agent with</span>
    {memori_img_inline} and
    {exa_img_inline}
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.subheader("🔑 API Keys")

    st.image("./assets/Nebius.png", width=200)
    nebius_api_key_input = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius API key for LangChain agent",
    )

    exa_api_key_input = st.text_input(
        "ExaAI API Key",
        value=os.getenv("EXA_API_KEY", ""),
        type="password",
        help="Your ExaAI API key for web search",
    )

    if st.button("Save API Keys"):
        if nebius_api_key_input:
            os.environ["NEBIUS_API_KEY"] = nebius_api_key_input
        if exa_api_key_input:
            os.environ["EXA_API_KEY"] = exa_api_key_input
        if nebius_api_key_input or exa_api_key_input:
            st.success("✅ API keys saved for this session")
        else:
            st.warning("Please enter at least one API key")

    # Quick status
    both_keys_present = bool(os.getenv("EXA_API_KEY")) and bool(
        os.getenv("NEBIUS_API_KEY")
    )
    if both_keys_present:
        st.caption("Both API keys detected ✅")
    else:
        st.caption("Missing API keys – some features may not work ⚠️")

    st.markdown("---")
    st.markdown("### 💡 About")
    st.markdown(
        """
        This application helps you search for jobs using AI-powered web search:
        - **Smart Job Search**: Uses ExaAI to find relevant job listings
        - **Multiple Job Sites**: Searches across LinkedIn, Indeed, Glassdoor, and more
        - **Memory**: Ask questions about your previous searches using Memori
        - **Direct Links**: Click through to apply directly to jobs

        Powered by LangChain for intelligent orchestration and ExaAI for web search.
        
        ---
        
        Made with ❤️ by [Studio1](https://www.Studio1hq.com) Team
        """
    )

# Get API keys from environment
exa_key = os.getenv("EXA_API_KEY", "")
nebius_key = os.getenv("NEBIUS_API_KEY", "")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "job_search_results" not in st.session_state:
    st.session_state.job_search_results = None

if "search_config" not in st.session_state:
    st.session_state.search_config = None

if "memori_initialized" not in st.session_state:
    st.session_state.memori_initialized = False

if "memory_messages" not in st.session_state:
    st.session_state.memory_messages = []

if "resume_uploaded" not in st.session_state:
    st.session_state.resume_uploaded = False

if "resume_data" not in st.session_state:
    st.session_state.resume_data = None

# Initialize Memori (once)
if not st.session_state.memori_initialized and nebius_key:
    try:
        st.session_state.memori = Memori(
            database_connect="sqlite:///memori.db",
            conscious_ingest=False,
            auto_ingest=False,
        )
        st.session_state.memori.enable()
        st.session_state.memori_initialized = True
    except Exception as e:
        st.warning(f"Memori initialization note: {str(e)}")

# Check if API keys are set
if not exa_key or not nebius_key:
    st.warning("⚠️ Please enter your API keys in the sidebar to start searching!")
    st.stop()

# Initialize LangChain LLM
if "llm" not in st.session_state and nebius_key:
    try:
        st.session_state.llm = ChatNebius(
            model="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            temperature=0.6,
            top_p=0.95,
            api_key=nebius_key,
        )
    except Exception as e:
        st.error(f"Failed to initialize LangChain LLM: {str(e)}")

# Tabs: Job Search, Resume, and Memory
tab1, tab2, tab3 = st.tabs(["🔍 Job Search", "📄 Resume", "🧠 Memory"])

with tab1:
    st.markdown("#### Search for Jobs")

    col1, col2 = st.columns([2, 1])
    with col1:
        job_title = st.text_input(
            "Job Title *",
            placeholder="e.g., Software Engineer, Data Scientist",
            help="The job title you're looking for",
        )
    with col2:
        num_jobs = st.slider(
            "Number of Jobs",
            min_value=1,
            max_value=20,
            value=5,
            help="How many job listings to show",
        )

    col3, col4 = st.columns(2)
    with col3:
        location = st.text_input(
            "Location",
            placeholder="e.g., San Francisco, CA or Remote",
            help="Job location (optional)",
        )
    with col4:
        work_style = st.selectbox(
            "Work Style",
            options=["Any", "Remote", "Hybrid", "Onsite"],
            help="Preferred work arrangement",
        )

    run_search = st.button("🔍 Search Jobs", type="primary")

    if run_search:
        if not job_title:
            st.error("Please enter a job title")
        else:
            config = JobSearchConfig(
                job_title=job_title,
                location=location if location else None,
                work_style=work_style if work_style != "Any" else None,
                num_jobs=num_jobs,
            )
            st.session_state.search_config = config

            with st.spinner("🔍 Searching for jobs... This may take a few moments..."):
                try:
                    st.write("🌐 Searching job sites with ExaAI...")
                    job_listings = process_job_search(config)
                    st.write(f"✅ Found {len(job_listings)} job listing(s)")

                    st.session_state.job_search_results = job_listings

                    # Display results
                    st.markdown(f"## 💼 Job Search Results")
                    st.markdown(f"**Search Query:** {job_title}")
                    if location:
                        st.markdown(f"**Location:** {location}")
                    st.markdown(f"**Work Style:** {work_style}")
                    st.markdown("---")

                    for i, job in enumerate(job_listings, 1):
                        with st.container():
                            st.markdown(f"### {i}. {job.title}")
                            st.markdown(f"**Company:** {job.company}")
                            st.markdown(f"**Location:** {job.location}")
                            st.markdown(f"**Work Style:** {job.work_style}")
                            if job.salary:
                                st.markdown(f"**Salary:** {job.salary}")

                            # Clickable link
                            st.markdown(f"**🔗 [Apply Here]({job.url})**")

                            # Description preview
                            with st.expander("View Description"):
                                st.markdown(job.description)

                            st.markdown("\n---\n")

                    # Ingest search into Memori for Memory Q&A
                    if st.session_state.memori_initialized:
                        try:
                            # Store search summary
                            summary_text = (
                                f"Searched for {job_title} jobs"
                                + (f" in {location}" if location else "")
                                + f" ({work_style} work style). Found {len(job_listings)} listings."
                            )
                            st.session_state.memori.record_conversation(
                                user_input=f"Search jobs: {job_title} in {location or 'any location'} ({work_style})",
                                ai_output=summary_text,
                            )

                            # Store each job description in memori for resume matching
                            for job in job_listings:
                                try:
                                    job_description_text = f"""Job Listing:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Work Style: {job.work_style}
Salary: {job.salary or 'Not specified'}
URL: {job.url}

Full Job Description:
{job.description}
"""
                                    st.session_state.memori.record_conversation(
                                        user_input=f"Job listing: {job.title} at {job.company}",
                                        ai_output=job_description_text,
                                    )
                                except Exception as ingest_error:
                                    # Continue with other jobs if one fails to ingest
                                    st.warning(
                                        f"Could not store job '{job.title}' in memory: {str(ingest_error)}"
                                    )
                        except Exception as e:
                            st.warning(
                                f"Could not store job search results in memory: {str(e)}"
                            )

                except Exception as e:
                    st.error(f"❌ Error during job search: {str(e)}")

with tab2:
    st.markdown("#### Upload Your Resume")
    st.markdown(
        "Upload your resume to get personalized job recommendations and resume improvement suggestions."
    )

    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=["pdf", "txt"],
        help="Upload your resume in PDF or text format",
    )

    if uploaded_file is not None:
        if st.button("📤 Process Resume", type="primary"):
            with st.spinner("📄 Processing resume... This may take a moment..."):
                try:
                    # Extract text from file
                    if uploaded_file.type == "application/pdf":
                        # Reset file pointer for PDF
                        uploaded_file.seek(0)
                        resume_text = extract_text_from_pdf(uploaded_file)
                    else:
                        # Reset file pointer for text
                        uploaded_file.seek(0)
                        resume_text = str(uploaded_file.read(), "utf-8")

                    # Parse resume using LLM
                    parsed_resume = parse_resume(resume_text, llm=st.session_state.llm)

                    # Store in session state
                    st.session_state.resume_data = parsed_resume
                    st.session_state.resume_uploaded = True

                    # Store in Memori
                    if st.session_state.memori_initialized:
                        try:
                            resume_summary = f"""Resume Information:
{parsed_resume.get('extracted_summary', 'Resume uploaded and processed')}

Key Details:
- Skills identified: {len(parsed_resume.get('skills', []))} skills
- Email: {parsed_resume.get('email', 'Not found')}
- Phone: {parsed_resume.get('phone', 'Not found')}
"""

                            st.session_state.memori.record_conversation(
                                user_input="Uploaded resume for job matching",
                                ai_output=resume_summary,
                            )
                            st.success("✅ Resume processed and stored in memory!")
                        except Exception as e:
                            st.warning(
                                f"Resume processed but couldn't store in memory: {str(e)}"
                            )

                    # Display extracted information
                    st.markdown("### 📋 Extracted Resume Information")
                    with st.expander("View Resume Summary"):
                        st.markdown(
                            parsed_resume.get(
                                "extracted_summary", "No summary available"
                            )
                        )

                    if parsed_resume.get("skills"):
                        st.markdown("**Skills Found:**")
                        st.write(", ".join(parsed_resume["skills"][:20]))

                except Exception as e:
                    st.error(f"❌ Error processing resume: {str(e)}")

    if st.session_state.resume_uploaded and st.session_state.resume_data:
        st.success("✅ Resume is uploaded and ready for job matching!")
        if st.button("🗑️ Remove Resume"):
            st.session_state.resume_uploaded = False
            st.session_state.resume_data = None
            st.rerun()

with tab3:
    st.markdown("#### Ask about your job searches and resume")

    if st.session_state.resume_uploaded:
        st.info(
            "📄 Your resume is uploaded! You can ask about job matching and resume improvements."
        )
    else:
        st.info(
            "💡 Upload your resume in the Resume tab to get personalized job matching recommendations!"
        )

    for message in st.session_state.memory_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    memory_prompt = st.chat_input("Ask about past job searches (Memori-powered)…")

    if memory_prompt:
        st.session_state.memory_messages.append(
            {"role": "user", "content": memory_prompt}
        )
        with st.chat_message("user"):
            st.markdown(memory_prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking…"):
                try:
                    memori_context = ""
                    if st.session_state.memori_initialized:
                        try:
                            memori_results = st.session_state.memori.search(
                                memory_prompt, limit=5
                            )
                            if memori_results:
                                memori_context = (
                                    "\n\nMemori context from prior searches:\n"
                                    + "\n".join(f"- {r}" for r in memori_results)
                                )
                        except Exception as search_error:
                            # Continue without Memori context if search fails
                            st.warning(f"Could not search memory: {str(search_error)}")

                    # Get current search results context
                    search_context = ""
                    if (
                        st.session_state.job_search_results
                        and st.session_state.search_config
                    ):
                        search_context = f"\n\nLatest Job Search Results for '{st.session_state.search_config.job_title}':\n"
                        for i, job in enumerate(st.session_state.job_search_results, 1):
                            search_context += f"{i}. {job.title} at {job.company} - {job.location} - {job.url}\n"
                            search_context += (
                                f"   Description: {job.description[:200]}...\n\n"
                            )

                    # Get resume context if available
                    resume_context = ""
                    if (
                        st.session_state.resume_uploaded
                        and st.session_state.resume_data
                    ):
                        resume_info = st.session_state.resume_data.get(
                            "extracted_summary", ""
                        )
                        resume_context = (
                            f"\n\nUser's Resume Information:\n{resume_info}\n"
                        )

                    # Create prompt for LLM
                    full_prompt = f"""You are a helpful job search assistant with access to:
1. User's resume information (if uploaded)
2. Previous job searches and listings
3. Job descriptions from searches

You can answer questions about:
- Previous job searches, companies, locations, job titles
- Resume analysis and job matching
- Which jobs the user is best suited for based on their resume
- What to add to their resume to match specific job requirements
- Comparing resume against job descriptions

{resume_context}
{search_context}
{memori_context}

Answer questions helpfully. If asked about resume matching or improvements, use the resume information and job descriptions to provide specific, actionable advice.
If asked outside scope, politely say you only answer about stored job searches and resume matching."""

                    # Use LangChain LLM for response
                    messages = [
                        HumanMessage(
                            content=full_prompt + "\n\nUser question: " + memory_prompt
                        )
                    ]
                    response = st.session_state.llm.invoke(messages)
                    response_text = response.content

                    if st.session_state.memori_initialized:
                        try:
                            st.session_state.memori.record_conversation(
                                user_input=memory_prompt,
                                ai_output=response_text,
                            )
                        except Exception as ingest_error:
                            # Continue even if memory ingestion fails
                            st.warning(
                                f"Could not store conversation in memory: {str(ingest_error)}"
                            )

                    st.session_state.memory_messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    st.markdown(response_text)
                except Exception as e:
                    err = f"❌ Error: {str(e)}"
                    st.session_state.memory_messages.append(
                        {"role": "assistant", "content": err}
                    )
                    st.error(err)
