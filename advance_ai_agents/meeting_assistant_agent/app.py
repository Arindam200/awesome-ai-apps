import os

from agno.run.workflow import WorkflowRunEvent
from dotenv import load_dotenv
from main import workflow
import asyncio
import base64
import nest_asyncio
import streamlit as st
nest_asyncio.apply()

st.set_page_config(page_title="Meeting Assistant Agent", layout="wide")

load_dotenv()

with open("./assets/Nebius.png", "rb") as nebius_file:
    nebius_base64 = base64.b64encode(nebius_file.read()).decode()

with open("./assets/agno.png", "rb") as agno_file:
    agno_base64 = base64.b64encode(agno_file.read()).decode()

# Create title with embedded image
title_html = f"""
<div style="display: flex;  width: 100%; ">
    <h1 style="margin: 0; padding: 0; font-size: 2.5rem; font-weight: bold;">
        <span style="font-size:2.5rem;">📝</span> Meeting Assistant Agent with
        <img src="data:image/png;base64,{agno_base64}" style="height: 80px; vertical-align: middle; bottom: 10px;"/>
    </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)
st.markdown(
    "**Streamline your meetings with AI-powered transcription, task creation, and notifications**"
)

with st.sidebar:
    st.image("./assets/Nebius.png", width=150)
    nebius_key = st.text_input(
        "Enter your Nebius API key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
    )

    slack_key = st.text_input(
        "Enter your Slack Bot Token",
        value=os.getenv("SLACK_BOT_TOKEN", ""),
        type="password",
    )

    linear_key = st.text_input(
        "Enter your Linear API key",
        value=os.getenv("LINEAR_API_KEY", ""),
        type="password",
    )

    if st.button("Save Keys", use_container_width=True):
        if nebius_key:
            os.environ["NEBIUS_API_KEY"] = nebius_key
        if slack_key:
            os.environ["SLACK_BOT_TOKEN"] = slack_key
        if linear_key:
            os.environ["LINEAR_API_KEY"] = linear_key
        st.success("API keys saved successfully!")

    uploaded_file = st.file_uploader(
        "Upload Meeting Notes", accept_multiple_files="false", type=["txt"]
    )

    if uploaded_file:
        with open(f"./{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("File uploaded successfully!")

    meet_processing = st.button("Process Meeting Notes")

    st.markdown("---")
    st.markdown(
        "Developed with ❤️ by [Arindam Majumder](https://www.youtube.com/c/Arindam_1729)"
    )

about_md = """
## About

This application is powered by a set of advanced AI agents for meeting assistance:

- **Meeting Transcription**: Transcribes meeting notes into a clean summary.
- **Task Creation**: Generates actionable tasks in Linear based on meeting discussions.
- **Slack Notifications**: Sends summaries and key decisions to your Slack channel.

Each stage leverages state-of-the-art language models and tools to enhance productivity and communication.

"""

summary = None


async def stream_meeting_summary(file_path, status):
    # Correct import
    # Correct import

    response = await workflow.arun(
        message=f"Process the meeting notes from {file_path}: summarize, create Linear tasks, and send a Slack notification with key outcomes.",
        markdown=True,
        stream=True,
        stream_intermediate_steps=True,
    )

    content = ""
    async for event in response:
        if event.event == "StepStarted":
            status.update(label=f"🚀 Step started: {event.step_name}")
        elif event.event == "StepCompleted":
            status.update(label=f"✅ Step completed: {event.step_name}")
        elif event.event == "ParallelExecutionStarted":
            status.update(label=f"🔄 Parallel execution started: {event.step_name}")
        elif event.event == "ParallelExecutionCompleted":
            status.update(label=f"✅ Parallel execution completed: {event.step_name}")
        elif event.event == WorkflowRunEvent.workflow_completed.value:
            content = event.content
    return content


if meet_processing:
    if uploaded_file:
        with st.status("Processing meeting notes...", expanded=True) as status:
            summary = asyncio.run(
                stream_meeting_summary(f"./{uploaded_file.name}", status)
            )
            status.update(label="Processing complete!", state="complete")
        if summary:
            st.markdown(summary)

    else:
        st.warning("Please enter your meeting notes before processing.")

if not summary:
    st.markdown(about_md)