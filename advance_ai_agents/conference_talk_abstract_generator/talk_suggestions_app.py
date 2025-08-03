import streamlit as st
from openai import OpenAI
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.vector_search import VectorQuery, VectorSearch
from couchbase.search import SearchRequest, MatchNoneQuery
from datetime import timedelta
import time

# --- Local Imports ---
# Import the main function from your new ADK agent module
from adk_research_agent import run_adk_research

# --- Setup ---
load_dotenv()

# Initialize OpenAI client for the final generation step
# Ensure your .env file has NEBIUS_API_BASE and NEBIUS_API_KEY
client = OpenAI(
    base_url=os.getenv("NEBIUS_API_BASE"),
    api_key=os.getenv("NEBIUS_API_KEY")
)

# --- Couchbase Connection Class (Unchanged) ---
class CouchbaseConnection:
    def __init__(self):
        # This class is copied verbatim from your original code.
        # No changes were needed here.
        # ... (full class code as you provided)
        try:
            connection_string = os.getenv('CB_CONNECTION_STRING')
            username = os.getenv('CB_USERNAME')
            password = os.getenv('CB_PASSWORD')
            bucket_name = os.getenv('CB_BUCKET')
            collection_name = os.getenv('CB_COLLECTION')
            
            if not all([connection_string, username, password, bucket_name, collection_name]):
                raise ValueError("Missing required Couchbase environment variables")
            
            auth = PasswordAuthenticator(username, password)
            timeout_options = ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10), query_timeout=timedelta(seconds=20), search_timeout=timedelta(seconds=20))
            options = ClusterOptions(auth, timeout_options=timeout_options)
            
            self.cluster = Cluster(connection_string, options)
            self.cluster.ping()
            
            self.bucket = self.cluster.bucket(bucket_name)
            self.scope = self.bucket.scope("_default")
            self.collection = self.bucket.collection(collection_name)
            self.search_index_name = os.getenv('CB_SEARCH_INDEX', "kubecontalks")
            
        except Exception as e:
            st.error(f"Failed to initialize Couchbase connection: {str(e)}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        try:
            response = client.embeddings.create(
                model="intfloat/e5-mistral-7b-instruct",
                input=text,
                timeout=30
            )
            return response.data[0].embedding
        except Exception as e:
            st.error(f"Error generating embedding: {str(e)}")
            raise

    def get_similar_talks(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        try:
            embedding = self.generate_embedding(query)
            search_req = SearchRequest.create(MatchNoneQuery()).with_vector_search(
                VectorSearch.from_vector_query(
                    VectorQuery("embedding", embedding, num_candidates=num_results)
                )
            )
            result = self.scope.search(self.search_index_name, search_req, timeout=timedelta(seconds=20))
            rows = list(result.rows())
            
            similar_talks = []
            for row in rows:
                try:
                    doc = self.collection.get(row.id, timeout=timedelta(seconds=5))
                    if doc and doc.value:
                        talk = doc.value
                        similar_talks.append({
                            "title": talk.get("title", "N/A"),
                            "description": talk.get("description", "N/A"),
                            "category": talk.get("category", "N/A"),
                            "speaker": talk.get("speaker", "N/A"),
                            "score": row.score
                        })
                except Exception as doc_error:
                    st.warning(f"Could not fetch document {row.id}: {doc_error}")
            return similar_talks
        except Exception as e:
            st.error(f"Error during vector search: {str(e)}")
            return []


# --- Final Prompt Generation (Modified to use ADK research) ---
def generate_talk_suggestion(query: str, similar_talks: List[Dict[str, Any]], adk_research: str) -> str:
    """Generates the final talk proposal by synthesizing all available context."""
    historical_context = "\n\n".join([
        f"Title: {talk['title']}\nDescription: {talk['description']}\nCategory: {talk['category']}"
        for talk in similar_talks
    ]) if similar_talks else "No similar historical talks were found in our database."

    prompt = f"""You are an expert conference program advisor for cloud-native technologies.
Your mission is to create a compelling, unique, and timely talk proposal.

**User's Core Idea:** "{query}"

To assist you, here is a two-part analysis:

---
**PART 1: HISTORICAL CONTEXT (FROM OUR DATABASE)**
These are similar talks that have been given in the past. Your proposal MUST offer a fresh perspective or build upon these in a novel way. Do not simply repeat these topics.

{historical_context}
---
**PART 2: REAL-TIME WEB ANALYSIS (FROM OUR RESEARCH AGENT)**
This is a fresh analysis of what's currently happening on the web regarding this topic (latest discussions, emerging tech, community sentiment). This provides the "zeitgeist" and reveals current gaps.

{adk_research}
---

**YOUR TASK:**
Synthesize the information from ALL parts above (user idea, historical context, and real-time analysis). Create a complete talk proposal that is timely, avoids repetition, and addresses a genuine gap or novel angle.

**REQUIRED OUTPUT FORMAT:**

**Title:**
*A compelling, modern title that captures the essence of your unique angle.*

**Abstract:**
*A detailed 2-3 paragraph summary. It should briefly acknowledge the existing landscape and then clearly explain what new insights, techniques, or case studies this talk will present.
   1. Focuses on end-user/consumer perspective
#         2. Builds upon existing concepts rather than repeating them
#         3. Follows a similar structure to successful talks
#         4. Addresses current trends and gaps in the topic area*

**Key Learning Objectives:**
*Provide 3-4 bullet points of what an attendee will learn.*

**Target Audience:**
*Specify the ideal audience (e.g., Beginner DevOps Engineers, Expert SREs, Platform Architects).*

**Why This Talk is Unique:**
*A crucial section explaining precisely how this talk differs from past talks and aligns with the current trends identified in the real-time analysis.*
"""

    st.write("Generating final talk suggestion with enriched context...")
    try:
        response = client.chat.completions.create(
            model="Qwen/Qwen3-235B-A22B",
            messages=[
                {"role": "system", "content": "You are a world-class conference program advisor with deep expertise in cloud-native technologies."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error calling the final generation LLM: {str(e)}")
        return "Failed to generate the final proposal due to an API error."

# --- Main Streamlit Application ---
def main():
    st.set_page_config(layout="wide")
    st.title("KubeCon Talk Proposal Generation Helper")
    st.markdown("This tool combines historical talk data with real-time web research to create unique, high-impact talk proposals. Keep in mind that this is a tool meant to just provide suggestions for talks. Don't submit this as your own talk proposal. Always use original talk abstract written by you. You can use this for reference. ")

    try:
        # Initialize Couchbase connection once
        if 'cb_connection' not in st.session_state:
            with st.spinner("Connecting to Couchbase DB..."):
                st.session_state.cb_connection = CouchbaseConnection()
        cb = st.session_state.cb_connection
        
        user_query = st.text_area(
            "Enter the core idea or topic for your talk proposal:",
            placeholder="e.g., Using OpenTelemetry's inferred spans feature for better observability in serverless environments.",
            height=100
        )

        if st.button("Generate Full Proposal", type="primary"):
            if not user_query:
                st.warning("Please enter your talk idea first!")
                return

            adk_research_results = ""
            similar_talks = []

            # Step 1: ADK Agent Research
            with st.spinner("Step 1/3: Running Research Agent to scan the web for latest trends... (This may take a minute)"):
                try:
                    adk_research_results = run_adk_research(user_query)
                    st.success("✅ Step 1: Real-time web research complete!")
                except Exception as e:
                    st.error(f"Failed to run ADK research agent: {e}")
                    return

            # Step 2: Couchbase Vector Search
            with st.spinner("Step 2/3: Searching internal database for historical context..."):
                similar_talks = cb.get_similar_talks(user_query)
                st.success("✅ Step 2: Historical context search complete!")

            # Step 3: Final Synthesis
            with st.spinner("Step 3/3: Synthesizing all data and generating final proposal..."):
                if adk_research_results:
                    final_proposal = generate_talk_suggestion(user_query, similar_talks, adk_research_results)
                    st.success("✅ Step 3: Proposal generation complete!")
                    
                    st.divider()
                    st.subheader("💡 Generated Talk Proposal")
                    st.markdown(final_proposal)
                    st.divider()

                    # Display the context used for generation in expanders
                    with st.expander("View Real-Time Web Analysis (from Research Agent)"):
                        st.markdown(adk_research_results)
                    
                    with st.expander("View Historical Context (from Couchbase DB)"):
                        if similar_talks:
                            st.json(similar_talks)
                        else:
                            st.info("No similar historical talks were found in the database.")
                else:
                    st.error("Could not generate proposal without results from the research agent.")

    except Exception as e:
        st.error(f"A critical error occurred in the application: {str(e)}")
        st.error("Please check your connection settings and environment variables, then refresh the page.")

if __name__ == "__main__":
    main()