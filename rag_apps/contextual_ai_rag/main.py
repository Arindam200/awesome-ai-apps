import streamlit as st
import os
import base64
import re
from dotenv import load_dotenv
from contextual import ContextualAI
from llama_index.llms.nebius import NebiusLLM

load_dotenv()

def init_session_state():
    """Initialize Streamlit session state variables."""
    if "datastore_id" not in st.session_state:
        st.session_state.datastore_id = ""
    if "agent_id" not in st.session_state:
        st.session_state.agent_id = ""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "uploaded_docs" not in st.session_state:
        st.session_state.uploaded_docs = []

def create_client():
    """Create and return Contextual AI client with API key."""
    api_key = os.getenv("CONTEXTUAL_API_KEY")
    if not api_key:
        return None
    try:
        return ContextualAI(api_key=api_key)
    except Exception as e:
        st.error(f"Client error: {e}")
        return None

def handle_datastore(client, name):
    """Create datastore or return existing one by name."""
    try:
        datastores = client.datastores.list()
        existing = next((ds for ds in datastores if ds.name == name), None)
        
        if existing:
            return existing.id, "Using existing datastore"
        else:
            result = client.datastores.create(name=name)
            return result.id, "Created new datastore"
    except Exception as e:
        st.error(f"Datastore error: {e}")
        return None, None

def handle_agent(client, name, datastore_id):
    """Create agent or return existing one by name."""
    try:
        agents = client.agents.list()
        existing = next((a for a in agents if a.name == name), None)
        
        if existing:
            return existing.id, "Using existing agent"
        else:
            result = client.agents.create(
                name=name,
                description="RAG agent",
                datastore_ids=[datastore_id]
            )
            return result.id, "Created new agent"
    except Exception as e:
        st.error(f"Agent error: {e}")
        return None, None

def upload_files(client, datastore_id, files):
    """Upload multiple files to datastore with progress tracking."""
    progress = st.progress(0)
    for i, file in enumerate(files):
        progress.progress(i / len(files))
        try:
            media_type = getattr(file, "type", None) or "application/octet-stream"
            payload = (file.name, file.getvalue(), media_type)
            client.datastores.documents.ingest(datastore_id=datastore_id, file=payload)
            st.session_state.uploaded_docs.append(file.name)
        except Exception as e:
            st.error(f"Upload failed for {file.name}: {e}")
    progress.progress(1.0)
    progress.empty()


def escape_dollars(text):
    """Escape dollar signs to prevent markdown math mode issues."""
    # Fixes streamlit math mode issues
    return text.replace("$", "\\$") if text else text

def enhance_with_nebius(original_response, query):
    """Use Nebius to enhance the Contextual AI response."""
    try:
        nebius_api_key = os.getenv("NEBIUS_API_KEY")
        if not nebius_api_key:
            return original_response
        
        nebius_llm = NebiusLLM(
            model="Qwen/Qwen3-235B-A22B", 
            api_key=nebius_api_key
        )
        
        enhancement_prompt = f"""Based on the original query and AI response below, provide a brief enhancement that adds key insights, improves clarity, or suggests relevant follow-up questions. Keep it concise and valuable.

Original Query: {query}
AI Response: {original_response}

Enhancement:"""
        
        enhanced = nebius_llm.complete(enhancement_prompt)
        return f"{original_response}\n\n**💡 Enhanced Insights:**\n{enhanced}"
    
    except Exception as e:
        return original_response

def query_response(client, agent_id, query):
    """Send query to agent and return formatted response."""
    try:
        response = client.agents.query.create(
            agent_id=agent_id,
            messages=[{"role": "user", "content": query}]
        )
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            answer = response.message.content
        else:
            answer = str(response)
        
        return escape_dollars(answer), response
    except Exception as e:
        return f"Query error: {e}", None

def show_sources(client, response_obj, agent_id):
    """Display source document images from query response."""
    try:
        if not (hasattr(response_obj, 'retrieval_contents') and response_obj.retrieval_contents):
            st.info("No sources available")
            return
        
        for i, content in enumerate(response_obj.retrieval_contents[:2]):
            ret_info = client.agents.query.retrieval_info(
                message_id=response_obj.message_id,
                agent_id=agent_id,
                content_ids=[content.content_id]
            )
            
            if hasattr(ret_info, 'content_metadatas') and ret_info.content_metadatas:
                meta = ret_info.content_metadatas[0]
                if hasattr(meta, 'page_img') and meta.page_img:
                    raw = meta.page_img
                    b64 = raw.split(",", 1)[-1] if "base64," in raw else raw
                    st.image(base64.b64decode(b64), caption=f"Source {i+1}")
    except Exception as e:
        st.error(f"Source error: {e}")

