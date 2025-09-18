import os
import streamlit as st
from dotenv import load_dotenv
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.agent import Agent
from agno.vectordb.pineconedb import PineconeDb
from agno.embedder.google import GeminiEmbedder
from agno.models.google import Gemini
import os
import typer
from typing import Optional
from rich.prompt import Prompt

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = st.secrets['GOOGLE_API_KEY']
# GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Initialize embedder and vector DB
embeddings = GeminiEmbedder(api_key=GOOGLE_API_KEY, id='models/gemini-embedding-001')

# api_key = os.getenv("PINECONE_API_KEY")
api_key=st.secrets["PINECONE_API_KEY"]
index_name = "agno"


vector_db = PineconeDb(
    name=index_name,
    dimension=1536,
    metric="cosine",
    spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
    api_key=api_key,
    embedder=embeddings,
)



"""
knowledge_base = PDFKnowledgeBase(
    path="atten.pdf",
    vector_db=vector_db,
    # reader=PDFReader(chunk=True)
)



def pinecone_agent(user: str = "user"):
    run_id: Optional[str] = None

    agent = Agent(
        knowledge=knowledge_base,
        # show_tool_calls=True,
        debug_mode=True,
        model=Gemini(id="gemini-2.0-flash-lite"),
        markdown=True,
    )

    if run_id is None:
        run_id = agent.run_id
        print(f"Started Run: {run_id}\n")
    else:
        print(f"Continuing Run: {run_id}\n")

    while True:
        message = Prompt.ask(f"[bold] :sunglasses: {user} [/bold]")
        if message in ("exit", "bye"):
            break
        agent.print_response(message)

if __name__ == "__main__":
    # Comment out after first run
    knowledge_base.load(recreate=True, upsert=True)

    typer.run(pinecone_agent)"""



""""
    
            if uploaded_file is not None:
                if 'pdf_bytes' not in st.session_state:
                    uploaded_file.seek(0)
                    st.session_state.pdf_bytes = uploaded_file.read()

                if st.button("Load Knowledge Base") or st.session_state.get('agent') is None:
                    try:
                        # Write file once to disk or process directly from memory
                        with open("temp_uploaded_file.pdf", "wb") as f:
                            f.write(st.session_state.pdf_bytes)

                        pdf_knowledge_base = PDFKnowledgeBase(
                            path="temp_uploaded_file.pdf",
                            vector_db=vector_db,
                            reader=PDFReader(chunk=True)
                        )
                        pdf_knowledge_base.load(recreate=False)

                        agent = Agent(
                            knowledge=pdf_knowledge_base,
                            show_tool_calls=True,
                            model=Gemini(id="gemini-2.0-flash-lite"),
                            markdown=True,
                            read_chat_history=True
                        )

                        st.session_state.pdf_knowledge_base = pdf_knowledge_base
                        st.session_state.agent = agent
                        st.success("✅ Knowledge base loaded!")

                    except Exception as e:
                        st.error(f"❌ Failed to load knowledge base: {e}")

            # Query interface that doesn't cause rerun of file loading
            if st.session_state.get('agent'):
                query = st.text_input("🤖 Ask Me Anything About This Paper")
                if query:
                    response = st.session_state.agent.run(query)
                    st.markdown("### Response")
                    st.write(response.content)
                    
                    
                    """