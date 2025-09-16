from agno.agent import Agent
from ..models.schemas import SubOptimalApproach,SuboptimalCode
from agno.models.groq import Groq
from agno.tools.python import PythonTools
import streamlit as st
from agno.models.google import Gemini
import os
from dotenv import load_dotenv
load_dotenv()

# groq_api_key=os.getenv('GROQ_API_KEY')
# google_api_key=os.getenv('GOOGLE_API_KEY')
groq_api_key=st.secrets['GROQ_API_KEY']
google_api_key=st.secrets['GOOGLE_API_KEY']


suboptimal_agent = Agent(
    name="Algorithm Optimization Specialist",
    model=Groq(id='llama-3.3-70b-versatile', api_key=groq_api_key),
    description="You are an expert in generating moderately improved (sub-optimal) algorithm approaches that enhance brute-force solutions without reaching full optimization.",
    instructions=[
        "🚨 CRITICAL: ALWAYS PROVIDE SUB-OPTIMAL SOLUTIONS ONLY. These must improve on brute-force but leave clear room for further optimization. NEVER provide the most efficient (optimal) approach.",
        
        "ANALYSIS PHASE:",
        "- Carefully analyze the given problem statement, constraints, and examples.",
        "- Identify core inefficiencies in the basic/brute-force approach (e.g., unnecessary nested loops).",
        "- Recognize patterns for moderate improvements, but avoid advanced techniques that would achieve the best possible complexity.",
        
        "SUB-OPTIMIZATION STRATEGY (MODERATE IMPROVEMENTS ONLY):",
        "- Aim for partial efficiency gains: e.g., reduce O(n^3) to O(n^2 log n) or O(n^2), but NOT to O(n log n) or O(n) if better is possible.",
        "- Use basic optimizations like sorting + binary search, simple memoization, or single hash maps, but avoid two-pointers, sliding windows, or space-optimized DP if they lead to optimal.",
        "- For DP problems: Use basic top-down recursion with memoization (O(n^2) time if possible), not bottom-up or O(1) space.",
        "- For search problems: Use sorting + O(n log n) searches, not O(1) hash lookups if that would be optimal.",
        "- Balance: Ensure time/space is better than brute but worse than optimal (e.g., keep O(n) space if O(1) is possible).",
        "- Handle edge cases but do not over-engineer for perfection.",
        
        "VALIDATION CRITERIA (ENFORCE SUB-OPTIMAL):",
        "- Sub-optimal time complexity MUST be strictly better than brute-force but worse than the known optimal (e.g., for 3Sum: brute O(n^3) → sub-optimal O(n^2 log n) with sort + binary search, NOT O(n^2) with two-pointers).",
        "- Sub-optimal space complexity should be improved or equal, but not minimized fully.",
        "- Explain WHY this is sub-optimal: Highlight remaining inefficiencies and potential for better approaches (without describing them).",
        "- Compare complexities: e.g., 'Brute: O(n^3), Sub-optimal: O(n^2 log n), leaving room for O(n^2) optimal'.",
        
        "EXAMPLES OF SUB-OPTIMAL VS. OPTIMAL:",
        "- Problem: Two Sum. Brute: O(n^2) nested loops. Sub-optimal: Sort + binary search (O(n log n)). Optimal: Hash map (O(n)). Provide only sort + binary search.",
        "- Problem: Fibonacci. Brute: O(2^n) recursion. Sub-optimal: Memoization (O(n) time, O(n) space). Optimal: O(1) space iterative. Provide only memoization.",
        "- Problem: Sorting. Brute: Bubble sort O(n^2). Sub-optimal: Insertion sort O(n^2). Optimal: Quick sort O(n log n). Provide insertion sort.",
        
        "OUTPUT REQUIREMENTS:",
        "- Provide clear, step-by-step sub-optimal algorithmic approach.",
        "- State precise time and space complexity with justification.",
        "- Ensure the approach is implementable, maintains correctness, and is distinctly sub-optimal."
    ],
    add_context="🚨 STRICT ENFORCEMENT: If the generated approach matches known optimal solutions (e.g., from LeetCode standards), reject and regenerate with a less efficient variant. Sub-optimal means 'good but not best'—always leave inefficiencies for the optimal agent to address. Violating this will invalidate the response.",
    show_tool_calls=True,
    add_datetime_to_instructions=True,
    response_model=SubOptimalApproach,
    use_json_mode=True
)




sub_agent = Agent(
    name="Optimized Code Implementation Specialist",
    model=Gemini(id="gemini-2.0-flash", api_key=google_api_key),
    tools=[PythonTools(run_code=True)],
    description="You are an elite competitive programming expert who transforms algorithmic approaches into production-ready, optimized Python implementations.",
    instructions=[
        "INPUT ANALYSIS:",
        "- Parse the JSON input containing: problem statement, basic approach, basic code, and optimized algorithm",
        "- Understand the optimization strategy and why it's more efficient than the basic approach",
        "- Identify key data structures and algorithmic techniques to implement",
        
        "CODE IMPLEMENTATION STANDARDS:",
        "- Write clean, readable Python code following PEP 8 conventions",
        "- Use meaningful variable names and add minimal but essential comments",
        "- Implement proper error handling for edge cases mentioned in constraints",
        "- Optimize for both readability and performance",
        
        "OPTIMIZATION IMPLEMENTATION:",
        "- Faithfully implement the provided optimized algorithm",
        "- Use appropriate Python data structures (dict, set, deque, heapq, etc.)",
        "- Apply Python-specific optimizations (list comprehensions, built-in functions)",
        "- Ensure the implementation handles all edge cases from the problem constraints",
        
        "VALIDATION & TESTING:",
        "- Test the code with provided examples to ensure correctness",
        "- Verify the implementation matches the expected time/space complexity",
        "- Compare performance against the basic approach when possible",
        
        "OUTPUT REQUIREMENTS:",
        "- Provide complete, runnable Python code",
        "- Include complexity analysis with detailed explanation",
        "- Ensure the optimized code is significantly different from the basic approach",
        "- Demonstrate why the optimization provides better performance"
    ],
    show_tool_calls=True,
    response_model=SuboptimalCode
)