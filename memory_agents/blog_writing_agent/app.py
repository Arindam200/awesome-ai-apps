"""
Blog Writing Agent Streamlit App

A Streamlit application featuring two AI agents:
1. Knowledge Agent: Analyzes uploaded documents to extract writing style, tone, and structure
2. Writing Agent: Generates new content using the stored writing style information

This file contains the Streamlit interface while the agent logic is in agents.py
"""

import os

from agents import (
import base64
import streamlit as st
    initialize_memori,
    create_memory_tool_instance,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    analyze_writing_style,
    store_writing_style_in_memori,
    generate_blog_with_style,
    get_stored_writing_style,
    save_generated_blog,
)

# Page configuration
st.set_page_config(
    page_title="AI Blog Agent",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "query_history" not in st.session_state:
    st.session_state.query_history = []
if "style_analysis" not in st.session_state:
    st.session_state.style_analysis = None
if "text_content" not in st.session_state:
    st.session_state.text_content = None

with open("./assets/gibson.svg", "r", encoding="utf-8") as gibson_file:
    gibson_svg = (
        gibson_file.read()
        .replace("\n", "")
        .replace("\r", "")
        .replace("  ", "")
        .replace('"', "'")
    )

gibson_svg_inline = f'<span style="height:80px; width:200px; display:inline-block; vertical-align:middle; margin-left:8px;margin-top:20px;margin-right:8px;">{gibson_svg}</span>'

# Create title with embedded images (SVG and PNG in one line)
title_html = f"""
<div style='display:flex; align-items:center; width:100%; padding:24px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.5rem; font-weight:bold; display:flex; align-items:center;'>
    Blog Writing Agent with {gibson_svg_inline} Memori
  </h1>
</div>
"""


# Initialize Memori
@st.cache_resource
def get_memory_system():
    """Initialize Memori memory system"""
    try:
        memory_system = initialize_memori()
        return memory_system
    except Exception as e:
        st.error(f"Failed to initialize Memori: {e}")
        return None


# Initialize memory system
memory_system = get_memory_system()
if memory_system is None:
    st.stop()

# Create memory tool
memory_tool = create_memory_tool_instance(memory_system)

with st.sidebar:
    st.image("./assets/digital_ocean.png", width=250)

    digital_ocean_endpoint = st.text_input(
        "Digital Ocean Endpoint",
        value=os.getenv("DIGITAL_OCEAN_ENDPOINT", ""),
        type="password",
        help="Your Digital Ocean endpoint URL",
    )

    digital_ocean_key = st.text_input(
        "Digital Ocean Agent Access Key",
        value=os.getenv("DIGITAL_OCEAN_AGENT_ACCESS_KEY", ""),
        type="password",
        help="Your Digital Ocean agent access key",
    )

    if st.button("Save Digital Ocean Config", use_container_width=True):
        if digital_ocean_endpoint:
            os.environ["DIGITAL_OCEAN_ENDPOINT"] = digital_ocean_endpoint
        if digital_ocean_key:
            os.environ["DIGITAL_OCEAN_AGENT_ACCESS_KEY"] = digital_ocean_key
        st.success("Digital Ocean configuration saved successfully!")

    st.markdown("---")


def knowledge_agent_sidebar():
    """Knowledge Agent interface in the sidebar"""
    st.sidebar.header("📚 Knowledge Agent")
    st.sidebar.markdown("**Upload & analyze your writing style**")

    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "Upload your article (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        help="Upload a document that represents your writing style",
    )

    if uploaded_file is not None:
        st.sidebar.success(f"✅ File uploaded: {uploaded_file.name}")

        # Extract text based on file type
        text_content = ""
        try:
            if uploaded_file.type == "application/pdf":
                text_content = extract_text_from_pdf(uploaded_file)
            elif (
                uploaded_file.type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                text_content = extract_text_from_docx(uploaded_file)
            elif uploaded_file.type == "text/plain":
                text_content = extract_text_from_txt(uploaded_file)
        except Exception as e:
            st.sidebar.error(f"Error extracting text: {e}")
            return

        if text_content:
            # Text preview removed - not needed

            # Analyze button
            if st.sidebar.button("🔍 Analyze Writing Style", type="primary"):
                with st.spinner("Analyzing..."):
                    try:
                        style_analysis = analyze_writing_style(text_content)

                        if style_analysis:
                            st.sidebar.subheader("🎯 Style Analysis")

                            # Display key results compactly
                            st.sidebar.markdown(
                                f"**Tone:** {style_analysis.get('tone', 'N/A')}"
                            )
                            st.sidebar.markdown(
                                f"**Voice:** {style_analysis.get('voice', 'N/A')}"
                            )
                            st.sidebar.markdown(
                                f"**Structure:** {style_analysis.get('structure', 'N/A')[:50]}..."
                            )

                            # Store the analysis results in session state
                            st.session_state.style_analysis = style_analysis
                            st.session_state.text_content = text_content

                            # Automatically store the style in memory
                            with st.spinner("Storing style in memory..."):
                                try:
                                    formatted_style = store_writing_style_in_memori(
                                        memory_system,
                                        st.session_state.style_analysis,
                                        st.session_state.text_content,
                                    )
                                    if formatted_style:
                                        st.sidebar.success(
                                            "✅ Analysis complete & style stored in memory!"
                                        )
                                        st.rerun()  # Refresh to show updated state
                                    else:
                                        st.sidebar.error("❌ Failed to store style")
                                except Exception as e:
                                    st.sidebar.error(f"❌ Error storing style: {e}")
                        else:
                            st.sidebar.error("❌ Failed to analyze style")
                    except Exception as e:
                        st.sidebar.error(f"❌ Error: {e}")

    # Show current style status
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Current Status")

    # Only show writing style as found if we have it in session state (after analysis)
    if "style_analysis" in st.session_state and st.session_state.style_analysis:
        st.sidebar.success("✅ Writing style profile found")
        st.sidebar.info("You can now generate content using the Writing Agent!")

    else:
        st.sidebar.warning("⚠️ No writing style profile")
        st.sidebar.info(
            "Upload a document and click 'Analyze Writing Style' to get started"
        )


def writing_agent_main():
    """Writing Agent interface in the main area"""
    # Display custom HTML title with embedded logos
    st.markdown(title_html, unsafe_allow_html=True)

    st.markdown(
        "**Generate new blog posts - with or without your personal writing style**"
    )

    # Chat input for blog generation
    topic = st.chat_input(
        "What topic would you like me to write about? (e.g., The benefits of artificial intelligence in healthcare)"
    )

    if topic:
        # Check if we have writing style to enhance the generation
        has_writing_style = (
            "style_analysis" in st.session_state and st.session_state.style_analysis
        )

        if has_writing_style:
            spinner_text = (
                "Still editing your blog post using your unique writing style..."
            )
        else:
            spinner_text = "Generating your blog post..."

        with st.spinner(spinner_text):
            try:
                # Generate content (with or without writing style)
                blog_content = generate_blog_with_style(memory_tool, topic)

                if blog_content:
                    # st.subheader("📝 Generated Blog Post")

                    # Display the blog content
                    st.markdown(blog_content)

                    # Action buttons
                    col1, col2, col3 = st.columns([1, 1, 2])

                    with col1:
                        # Download as text
                        st.download_button(
                            label="📄 Download TXT",
                            data=blog_content,
                            file_name=f"blog_post_{topic.replace(' ', '_')[:30]}.txt",
                            mime="text/plain",
                            use_container_width=True,
                        )

                    with col2:
                        # Copy to clipboard
                        if st.button("📋 Copy to Clipboard", use_container_width=True):
                            st.write("Content copied to clipboard!")

                    with col3:
                        # Store the generated content
                        try:
                            save_generated_blog(memory_system, topic, blog_content)
                            st.success("💾 Blog post saved to memory!")
                        except Exception as e:
                            st.warning(f"Note: Could not save to memory: {e}")
                else:
                    st.error("❌ Failed to generate blog post")
            except Exception as e:
                st.error(f"❌ Error generating blog: {e}")

    # Only show About section when no topic is being processed
    if not topic:
        st.markdown("### About this application")
        st.markdown(
            "This application is powered by Memori and Digital Ocean Gradient to help you create blog in your own style."
        )
        st.markdown("**It features:**")
        st.markdown(
            "• **Smart Content Generation**: AI-powered blog writing with customizable topics"
        )
        st.markdown(
            "• **Writing Style Analysis**: Upload your documents to analyze and replicate your unique writing style"
        )
        st.markdown(
            "• **Memory Integration**: Uses Memori to remember your preferences and improve content quality"
        )
        st.markdown(
            "• **Flexible Workflow**: Generate blogs immediately or generate them with your personal writing style"
        )


def main():
    # Knowledge Agent in sidebar
    knowledge_agent_sidebar()

    # Writing Agent in main area
    writing_agent_main()


if __name__ == "__main__":
    main()