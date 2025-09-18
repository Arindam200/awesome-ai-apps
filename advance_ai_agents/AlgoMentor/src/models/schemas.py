from pydantic import BaseModel, Field
from typing import List, Optional

class LeetCodeProblem(BaseModel):
    """Model for LeetCode problem structure"""
    user_input: str
    constraints: str
    examples: List[str]
    problem_statement: str = Field(description="the problem statement")
    basic_approach: str = Field(description="the approach to solve the problem")
    basic_algorithm: str = Field(description="the algorithm to solve the problem")
    basic_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    basic_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    basic_code: str = Field(description="the code to solve the problem")


class CodeVerifyInput(BaseModel):
    code:str=Field(description="The python code that needs to be verified")
    test_cases:List[str]=Field(description="The test cases for the code that needs to be verified")
    final_debuged_suboptimized_code:str=Field(description="The final debuged suboptimized code that verified")
    time_complexity:str=Field(description="The time complexity of the code ")
    space_complexity:str=Field(description="The space complexity of the code ")
    libraries: str=Field(description="The libraries used in the code")



class BruteForceApproach(BaseModel):
    """Model for brute force approach"""
    problem_statement: str = Field(description="the problem statement")
    basic_approach: str = Field(description="the basic or bruteforce approach to solve the problem")
    basic_algorithm: str = Field(description="the basic or bruteforce algorithm to solve the problem")
    basic_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    basic_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    code: str = Field(description="the code to solve the problem")
    updated_code: str = Field(description="the updated and working code to solve the problem")

class SubOptimalApproach(BaseModel):
    """Model for sub-optimal approach"""
    problem_statement: str = Field(description="the problem statement")
    basic_approach: str = Field(description="the approach to solve the problem")
    basic_algorithm: str = Field(description="the algorithm to solve the problem")
    basic_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    basic_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    basic_code: str = Field(description="the code to solve the problem")
    suboptimal_approach: str = Field(description="the optimized approach to solve the problem")
    suboptimal_algorithm: str = Field(description="the optimized algorithm to solve the problem")
    suboptimal_time_complexity: str = Field(description="the time complexity of the optimized algorithm")
    suboptimal_space_complexity: str = Field(description="the space complexity of the optimized algorithm")

class SuboptimalCode(BaseModel):
    """Model for sub-optimal code implementation"""
    sub_optimal_algorithm: str = Field(description="the optimized algorithm description")
    sub_optimal_approach: str = Field(description="the optimized approach explanation")
    problem_statement: str = Field(description="the original problem statement")
    basic_approach_code: str = Field(description="the basic/brute-force code")
    sub_optimal_code: str = Field(description="the optimized implementation code")
    time_space_complexity: str = Field(description="the time and space complexity analysis of the optimized code")

class OptimalApproach(BaseModel):
    """Model for optimal approach"""
    optimal_approach: str = Field(description="the most optimal approach")
    optimal_algorithm: str = Field(description="the most optimal algorithm")
    optimal_time_complexity: str = Field(description="optimal time complexity")
    optimal_space_complexity: str = Field(description="optimal space complexity")

class CodeVerification(BaseModel):
    """Model for code verification results"""
    final_debuged_suboptimized_code: str = Field(description="final debugged code")
    time_complexity: str = Field(description="time complexity")
    space_complexity: str = Field(description="space complexity")
    time_space_complexity: str = Field(description="combined time and space complexity")


class Explainer(BaseModel):
    """Structured model for comprehensive code explanation"""
    code: str = Field(description="The original code to explain")
    problem_statement: str = Field(description="Clear restatement of what problem this code solves")
    approach_summary: str = Field(description="High-level algorithm approach and key insights")
    detailed_approach: str = Field(description="Step-by-step breakdown of the solution strategy")
    time_complexity: str = Field(description="Detailed time complexity analysis with explanation")
    space_complexity: str = Field(description="Detailed space complexity analysis with explanation")
    code_walkthrough: str = Field(description="Section-wise code explanation with logic breakdown")
    edge_cases: str = Field(description="Important edge cases and how the code handles them")
    key_concepts: str = Field(description="Important algorithms, data structures, or programming concepts used")


