import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()



# Import the career_guidance_system
from career_guidance_system import CareerGuidanceSystem
from career_chatbot import display_chat_interface


# Set page config
st.set_page_config(
    page_title="AI Career Guidance Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; font-weight: bold; color: #4285F4;}
    .sub-header {font-size: 1.2rem; margin-bottom: 2rem; color: #9E9E9E;}
    /* Dark theme */
    .stApp {background-color: #121212; color: #E0E0E0;}
    [data-testid="stSidebar"] {background-color: #1E1E1E; border-right: 1px solid #333;}
    h1, h2, h3, h4, h5, h6 {color: #90CAF9 !important;}
    .stButton > button {background-color: #303F9F; color: white; border: none; font-weight: bold;}
    .stButton > button:hover {background-color: #5C6BC0;}
    /* Section styling */
    .career-section {
        background-color: #1A237E; 
        color: white; 
        border-radius: 8px; 
        padding: 20px; 
        margin-bottom: 20px;
    }
    .market-section {
        background-color: #0D47A1; 
        color: white; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 15px;
    }
    .roadmap-section {
        background-color: #1B5E20; 
        color: white; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 15px;
    }
    .insights-section {
        background-color: #4A148C; 
        color: white; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)
# groq_api_key=os.getenv('GROQ_API_KEY')
# serpapi_key=os.getenv('SERPAPI_API_KEY')

# Initialize session state variables
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = ""
if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = ""
if "career_system" not in st.session_state:
    st.session_state.career_system = None
if "selected_career" not in st.session_state:
    st.session_state.selected_career = None
if "selected_category" not in st.session_state:  
    st.session_state.selected_category = None   
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}
if "career_analysis" not in st.session_state:
    st.session_state.career_analysis = None
if "show_chat" not in st.session_state:
    st.session_state.show_chat = False
if "messages" not in st.session_state:
    st.session_state.messages = []

# Title and description
st.markdown("<div class='main-header'>🚀 AI-Powered Career Guidance Platform</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Explore career options, analyze job markets, and create personalized learning paths with AI</div>", unsafe_allow_html=True)

# Sidebar for API key and user profile
with st.sidebar:
    st.header("Configuration")
    groq_api_key = st.text_input("Groq API Key", type="password", value=st.session_state.groq_api_key)
    serpapi_key = st.text_input("SerpAPI Key (for web search)", type="password", value=st.session_state.serpapi_key)
    
    if groq_api_key:
        st.session_state.groq_api_key = groq_api_key
        st.session_state.serpapi_key = serpapi_key
        
        # Initialize career guidance system if API key is provided
        if not st.session_state.career_system:
            with st.spinner("Initializing AI systems..."):
                st.session_state.career_system = CareerGuidanceSystem(
                    groq_api_key=groq_api_key, 
                    serpapi_key=serpapi_key
                )
                st.success("Career guidance system initialized successfully!")
                if serpapi_key:
                    st.info("Web search capabilities enabled! The system will provide up-to-date information on careers.")
                else:
                    st.warning("Web search capabilities are disabled. For the best experience, provide a SerpAPI key.")
    
        
    # User profile section
    st.markdown("### 👤 Your Profile")
    user_name = st.text_input("Name", value=st.session_state.user_profile.get("name", ""))
    
    education_level = st.selectbox(
        "Education Level",
        ["High School", "Some College", "Bachelor's Degree", "Master's Degree", "PhD", "Other"],
        index=2
    )
    
    experience = st.selectbox(
        "Experience Level",
        ["Student/No experience", "0-2 years", "3-5 years", "5-10 years", "10+ years"],
        index=0
    )
    
    # Update profile in session state
    if user_name:
        st.session_state.user_profile = {
            "name": user_name,
            "education": education_level,
            "experience": experience
        }


# Create tabs for main content
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Discover Careers", 
    "📊 Market Analysis", 
    "📚 Learning Roadmap",
    "💡 Career Insights",
    "💬 Chat Assistant"
])

# Tab 1: Discover Careers
with tab1:
    st.markdown("## Discover Your Ideal Career Path")
    
    # Check if API key is provided
    if not st.session_state.groq_api_key:
        st.warning("Please enter your Groq API key in the sidebar to get started.")
    else:
        # Display the user's profile summary
        if st.session_state.user_profile and "name" in st.session_state.user_profile:
            st.markdown(f"""
            <div style="background-color: #212121; border-radius: 8px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #4285F4;">
                <h3 style="color: #82B1FF; margin-top: 0;">👋 Hello, {st.session_state.user_profile['name']}!</h3>
                <p style="font-size: 16px; line-height: 1.6;">
                    Based on your profile as a <span style="background-color: #303F9F; color: white; padding: 2px 5px; border-radius: 3px;">{st.session_state.user_profile['education']}</span> 
                    graduate with <span style="background-color: #303F9F; color: white; padding: 2px 5px; border-radius: 3px;">{st.session_state.user_profile['experience']}</span> of experience, 
                    we'll help you find the perfect career path.
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Career categories
        st.markdown("### Select a Career Category")
        
        # Get career options from the system
        if st.session_state.career_system:
            career_options = st.session_state.career_system.get_career_options()
        else:
            # Fallback options
            career_options = {
                "Technology": [
                    "Software Engineering", 
                    "Data Science", 
                    "Cybersecurity", 
                    "AI/ML Engineering", 
                    "DevOps",
                    "Cloud Architecture",
                    "Mobile Development"
                ],
                "Healthcare": [
                    "Medicine", 
                    "Nursing", 
                    "Pharmacy", 
                    "Biomedical Engineering",
                    "Healthcare Administration",
                    "Physical Therapy"
                ],
                "Business": [
                    "Finance", 
                    "Marketing", 
                    "Management", 
                    "Human Resources",
                    "Entrepreneurship",
                    "Business Analysis"
                ],
                "Creative": [
                    "Graphic Design", 
                    "UX/UI Design", 
                    "Content Creation", 
                    "Digital Marketing",
                    "Animation",
                    "Film Production"
                ]
            }
        
        # Display category buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💻 Technology", help="Careers in software, data, cybersecurity, and more", key="tech_button", use_container_width=True):
                st.session_state.selected_category = "Technology"
                st.session_state.career_analysis = None
        with col2:
            if st.button("🏥 Healthcare", help="Medical and health-related careers", key="health_button", use_container_width=True):
                st.session_state.selected_category = "Healthcare"
                st.session_state.career_analysis = None
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("💼 Business", help="Finance, marketing, management careers", key="business_button", use_container_width=True):
                st.session_state.selected_category = "Business"
                st.session_state.career_analysis = None
        with col4:
            if st.button("🎨 Creative", help="Design, content creation, and artistic careers", key="creative_button", use_container_width=True):
                st.session_state.selected_category = "Creative"
                st.session_state.career_analysis = None
        
        # Display career options if category is selected
        if st.session_state.selected_category:
            st.markdown(f"### {st.session_state.selected_category} Careers")
            
            # Show career options
            selected_careers = career_options[st.session_state.selected_category]
            career_cols = st.columns(2)
            
            for i, career in enumerate(selected_careers):
                with career_cols[i % 2]:
                    if st.button(career, key=f"career_{i}", use_container_width=True):
                        st.session_state.selected_career = career
                        st.session_state.career_analysis = None
            
            # Show selected career details
            if st.session_state.selected_career:
                st.markdown(f"""
                <div style="background-color: #212121; border-radius: 8px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #4285F4;">
                    <h3 style="color: #82B1FF; margin-top: 0;">🎯 Selected Career: {st.session_state.selected_career}</h3>
                    <p style="font-size: 16px; line-height: 1.6;">
                        Let's analyze this career path to help you understand the opportunities, 
                        requirements, and job market.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Allow user to analyze career
                if st.session_state.career_analysis is None:
                    # Status of career system
                    if st.session_state.career_system:
                        if st.session_state.serpapi_key:
                            st.success("Our AI career advisors are ready to provide detailed analysis with up-to-date information!")
                        else:
                            st.success("Our AI career advisors are ready to provide detailed analysis!")
                    
                    if st.button("🔍 Analyze This Career Path", type="primary", use_container_width=True):
                        with st.spinner(f"Analyzing {st.session_state.selected_career} career path... This may take a few minutes."):
                            try:
                                # Use the comprehensive career analysis method
                                if st.session_state.career_system:
                                    career_analysis = st.session_state.career_system.comprehensive_career_analysis(
                                        st.session_state.selected_career,
                                        st.session_state.user_profile
                                    )
                                else:
                                    # Fallback to basic analysis
                                    career_analysis = {
                                        "career_name": st.session_state.selected_career,
                                        "research": f"Analysis for {st.session_state.selected_career} would be generated by AI in a real implementation.",
                                        "market_analysis": f"Market analysis for {st.session_state.selected_career}.",
                                        "learning_roadmap": f"Learning roadmap for {st.session_state.selected_career}.",
                                        "industry_insights": f"Industry insights for {st.session_state.selected_career}."
                                    }
                                
                                st.session_state.career_analysis = career_analysis
                                st.success("Analysis complete!")
                                st.session_state.show_chat = True  # Enable chat after analysis
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error during analysis: {str(e)}")
                
                # Display analysis results if available
                if st.session_state.career_analysis:
                    # Get the research content
                    research = st.session_state.career_analysis.get("research", "")
                    if isinstance(research, str) and research:
                        st.markdown(f"""
                            <div class="career-section">
                            <h3 style="color: #82B1FF; margin-top: 0;">Overview of {st.session_state.selected_career}</h3>
                             <div style="font-size: 16px; line-height: 1.6;">
                                {research}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

# Tab 2: Market Analysis
with tab2:
    st.markdown("## Job Market Analysis")
    
    if not st.session_state.groq_api_key:
        st.warning("Please enter your Groq API key in the sidebar to get started.")
    elif not st.session_state.selected_career:
        st.info("Please select a career in the 'Discover Careers' tab first.")
    else:
        st.markdown(f"### Market Analysis for: {st.session_state.selected_career}")
        
        # Check if we already have analysis
        if st.session_state.career_analysis and "market_analysis" in st.session_state.career_analysis:
            # Display the market analysis
            market_analysis = st.session_state.career_analysis["market_analysis"]
            
            # Display the market analysis as Markdown
            st.markdown(f"""
              <div class="market-section">
                <h4 style="margin-top: 0;">📊 Market Analysis</h4>
                <div style="font-size: 16px; line-height: 1.6;">
                    {market_analysis}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Job growth visualization
            st.markdown("### Job Growth Projection")
            
            # Create sample data
            years = list(range(2025, 2030))
            growth_rate = np.random.uniform(0.05, 0.15)
            starting_jobs = np.random.randint(80000, 200000)
            jobs = [starting_jobs * (1 + growth_rate) ** i for i in range(5)]
            
            # Calculate CAGR (Compound Annual Growth Rate)
            cagr = (jobs[-1]/jobs[0])**(1/4) - 1  # 4-year CAGR
            
            job_fig = px.line(
                x=years, 
                y=jobs,
                labels={"x": "Year", "y": "Projected Jobs"},
                title=f"Projected Job Growth for {st.session_state.selected_career}"
            )
            
            # Apply styling
            job_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#212121",
                plot_bgcolor="#212121",
                font=dict(color="#E0E0E0"),
                title_font=dict(color="#82B1FF"),
                xaxis=dict(gridcolor="#424242"),
                yaxis=dict(gridcolor="#424242")
            )
            
            job_fig.update_traces(mode="lines+markers", line=dict(width=3, color="#2196F3"), marker=dict(size=10))
            
            # Add annotation for CAGR
            job_fig.add_annotation(
                x=years[2],
                y=jobs[2],
                text=f"CAGR: {cagr:.1%}",
                showarrow=True,
                arrowhead=1,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="#FF5722",
                font=dict(size=14, color="#FF5722"),
                bgcolor="#212121",
                bordercolor="#FF5722",
                borderwidth=2,
                borderpad=4,
                ax=-50,
                ay=-40
            )
            
            st.plotly_chart(job_fig, use_container_width=True)
            
            # Salary analysis
            st.markdown("### Salary Analysis")
            
            experience_levels = ["Entry Level", "Mid Level", "Senior", "Expert"]
            base_salary = np.random.randint(60000, 90000)
            salaries = [base_salary]
            for i in range(1, 4):
                salaries.append(salaries[-1] * (1 + np.random.uniform(0.2, 0.4)))
            
            salary_fig = px.bar(
                x=experience_levels,
                y=salaries,
                labels={"x": "Experience Level", "y": "Annual Salary ($)"},
                title=f"Salary by Experience Level - {st.session_state.selected_career}"
            )
            
            # Apply styling
            salary_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#212121",
                plot_bgcolor="#212121",
                font=dict(color="#E0E0E0"),
                title_font=dict(color="#82B1FF"),
                xaxis=dict(gridcolor="#424242"),
                yaxis=dict(gridcolor="#424242")
            )
            
            salary_fig.update_traces(marker=dict(color=["#64B5F6", "#42A5F5", "#2196F3", "#1976D2"]))
            
            st.plotly_chart(salary_fig, use_container_width=True)
            
        else:
            # Generate new market analysis
            if st.button("Generate Market Analysis", type="primary", use_container_width=True):
                with st.spinner("Generating market analysis with up-to-date information..."):
                    try:
                        if st.session_state.career_system:
                            # Use the market analysis method
                            market_analysis = st.session_state.career_system.analyze_market_trends(
                                st.session_state.selected_career
                            )
                            
                            # Save to session state
                            if "career_analysis" not in st.session_state:
                                st.session_state.career_analysis = {}
                            
                            if isinstance(st.session_state.career_analysis, dict):
                                st.session_state.career_analysis["market_analysis"] = market_analysis
                            else:
                                st.session_state.career_analysis = {
                                    "career_name": st.session_state.selected_career,
                                    "market_analysis": market_analysis
                                }
                            
                            # Show success message and rerun
                            st.success("Market analysis complete!")
                            st.rerun()
                        else:
                            st.error("Career guidance system not initialized. Please check your API key.")
                        
                    except Exception as e:
                        st.error(f"Error generating market analysis: {str(e)}")

# Tab 3: Learning Roadmap
with tab3:
    st.markdown("## Personalized Learning Roadmap")
    
    if not st.session_state.groq_api_key:
        st.warning("Please enter your Groq API key in the sidebar to get started.")
    elif not st.session_state.selected_career:
        st.info("Please select a career in the 'Discover Careers' tab first.")
    else:
        st.markdown(f"### Learning Roadmap for: {st.session_state.selected_career}")
        
        # Experience level for roadmap
        experience_options = {
            "Student/No experience": "beginner",
            "0-2 years": "beginner",
            "3-5 years": "intermediate",
            "5-10 years": "advanced",
            "10+ years": "expert"
        }
        
        user_experience = st.session_state.user_profile.get("experience", "Student/No experience")
        experience_level = experience_options.get(user_experience, "beginner")
        
        # Display user's current level
        st.markdown(f"""
        <div style="background-color:#1A237E; color:#E0E0E0; border-radius:8px; padding:15px; margin-bottom:20px;">
            <h4 style="margin-top:0; color:#82B1FF;">Your Current Level: {experience_level.title()}</h4>
            <p>This roadmap is tailored for someone at your experience level.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Check if we already have a roadmap in the career analysis
        if st.session_state.career_analysis and "learning_roadmap" in st.session_state.career_analysis:
            roadmap = st.session_state.career_analysis["learning_roadmap"]
            
            # Display roadmap
            st.markdown(f"""
                <div class="roadmap-section">
                <h4 style="margin-top: 0;">📚 Learning Roadmap</h4>
                <div style="font-size: 16px; line-height: 1.6;">
                    {roadmap}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Create a simple timeline visualization
            st.markdown("### Learning Journey Timeline")
            
            # Create a timeline dataframe
            months = ["Initial Setup", "3 Months", "6 Months", "9 Months", "1 Year", "2 Years"]
            progress = [100, 80, 60, 40, 20, 10] if experience_level == "beginner" else [100, 100, 80, 60, 40, 20]
            
            fig = px.bar(
                x=progress, 
                y=months,
                orientation='h',
                labels={"x": "Progress (%)", "y": "Learning Stage"},
                title=f"Learning Journey for {st.session_state.selected_career}"
            )
            
            # Apply styling
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#212121",
                plot_bgcolor="#212121",
                font=dict(color="#E0E0E0"),
                xaxis=dict(gridcolor="#424242"),
                yaxis=dict(gridcolor="#424242", categoryorder="array", categoryarray=months[::-1])
            )
            
            fig.update_traces(marker=dict(color="#4CAF50"))
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            # Generate new roadmap
            if st.button("Generate Learning Roadmap", type="primary", use_container_width=True):
                with st.spinner("Generating personalized learning roadmap with current resources..."):
                    try:
                        if st.session_state.career_system:
                            # Use the learning roadmap method
                            roadmap = st.session_state.career_system.create_learning_roadmap(
                                st.session_state.selected_career,
                                experience_level
                            )
                            
                            # Save to session state
                            if "career_analysis" not in st.session_state:
                                st.session_state.career_analysis = {}
                            
                            if isinstance(st.session_state.career_analysis, dict):
                                st.session_state.career_analysis["learning_roadmap"] = roadmap
                            else:
                                st.session_state.career_analysis = {
                                    "career_name": st.session_state.selected_career,
                                    "learning_roadmap": roadmap
                                }
                            
                            # Show success and rerun
                            st.success("Learning roadmap generated successfully!")
                            st.rerun()
                        else:
                            st.error("Career guidance system not initialized. Please check your API key.")
                        
                    except Exception as e:
                        st.error(f"Error generating roadmap: {str(e)}")

# Tab 4: Career Insights
with tab4:
    st.markdown("## Advanced Career Insights")
    
    if not st.session_state.groq_api_key:
        st.warning("Please enter your groq API key in the sidebar to get started.")
    elif not st.session_state.selected_career:
        st.info("Please select a career in the 'Discover Careers' tab first.")
    else:
        # Display career insights
        if st.session_state.career_analysis and "industry_insights" in st.session_state.career_analysis:
            insights_text = st.session_state.career_analysis["industry_insights"]
            
            # Display insights
            st.markdown(f"""
                <div class="insights-section">
                <h4 style="margin-top: 0;">💡 Industry Insights</h4>
                <div style="font-size: 16px; line-height: 1.6;">
                    {insights_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Display skills visualization
            st.markdown("### Key Skills Assessment")
            
            skills = {
                "Technical": np.random.randint(70, 95),
                "Problem-solving": np.random.randint(70, 95),
                "Communication": np.random.randint(70, 95),
                "Teamwork": np.random.randint(70, 95),
                "Industry Knowledge": np.random.randint(70, 95)
            }
            
            skills_fig = px.bar(
                x=list(skills.keys()),
                y=list(skills.values()),
                labels={"x": "Skill", "y": "Importance (%)"},
                title=f"Skills Importance for {st.session_state.selected_career}"
            )
            
            # Apply styling
            skills_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#212121",
                plot_bgcolor="#212121",
                font=dict(color="#E0E0E0"),
                xaxis=dict(gridcolor="#424242"),
                yaxis=dict(gridcolor="#424242")
            )
            
            st.plotly_chart(skills_fig, use_container_width=True)
            
        else:
            # Generate new insights
            if st.button("Generate Industry Insights", type="primary", use_container_width=True):
                with st.spinner("Gathering industry insights from professionals..."):
                    try:
                        if st.session_state.career_system:
                            # Get insights using the career system
                            insights = st.session_state.career_system.get_career_insights(
                                st.session_state.selected_career
                            )
                            
                            # Save to session state
                            if "career_analysis" not in st.session_state:
                                st.session_state.career_analysis = {}
                            
                            if isinstance(st.session_state.career_analysis, dict):
                                st.session_state.career_analysis["industry_insights"] = insights
                            else:
                                st.session_state.career_analysis = {
                                    "career_name": st.session_state.selected_career,
                                    "industry_insights": insights
                                }
                            
                            st.success("Industry insights generated successfully!")
                            st.rerun()
                        else:
                            st.error("Career guidance system not initialized. Please check your API key.")
                        
                    except Exception as e:
                        st.error(f"Error generating insights: {str(e)}")

# Tab 5: Chat Assistant
with tab5:
    st.markdown("## Career Chat Assistant")
    
    if not st.session_state.groq_api_key:
        st.warning("Please enter your GROQ API key in the sidebar to get started.")
    elif not st.session_state.selected_career:
        st.info("Please select a career in the 'Discover Careers' tab first.")
    else:
        # Display integrated chat interface
        career_data = st.session_state.career_analysis
        career_system = st.session_state.career_system
        
        display_chat_interface(career_data, career_system)

# Add information about the AI system
with st.expander("ℹ️ About this AI Career Guidance System"):
    st.markdown("""
    This AI-powered Career Guidance Platform uses advanced AI technologies to provide personalized career insights:
    
    - **LangChain**: For structured interaction with AI language models
    - **Web Search**: The system can search the internet for up-to-date information (requires SerpAPI key)
    - **Streamlit**: Powers the interactive web interface
    
    The system provides five key services:
    1. **Career Discovery**: Explore career options across different fields
    2. **Market Analysis**: Understand job growth, salary trends, and market demand
    3. **Learning Roadmap**: Get personalized education and skill development plans
    4. **Industry Insights**: Learn about workplace culture, advancement opportunities, and day-to-day responsibilities
    5. **Chat Assistant**: Ask specific questions about your selected career path
    
    For the best experience, enter your API key in the sidebar.
    """) 