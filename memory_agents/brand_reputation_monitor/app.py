"""
Brand Reputation Monitoring Chat App
Conversational interface with Memori for contextual conversations
"""

import os
import base64
import streamlit as st
from memori import Memori
from dotenv import load_dotenv
import json
from typing import List
from workflow import (
    get_google_news_page_urls,
    scrape_news_pages,
    get_best_news_urls,
    scrape_news_articles,
    process_news_list,
    Config,
)
from agno.models.nebius import Nebius
from agno.agent import Agent

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Brand Reputation Monitor",
    layout="wide",
)

# Inline title with Gibson SVG logo
try:
    with open("./assets/gibson.svg", encoding="utf-8") as gibson_file:
        gibson_svg = gibson_file.read()

    with open("./assets/brightdata_logo.png", "rb") as brightdata_file:
        brightdata_base64 = base64.b64encode(brightdata_file.read()).decode()
    gibson_svg_base64 = base64.b64encode(gibson_svg.encode("utf-8")).decode()
    gibson_svg_inline = (
        f'<img src="data:image/svg+xml;base64,{gibson_svg_base64}" '
        f"style='height:40px; width:auto; display:inline-block; vertical-align:middle; margin:0 6px;' alt='GibsonAI Logo'>"
    )
except Exception:
    gibson_svg_inline = ""

