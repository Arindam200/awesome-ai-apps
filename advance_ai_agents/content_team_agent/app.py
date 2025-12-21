import base64
import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
from pathlib import Path
import nest_asyncio
from main import content_seo_workflow
from agno.run.workflow import WorkflowRunEvent

nest_asyncio.apply()

st.set_page_config(page_title="Content Team SEO Agent", layout="wide")

load_dotenv()


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


agno_img_inline = _load_inline_image("assets/agno.png", height_px=60)
serpapi_img_inline = _load_inline_image("assets/serpapi.png", height_px=45)

title_html = f"""
<div style='display:flex; align-items:center; width:120%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.5rem; font-weight:800; display:flex; align-items:center; gap:5px;'>
    <span>SEO Content Agent Team with</span>
    {agno_img_inline} &
    {serpapi_img_inline}
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)
# Title
# st.markdown("## 📝 Content Team SEO Workflow With SerpAPI")

with st.sidebar:
    # st.header("⚙️ Configuration")
    st.image(
        "https://mintcdn.com/nebius-723e8b65/jsgY7B_gdaTjMC6y/logo/Main-logo-TF-Dark.svg?fit=max&auto=format&n=jsgY7B_gdaTjMC6y&q=85&s=92ebc07d32d93f3918de2f7ec4a0754a",
        width=250,
    )

    nebius_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Get your API key from https://studio.nebius.ai/",
    )

    serpapi_key = st.text_input(
        "SerpAPI Key",
        value=os.getenv("SERPAPI_API_KEY", ""),
        type="password",
        help="Get your API key from https://serpapi.com/",
    )

    if st.button("Save API Keys", use_container_width=True):
        if nebius_key:
            os.environ["NEBIUS_API_KEY"] = nebius_key
        if serpapi_key:
            os.environ["SERPAPI_API_KEY"] = serpapi_key
        st.success("API keys saved successfully!")

    st.markdown("---")
    st.markdown("## 🎯 Key Capabilities")
    st.markdown(
        """
        - **Google AI Research**: AI Mode & Overview analysis
        - **Competitor Analysis**: Top-ranking content insights
        - **Keyword Clustering**: Semantic keyword groups
        - **Smart Optimization**: AI-powered improvements
        """
    )
    st.markdown("---")

    input_method = st.radio(
        "Choose your input method:",
        [
            "Topic Only (Pre-Writing Brief)",
            "URL to Existing Article",
            "Title + Content",
        ],
        horizontal=True,
    )

    st.markdown("---")
    st.markdown(
        "Developed with ❤️ by [Arindam](https://www.youtube.com/c/Arindam_1729)"
    )

process_button = None

if not process_button:
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%); padding: 25px; border-radius: 15px; color: white; margin: 20px 0; border: 1px solid rgba(255, 255, 255, 0.1);">
            <h3 style="color: #ffffff; margin-top: 0;">✨ Transform Your Content Strategy</h3>
            <p style="font-size: 16px; margin-bottom: 0; color: #e0e0e0;">
                Leverage AI-powered insights to create content that ranks on Google AI Search. 
                Get comprehensive keyword research, competitor analysis, and actionable optimization recommendations.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div style="background-color: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.1); height: 100%;">
                <h3 style="color: #ffffff; margin-top: 0; display: flex; align-items: center;">
                    <span style="font-size: 32px; margin-right: 10px;">🔍</span>
                    Pre-Writing Mode
                </h3>
                <p style="color: #b0b0b0; margin-bottom: 15px;">
                    <strong style="color: #ffffff;">Generate comprehensive SEO content briefs</strong> before you start writing.
                </p>
                <ul style="color: #b0b0b0; padding-left: 20px;">
                    <li><strong style="color: #e0e0e0;">Keyword Research:</strong> Discover primary & related keywords</li>
                    <li><strong style="color: #e0e0e0;">Content Structure:</strong> Get recommended headings & outline</li>
                    <li><strong style="color: #e0e0e0;">FAQ Opportunities:</strong> Identify questions to answer</li>
                    <li><strong style="color: #e0e0e0;">Writing Guidelines:</strong> Best practices for SEO optimization</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div style="background-color: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.1); height: 100%;">
                <h3 style="color: #ffffff; margin-top: 0; display: flex; align-items: center;">
                    <span style="font-size: 32px; margin-right: 10px;">✏️</span>
                    Optimization Mode
                </h3>
                <p style="color: #b0b0b0; margin-bottom: 15px;">
                    <strong style="color: #ffffff;">Improve existing articles</strong> for better search rankings.
                </p>
                <ul style="color: #b0b0b0; padding-left: 20px;">
                    <li><strong style="color: #e0e0e0;">Content Audit:</strong> Identify gaps & opportunities</li>
                    <li><strong style="color: #e0e0e0;">Keyword Integration:</strong> Natural keyword optimization</li>
                    <li><strong style="color: #e0e0e0;">E-E-A-T Assessment:</strong> Enhance authority signals</li>
                    <li><strong style="color: #e0e0e0;">Section Rewrites:</strong> AI-optimized content improvements</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("---")

topic = None
title = None
content = None
url = None

if input_method == "Topic Only (Pre-Writing Brief)":
    topic = st.text_input(
        "Enter the topic for your content brief:",
        placeholder="e.g., Python async programming best practices",
        help="This will generate a comprehensive SEO content brief before writing.",
    )

elif input_method == "URL to Existing Article":
    url = st.text_input(
        "Enter the article URL:",
        placeholder="https://example.com/article",
        help="The article will be extracted and optimized for SEO.",
    )

elif input_method == "Title + Content":
    title = st.text_input(
        "Enter the article title:",
        placeholder="Your Article Title",
    )
    content = st.text_area(
        "Paste your article content:",
        height=300,
        placeholder="Paste your full article content here...",
        help="The complete article content for optimization.",
    )

# Process button
process_button = st.button(
    "🚀 Generate SEO Analysis", type="primary", use_container_width=True
)


async def stream_seo_analysis(topic, title, content, url, status):
    """Stream the SEO analysis workflow execution."""
    try:
        response = await content_seo_workflow.arun(
            input="Generate SEO optimization analysis",
            topic=topic,
            title=title,
            content=content,
            url=url,
            stream=True,
            stream_intermediate_steps=True,
        )

        content_output = ""
        async for event in response:
            if hasattr(event, "event"):
                if event.event == "StepStarted":
                    status.update(label=f"🚀 Step started: {event.step_name}")
                elif event.event == "StepCompleted":
                    status.update(label=f"✅ Step completed: {event.step_name}")
                elif event.event == "ParallelExecutionStarted":
                    status.update(
                        label=f"🔄 Parallel execution started: {event.step_name}"
                    )
                elif event.event == "ParallelExecutionCompleted":
                    status.update(
                        label=f"✅ Parallel execution completed: {event.step_name}"
                    )
                elif event.event == WorkflowRunEvent.workflow_completed.value:
                    content_output = (
                        event.content if hasattr(event, "content") else str(event)
                    )
            else:
                # Handle different event formats
                if hasattr(event, "step_name"):
                    status.update(label=f"🔄 Processing: {event.step_name}")

        return content_output
    except Exception as e:
        # Fallback to non-streaming if streaming fails
        status.update(label="⚠️ Using standard execution mode...")
        result = await content_seo_workflow.arun(
            input="Generate SEO optimization analysis",
            topic=topic,
            title=title,
            content=content,
            url=url,
        )
        return result.content if hasattr(result, "content") else str(result)


if process_button:
    # Validate inputs
    if input_method == "Topic Only (Pre-Writing Brief)" and not topic:
        st.error("⚠️ Please enter a topic for the content brief.")
    elif input_method == "URL to Existing Article" and not url:
        st.error("⚠️ Please enter an article URL.")
    elif input_method == "Title + Content" and (not title or not content):
        st.error("⚠️ Please provide both title and content.")
    else:
        # Check API keys
        if not os.getenv("NEBIUS_API_KEY"):
            st.error("⚠️ Please enter your Nebius API key in the sidebar.")
        elif not os.getenv("SERPAPI_API_KEY"):
            st.error("⚠️ Please enter your SerpAPI key in the sidebar.")
        else:
            # Process workflow with status updates
            with st.status("Processing SEO analysis...", expanded=True) as status:
                try:
                    summary = asyncio.run(
                        stream_seo_analysis(topic, title, content, url, status)
                    )
                    status.update(label="✅ Processing complete!", state="complete")
                except Exception as e:
                    status.update(label=f"❌ Error: {str(e)}", state="error")
                    st.error(f"An error occurred: {str(e)}")
                    import traceback

                    st.code(traceback.format_exc())
                    summary = None

            # Display results in main markdown area (outside of st.status)
            if summary:
                st.success("🎉 SEO Analysis Complete!")
                st.markdown("---")

                # Get report paths
                tmp_dir = Path(__file__).parent.joinpath(".tmp")
                reports_dir = tmp_dir.joinpath("reports", "content_seo")
                articles_dir = tmp_dir.joinpath("articles")

                # Determine which reports exist based on mode
                is_optimization_mode = url or (title and content)

                # Display Search Insights
                search_insights_path = reports_dir.joinpath("search_insights.md")
                if search_insights_path.exists():
                    # st.markdown("## Search Insights & Keyword Research")
                    with open(search_insights_path, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
                    st.markdown("---")

                # Display Content Brief (pre-writing mode) or Article Audit (optimization mode)
                if is_optimization_mode:
                    article_audit_path = reports_dir.joinpath("article_audit.md")
                    if article_audit_path.exists():
                        # st.markdown("## Article Audit & Improvement Plan")
                        with open(article_audit_path, "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                        st.markdown("---")
                else:
                    content_brief_path = reports_dir.joinpath("content_brief.md")
                    if content_brief_path.exists():
                        # st.markdown("## Content Brief & Writing Guidelines")
                        with open(content_brief_path, "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                        st.markdown("---")

                # Display Section Edits (only for optimization mode)
                if is_optimization_mode:
                    section_edits_path = reports_dir.joinpath("section_edits.md")
                    if section_edits_path.exists():
                        # st.markdown("## Optimized Section Rewrites")
                        with open(section_edits_path, "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                        st.markdown("---")

                # Display extracted articles (if URL was provided)
                if url and articles_dir.exists():
                    article_files = list(articles_dir.glob("*.md"))
                    if article_files:
                        # Get the most recent article file
                        latest_article = max(
                            article_files, key=lambda p: p.stat().st_mtime
                        )
                        # st.markdown("## Extracted Article")
                        st.info(f"📄 Article saved to: `{latest_article.name}`")
                    
