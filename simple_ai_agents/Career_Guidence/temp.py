import streamlit as st
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.agents import load_tools, initialize_agent, AgentType
from langchain_community.utilities import SerpAPIWrapper
from datetime import datetime
import os
import time
import uuid

# Streamlit page configuration
st.set_page_config(page_title="Career Guidance System", layout="wide")

class CareerGuidanceSystem:
    def __init__(self, groq_api_key=None, serpapi_key=None):
        """Initialize the career guidance system"""
        self.groq_api_key = groq_api_key
        self.serpapi_key = serpapi_key
        
        # Set environment variable for Groq API key
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
        
        # Set environment variable for SerpAPI key
        if serpapi_key:
            os.environ["SERPAPI_API_KEY"] = serpapi_key
        
        # Initialize the language model
        if groq_api_key:
            self.llm = ChatGroq(
                model_name="gemma2-9b-it",
                groq_api_key=groq_api_key
            )
            
            # Initialize search tools if SerpAPI key is provided
            if serpapi_key:
                self.search = SerpAPIWrapper(serpapi_api_key=serpapi_key)
                self.tools = load_tools(["serpapi"], llm=self.llm)
                self.search_agent = initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    handle_parsing_errors=True,
                    max_iterations=6
                )
            else:
                self.search = None
                self.search_agent = None
        else:
            self.llm = None
            self.search = None
            self.search_agent = None
        
        # Career data storage with caching
        self.career_data = {}
        self.search_cache = {}
        self.user_profile = {}
        
        # Fallback career options
        self.fallback_career_options = {
            "Technology": [
                "Software Engineering", "Data Science", "Cybersecurity",
                "AI/ML Engineering", "DevOps", "Cloud Architecture",
                "Mobile Development"
            ],
            "Healthcare": [
                "Medicine", "Nursing", "Pharmacy", "Biomedical Engineering",
                "Healthcare Administration", "Physical Therapy"
            ],
            "Business": [
                "Finance", "Marketing", "Management", "Human Resources",
                "Entrepreneurship", "Business Analysis"
            ],
            "Creative": [
                "Graphic Design", "UX/UI Design", "Content Creation",
                "Digital Marketing", "Animation", "Film Production"
            ]
        }

    def search_with_cache(self, query, cache_key, ttl_hours=24, max_retries=3):
        """Perform a search with caching"""
        if cache_key in self.search_cache:
            timestamp = self.search_cache[cache_key]['timestamp']
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            if age_hours < ttl_hours:
                return self.search_cache[cache_key]['data']
        
        if self.search_agent:
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    result = self.search_agent.run(query)
                    self.search_cache[cache_key] = {
                        'data': result,
                        'timestamp': datetime.now()
                    }
                    time.sleep(1)
                    return result
                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    time.sleep(2)
            
            try:
                prompt = PromptTemplate(
                    input_variables=["query"],
                    template="""
                    Please provide information on the following: {query}
                    Structure your response clearly with headings and bullet points.
                    """
                )
                chain = LLMChain(llm=self.llm, prompt=prompt)
                result = chain.run(query=query)
                self.search_cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }
                return result
            except:
                return f"Search failed after {max_retries} attempts. Last error: {last_error}"
        else:
            return "Search unavailable. Please provide a SerpAPI key."

    def format_search_results(self, results, title):
        """Format search results into markdown"""
        formatted = f"# {title}\n\n"
        if isinstance(results, str):
            lines = results.split('\n')
            clean_lines = []
            for line in lines:
                if "I'll search for" not in line and "I need to search for" not in line:
                    if not line.startswith("Action:") and not line.startswith("Observation:"):
                        clean_lines.append(line)
            formatted += "\n".join(clean_lines)
        else:
            formatted += "No results available."
        return formatted

    def get_career_options(self):
        """Return all available career categories and options"""
        return self.fallback_career_options

    def comprehensive_career_analysis(self, career_name, user_profile=None):
        """Run a comprehensive analysis of a career"""
        if career_name in self.career_data:
            return self.career_data[career_name]
        
        if self.search_agent and self.serpapi_key:
            overview_query = (
                f"Create a detailed overview of the {career_name} career with the following structure:\n"
                f"1. Role Overview: What do {career_name} professionals do?\n"
                f"2. Key Responsibilities: List the main tasks and responsibilities\n"
                f"3. Required Technical Skills: List the technical skills needed\n"
                f"4. Required Soft Skills: List the soft skills needed\n"
                f"5. Educational Background: What education is typically required?"
            )
            overview_result = self.search_with_cache(overview_query, f"{career_name}_overview")
            research = self.format_search_results(overview_result, f"{career_name} Career Analysis")

            market_query = (
                f"Analyze the job market for {career_name} professionals with the following structure:\n"
                f"1. Job Growth Projections: How is job growth trending?\n"
                f"2. Salary Ranges: What are salary ranges by experience level?\n"
                f"3. Top Industries: Which industries hire the most {career_name} professionals?\n"
                f"4. Geographic Hotspots: Which locations have the most opportunities?\n"
                f"5. Emerging Trends: What new trends are affecting this field?"
            )
            market_result = self.search_with_cache(market_query, f"{career_name}_market")
            market_analysis = self.format_search_results(market_result, f"{career_name} Market Analysis")

            experience_level = "beginner"
            if user_profile and "experience" in user_profile:
                exp = user_profile["experience"]
                if "5-10" in exp or "10+" in exp:
                    experience_level = "advanced"
                elif "3-5" in exp:
                    experience_level = "intermediate"

            roadmap_query = (
                f"Create a learning roadmap for becoming a {career_name} professional at the {experience_level} level with this structure:\n"
                f"1. Skills to Develop: What skills should they focus on?\n"
                f"2. Education Requirements: What degrees or certifications are needed?\n"
                f"3. Recommended Courses: What specific courses or training programs work best?\n"
                f"4. Learning Resources: What books, websites, or tools are helpful?\n"
                f"5. Timeline: Provide a realistic timeline for skill acquisition"
            )
            roadmap_result = self.search_with_cache(roadmap_query, f"{career_name}_roadmap_{experience_level}")
            learning_roadmap = self.format_search_results(roadmap_result, f"{career_name} Learning Roadmap")

            insights_query = (
                f"Provide industry insights for {career_name} professionals with this structure:\n"
                f"1. Workplace Culture: What is the typical work environment like?\n"
                f"2. Day-to-Day Activities: What does a typical workday include?\n"
                f"3. Career Progression: What career advancement paths exist?\n"
                f"4. Work-Life Balance: How is the work-life balance in this field?\n"
                f"5. Success Strategies: What tips help professionals succeed in this field?"
            )
            insights_result = self.search_with_cache(insights_query, f"{career_name}_insights")
            industry_insights = self.format_search_results(insights_result, f"{career_name} Industry Insights")

            results1 = {
                "career_name": career_name,
                "research": research,
                "market_analysis": market_analysis,
                "learning_roadmap": learning_roadmap,
                "industry_insights": industry_insights,
                "timestamp": datetime.now().isoformat()
            }
            self.career_data[career_name] = results1
            return results1
        
        elif self.llm:
            career_prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Provide a comprehensive analysis of the {career} career path.
                Include role overview, key responsibilities, required technical and soft skills,
                and educational background or alternative paths into the field.
                Format the response in markdown with clear headings and bullet points.
                """
            )
            market_prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Analyze the current job market for {career} professionals.
                Include information on job growth projections, salary ranges by experience level,
                top industries hiring, geographic hotspots, and emerging trends affecting the field.
                Format the response in markdown with clear headings.
                """
            )
            roadmap_prompt = PromptTemplate(
                input_variables=["career", "experience_level"],
                template="""
                Create a detailed learning roadmap for someone pursuing a {career} career path.
                The person is at a {experience_level} level.
                Include essential skills to develop, specific education requirements, recommended courses and resources,
                and a timeline for skill acquisition. Structure the response with clear sections and markdown formatting.
                """
            )
            insights_prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Provide detailed insider insights about working as a {career} professional.
                Include information on workplace culture, day-to-day activities, career progression paths,
                work-life balance considerations, and success strategies.
                Format the response in markdown with clear headings.
                """
            )
            career_chain = LLMChain(llm=self.llm, prompt=career_prompt)
            market_chain = LLMChain(llm=self.llm, prompt=market_prompt)
            roadmap_chain = LLMChain(llm=self.llm, prompt=roadmap_prompt)
            insights_chain = LLMChain(llm=self.llm, prompt=insights_prompt)
            
            experience_level = "beginner"
            if user_profile and "experience" in user_profile:
                exp = user_profile["experience"]
                if "5-10" in exp or "10+" in exp:
                    experience_level = "advanced"
                elif "3-5" in exp:
                    experience_level = "intermediate"
            
            research = career_chain.run(career=career_name)
            market_analysis = market_chain.run(career=career_name)
            learning_roadmap = roadmap_chain.run(career=career_name, experience_level=experience_level)
            industry_insights = insights_chain.run(career=career_name)
            
            results2 = {
                "career_name": career_name,
                "research": research,
                "market_analysis": market_analysis,
                "learning_roadmap": learning_roadmap,
                "industry_insights": industry_insights,
                "timestamp": datetime.now().isoformat()
            }
            self.career_data[career_name] = results2
            return results2
        
        return {
            "career_name": career_name,
            "research": f"Career analysis for {career_name} unavailable. Please provide API keys.",
            "market_analysis": "Market analysis unavailable. Please provide API keys.",
            "learning_roadmap": "Learning roadmap unavailable. Please provide API keys.",
            "industry_insights": "Industry insights unavailable. Please provide API keys."
        }

    def chat_with_assistant(self, question, career_data=None):
        """Engage in conversation about career questions"""
        if not self.llm:
            return "Career assistant is not available. Please provide a Groq API key."
        
        try:
            context = ""
            if career_data and isinstance(career_data, dict):
                career_name = career_data.get("career_name", "the selected career")
                context = f"The user has selected the {career_name} career path. "
                
                if any(kw in question.lower() for kw in ["skill", "learn", "study", "education", "degree"]):
                    context += f"Here's information about the career: {career_data.get('research', '')} "
                    context += f"Here's learning roadmap information: {career_data.get('learning_roadmap', '')} "
                
                if any(kw in question.lower() for kw in ["market", "job", "salary", "pay", "demand", "trend"]):
                    context += f"Here's market analysis information: {career_data.get('market_analysis', '')} "
                
                if any(kw in question.lower() for kw in ["work", "day", "culture", "balance", "advance"]):
                    context += f"Here's industry insights information: {career_data.get('industry_insights', '')} "
            
            prompt = PromptTemplate(
                input_variables=["context", "question"],
                template="""
                You are a career guidance assistant helping a user with their career questions.
                
                Context about the user's selected career:
                {context}
                
                User question: {question}
                
                Provide a helpful, informative response that directly addresses the user's question.
                Be conversational but concise. Include specific advice or information when possible.
                Format your response in markdown with bullet points and headings where appropriate.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            response = chain.run(context=context, question=question)
            return response
        
        except Exception as e:
            return f"I encountered an error while processing your question: {str(e)}"

