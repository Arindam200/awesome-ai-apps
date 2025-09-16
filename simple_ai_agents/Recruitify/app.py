import patch_sqlite
import streamlit as st
import asyncio
import nest_asyncio
from interview import Interview
nest_asyncio.apply()

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
    
# This MUST be the first Streamlit command
st.set_page_config(
    page_title="Recruitify",
    page_icon="🚀",
    layout="wide"
)

import ui
from agents import ResumeAnalysisAgent
import atexit



# # Role requirements dictionary

ROLE_REQUIREMENTS = {
    "AI/ML Engineer": [
        "Python", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow",
        "MLOps", "Scikit-Learn", "NLP", "Computer Vision", "Reinforcement Learning",
        "Hugging Face", "Data Engineering", "Feature Engineering", "AutoML"
    ],
    "Frontend Engineer": [
        "JavaScript", "TypeScript", "React", "Vue", "Angular",
        "HTML5", "CSS3", "Next.js", "Svelte", "Tailwind CSS",
        "GraphQL", "Redux", "WebAssembly", "Three.js", "Performance Optimization"
    ],
    "Backend Engineer": [
        "Python or Java or Node.js", "REST APIs", "Cloud Services",
        "Kubernetes", "Docker", "GraphQL", "Microservices", "gRPC",
        "Spring Boot or Flask or FastAPI", "SQL & NoSQL Databases",
        "Redis", "RabbitMQ", "CI/CD"
    ],
    "Data Engineer": [
        "Python or Scala", "SQL", "Apache Spark", "Hadoop", "Kafka",
        "ETL Pipelines", "Airflow", "BigQuery", "Redshift", "Data Warehousing",
        "Snowflake", "Azure Data Factory", "GCP", "AWS Glue", "DBT"
    ],
    "DevOps Engineer": [
        "Kubernetes", "Docker", "Terraform", "CI/CD", "AWS or Azure or GCP",
        "Jenkins", "Ansible", "Prometheus", "Grafana", "Helm",
        "Linux Administration", "Networking", "Site Reliability Engineering (SRE)"
    ],
    "Full Stack Developer": [
        "JavaScript or TypeScript", "React", "Node.js", "Express",
        "MongoDB", "SQL", "RESTful APIs", "Git", "CI/CD",
        "Cloud Services", "Responsive Design", "Authentication & Authorization"
    ],
    "Product Manager": [
        "Product Strategy", "User Research", "Agile Methodologies", "Roadmapping",
        "Market Analysis", "Stakeholder Management", "Data Analysis", "User Stories",
        "Product Lifecycle", "A/B Testing", "KPI Definition", "Prioritization",
        "Competitive Analysis", "Customer Journey Mapping"
    ],
    "Data Scientist": [
        "Python or R", "SQL", "Machine Learning", "Statistics",
        "Data Visualization", "Pandas", "NumPy", "Scikit-learn",
        "Jupyter", "Hypothesis Testing", "Feature Engineering", "Model Evaluation"
    ]
}


# Initialize session state variables
if 'resume_agent' not in st.session_state:
    st.session_state.resume_agent = None

if 'resume_analyzed' not in st.session_state:
    st.session_state.resume_analyzed = False

if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None


# Important part to check
def setup_agent(config):
    """Set up the resume analysis agent with the provided configuration"""
    if not config["google_api_key"]:
        st.error("⚠️ Please enter your Google API Key in the sidebar.")
        return None

    # Initialize or update the agent with the API key
    if st.session_state.resume_agent is None:
        st.session_state.resume_agent = ResumeAnalysisAgent(api_key=config["google_api_key"])
    else:
        st.session_state.resume_agent.api_key = config["google_api_key"]

    return st.session_state.resume_agent

def analyze_resume(agent, resume_file, role, custom_jd):
    """Analyze the resume with the agent"""
    if not resume_file:
        st.error("⚠️ Please upload a resume.")
        return None

    try:
        with st.spinner("🔍 Analyzing resume... This may take a minute."):
            if custom_jd:
                result = agent.analyze_resume(resume_file, custom_jd=custom_jd)
            else:
                result = agent.analyze_resume(resume_file, role_requirements=ROLE_REQUIREMENTS[role])

            st.session_state.resume_analyzed = True
            st.session_state.analysis_result = result
            return result
    except Exception as e:
        st.error(f"⚠️ Error analyzing resume: {e}")
        return None

def ask_question(agent, question):
    """Ask a question about the resume"""
    try:
        with st.spinner("Generating response..."):
            response = agent.ask_question(question)
            return response
    except Exception as e:
        return f"Error: {e}"

