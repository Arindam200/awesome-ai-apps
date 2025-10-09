"""
Conference-Agnostic Talk RAG Application
Main Streamlit interface for the enhanced conference talk suggestion system
"""
from typing import List, Dict, Any
import json
import os
import os
import sys

from datetime import datetime
import asyncio
import streamlit as st
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.scrapers.parallel_crawler import crawl_single_conference
from src.models.corpus_manager import ConferenceCorpusManager, store_crawled_conference
from src.config.nebius_client import NebiusClient
from src.research.adk_research_agent import run_adk_research
from src.ui.prompts import create_talk_proposal_prompt, get_system_message

# Page configuration
st.set_page_config(
    page_title="Conference Talk RAG System",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

class ConferenceTalkApp:
    def __init__(self):
        self.nebius_client = NebiusClient()
        self.corpus_manager = None

        # Initialize session state
        if 'conferences' not in st.session_state:
            st.session_state.conferences = []
        if 'selected_conference' not in st.session_state:
            st.session_state.selected_conference = None
        if 'crawl_results' not in st.session_state:
            st.session_state.crawl_results = None

    def init_corpus_manager(self):
        """Initialize corpus manager with error handling"""
        if self.corpus_manager is None:
            try:
                self.corpus_manager = ConferenceCorpusManager()
                return True
            except Exception as e:
                st.error(f"Failed to connect to Couchbase: {str(e)}")
                st.error("Please ensure Couchbase is running and environment variables are set correctly.")
                return False
        return True

    def render_sidebar(self):
        """Render sidebar with conference management"""
        with st.sidebar:
            st.title("🎤 Conference RAG")
            st.markdown("---")

            # Conference management section
            st.subheader("📚 Manage Conferences")

            if st.button("🔄 Refresh Conference List", use_container_width=True):
                self.load_conferences()

            # Display stored conferences
            if st.session_state.conferences:
                st.markdown("**Stored Conferences:**")
                for conf in st.session_state.conferences[:5]:  # Show recent 5
                    with st.container():
                        st.markdown(f"**{conf['name']}** ({conf['year']})")
                        st.caption(f"Platform: {conf['platform']} | Talks: {conf['total_talks']}")
                        if st.button(f"Select", key=f"select_{conf['id']}", use_container_width=True):
                            st.session_state.selected_conference = conf['id']
                            st.success(f"Selected: {conf['name']}")
                        st.markdown("---")
            else:
                st.info("No conferences stored yet. Add one below!")

            # Environment status
            st.subheader("🔧 System Status")
            self.show_environment_status()

    def show_environment_status(self):
        """Show environment configuration status"""
        required_vars = [
            ("Nebius AI API", "NEBIUS_API_KEY"),
            ("Exa API", "EXA_API_KEY"),
            ("Tavily API", "TAVILY_API_KEY"),
            ("Couchbase", "CB_CONNECTION_STRING")
        ]

        for name, var in required_vars:
            if os.getenv(var):
                st.success(f"✅ {name}")
            else:
                st.error(f"❌ {name}")

    def load_conferences(self):
        """Load conferences from Couchbase"""
        if self.init_corpus_manager():
            try:
                conferences = self.corpus_manager.list_conferences()
                st.session_state.conferences = conferences
                if conferences:
                    st.success(f"Loaded {len(conferences)} conferences")
                else:
                    st.info("No conferences found in database")
            except Exception as e:
                st.error(f"Error loading conferences: {str(e)}")

    def render_main_interface(self):
        """Render main application interface"""
        st.title("🎤 Conference-Agnostic CFP Generation system")
        st.markdown("""
        This system automatically crawls any conference website, builds a searchable corpus,
        and generates unique talk proposals using real-time research and historical context.
        """)

        # Tabs for different functionalities
        tab1, tab2, tab3 = st.tabs(["🚀 Add Conference", "💡 Generate Proposal", "📊 Analytics"])

        with tab1:
            self.render_conference_crawler()

        with tab2:
            self.render_talk_generator()

        with tab3:
            self.render_analytics()

    def render_conference_crawler(self):
        """Render conference crawling interface"""
        st.header("🕷️ Add New Conference")

        # Input section
        col1, col2 = st.columns([3, 1])

        with col1:
            conference_url = st.text_input(
                "Conference Schedule URL:",
                placeholder="https://kccncna2024.sched.com/ or https://sessionize.com/event-name/",
                help="Enter the main schedule/agenda URL of any conference"
            )

        with col2:
            st.markdown("**Supported Platforms:**")
            st.markdown("• Sched.com")
            st.markdown("• Sessionize.com")
            st.markdown("• Generic sites")

        # Crawling options
        with st.expander("⚙️ Advanced Options"):
            col1, col2 = st.columns(2)
            with col1:
                batch_size = st.slider("Batch Size", 5, 20, 10,
                                     help="Number of talks to process in parallel")
            with col2:
                rate_limit = st.slider("Rate Limit (seconds)", 0.5, 3.0, 1.0,
                                     help="Delay between batches to be respectful")

        # Crawl button
        if st.button("🚀 Crawl Conference", type="primary", use_container_width=True):
            if not conference_url:
                st.warning("Please enter a conference URL")
                return

            if not self.init_corpus_manager():
                return

            self.crawl_conference(conference_url, batch_size, rate_limit)

    def crawl_conference(self, url: str, batch_size: int, rate_limit: float):
        """Execute conference crawling with progress tracking"""

        progress_container = st.container()

        with progress_container:
            st.info("🚀 Starting conference crawl...")

            # Create progress components
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # Step 1: Crawl conference
                status_text.text("📡 Detecting platform and crawling talks...")
                progress_bar.progress(20)

                # Run async crawling
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    crawl_result = loop.run_until_complete(
                        crawl_single_conference(url, batch_size, rate_limit, verbose=False)
                    )
                finally:
                    loop.close()

                if not crawl_result['success']:
                    st.error(f"❌ Crawling failed: {crawl_result.get('error')}")
                    return

                progress_bar.progress(60)
                status_text.text("💾 Storing in Couchbase and generating embeddings...")

                # Step 2: Store in Couchbase with embeddings
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    store_result = loop.run_until_complete(
                        store_crawled_conference(crawl_result)
                    )
                finally:
                    loop.close()

                progress_bar.progress(100)
                status_text.text("✅ Conference successfully added!")

                # Display results
                st.success("🎉 Conference Added Successfully!")

                # Show summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Conference", crawl_result['conference']['name'])
                with col2:
                    st.metric("Platform", crawl_result['conference']['platform'].title())
                with col3:
                    st.metric("Talks Stored", store_result['successful_stores'])

                # Show detailed stats
                with st.expander("📊 Detailed Results"):
                    st.json({
                        'conference_info': crawl_result['conference'],
                        'crawl_stats': crawl_result['stats'],
                        'storage_stats': store_result
                    })

                # Refresh conference list
                self.load_conferences()

                # Auto-select the new conference
                st.session_state.selected_conference = crawl_result['conference']['id']

            except Exception as e:
                st.error(f"❌ Error during crawling: {str(e)}")
                st.exception(e)

    def render_talk_generator(self):
        """Render talk proposal generation interface"""
        st.header("💡 Generate Talk Proposal")

        # Conference selection
        if not st.session_state.conferences:
            st.warning("📚 No conferences available. Please add a conference first.")
            return

        # Conference selector
        conference_options = {f"{conf['name']} ({conf['year']})": conf['id']
                            for conf in st.session_state.conferences}

        selected_name = st.selectbox(
            "Select Conference:",
            options=list(conference_options.keys()),
            index=0 if not st.session_state.selected_conference else
                  list(conference_options.values()).index(st.session_state.selected_conference)
                  if st.session_state.selected_conference in conference_options.values() else 0
        )

        selected_conference_id = conference_options[selected_name]
        st.session_state.selected_conference = selected_conference_id

        # Talk idea input
        st.markdown("### 🎯 Your Talk Idea")
        talk_idea = st.text_area(
            "Describe your talk idea:",
            placeholder="e.g., Advanced OpenTelemetry patterns for distributed tracing in Kubernetes environments",
            height=100,
            help="Be specific about the technology, use case, or problem you want to address"
        )

        # Generation options
        with st.expander("🔧 Generation Options"):
            col1, col2 = st.columns(2)
            with col1:
                num_similar = st.slider("Similar Talks to Find", 3, 10, 5)
                enable_research = st.checkbox("Enable Real-time Research", value=True)
            with col2:
                temperature = st.slider("Creativity Level", 0.1, 1.0, 0.7)
                max_tokens = st.slider("Response Length", 1000, 3000, 2000)

        # Generate button
        if st.button("🚀 Generate Talk Proposal", type="primary", use_container_width=True):
            if not talk_idea.strip():
                st.warning("Please describe your talk idea")
                return

            if not self.init_corpus_manager():
                return

            self.generate_talk_proposal(
                talk_idea, selected_conference_id, num_similar,
                enable_research, temperature, max_tokens
            )

    def generate_talk_proposal(self, talk_idea: str, conference_id: str, num_similar: int,
                             enable_research: bool, temperature: float, max_tokens: int):
        """Generate talk proposal with progress tracking"""

        progress_container = st.container()

        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # Step 1: Real-time research (if enabled)
                adk_research = ""
                if enable_research:
                    status_text.text("🔬 Running real-time research...")
                    progress_bar.progress(20)

                    try:
                        adk_research = run_adk_research(talk_idea)
                        st.success("✅ Real-time research completed")
                    except Exception as e:
                        st.warning(f"⚠️ Research failed: {str(e)}")
                        adk_research = "Research unavailable"
                else:
                    progress_bar.progress(20)

                # Step 2: Vector search for similar talks
                status_text.text("🔍 Searching conference corpus...")
                progress_bar.progress(50)

                similar_talks = self.corpus_manager.get_similar_talks(
                    talk_idea, conference_id, num_similar
                )

                # Step 3: Generate final proposal
                status_text.text("🤖 Generating talk proposal with Nebius AI...")
                progress_bar.progress(80)

                proposal = self.generate_final_proposal(
                    talk_idea, similar_talks, adk_research, temperature, max_tokens, conference_id
                )

                progress_bar.progress(100)
                status_text.text("✅ Proposal generated successfully!")

                # Display results
                st.markdown("---")
                st.markdown("## 🎤 Generated Talk Proposal")
                st.markdown(proposal)

                # Show context used
                col1, col2 = st.columns(2)

                with col1:
                    with st.expander("🔬 Real-time Research Context"):
                        if adk_research and adk_research != "Research unavailable":
                            st.markdown(adk_research)
                        else:
                            st.info("Real-time research was disabled or failed")

                with col2:
                    with st.expander("📚 Similar Conference Talks"):
                        if similar_talks:
                            for i, talk in enumerate(similar_talks, 1):
                                title = talk.get("title", "Untitled")
                                speaker = talk.get("speaker", "Unknown")
                                category = talk.get("category", "Uncategorized")
                                score = talk.get("score")
                                score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "N/A"
                                description = talk.get("description", "")
                                st.markdown(f"**{i}. {title}**")
                                st.caption(f"Speaker: {speaker} | Category: {category}")
                                st.markdown(f"*Score: {score_str}*")
                                with st.expander("Description"):
                                    st.markdown(description[:500] + "..." if len(description) > 500 else description)
                                st.markdown("---")
                        else:
                            st.info("No similar talks found in conference corpus")

            except Exception as e:
                st.error(f"❌ Error generating proposal: {str(e)}")
                st.exception(e)

    def generate_final_proposal(self, query: str, similar_talks: List[Dict],
                              adk_research: str, temperature: float, max_tokens: int,
                              conference_id: str) -> str:
        """Generate final talk proposal using OpenRouter/Grok-4 with structured prompt approach"""

        # Get conference info
        conferences = {conf['id']: conf for conf in st.session_state.conferences}
        conference_info = conferences.get(conference_id, {})

        # Create the structured prompt using the imported function
        prompt = create_talk_proposal_prompt(
            query=query,
            conference_info=conference_info,
            similar_talks=similar_talks,
            adk_research=adk_research
        )

        try:
            messages = [
                {"role": "system", "content": get_system_message()},
                {"role": "user", "content": prompt}
            ]

            return self.nebius_client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

        except Exception as e:
            return f"Error generating proposal: {str(e)}"

    def render_analytics(self):
        """Render analytics and conference statistics"""
        st.header("📊 Conference Analytics")

        if not st.session_state.conferences:
            st.info("No conferences to analyze. Add some conferences first!")
            return

        if not self.init_corpus_manager():
            return

        # Conference selector for analytics
        conference_options = {f"{conf['name']} ({conf['year']})": conf['id']
                            for conf in st.session_state.conferences}

        selected_name = st.selectbox(
            "Select Conference for Analysis:",
            options=list(conference_options.keys()),
            key="analytics_conference"
        )

        selected_conference_id = conference_options[selected_name]

        try:
            stats = self.corpus_manager.get_conference_stats(selected_conference_id)

            if 'error' in stats:
                st.error(f"Error loading stats: {stats['error']}")
                return

            # Overview metrics
            st.subheader("📈 Overview")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Talks", stats['total_talks'])
            with col2:
                st.metric("Platform", stats['metadata'].get('platform', 'Unknown').title())
            with col3:
                st.metric("Year", stats['metadata'].get('year', 'Unknown'))
            with col4:
                embedding_model = stats['metadata'].get('embedding_model', 'Unknown')
                st.metric("Embedding Model", embedding_model.split('/')[-1] if '/' in embedding_model else embedding_model)

            # Category distribution
            if stats.get('category_distribution'):
                st.subheader("🏷️ Category Distribution")

                categories = stats['category_distribution'][:10]  # Top 10
                category_names = [cat['category'] for cat in categories]
                category_counts = [cat['count'] for cat in categories]

                st.bar_chart(dict(zip(category_names, category_counts)))

                # Detailed breakdown
                with st.expander("📋 Detailed Category Breakdown"):
                    for cat in categories:
                        st.markdown(f"**{cat['category']}**: {cat['count']} talks")

            # Conference metadata
            with st.expander("🔧 Technical Details"):
                st.json(stats['metadata'])

        except Exception as e:
            st.error(f"Error loading analytics: {str(e)}")

    def run(self):
        """Main application entry point"""
        try:
            # Load conferences on startup
            if not st.session_state.conferences:
                self.load_conferences()

            # Render UI
            self.render_sidebar()
            self.render_main_interface()

        except Exception as e:
            st.error(f"Application error: {str(e)}")
            st.exception(e)

        finally:
            # Clean up connections
            if self.corpus_manager:
                self.corpus_manager.close()

def main():
    """Application entry point"""
    app = ConferenceTalkApp()
    app.run()

if __name__ == "__main__":
    main()