title_html = f"""
<div style='display:flex; align-items:center; width:100%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.5rem; font-weight:700; display:flex; align-items:center; gap:8px;'>
    <span>Brand Reputation Monitor with</span>
    {gibson_svg_inline}
    <span style='color:#c3f624;'>Memori</span>
    <span style='font-size:2rem'>&</span>
    <img src="data:image/png;base64,{brightdata_base64}" style="height: 80px; width: auto; display:inline-block; vertical-align:middle; margin:0 6px;" alt="Bright Data Logo">
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("./assets/nebius.png", width=170)

    nebius_api_key_input = st.text_input(
        "Nebius AI API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius AI API key for AI analysis",
    )

    brightdata_api_key_input = st.text_input(
        "Bright Data API Key",
        value=os.getenv("BRIGHTDATA_API_KEY", ""),
        type="password",
        help="Your Bright Data API key for web scraping",
    )

    if st.button("Save API Keys"):
        if nebius_api_key_input:
            os.environ["NEBIUS_API_KEY"] = nebius_api_key_input
        if brightdata_api_key_input:
            os.environ["BRIGHTDATA_API_KEY"] = brightdata_api_key_input
        if nebius_api_key_input or brightdata_api_key_input:
            st.success("✅ API keys saved for this session")
        else:
            st.warning("Please enter at least one API key")

    # Quick status
    both_keys_present = bool(os.getenv("NEBIUS_API_KEY")) and bool(
        os.getenv("BRIGHTDATA_API_KEY")
    )
    if both_keys_present:
        st.caption("Both API keys detected ✅")
    else:
        st.caption("Missing API keys – some features may not work ⚠️")

    st.markdown("---")
    st.markdown("### 💡 About")
    st.markdown(
        """
    This application is powered by a set of advanced AI agents for brand reputation monitoring and analysis:
    - **News Analysis**: Analyzes news articles about the brand
    - **Sentiment Tracking**: Tracks sentiment about the brand
    - **Brand Insights**: Provides insights about the brand reputation

    Each stage leverages state-of-the-art language models and tools to provide actionable, data-driven insights.
    
    ---
    
    Made with ❤️ by [Studio1](https://www.Studio1hq.com) Team
    """
    )

# Get API keys from environment
nebius_key = os.getenv("NEBIUS_API_KEY", "")
brightdata_key = os.getenv("BRIGHTDATA_API_KEY", "")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = (
        "welcome"  # welcome, asked_company, asked_keywords, analyzing, chatting
    )

if "user_company" not in st.session_state:
    st.session_state.user_company = None

if "search_queries" not in st.session_state:
    st.session_state.search_queries = None

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "memori_initialized" not in st.session_state:
    st.session_state.memori_initialized = False

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

# Initialize Nebius AI model (once)
if "nebius_model" not in st.session_state and nebius_key:
    try:
        st.session_state.nebius_model = Nebius(
            id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
            api_key=nebius_key,
        )
    except Exception as e:
        st.error(f"Failed to initialize Nebius AI model: {str(e)}")

# Check if API keys are set
if not nebius_key or not brightdata_key:
    st.warning("⚠️ Please enter your API keys in the sidebar to start monitoring!")
    st.stop()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Welcome message
if (
    st.session_state.conversation_state == "welcome"
    and len(st.session_state.messages) == 0
):
    welcome_msg = """
👋 Welcome! I'm your Brand Reputation Monitor.

I help you track and analyze your brand's reputation by monitoring news, sentiment, and public perception. I can:

1. **Monitor News Coverage** - Track news articles about your brand
2. **Analyze Sentiment** - Understand positive, negative, or neutral sentiment
3. **Extract Insights** - Get actionable insights about your brand reputation

All our conversations are tracked with Memori, so you can ask follow-up questions anytime!

**Let's get started!** 

What is the name of your company?
"""
    st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
    st.session_state.conversation_state = "asked_company"
    with st.chat_message("assistant"):
        st.markdown(welcome_msg)

# Chat input
if prompt := st.chat_input("Type your message here..."):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process based on conversation state
    if st.session_state.conversation_state == "asked_company":
        # User provided company name
        st.session_state.user_company = prompt

        response = f"""
Great! I understand you want to monitor reputation for: **{prompt}**

Now, what keywords would you like me to search for? Please provide search terms separated by commas.

**Examples:**
- `{prompt} news, {prompt} reviews, {prompt} controversy, {prompt} announcement`
- `{prompt} stock, {prompt} earnings, {prompt} product launch`
- `{prompt} customer feedback, {prompt} complaints, {prompt} success`

**Please enter your search keywords:**
"""
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.conversation_state = "asked_keywords"
        with st.chat_message("assistant"):
            st.markdown(response)

    elif st.session_state.conversation_state == "asked_keywords":
        # User provided search keywords
        try:
            # Parse keywords from user input
            keywords = [
                keyword.strip() for keyword in prompt.split(",") if keyword.strip()
            ]
            st.session_state.search_queries = keywords

            # Create config object
            config = Config(
                search_queries=keywords, num_news=5  # Default to 5 news articles
            )

            response = f"""
Perfect! I'll monitor reputation for **{st.session_state.user_company}** using these keywords:
{', '.join(keywords)}

Let me start analyzing the news and sentiment...
"""
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.conversation_state = "analyzing"
            with st.chat_message("assistant"):
                st.markdown(response)

            # Run the analysis
            with st.chat_message("assistant"):
                with st.spinner(
                    "🔍 Analyzing brand reputation... This may take a few minutes..."
                ):
                    try:
                        # Step 1: Get Google News page URLs
                        st.write("📰 Retrieving Google News page URLs...")
                        google_news_page_urls = get_google_news_page_urls(
                            config.search_queries
                        )
                        st.write(
                            f"✅ Found {len(google_news_page_urls)} Google News page(s)"
                        )

                        # Step 2: Scrape news pages
                        st.write("🔍 Scraping news pages...")
                        scraped_news_pages = scrape_news_pages(google_news_page_urls)
                        st.write("✅ News pages scraped!")

                        # Step 3: Extract best news URLs
                        st.write("🎯 Extracting most relevant news...")
                        news_urls = get_best_news_urls(
                            scraped_news_pages, config.num_news
                        )
                        st.write(f"✅ Found {len(news_urls)} relevant articles")

                        # Step 4: Scrape news articles
                        st.write("📄 Scraping news articles...")
                        news_list = scrape_news_articles(news_urls)
                        st.write("✅ Articles scraped!")

                        # Step 5: Analyze news
                        st.write("🧠 Analyzing sentiment and insights...")
                        news_analysis_list = process_news_list(news_list)
                        st.write("✅ Analysis complete!")

                        # Store results
                        st.session_state.analysis_results = news_analysis_list

                        # Format results for display
                        results_html = f"""
## 📊 Brand Reputation Report for {st.session_state.user_company}

**Search Keywords:** {', '.join(keywords)}
**Analysis Date:** {st.session_state.messages[-1]['content'][:50]}...

---

"""
                        for i, analysis in enumerate(news_analysis_list, 1):
                            sentiment_emoji = {
                                "positive": "😊",
                                "negative": "😞",
                                "neutral": "😐",
                            }.get(analysis.sentiment_analysis.lower(), "😐")

                            results_html += f"""
### {i}. {analysis.title}
**URL:** {analysis.url}
**Summary:** {analysis.summary}
**Sentiment:** {sentiment_emoji} {analysis.sentiment_analysis.title()}

**Key Insights:**
"""
                            for insight in analysis.insights:
                                results_html += f"- {insight}\n"
                            results_html += "\n---\n\n"

                        # Add results to chat
                        st.session_state.messages.append(
                            {"role": "assistant", "content": results_html}
                        )
                        st.markdown(results_html)

                        # Add follow-up prompt
                        follow_up = f"""
💡 **What would you like to do next?**

You can ask me questions like:
- "What's the overall sentiment for {st.session_state.user_company}?"
- "Can you explain the insights from the analysis?"
- "What company are we analyzing?"
- "What keywords did we search for?"
- "Can you summarize the key findings?"
- "What are the main concerns mentioned?"

Or request a new analysis with different keywords!
"""
                        st.session_state.messages.append(
                            {"role": "assistant", "content": follow_up}
                        )
                        st.markdown(follow_up)

                        # Update state to chatting
                        st.session_state.conversation_state = "chatting"

                    except Exception as e:
                        error_msg = f"❌ Error during analysis: {str(e)}"
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
                        st.error(error_msg)
                        st.session_state.conversation_state = "chatting"

        except Exception as e:
            error_msg = f"❌ Error parsing keywords: {str(e)}"
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
            st.error(error_msg)

    elif st.session_state.conversation_state == "chatting":
        # User is asking follow-up questions
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    # Check if user wants new analysis
                    prompt_lower = prompt.lower()
                    is_new_analysis = any(
                        keyword in prompt_lower
                        for keyword in [
                            "analyze",
                            "analysis",
                            "monitor",
                            "search",
                            "new keywords",
                            "different keywords",
                        ]
                    )

                    if is_new_analysis:
                        # Reset to ask for new keywords
                        response = f"""
I understand you want to run a new analysis for **{st.session_state.user_company}**.

What new keywords would you like me to search for? Please provide search terms separated by commas.

**Examples:**
- `{st.session_state.user_company} news, {st.session_state.user_company} reviews, {st.session_state.user_company} controversy`
- `{st.session_state.user_company} stock, {st.session_state.user_company} earnings`
- `{st.session_state.user_company} customer feedback, {st.session_state.user_company} complaints`

**Please enter your new search keywords:**
"""
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response}
                        )
                        st.session_state.conversation_state = "asked_keywords"
                        st.markdown(response)
                    else:
                        # Use LangChain for follow-up questions with context from Memori
                        # First, search Memori for relevant context
                        memori_context = ""
                        if st.session_state.memori_initialized:
                            try:
                                # Search Memori for relevant past conversations
                                memori_results = st.session_state.memori.search(
                                    prompt, limit=3
                                )
                                if memori_results:
                                    memori_context = "\n\nRelevant context from previous conversations:\n"
                                    for result in memori_results:
                                        memori_context += f"- {result}\n"
                            except Exception as e:
                                pass  # Silently fail if Memori search doesn't work

                        # Build context from recent messages and analysis results
                        context_str = ""
                        for msg in st.session_state.messages[-6:]:  # Last 6 messages
                            role = msg["role"]
                            content = msg["content"][:1000]  # Limit content length
                            context_str += f"{role}: {content}\n\n"

                        # Add analysis results to context
                        analysis_context = ""
                        if st.session_state.analysis_results:
                            analysis_context = f"\n\nCurrent Analysis Results for {st.session_state.user_company}:\n"
                            for i, analysis in enumerate(
                                st.session_state.analysis_results, 1
                            ):
                                analysis_context += f"{i}. {analysis.title} - {analysis.sentiment_analysis} - {analysis.summary}\n"

                        # Create agent for follow-up questions
                        followup_agent = Agent(
                            name="Brand Reputation Assistant",
                            description=f"""You are a Brand Reputation Monitor assistant. You help users understand their brand reputation analysis results.

You have access to:
- Company name: {st.session_state.user_company}
- Search keywords used: {', '.join(st.session_state.search_queries) if st.session_state.search_queries else 'Not specified'}
- Analysis results: {analysis_context}

Answer questions about the analysis, company, keywords, sentiment, insights, etc.
Be helpful, concise, and reference specific data from the analysis when relevant.

{memori_context}

Recent conversation context:
{context_str}""",
                            model=st.session_state.nebius_model,
                            markdown=True,
                        )

                        response = followup_agent.run(prompt)

                        # FIX: Convert RunOutput to string
                        response_text = (
                            str(response.content)
                            if hasattr(response, "content")
                            else str(response)
                        )

                        # Record to Memori (manually, since auto-ingest doesn't work)
                        if st.session_state.memori_initialized:
                            try:
                                from memorisdk import MemoriContext

                                context = MemoriContext(
                                    user_input=prompt, assistant_output=response_text
                                )
                                st.session_state.memori.ingest(context)
                            except Exception as e:
                                pass  # Silently fail to avoid UI clutter

                        # Add to chat
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response_text}
                        )
                        st.markdown(response_text)

                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    st.error(error_msg)
