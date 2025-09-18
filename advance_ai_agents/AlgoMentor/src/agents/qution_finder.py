from ..models.schemas import QuestionFinderInput
import streamlit as st
from agno.agent import Agent
from agno.models.google import Gemini
import os
from dotenv import load_dotenv
load_dotenv()

# google_api_key=os.getenv("GOOGLE_API_KEY")
google_api_key=st.secrets['GOOGLE_API_KEY']


# Agent without tools for structured output
question_finder=Agent(
    name='Question Finder',
    model=Gemini(id='gemini-2.0-flash',api_key=google_api_key),
    description = "Formats given content into structured format",
    instructions = [
        "Format the given content into the required structure with problem statement, difficulty, examples,constraints, and explanations."
        ],
    response_model=QuestionFinderInput
)