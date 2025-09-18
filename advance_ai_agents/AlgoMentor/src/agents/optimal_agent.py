from agno.agent import Agent
from ..models.schemas import OptimalApproach,OptimalCode
from agno.models.groq import Groq
from agno.tools.python import PythonTools
import streamlit as st
from agno.models.google import Gemini
import os
from dotenv import load_dotenv
load_dotenv()

# googel_api_key=os.getenv('GOOGLE_API_KEY')
# groq_api_key=os.getenv('GROQ_API_KEY')
groq_api_key=st.secrets['GROQ_API_KEY']
google_api_key=st.secrets['GOOGLE_API_KEY']

optimal_code_agent=Agent(
    name="optimal code writter",
    model=Gemini(id='gemini-2.0-flash',api_key=google_api_key),
    tools=[PythonTools()],
    description="You are an expert competitive programming and algorithms agent specializing in writing optimal solutions.",
    instructions=[
        "You will receive json object that contain the following information from the user:",
        "1. Problem statement",
        "2. Optimal approach",
        "3. Optimal algorithm",
        "4. Optimal time and space complexity",

        "Your tasks are:",
         "- Carefully analyze the problem statement and the provided approaches.(sub_optimal_approach)",
        "- Identify inefficiencies or limitations in the given code and suboptimal algorithm.",
        "- Propose a more optimized code based on the algorithm with improved time and/or space complexity.",
        "- Explain why your optimized solution is better.",
        "- Provide the final Python code implementation of the optimized approach, ensuring it is clean, modular, and efficient.",
        "- Clearly state the optimized solution's time and space complexity."
    ],
    show_tool_calls=True,
    add_datetime_to_instructions=True,
    response_model=OptimalCode,
    use_json_mode=True
)

# Enhanced optimal_agent with stronger validation requirements
optimal_agent_enhanced=Agent(
    name="Optimal Approach Agent Enhanced",
    model=Groq(id='llama-3.3-70b-versatile', api_key=groq_api_key),
    description="Expert algorithm optimization specialist that transforms suboptimal solutions into mathematically optimal approaches with superior complexity.",
    instructions=[
        " MISSION: Transform suboptimal approaches into fundamentally different, mathematically optimal solutions.",
        "",
        " INPUT ANALYSIS:",
        "You will receive:",
        "1. Problem statement",
        "2. Suboptimal approach (inefficient method)",
        "3. Suboptimal algorithm (step-by-step inefficient process)",
        "4. Suboptimal time complexity (higher complexity)",
        "5. Suboptimal space complexity (potentially wasteful)",
        "",
        " OPTIMIZATION REQUIREMENTS:",
        "- The optimal approach MUST be fundamentally different from the suboptimal one",
        "- Target complexities: O(n) time, O(1) or O(n) space when possible",
        "- For Dynamic Programming: aim for O(n) time, O(1) space using space optimization techniques",
        "- For sorting problems: consider O(n log n) → O(n) improvements using counting/bucket sort",
        "- For search problems: consider O(n²) → O(n) using hash maps/sets",
        "- For graph problems: optimize using advanced algorithms (Dijkstra, Floyd-Warshall, etc.)",
        "",
        " ANALYSIS PROCESS:",
        "1. Identify the core inefficiency in the suboptimal approach",
        "2. Research mathematical properties or patterns that can be exploited",
        "3. Apply advanced data structures (hash maps, heaps, tries, segment trees)",
        "4. Use algorithmic techniques (two pointers, sliding window, divide & conquer, DP)",
        "5. Eliminate redundant computations through memoization or mathematical formulas",
        "",
        " VALIDATION CRITERIA:",
        "- Optimal time complexity MUST be strictly better than suboptimal",
        "- Optimal space complexity should be equal or better than suboptimal",
        "- The approach should use completely different logic/strategy",
        "- Explain WHY the optimal solution is mathematically superior",
        "- Provide concrete complexity comparison (e.g., O(n²) → O(n log n))"
    ],
    add_context=" CRITICAL REQUIREMENT: The optimal approach must be FUNDAMENTALLY DIFFERENT and MATHEMATICALLY SUPERIOR to the suboptimal approach. Never provide the same algorithm with minor tweaks - always find a completely different, more efficient paradigm. The optimal solution must have strictly better time/space complexity and use entirely different algorithmic strategies (e.g., brute force → dynamic programming, nested loops → hash maps, recursion → iterative with stack).",
    show_tool_calls=True,
    add_datetime_to_instructions=True,
    response_model=OptimalApproach,
    use_json_mode=True
)