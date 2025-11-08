import os
import re

from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex, PromptTemplate
from llama_index.embeddings.nebius import NebiusEmbedding
from llama_index.llms.nebius import NebiusLLM
from llama_index.readers.github import GithubRepositoryReader, GithubClient
import streamlit as st
load_dotenv()

def parse_github_url(url):
    pattern = r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo, branch = match.groups()
    return owner, repo, branch if branch else "main"

@st.cache_resource
def load_github_data(github_token, owner, repo, branch="main"):
    github_client = GithubClient(github_token)
    loader = GithubRepositoryReader(
        github_client,
        owner=owner,
        repo=repo,
        filter_file_extensions=(
            [".py", ".ipynb", ".js", ".ts", ".md"],
            GithubRepositoryReader.FilterType.INCLUDE
        ),
        verbose=False,
        concurrent_requests=5,
    )
    return loader.load_data(branch=branch)

def run_rag_completion(query_text: str, docs) -> str:
    llm = NebiusLLM(
        model="deepseek-ai/DeepSeek-V3",
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    embed_model = NebiusEmbedding(
        model_name="BAAI/bge-en-icl",
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    Settings.llm = llm
    Settings.embed_model = embed_model

    index = VectorStoreIndex.from_documents(docs)
    query_engine = index.as_query_engine(similarity_top_k=5, streaming=True)

    qa_prompt_tmpl = PromptTemplate(
        "Context information is below.\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n"
        "Given the context information, please answer the query.\n"
        "Query: {query_str}\n"
        "Answer: "
    )

    query_engine.update_prompts({"response_synthesizer:text_qa_template": qa_prompt_tmpl})
    response = query_engine.query(query_text)
    return str(response)

def main():
    st.set_page_config(page_title="Chat with Code", layout="wide")

    @st.fragment
    def download_response(response:str) :
        st.download_button(
                label="Download message",
                type="secondary",
                data=response,
                file_name="chatbot_response.md",
                mime="text/plain",
                icon=":material/download:",
            )

    # Initialize session states
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "docs" not in st.session_state:
        st.session_state.docs = None

    # Header with title and buttons
    col1, col2, col5, col3, col4 = st.columns([3, 1, 1, 1, 1])
    with col1:
        st.title("🤖 Chat with Code ")
    with col3:
        st.link_button("⭐ Star Repo", "https://github.com/Arindam200/nebius-cookbook")
    with col4:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    st.caption("Powered by Nebius AI (DeepSeek-V3) and LlamaIndex")

    # Sidebar
    with st.sidebar:
        # st.title("Select Model")
        # model = st.selectbox(
        #     "",
        #     ["DeepSeek-V3"],
        #     index=0
        # )
        # st.divider()
        st.subheader("GitHub Repository URL")
        repo_url = st.text_input("", placeholder="Enter repository URL")

        if st.button("Load Repository"):
            if repo_url:
                try:
                    github_token = os.getenv("GITHUB_TOKEN")
                    nebius_api_key = os.getenv("NEBIUS_API_KEY")

                    if not github_token or not nebius_api_key:
                        st.error("Missing API keys")
                        st.stop()

                    owner, repo, branch = parse_github_url(repo_url)
                    with st.spinner("Loading repository..."):
                        st.session_state.docs = load_github_data(github_token, owner, repo, branch)
                    st.success("✓ Repository loaded successfully")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about the repository..."):
        if not st.session_state.docs:
            st.error("Please load a repository first")
            st.stop()

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = run_rag_completion(prompt, st.session_state.docs)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    download_response(response)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()