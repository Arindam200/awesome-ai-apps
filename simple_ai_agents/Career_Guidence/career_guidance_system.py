from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.agents import load_tools, initialize_agent, AgentType
from langchain_community.utilities import SerpAPIWrapper
from datetime import datetime
from langchain_groq import ChatGroq

import os
import time

class CareerGuidanceSystem:
    def __init__(self, groq_api_key=None, serpapi_key=None):
        """Initialize the career guidance system"""
        self.groq_api_key = groq_api_key
        self.serpapi_key = serpapi_key
        
        # Set environment variable for GroqAI API key
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
        
        # Set environment variable for SerpAPI key
        if serpapi_key:
            os.environ["SERPER_API_KEY"] = serpapi_key
        
        # Initialize the language model
        if groq_api_key:
            self.llm = ChatGroq(
                model='gemma2-9b-it',
                groq_api_key=groq_api_key,
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
                    handle_parsing_errors=True,  # Add error handling
                    max_iterations=6  # Limit number of iterations to prevent loops
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
        
        # Small set of fallback data for common careers if search fails
        self.fallback_career_options = {
            "Technology": [
                "Software Engineering", 
                "Data Science", 
                "Cybersecurity", 
                "AI/ML Engineering", 
                "DevOps",
                "Cloud Architecture",
                "Mobile Development",
                "Web Development",
                "Game Development",
                "Blockchain Development",
                "MLOPS",
                "DEVOPS"
            ],
            "Healthcare": [
                "Medicine", 
                "Nursing", 
                "Pharmacy", 
                "Biomedical Engineering",
                "Healthcare Administration",
                "Physical Therapy",
                "MBBS",
                "BHMS",
                "BAMS",
                "BDS",
            ],
            "Business": [
                "Finance", 
                "Marketing", 
                "Management", 
                "Human Resources",
                "Entrepreneurship",
                "Business Analysis",
                "CA",
                "CMA",
                "CS",
                "Stock Broker"
            ],
            "Creative": [
                "Graphic Design", 
                "UX/UI Design", 
                "Content Creation", 
                "Digital Marketing",
                "Animation",
                "Film Production"
                ,"Photography",
                "Fashion Design",
                "musician"
            ]
        }
    
    def search_with_cache(self, query, cache_key, ttl_hours=24, max_retries=3):
        """Perform a search with caching to avoid redundant API calls"""
        # Check if we have cached results that aren't expired
        if cache_key in self.search_cache:
            timestamp = self.search_cache[cache_key]['timestamp']
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            if age_hours < ttl_hours:
                return self.search_cache[cache_key]['data']
        
        # If not cached or expired, perform the search
        if self.search_agent:
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    result = self.search_agent.run(query)
                    
                    # Cache the result with timestamp
                    self.search_cache[cache_key] = {
                        'data': result,
                        'timestamp': datetime.now()
                    }
                    
                    # Add a small delay to prevent rate limiting
                    time.sleep(1)
                    
                    return result
                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    time.sleep(2)  # Wait before retrying
            
            # If all retries failed, fall back to direct LLM query without agent
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
                
                # Cache this result as well
                self.search_cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }
                
                return result
            except:
                return f"Search failed after {max_retries} attempts. Last error: {last_error}"
        else:
            return "Search unavailable. Please provide a SerpAPI key for web search capabilities."
    
    def format_search_results(self, results, title):
        """Format search results into a well-structured markdown document"""
        formatted = f"# {title}\n\n"
        
        # Clean up and format the results
        if isinstance(results, str):
            # Remove any warnings or errors from the output
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
        # Use fallback options if no search available
        return self.fallback_career_options
    
    def comprehensive_career_analysis(self, career_name, user_profile=None):
        """Run a comprehensive analysis of a career using web search"""
        try:
            # Check if we already have this analysis cached
            if career_name in self.career_data:
                return self.career_data[career_name]
            
            # If we have search capabilities, use them to get real-time information
            if self.search_agent and self.serpapi_key:
                # Perform searches for each aspect of the career
                
                # 1. Career Overview and Skills - use more structured query
                overview_query = (
                    f"Create a detailed overview of the {career_name} career with the following structure:\n"
                    f"1. Role Overview: What do {career_name} professionals do?\n"
                    f"2. Key Responsibilities: List the main tasks and responsibilities\n"
                    f"3. Required Technical Skills: List the technical skills needed\n"
                    f"4. Required Soft Skills: List the soft skills needed\n"
                    f"5. Educational Background: What education is typically required?"
                )
                overview_result = self.search_with_cache(
                    overview_query,
                    f"{career_name}_overview"
                )
                research = self.format_search_results(overview_result, f"{career_name} Career Analysis")
                
                # 2. Market Analysis - use more structured query
                market_query = (
                    f"Analyze the job market for {career_name} professionals with the following structure:\n"
                    f"1. Job Growth Projections: How is job growth trending?\n"
                    f"2. Salary Ranges: What are salary ranges by experience level?\n"
                    f"3. Top Industries: Which industries hire the most {career_name} professionals?\n"
                    f"4. Geographic Hotspots: Which locations have the most opportunities?\n"
                    f"5. Emerging Trends: What new trends are affecting this field?"
                )
                market_result = self.search_with_cache(
                    market_query,
                    f"{career_name}_market"
                )
                market_analysis = self.format_search_results(market_result, f"{career_name} Market Analysis")
                
                # 3. Learning Roadmap
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
                roadmap_result = self.search_with_cache(
                    roadmap_query,
                    f"{career_name}_roadmap_{experience_level}"
                )
                learning_roadmap = self.format_search_results(roadmap_result, f"{career_name} Learning Roadmap")
                
                # 4. Industry Insights
                insights_query = (
                    f"Provide industry insights for {career_name} professionals with this structure:\n"
                    f"1. Workplace Culture: What is the typical work environment like?\n"
                    f"2. Day-to-Day Activities: What does a typical workday include?\n"
                    f"3. Career Progression: What career advancement paths exist?\n"
                    f"4. Work-Life Balance: How is the work-life balance in this field?\n"
                    f"5. Success Strategies: What tips help professionals succeed in this field?"
                )
                insights_result = self.search_with_cache(
                    insights_query,
                    f"{career_name}_insights"
                )
                industry_insights = self.format_search_results(insights_result, f"{career_name} Industry Insights")
                
                # Create the combined result
                results = {
                    "career_name": career_name,
                    "research": research,
                    "market_analysis": market_analysis,
                    "learning_roadmap": learning_roadmap,
                    "industry_insights": industry_insights,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Cache the results
                self.career_data[career_name] = results
                
                return results
            
            # If no search capabilities, use LLM to generate analysis
            elif self.llm:
                # Use LLM chains for each analysis component
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
                
                # Create chains and run them
                career_chain = LLMChain(llm=self.llm, prompt=career_prompt)
                market_chain = LLMChain(llm=self.llm, prompt=market_prompt)
                roadmap_chain = LLMChain(llm=self.llm, prompt=roadmap_prompt)
                insights_chain = LLMChain(llm=self.llm, prompt=insights_prompt)
                
                # Get experience level from user profile
                experience_level = "beginner"
                if user_profile and "experience" in user_profile:
                    exp = user_profile["experience"]
                    if "5-10" in exp or "10+" in exp:
                        experience_level = "advanced"
                    elif "3-5" in exp:
                        experience_level = "intermediate"
                
                # Generate all components
                research = career_chain.run(career=career_name)
                market_analysis = market_chain.run(career=career_name)
                learning_roadmap = roadmap_chain.run(career=career_name, experience_level=experience_level)
                industry_insights = insights_chain.run(career=career_name)
                
                # Create the result dictionary
                results = {
                    "career_name": career_name,
                    "research": research,
                    "market_analysis": market_analysis,
                    "learning_roadmap": learning_roadmap,
                    "industry_insights": industry_insights,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Store in cache
                self.career_data[career_name] = results
                
                return results
            
            # If neither search nor LLM are available
            return {
                "career_name": career_name,
                "research": f"Career analysis for {career_name} unavailable. Please provide API keys for enhanced capabilities.",
                "market_analysis": "Market analysis unavailable. Please provide API keys for enhanced capabilities.",
                "learning_roadmap": "Learning roadmap unavailable. Please provide API keys for enhanced capabilities.",
                "industry_insights": "Industry insights unavailable. Please provide API keys for enhanced capabilities."
            }
            
        except Exception as e:
            # Return error information
            return {
                "career_name": career_name,
                "research": f"Error analyzing career: {str(e)}",
                "market_analysis": "Market analysis not available due to an error",
                "learning_roadmap": "Learning roadmap not available due to an error",
                "industry_insights": "Industry insights not available due to an error"
            }
    
    def search_career_information(self, career):
        """Get basic information about a specific career using search"""
        # Check the cache
        if career in self.career_data and "research" in self.career_data[career]:
            return self.career_data[career]["research"]
        
        # Use search agent if available
        if self.search_agent:
            query = f"What are the key responsibilities, required skills, and education for a {career} career?"
            result = self.search_with_cache(
                query,
                f"{career}_info"
            )
            formatted = self.format_search_results(result, f"{career} Career Information")
            return formatted
        
        # Use LLM if available but no search
        elif self.llm:
            prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Provide information about the {career} career path.
                Include role description, key responsibilities, required skills, 
                and typical educational requirements.
                Format as markdown with clear sections.
                """
            )
            chain = LLMChain(llm=self.llm, prompt=prompt)
            return chain.run(career=career)
        
        # Fallback to generic response
        return f"{career} is a career field that requires specialized skills and education. Enable web search for detailed information."
    
    def analyze_market_trends(self, career):
        """Analyze market trends for a specific career using search"""
        # Check the cache
        if career in self.career_data and "market_analysis" in self.career_data[career]:
            return self.career_data[career]["market_analysis"]
        
        # Use search agent if available
        if self.search_agent:
            query = f"What are the current job market trends, salary ranges, and growth projections for {career} careers?"
            result = self.search_with_cache(
                query,
                f"{career}_market"
            )
            formatted = self.format_search_results(result, f"{career} Market Analysis")
            return formatted
        
        # Use LLM if available but no search
        elif self.llm:
            prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Analyze the current job market for {career} professionals.
                Include information on job growth projections, salary ranges by experience level,
                top industries hiring, geographic hotspots, and emerging trends affecting the field.
                Format the response in markdown with clear headings.
                """
            )
            chain = LLMChain(llm=self.llm, prompt=prompt)
            return chain.run(career=career)
        
        # Fallback to generic response
        return f"Market analysis for {career} requires web search capabilities. Please provide a SerpAPI key."
    
    def create_learning_roadmap(self, career, experience_level="beginner"):
        """Create a learning roadmap for a specific career"""
        # Check the cache
        if career in self.career_data and "learning_roadmap" in self.career_data[career]:
            return self.career_data[career]["learning_roadmap"]
        
        # Use search agent if available
        if self.search_agent:
            query = f"How to become a {career} professional for someone at {experience_level} level? Include skills to develop, education requirements, courses, resources, and timeline"
            result = self.search_with_cache(
                query,
                f"{career}_roadmap_{experience_level}"
            )
            formatted = self.format_search_results(result, f"{career} Learning Roadmap")
            return formatted
        
        # Use LLM if available but no search
        elif self.llm:
            prompt = PromptTemplate(
                input_variables=["career", "experience_level"],
                template="""
                Create a detailed learning roadmap for someone pursuing a {career} career path.
                The person is at a {experience_level} level.
                Include essential skills to develop, specific education requirements, recommended courses and resources,
                and a timeline for skill acquisition. Structure the response with clear sections and markdown formatting.
                """
            )
            chain = LLMChain(llm=self.llm, prompt=prompt)
            return chain.run(career=career, experience_level=experience_level)
        
        # Fallback to generic response
        return f"A personalized learning roadmap for {career} requires web search capabilities. Please provide a SerpAPI key."
    
    def get_career_insights(self, career):
        """Get industry insights for a specific career"""
        # Check the cache
        if career in self.career_data and "industry_insights" in self.career_data[career]:
            return self.career_data[career]["industry_insights"]
        
        # Use search agent if available
        if self.search_agent:
            query = f"What is the workplace culture, day-to-day activities, career progression, and work-life balance like for {career} professionals?"
            result = self.search_with_cache(
                query,
                f"{career}_insights"
            )
            formatted = self.format_search_results(result, f"{career} Industry Insights")
            return formatted
        
        # Use LLM if available but no search
        elif self.llm:
            prompt = PromptTemplate(
                input_variables=["career"],
                template="""
                Provide detailed insider insights about working as a {career} professional.
                Include information on workplace culture, day-to-day activities, career progression paths,
                work-life balance considerations, and success strategies.
                Format the response in markdown with clear headings.
                """
            )
            chain = LLMChain(llm=self.llm, prompt=prompt)
            return chain.run(career=career)
        
        # Fallback to generic response
        return f"Industry insights for {career} require web search capabilities. Please provide a SerpAPI key."
    
    def chat_with_assistant(self, question, career_data=None):
        """Engage in conversation with a user about career questions"""
        if not self.llm:
            return "Career assistant is not available. Please provide an GROQ API key."
        
        try:
            # Create context from career data if available
            context = ""
            if career_data and isinstance(career_data, dict):
                career_name = career_data.get("career_name", "the selected career")
                context = f"The user has selected the {career_name} career path. "
                
                # Add relevant sections from career data based on question keywords
                if any(kw in question.lower() for kw in ["skill", "learn", "study", "education", "degree"]):
                    context += f"Here's information about the career: {career_data.get('research', '')} "
                    context += f"Here's learning roadmap information: {career_data.get('learning_roadmap', '')} "
                
                if any(kw in question.lower() for kw in ["market", "job", "salary", "pay", "demand", "trend"]):
                    context += f"Here's market analysis information: {career_data.get('market_analysis', '')} "
                
                if any(kw in question.lower() for kw in ["work", "day", "culture", "balance", "advance"]):
                    context += f"Here's industry insights information: {career_data.get('industry_insights', '')} "
            
            # Create prompt for the career assistant
            prompt = PromptTemplate(
                input_variables=["context", "question"],
                template="""
                You are a career guidance assistant helping a user with their career questions.
                
                Context about the user's selected career:
                {context}
                
                User question: {question}
                
                Provide a helpful, informative response that directly addresses the user's question.
                Be conversational but concise. Include specific advice or information when possible.
                Format your response in a structured way with bullet points and headings where appropriate.
                If the question is outside your knowledge, acknowledge that and provide general career guidance.
                """
            )
            
            # Generate response
            chain = LLMChain(llm=self.llm, prompt=prompt)
            response = chain.run(context=context, question=question)
            
            return response
        
        except Exception as e:
            return f"I encountered an error while processing your question: {str(e)}"
    
    def chat_response(self, user_query, career_data=None, user_profile=None):
        """
        Generate a response to a user's chat query about a career.
        
        Parameters:
        - user_query: The user's question or message
        - career_data: Dictionary containing career analysis information
        - user_profile: User profile information
        
        Returns:
        - Formatted HTML string with the response
        """
        try:
            # Extract career name if available
            career_name = career_data.get("career_name", "this career") if career_data else "this career"
            
            # Prepare system prompt with available career data
            system_prompt = f"""You are an expert career advisor specializing in {career_name}. 
            Answer the user's questions based on the following career data and your knowledge.
            Always format your responses with HTML styling - use appropriate headings, lists, 
            paragraphs, and emphasis to make your response visually appealing and structured.
            Always return formatted HTML content, not Markdown.
            """
            
            # Add career data to the prompt if available
            if career_data:
                # Add each section of career data we have
                for key, value in career_data.items():
                    if key != "career_name" and value:
                        section_name = key.replace("_", " ").title()
                        system_prompt += f"\n\n{section_name}:\n{value}"
            
            # Add user profile if available
            if user_profile:
                profile_text = f"The user has {user_profile.get('education', 'some education')} with "
                profile_text += f"{user_profile.get('experience', 'some')} experience. "
                
                # Add skills if available
                if "skills" in user_profile:
                    profile_text += "Their skill levels (out of 10) are: "
                    skills = user_profile["skills"]
                    for skill, level in skills.items():
                        profile_text += f"{skill}: {level}, "
                    profile_text = profile_text.rstrip(", ")
                
                system_prompt += f"\n\nUser Profile:\n{profile_text}"
            
            # Get response from LLM using API
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ]
            )
            
            answer = response.content
            
            # Ensure the response is properly formatted as HTML
            if "<" not in answer:
                # If no HTML tags are present, add basic formatting
                answer = f"<div><p>{answer}</p></div>"
            
            return answer
            
        except Exception as e:
            return f"""
            <div style="color: #FF5252;">
                <p>I'm sorry, but I encountered an error while processing your request:</p>
                <p><code>{str(e)}</code></p>
                <p>Please try again or contact support if the issue persists.</p>
            </div>
            """