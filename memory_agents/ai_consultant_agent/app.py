"""
AI Consultant Agent with Memori
Streamlit interface for AI readiness assessment + memory-powered follow-ups.
"""

import os
import base64

import streamlit as st
from dotenv import load_dotenv
from memori import Memori
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from workflow import CompanyProfile, run_ai_assessment

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="AI Consultant Agent",
    layout="wide",
)


def _load_inline_image(path: str, height_px: int) -> str:
    """Return an inline <img> tag for a local PNG, or empty string on failure."""
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return (
            f"<img src='data:image/png;base64,{encoded}' "
            f"style='height:{height_px}px; width:auto; display:inline-block; "
            f"vertical-align:middle; margin:0 8px;' alt='Logo'>"
        )
    except Exception:
        return ""


# Reuse existing logos from other agents
memori_img_inline = _load_inline_image(
    "../job_search_agent/assets/Memori_Logo.png", height_px=90
)
exa_img_inline = _load_inline_image(
    "../job_search_agent/assets/exa_logo.png", height_px=70
)

title_html = f"""
<div style='display:flex; align-items:center; width:120%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.5rem; font-weight:800; display:flex; align-items:center; gap:5px;'>
    <span>AI Consultant Agent with</span>
    {memori_img_inline}and
    {exa_img_inline}
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.subheader("🔑 API Keys")

    openai_api_key_input = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Your OpenAI API key for the consultant LLM (Memori v3 will register this client).",
    )

    memori_api_key_input = st.text_input(
        "Memori API Key (optional)",
        value=os.getenv("MEMORI_API_KEY", ""),
        type="password",
        help="Used for Memori Advanced Augmentation and higher quotas.",
    )

    exa_api_key_input = st.text_input(
        "ExaAI API Key",
        value=os.getenv("EXA_API_KEY", ""),
        type="password",
        help="Your ExaAI API key for web/case-study search",
    )

    if st.button("Save API Keys"):
        if openai_api_key_input:
            os.environ["OPENAI_API_KEY"] = openai_api_key_input
        if memori_api_key_input:
            os.environ["MEMORI_API_KEY"] = memori_api_key_input
        if exa_api_key_input:
            os.environ["EXA_API_KEY"] = exa_api_key_input
        if openai_api_key_input or exa_api_key_input or memori_api_key_input:
            st.success("✅ API keys saved for this session")
        else:
            st.warning("Please enter at least one API key")

    both_keys_present = bool(os.getenv("EXA_API_KEY")) and bool(
        os.getenv("OPENAI_API_KEY")
    )
    if both_keys_present:
        st.caption("Both API keys detected ✅")
    else:
        st.caption("Missing API keys – some features may not work ⚠️")

    st.markdown("---")
    st.markdown("### 💡 About")
    st.markdown(
        """
        This application acts as an **AI consultant** for companies:
        - Assesses **AI readiness** and where to integrate AI.
        - Suggests **use cases** across workforce, tools, and ecosystem.
        - Provides rough **cost bands** and risks.
        - Uses **Memori** + to remember past assessments and Q&A.

        Web research is powered by **ExaAI**, and reasoning is powered by **OpenAI** via Memori.

        ---

        Made with ❤️ by [Studio1](https://www.Studio1hq.com) Team
        """
    )

# Get API keys from environment
exa_key = os.getenv("EXA_API_KEY", "")

# Initialize session state
if "assessment_markdown" not in st.session_state:
    st.session_state.assessment_markdown = None

if "company_profile" not in st.session_state:
    st.session_state.company_profile = None

if "memory_messages" not in st.session_state:
    st.session_state.memory_messages = []

# Initialize Memori v3 + OpenAI client (once)
if "openai_client" not in st.session_state:
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        st.warning("OPENAI_API_KEY is not set – Memori v3 will not be active.")
    else:
        try:
            db_path = os.getenv("SQLITE_DB_PATH", "./memori.sqlite")
            database_url = f"sqlite:///{db_path}"
            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False},
            )
            # Optional DB connectivity check
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

            client = OpenAI(api_key=openai_key)
            mem = Memori(conn=SessionLocal).openai.register(client)
            # Basic attribution so Memori can attach memories
            mem.attribution(entity_id="ai-consultant-user", process_id="ai-consultant")
            mem.config.storage.build()

            st.session_state.memori = mem
            st.session_state.openai_client = client
        except Exception as e:
            st.warning(f"Memori v3 initialization note: {str(e)}")

# Check if keys are set for required services
if not exa_key:
    st.warning("⚠️ Please enter your ExaAI API key in the sidebar to run assessments!")
    st.stop()
if "openai_client" not in st.session_state:
    st.warning(
        "⚠️ OPENAI_API_KEY missing or Memori v3 failed to initialize – "
        "LLM responses will not work."
    )
    st.stop()

# Tabs: Assessment + Memory
tab1, tab2 = st.tabs(["📊 AI Assessment", "🧠 Memory"])

with tab1:
    st.markdown("#### Configure Company Profile & AI Assessment")

    col1, col2 = st.columns([2, 1])
    with col1:
        company_name = st.text_input(
            "Company Name *",
            placeholder="e.g., Acme Corp",
            help="The company you are assessing",
        )
        industry = st.text_input(
            "Industry *",
            placeholder="e.g., Retail, Fintech, Manufacturing",
            help="Primary industry or sector",
        )
        region = st.text_input(
            "Region / Market",
            placeholder="e.g., US, EU, Global, APAC",
            help="Where the company primarily operates",
        )
    with col2:
        company_size = st.selectbox(
            "Company Size *",
            options=["1-50", "51-200", "201-1000", "1000+"],
            help="Rough employee headcount band",
        )
        tech_maturity = st.selectbox(
            "Tech & Data Maturity *",
            options=["Low", "Medium", "High"],
            help="How mature is their data/engineering stack?",
        )

    goals = st.multiselect(
        "Business Goals for AI",
        options=[
            "Cost reduction",
            "Revenue growth",
            "Customer experience",
            "Operational efficiency",
            "Risk & compliance",
            "Innovation / new products",
        ],
        help="What is leadership trying to achieve with AI?",
    )

    ai_focus_areas = st.multiselect(
        "AI Focus Areas",
        options=[
            "Internal workflows & automation",
            "Customer support / CX",
            "Analytics & BI",
            "Product features",
            "Partner ecosystem / APIs",
        ],
        help="Where should we consider integrating AI?",
    )

    col3, col4 = st.columns(2)
    with col3:
        budget_range = st.selectbox(
            "Rough Budget Range *",
            options=["< $50k", "$50k-$250k", "$250k-$1M", ">$1M"],
        )
    with col4:
        time_horizon = st.selectbox(
            "Time Horizon for Initial Rollout *",
            options=["0-3 months", "3-6 months", "6-12 months", "12+ months"],
        )

    notes = st.text_area(
        "Additional Notes",
        placeholder="Any constraints, existing systems, data sources, or regulatory considerations.",
        height=120,
    )

    run_assessment = st.button("📊 Run AI Assessment", type="primary")

    if run_assessment:
        if not company_name or not industry:
            st.error("Please provide at least a company name and industry.")
        else:
            try:
                profile = CompanyProfile(
                    company_name=company_name.strip(),
                    industry=industry.strip(),
                    company_size=company_size,
                    region=region.strip() if region else None,
                    tech_maturity=tech_maturity,
                    goals=goals,
                    ai_focus_areas=ai_focus_areas,
                    budget_range=budget_range,
                    time_horizon=time_horizon,
                    notes=notes.strip() if notes else None,
                )
            except Exception as e:
                st.error(f"Invalid configuration: {e}")
            else:
                with st.spinner("🤖 Running AI assessment (research + reasoning)..."):
                    try:
                        assessment_markdown, _snippets = run_ai_assessment(
                            profile, st.session_state.openai_client
                        )
                        st.session_state.assessment_markdown = assessment_markdown
                        st.session_state.company_profile = profile

                        st.markdown(
                            f"## 🧾 AI Readiness & Cost Assessment for **{profile.company_name}**"
                        )
                        st.markdown(assessment_markdown)

                        # With Memori v3, conversations are captured automatically
                        # via the registered OpenAI client, so no manual recording here.
                    except Exception as e:
                        st.error(f"❌ Error during assessment: {e}")

    # Show last assessment if available and we didn't just run a new one
    if st.session_state.assessment_markdown and not run_assessment:
        st.markdown(
            "### Last Assessment Result "
            + (
                f"for **{st.session_state.company_profile.company_name}**"
                if st.session_state.company_profile
                else ""
            )
        )
        st.markdown(st.session_state.assessment_markdown)

with tab2:
    st.markdown("#### Ask about past AI assessments")

    if st.session_state.company_profile:
        st.info(
            f"Most recent company: **{st.session_state.company_profile.company_name}** "
            f"({st.session_state.company_profile.industry})"
        )
    else:
        st.info(
            "Run at least one assessment in the **AI Assessment** tab to ground the memory context."
        )

    for message in st.session_state.memory_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    memory_prompt = st.chat_input("Ask about past AI assessments (Memori-powered)…")

    if memory_prompt:
        st.session_state.memory_messages.append(
            {"role": "user", "content": memory_prompt}
        )
        with st.chat_message("user"):
            st.markdown(memory_prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking…"):
                try:
                    latest_context = ""
                    if (
                        st.session_state.assessment_markdown
                        and st.session_state.company_profile
                    ):
                        p = st.session_state.company_profile
                        latest_context = (
                            f"\n\nLatest assessment summary for {p.company_name} "
                            f"({p.industry}, {p.company_size}, {p.tech_maturity} tech maturity):\n"
                            f"{st.session_state.assessment_markdown[:1500]}\n"
                        )

                    full_prompt = f"""You are an AI consultant assistant with access to:
1. Stored AI readiness assessments (captured automatically by Memori v3).
2. The latest assessment in this session (if any).

You can answer questions about:
- What was previously recommended for a given company or industry.
- Whether AI was suggested for specific areas (workforce, tools, ecosystem, etc.).
- Cost bands, risks, and next steps that were advised before.
- How new questions relate to past assessments.

Use your memory of prior interactions (via Memori) plus the context below:
{latest_context}

Answer questions helpfully and concisely. If asked outside this scope, politely say you only answer about AI consulting and stored assessments."""

                    response = st.session_state.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": full_prompt},
                            {"role": "user", "content": memory_prompt},
                        ],
                    )
                    response_text = response.choices[0].message.content

                    st.session_state.memory_messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    st.markdown(response_text)
                except Exception as e:
                    err = f"❌ Error: {e}"
                    st.session_state.memory_messages.append(
                        {"role": "assistant", "content": err}
                    )
                    st.error(err)
