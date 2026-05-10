"""
Conversational Product Intelligence Chat App
Multi-agent system with Memori for contextual conversations
"""

import os
import base64
import streamlit as st
from memori import Memori
from agent import create_product_intelligence_team
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Product Intelligence Assistant",
    layout="wide",
)

# Inline title with Gibson SVG logo
try:
    with open("./assets/gibson.svg", encoding="utf-8") as gibson_file:
        gibson_svg = gibson_file.read()
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
    <span>Smart Product Launch Agent with</span>
    {gibson_svg_inline}
    <span style='color:#c3f624;'>Memori</span>
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.subheader("🔑 API Keys")

    st.image("./assets/brightdata_logo.png", width=200)
    brightdata_api_key_input = st.text_input(
        "Bright Data API Key",
        value=os.getenv("BRIGHTDATA_API_KEY", ""),
        type="password",
        help="Your Bright Data API key for web scraping",
    )

    nebius_api_key_input = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Your Nebius API key for AI models",
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
    This AI assistant helps you analyze competitors using:
    - **Product Launch Analysis**
    - **Market Sentiment Analysis**  
    - **Launch Metrics Analysis**
    
    The conversation is tracked with Memori, so you can ask follow-up questions!
    """
    )


# Get API keys from environment
nebius_key = os.getenv("NEBIUS_API_KEY", "")
brightdata_key = os.getenv("BRIGHTDATA_API_KEY", "")

# Set Bright Data API key for Agno (convert BRIGHTDATA_API_KEY to BRIGHT_DATA_API_KEY)
if brightdata_key:
    os.environ["BRIGHT_DATA_API_KEY"] = brightdata_key

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = (
        "welcome"  # welcome, asked_company, asked_analysis, chatting
    )

if "user_company" not in st.session_state:
    st.session_state.user_company = None

if "user_description" not in st.session_state:
    st.session_state.user_description = None

if "memori_initialized" not in st.session_state:
    st.session_state.memori_initialized = False

# Initialize Memori (once)
if not st.session_state.memori_initialized and nebius_key:
    try:
        st.session_state.memori = Memori(
            database_connect="mongodb://localhost:27017/memori",
            conscious_ingest=False,  # Disable auto-ingest to avoid format errors with Agno
            auto_ingest=False,
        )
        st.session_state.memori.enable()
        st.session_state.memori_initialized = True
    except Exception as e:
        st.warning(f"Memori initialization note: {str(e)}")

# Initialize agent team (once)
if "agent_team" not in st.session_state and nebius_key and brightdata_key:
    try:
        st.session_state.agent_team = create_product_intelligence_team()
    except Exception as e:
        st.error(f"Failed to initialize agent team: {str(e)}")

# Check if API keys are set
if not nebius_key or not brightdata_key:
    st.warning("⚠️ Please enter your API keys in the sidebar to start chatting!")
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
👋 Welcome I'm your Product Intelligence Analyst.

I help founders and product teams analyze competitors to inform their product launch strategy. I specialize in three types of analysis:

1. **Product Launch Analysis** - Evaluate competitor positioning, strengths, weaknesses, and strategic insights
2. **Market Sentiment Analysis** - Analyze social media sentiment, customer feedback, and brand perception  
3. **Launch Metrics Analysis** - Track KPIs, adoption rates, press coverage, and performance indicators

All our conversations are tracked with memori, so you can ask follow-up questions anytime!

**Let's get started!** 

What is the name of your company and what does it do?
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
        # User provided company info
        st.session_state.user_company = prompt
        st.session_state.user_description = prompt

        response = f"""
Great! I understand you're working on: **{prompt}**

Now, what type of analysis would you like me to perform?

**1. Product Launch Analysis** 📊  
   Evaluate competitor positioning, launch tactics, strengths, weaknesses, and strategic insights

**2. Market Sentiment Analysis** 💬  
   Analyze social media sentiment, customer reviews, and brand perception

**3. Launch Metrics Analysis** 📈  
   Track user adoption, press coverage, engagement metrics, and performance KPIs

**Please tell me:**
- Which type of analysis you want (1, 2, or 3)
- Which competitor company you'd like me to analyze