class ExampleExplanation(BaseModel):
    """Structured model for step-by-step example walkthrough"""
    code: str = Field(description="The original code being demonstrated")
    example_input: str = Field(description="The chosen example input with explanation of why it's good")
    step_by_step_trace: str = Field(description="Detailed execution trace showing variable states")
    visual_representation: str = Field(description="ASCII art or visual representation if helpful")
    intermediate_outputs: str = Field(description="Key intermediate results and their significance")
    final_result: str = Field(description="Final output with verification")
    alternative_examples: str = Field(description="Brief mention of other test cases and their outcomes")


class TeamOutput(BaseModel):
    code: str = Field(description="The original code to explain")
    problem_statement: str = Field(description="Clear restatement of what problem this code solves")
    approach_summary: str = Field(description="High-level algorithm approach and key insights")
    detailed_approach: str = Field(description="Step-by-step breakdown of the solution strategy")
    time_complexity: str = Field(description="Detailed time complexity analysis with explanation")
    space_complexity: str = Field(description="Detailed space complexity analysis with explanation")
    code_walkthrough: str = Field(description="Section-wise code explanation with logic breakdown")
    edge_cases: str = Field(description="Important edge cases and how the code handles them")
    key_concepts: str = Field(description="Important algorithms, data structures, or programming concepts used")
    example_input: str = Field(description="The chosen example input with explanation of why it's good")
    step_by_step_trace: str = Field(description="Detailed execution trace showing variable states")
    visual_representation: str = Field(description="ASCII art or visual representation if helpful")
    intermediate_outputs: str = Field(description="Key intermediate results and their significance")
    final_result: str = Field(description="Final output with verification")


class OptimalApproach(BaseModel):
    problem_statement: str =Field(description="the problem statement")
    suboptimal_approach: str =Field(description="the approach to solve the problem")
    suboptimal_algorithm: str =Field(description="the algorithm to solve the problem")
    suboptimal_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    suboptimal_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    optimal_approach: str =Field(description="the most optimal approach to solve the problem")
    optimal_algorithm: str =Field(description="the most optimal algorithm to solve the problem")
    optimal_time_complexity: str = Field(description="the time complexity of the code")
    optimal_space_complexity: str = Field(description="the space complexity of the code")


class OptimalCode(BaseModel):
    problem_statement: str =Field(description="the problem statement")
    optimal_approach: str =Field(description="the approach to solve the problem")
    optimal_algorithm: str =Field(description="the algorithm to solve the problem")
    optimal_time_space_complexity: str = Field(description="the time and space complexity of the code")
    optimal_code: str = Field(description="the most optimal code to solve the problem")

class LeetCode(BaseModel):
    user_input:str
    constraints:str
    examples:List[str]
    problem_statement: str =Field(description="the problem statement")
    basic_approach: str =Field(description="the approach to solve the problem")
    basic_algorithm: str =Field(description="the algorithm to solve the problem")
    basic_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    basic_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    basic_code: str = Field(description="the code to solve the problem")
    
class QuestionFinderInput(BaseModel):
    user_input:str
    problem_statement:str
    difficulty:str
    examples:List[str]
    explanations:List[str]
    constraints:List[str]


class SubOptimalApproach(BaseModel):
    problem_statement: str = Field(description="the problem statement")
    basic_approach: str = Field(description="the approach to solve the problem")
    basic_algorithm: str = Field(description="the algorithm to solve the problem")
    basic_time_complexity: str = Field(description="the time complexity of the algorithm or code")
    basic_space_complexity: str = Field(description="the space complexity of the algorithm or code")
    basic_code: str = Field(description="the code to solve the problem")
    suboptimal_approach: str = Field(description="the optimized approach to solve the problem")
    suboptimal_algorithm: str = Field(description="the optimized algorithm to solve the problem")
    suboptimal_time_complexity: str = Field(description="the time complexity of the optimized algorithm")
    suboptimal_space_complexity: str = Field(description="the space complexity of the optimized algorithm")

class SuboptimalCode(BaseModel):
    sub_optimal_algorithm: str = Field(description="the optimized algorithm description")
    sub_optimal_approach: str = Field(description="the optimized approach explanation")
    problem_statement: str = Field(description="the original problem statement")
    basic_approach_code: str = Field(description="the basic/brute-force code")
    sub_optimal_code: str = Field(description="the optimized implementation code")
    time_space_complexity: str = Field(description="the time and space complexity analysis of the optimized code")