def evaluate_quality(client, query, response, criteria):
    """Evaluate response quality using LMUnit scoring."""
    try:
        result = client.lmunit.create(query=query, response=response, unit_test=criteria)
        score = result.score
        st.metric("Quality Score", f"{score:.1f}/5.0")
        
        if score >= 4.0:
            st.success("Excellent")
        elif score >= 3.0:
            st.info("Good")  
        elif score >= 2.0:
            st.warning("Fair")
        else:
            st.error("Poor")
    except Exception as e:
        st.error(f"Evaluation error: {e}")


def main():
    """Main Streamlit application entry point."""
    st.set_page_config(page_title="Contextual AI RAG", layout="wide")
    
    init_session_state()
    client = create_client()

    with st.sidebar:
        st.header("Setup")
        if not client:
            st.error("Missing CONTEXTUAL_API_KEY")
            st.code("CONTEXTUAL_API_KEY=your_key")
            st.stop()
        st.success("Connected")
        st.divider()
        
        st.subheader("1. Datastore")
        if not st.session_state.datastore_id:
            name = st.text_input("Name", "my-docs")
            if st.button("Create", key="ds"):
                ds_id, msg = handle_datastore(client, name)
                if ds_id:
                    st.session_state.datastore_id = ds_id
                    st.success(msg)
                    st.rerun()
        else:
            st.success("Ready")
            if st.button("Reset", key="ds_reset"):
                st.session_state.datastore_id = ""
                st.session_state.agent_id = ""
                st.session_state.uploaded_docs = []
                st.rerun()
        
        if st.session_state.datastore_id:
            st.subheader("2. Upload")
            files = st.file_uploader("Files", accept_multiple_files=True, 
                                   type=['pdf', 'txt', 'md', 'doc', 'docx'])
            
            if files and st.button("Upload", key="upload"):
                upload_files(client, st.session_state.datastore_id, files)
                st.success(f"Uploaded {len(files)} files")
                st.info("Contextual AI is now processing your documents. Complex PDFs with tables and charts may take a few minutes to fully index.")
                st.rerun()
            
            if st.session_state.uploaded_docs:
                with st.expander(f"{len(st.session_state.uploaded_docs)} docs"):
                    for doc in st.session_state.uploaded_docs:
                        st.write(f"• {doc}")
        
        if st.session_state.datastore_id:
            st.subheader("3. Agent")
            if not st.session_state.agent_id:
                name = st.text_input("Agent name", "my-agent")
                if st.button("Create", key="agent"):
                    agent_id, msg = handle_agent(client, name, st.session_state.datastore_id)
                    if agent_id:
                        st.session_state.agent_id = agent_id
                        st.success(msg)
                        st.rerun()
            else:
                st.success("Ready")
        
        st.divider()
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
    
    st.title("Contextual AI RAG")
    
    # Enhancement toggle (only show if Nebius API key is available)
    if os.getenv("NEBIUS_API_KEY"):
        enhance_enabled = st.toggle("Nebius Enhancement", value=False, 
                                  help="Use Nebius AI to enhance responses with additional insights")
    else:
        enhance_enabled = False
    
    if st.session_state.uploaded_docs and not st.session_state.agent_id:
        st.info("Documents uploaded! Contextual AI is processing and indexing your files. This may take a few minutes for complex documents. Create an agent in the sidebar when ready.")
    
    if st.session_state.agent_id:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask about your documents"):
            escaped_prompt = escape_dollars(prompt)
            st.session_state.chat_history.append({"role": "user", "content": escaped_prompt})
            
            with st.chat_message("user"):
                st.markdown(escaped_prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    answer, response_obj = query_response(client, st.session_state.agent_id, prompt)
                    
                    # Apply enhancement if enabled
                    if enhance_enabled:
                        with st.spinner("Enhancing with Nebius..."):
                            answer = enhance_with_nebius(answer, prompt)
                    
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    st.session_state["last_response"] = response_obj
                    st.session_state["last_query"] = escaped_prompt
        
        if "last_response" in st.session_state and st.session_state.last_response:
            with st.expander("Debug Tools"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Show Sources"):
                        show_sources(client, st.session_state.last_response, st.session_state.agent_id)
                
                with col2:
                    criteria = st.selectbox("Criteria", [
                        "Does the response extract accurate numerical data?",
                        "Are claims supported with evidence?",
                        "Does the response avoid unnecessary information?"
                    ])
                    
                    if st.button("Evaluate"):
                        last_msg = next((m["content"] for m in reversed(st.session_state.chat_history) 
                                       if m["role"] == "assistant"), None)
                        if last_msg:
                            evaluate_quality(client, st.session_state.last_query, last_msg, criteria)
    else:
        if not st.session_state.datastore_id:
            st.info("Create a datastore to get started")
        elif not st.session_state.uploaded_docs:
            st.info("Upload documents to your datastore")
        elif not st.session_state.agent_id:
            st.info("Create an agent to start chatting")
    
    st.caption("Powered by Contextual AI")

if __name__ == "__main__":
    main()