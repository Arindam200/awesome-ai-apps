import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
groq_api_key=st.secrets['GROQ_API_KEY']
google_api_key=st.secrets['GOOGLE_API_KEY']

# Model Configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"

# UI Configuration
PAGE_TITLE = "DSA Assistant"
PAGE_LAYOUT = "wide"
SIDEBAR_STATE = "expanded"

# Application Settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")