Example: "I want a Product Launch Analysis for Monday.com"
"""
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.conversation_state = "asked_analysis"
        with st.chat_message("assistant"):
            st.markdown(response)

    elif st.session_state.conversation_state == "asked_analysis":
        # User requested an analysis
        with st.chat_message("assistant"):
            with st.spinner(
                "🔍 Analyzing... This may take a few minutes as I gather data from the web..."
            ):
                try:
                    # Run the agent team
                    result = st.session_state.agent_team.run(
                        f"User's company: {st.session_state.user_description}\n\n"
                        f"User's request: {prompt}"
                    )

                    # Get the response
                    response_content = (
                        result.content if hasattr(result, "content") else str(result)
                    )

                    # Record to Memori (manually, since auto-ingest doesn't work with Agno)
                    if st.session_state.memori_initialized:
                        try:
                            from memorisdk import MemoriContext

                            context = MemoriContext(
                                user_input=prompt, assistant_output=response_content
                            )
                            st.session_state.memori.ingest(context)
                        except Exception as e:
                            pass  # Silently fail to avoid UI clutter

                    # Add to chat
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_content}
                    )
                    st.markdown(response_content)

                    # Update state to chatting
                    st.session_state.conversation_state = "chatting"

                    # Add follow-up prompt
                    follow_up = "\n\n---\n\n💡 **What would you like to do next?**\n- Ask follow-up questions about this analysis\n- Request another analysis for a different competitor\n- Ask me to dive deeper into specific areas"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": follow_up}
                    )
                    st.markdown(follow_up)

                except Exception as e:
                    error_msg = f"❌ Error running analysis: {str(e)}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    st.error(error_msg)

    elif st.session_state.conversation_state == "chatting":
        # User is asking follow-up questions or requesting new analysis
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    # Check if user wants another analysis
                    prompt_lower = prompt.lower()
                    is_new_analysis = any(
                        keyword in prompt_lower
                        for keyword in [
                            "analyze",
                            "analysis",
                            "competitor",
                            "research",
                            "investigate",
                            "look into",
                            "check out",
                            "tell me about",
                        ]
                    )

                    if is_new_analysis:
                        # Run agent team for new analysis
                        result = st.session_state.agent_team.run(
                            f"User's company: {st.session_state.user_description}\n\n"
                            f"Previous context: {st.session_state.messages[-3]['content'] if len(st.session_state.messages) > 3 else 'None'}\n\n"
                            f"User's request: {prompt}"
                        )
                        response_content = (
                            result.content
                            if hasattr(result, "content")
                            else str(result)
                        )
                    else:
                        # Use Nebius for follow-up questions with context from Memori
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

                        # Build context from recent messages
                        context_str = ""
                        for msg in st.session_state.messages[-6:]:  # Last 6 messages
                            role = msg["role"]
                            content = msg["content"][:1000]  # Limit content length
                            context_str += f"{role}: {content}\n\n"

                        # Use Agno Agent for follow-up
                        from agno.agent import Agent
                        from agno.models.nebius import Nebius

                        followup_agent = Agent(
                            model=Nebius(
                                id="Qwen/Qwen3-Coder-480B-A35B-Instruct",
                                api_key=nebius_key,
                            ),
                            markdown=True,
                        )

                        full_prompt = f"""You are a Product Intelligence Analyst helping {st.session_state.user_description}. 
                        
ALWAYS search your memory (Memori) first before answering any question. 
Answer questions based on the previous analysis and conversation context. 
Be concise and actionable.

{memori_context}

Recent conversation context:
{context_str}

User question: {prompt}"""

                        result = followup_agent.run(full_prompt)
                        response_content = (
                            result.content
                            if hasattr(result, "content")
                            else str(result)
                        )

                    # Record to Memori (manually, since auto-ingest doesn't work with Agno)
                    if st.session_state.memori_initialized:
                        try:
                            from memorisdk import MemoriContext

                            context = MemoriContext(
                                user_input=prompt, assistant_output=response_content
                            )
                            st.session_state.memori.ingest(context)
                        except Exception as e:
                            pass  # Silently fail to avoid UI clutter

                    # Add to chat
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_content}
                    )
                    st.markdown(response_content)

                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    st.error(error_msg)
