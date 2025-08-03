from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.llms.nebius import NebiusLLM
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

def calculate_task_duration(start_time: str, end_time: str) -> str:
    """Calculate the duration between two times in HH:MM format"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        duration = end - start
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        return f"{hours} hours and {minutes} minutes"
    except ValueError:
        return "Invalid time format. Please use HH:MM format."

def estimate_task_completion(tasks: int, time_per_task: int) -> str:
    """Estimate total time needed to complete a number of tasks"""
    total_minutes = tasks * time_per_task
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours} hours and {minutes} minutes"

def calculate_productivity(tasks_completed: int, total_time: int) -> str:
    """Calculate tasks completed per hour
    Args:
        tasks_completed: Number of tasks completed
        total_time: Total time in minutes
    Returns:
        String showing tasks per hour
    """
    if total_time <= 0:
        return "Cannot calculate productivity with zero or negative time"
    if tasks_completed < 0:
        return "Cannot calculate productivity with negative tasks"
    
    # Convert total_time to hours for the calculation
    hours = total_time / 60
    tasks_per_hour = tasks_completed / hours
    return f"{tasks_per_hour:.2f} tasks per hour"

# Create tools
duration_tool = FunctionTool.from_defaults(fn=calculate_task_duration)
estimate_tool = FunctionTool.from_defaults(fn=estimate_task_completion)
productivity_tool = FunctionTool.from_defaults(fn=calculate_productivity)

# Create the agent
agent = ReActAgent.from_tools(
    [duration_tool, estimate_tool, productivity_tool],
    llm=NebiusLLM(
        model="Qwen/Qwen3-235B-A22B",
        api_key=os.getenv("NEBIUS_API_KEY")
    ),
    verbose=True,
)

# Example usage
print("\nTask Management Assistant")
print("------------------------")

response = agent.chat("If I worked from 09:00 to 17:00 and completed 8 tasks, what was my productivity rate?")
print("\nResponse:", response)

# Add a more complex example
# response = agent.chat("If I have 3 tasks that each take 45 minutes, how long will it take to complete them all?")
# print("\nResponse:", response)