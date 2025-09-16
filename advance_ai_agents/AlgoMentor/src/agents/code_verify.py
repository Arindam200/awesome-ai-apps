import os
from dotenv import load_dotenv
load_dotenv()
from agno.agent import Agent
from agno.tools.python import PythonTools
from agno.models.groq import Groq
from agno.models.google import Gemini
from ..models.schemas import CodeVerifyInput
import streamlit as st
import atexit
import shutil
import tempfile

# Create a temporary directory
temp_dir = tempfile.mkdtemp()

# Register cleanup function to delete temp directory on exit
def cleanup_temp_dir():
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

atexit.register(cleanup_temp_dir)


groq_api_key=st.secrets['GROQ_API_KEY']
google_api_key=st.secrets['GOOGLE_API_KEY']

# groq_api_key=os.getenv('GROQ_API_KEY')
# google_api_key=os.getenv('GOOGLE_API_KEY')


code_runner = Agent(
    name="Optimized Code Executor",
    model=Gemini(id='gemini-2.0-flash', api_key=google_api_key),
    tools=[PythonTools(run_code=True, save_and_run=True,base_dir=temp_dir)],
    description="You are a Python developer specialized in code evaluation and testing.",
    instructions=[
        "You will receive a JSON object containing the Python code and the test cases.",
        "1. Analyze and understand the code logic.",
        "2. Run the provided code with the given examples.",
        "3. Compare the actual output with the expected output and show the results to the user.",
        "4. Provide detailed results including whether the code works correctly.",
        "5. If there are any issues, explain what went wrong and modify the code.",
        "6. If the code is working fine, update the code in the `updated_code` section of the Pydantic model and save it to a .py file.",
        "7. Always return an instance of `OptimizedCodeExecuter` with the required fields."
    ],
    expected_output="If the code works fine, return the working code. otherwise, return an error message.",
    exponential_backoff=True,
    retries=2,
)



# Agent without tools - with JSON mode
code_verify_agent = Agent(
    model=Groq(id="llama-3.3-70b-versatile",api_key=groq_api_key),
    description="Formats code verification results",
    instructions=[
        "Format the code verification results into structured output",
        "Ensure the output adheres to the Pydantic model's requirements",
        "always Include the updated code in the `final_debuged_suboptimized_code` section of the Pydantic model"

    ],
    expected_output="format the input into the structured output",
    response_model=CodeVerifyInput,
    exponential_backoff=True,
    retries=2,
)