# Initialize session state
# if 'career_system' not @staticmethod
# ...existing code...
# Initialize session state
if 'career_system' not in st.session_state:
    st.session_state.career_system = None

def generate_uuid():
    return str(uuid.uuid4())

# Initialize session state
if 'career_system' not in st.session_state:
    st.session_state.career_system = None
if 'career_data' not in st.session_state:
    st.session_state.career_data = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Main Streamlit UI
def main():
    st.title("Career Guidance System")
    st.markdown("Explore career paths, get market insights, and create personalized learning roadmaps.")

    # Sidebar for API keys and user profile
    with st.sidebar:
        st.header("Configuration")
        groq_api_key = st.text_input("Groq API Key", type="password")
        serpapi_key = st.text_input("SerpAPI Key", type="password")
        
        if st.button("Initialize System"):
            st.session_state.career_system = CareerGuidanceSystem(groq_api_key, serpapi_key)
            st.success("System initialized!")

        st.header("User Profile")
        education = st.selectbox("Education Level", ["High School", "Bachelor's", "Master's", "PhD", "Other"])
        experience = st.selectbox("Experience Level", ["0-2 years", "3-5 years", "5-10 years", "10+ years"])
        skills = st.text_area("Skills (comma-separated)")
        if st.button("Save Profile"):
            st.session_state.career_system.user_profile = {
                "education": education,
                "experience": experience,
                "skills": {skill.strip(): 5 for skill in skills.split(",") if skill.strip()}
            }
            st.success("Profile saved!")

    # Main content
    if st.session_state.career_system:
        career_system = st.session_state.career_system
        
        # Career selection
        st.header("Select a Career")
        career_categories = career_system.get_career_options()
        category = st.selectbox("Career Category", list(career_categories.keys()))
        career = st.selectbox("Specific Career", career_categories[category])
        
        if st.button("Analyze Career"):
            with st.spinner("Analyzing career..."):
                st.session_state.career_data = career_system.comprehensive_career_analysis(
                    career, career_system.user_profile
                )
        
        # Display career analysis
        if st.session_state.career_data:
            tabs = st.tabs(["Overview", "Market Analysis", "Learning Roadmap", "Industry Insights"])
            
            with tabs[0]:
                st.markdown(st.session_state.career_data["research"])
            
            with tabs[1]:
                st.markdown(st.session_state.career_data["market_analysis"])
            
            with tabs[2]:
                st.markdown(st.session_state.career_data["learning_roadmap"])
            
            with tabs[3]:
                st.markdown(st.session_state.career_data["industry_insights"])
        
        # Chat interface
        st.header("Career Advisor Chat")
        user_query = st.text_input("Ask a career question:")
        if st.button("Submit Question"):
            if user_query:
                response = career_system.chat_with_assistant(user_query, st.session_state.career_data)
                st.session_state.chat_history.append({"question": user_query, "response": response})
        
        # Display chat history
        for chat in st.session_state.chat_history:
            st.markdown(f"**Q: {chat['question']}**")
            st.markdown(chat['response'])
    else:
        st.warning("Please initialize the system with API keys.")

if __name__ == "__main__":
    main()