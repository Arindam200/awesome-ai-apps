
import os
import streamlit as st
from dotenv import load_dotenv
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.agent import Agent
from agno.vectordb.chroma import ChromaDb
from agno.embedder.google import GeminiEmbedder
from agno.models.google import Gemini

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = st.secrets['GOOGLE_API_KEY']
# GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Initialize embedder and vector DB
embeddings = GeminiEmbedder(api_key=GOOGLE_API_KEY, id='models/gemini-embedding-001')
vector_db = ChromaDb(collection="arxiv_papers", path="./research", persistent_client=True, embedder=embeddings)