def generate_interview_questions(agent, question_types, difficulty, num_questions):
    """Generate interview questions based on the resume"""
    try:
        with st.spinner("Generating personalized interview questions..."):
            questions = agent.generate_interview_questions(question_types, difficulty, num_questions)
            return questions
    except Exception as e:
        st.error(f"⚠️ Error generating questions: {e}")
        return []

def improve_resume(agent, improvement_areas, target_role):
    """Generate resume improvement suggestions"""
    try:
        with st.spinner("Analyzing and generating improvements..."):
            return agent.improve_resume(improvement_areas, target_role)
    except Exception as e:
        st.error(f"⚠️ Error generating improvements: {e}")
        return {}

def get_improved_resume(agent, target_role, highlight_skills):
    """Get an improved version of the resume"""
    try:
        with st.spinner("Creating improved resume..."):
            return agent.get_improved_resume(target_role, highlight_skills)
    except Exception as e:
        st.error(f"⚠️ Error creating improved resume: {e}")
        return "Error generating improved resume."

def cleanup():
    """Clean up resources when the app exits"""
    if st.session_state.resume_agent:
        st.session_state.resume_agent.cleanup()

# Register cleanup function
atexit.register(cleanup)

def main():
    # Setup page UI
    options=st.sidebar.selectbox(
        "Select a option",['Requirement Analyst','Interview Assistant']
    )

    if options=="Requirement Analyst":
        ui.setup_page()
        ui.display_header()

        # Set up sidebar and get configuration
        config = ui.setup_sidebar()

        # Set up the agent
        agent = setup_agent(config)

        # Create tabs for different functionalities
        tabs = ui.create_tabs()
        # Tab 1: Resume Analysis
        with tabs[0]:
            role, custom_jd = ui.role_selection_section(ROLE_REQUIREMENTS)
            uploaded_resume = ui.resume_upload_section()

            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("🔍 Analyze Resume", type="primary"):
                    if agent and uploaded_resume:
                        # Just store the result, don't display it here
                        analyze_resume(agent, uploaded_resume, role, custom_jd)
                        
            # Display analysis result (only once)
            if st.session_state.analysis_result:
                ui.display_analysis_results(st.session_state.analysis_result)

        # Tab 2: Resume Q&A
        with tabs[1]:
            # We need to ensure the agent and resume are available
            if st.session_state.resume_analyzed and st.session_state.resume_agent:
                ui.resume_qa_section(
                    has_resume=True,  # Explicitly set to True since we checked above
                    ask_question_func=lambda q: ask_question(st.session_state.resume_agent, q)
                )
            else:
                st.warning("Please upload and analyze a resume first in the 'Resume Analysis' tab.")

        # Tab 3: Interview Questions
        with tabs[2]:
            # We need to ensure the agent and resume are available
            if st.session_state.resume_analyzed and st.session_state.resume_agent:
                ui.interview_questions_section(
                    has_resume=True,  # Explicitly set to True since we checked above
                    generate_questions_func=lambda types, diff, num: generate_interview_questions(st.session_state.resume_agent, types, diff, num)
                )
            else:
                st.warning("Please upload and analyze a resume first in the 'Resume Analysis' tab.")

        # Tab 4: Resume Improvement
        with tabs[3]:
            if st.session_state.resume_analyzed and st.session_state.resume_agent:
                ui.resume_improvement_section(
                    has_resume=True,
                    improve_resume_func=lambda areas, role: improve_resume(st.session_state.resume_agent, areas, role)
                )
            else:
                st.warning("Please upload and analyze a resume first in the 'Resume Analysis' tab.")

        # Tab 5: Improved Resume
        with tabs[4]:
            if st.session_state.resume_analyzed and st.session_state.resume_agent:
                ui.improved_resume_section(
                    has_resume=True,
                    get_improved_resume_func=lambda role, skills: get_improved_resume(st.session_state.resume_agent, role, skills)
                )
            else:
                st.warning("Please upload and analyze a resume first in the 'Resume Analysis' tab.")
 
    else:
        with st.sidebar:
            groq_api_key=st.text_input("Enter your Groq Api Kyey Here",type='password')
            deepgram_api_key=st.text_input("Enter your Deepgram Api Key Here",type='password')
            if not groq_api_key:
                if not deepgram_api_key:
                    st.warning("please Enter your Groq  api key !")
                st.warning("please Enter your Groq And Deepgram api key !")

        # st.title("AI Interview Assistant")
        if groq_api_key and deepgram_api_key:
            interviewAssistant=Interview(groq_api_key,deepgram_api_key)
            interviewAssistant.run()


if __name__ == "__main__":
    main()