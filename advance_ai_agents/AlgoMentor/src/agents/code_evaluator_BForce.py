from agno.agent import Agent
from agno.tools.python import PythonTools
from agno.models.groq import Groq
import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()

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

# groq_api_key=os.getenv('GROQ_API_KEY')
groq_api_key=st.secrets['GROQ_API_KEY']

code_evaluator = Agent(
    tools=[PythonTools(run_code=True,save_and_run=True,base_dir=temp_dir)],
    model=Groq(id="llama-3.3-70b-versatile",api_key=groq_api_key),
    description="You are a Python developer specialized in code evaluation and testing.",
    instructions=[
        "you will recive a json object that contains the python code and the test_cases."
        "1. First, analyze and understand the code logic",
        "2. Run the provided code with the given examples",
        "3. Compare the actual output with the expected output and show to the user",
        "4. Provide detailed results including whether the code works correctly",
        "5. If there are any issues, explain what went wrong and suggest fixes"
        "6. if the code working fine then update the code to `updated_code` section in pydantic. and save to the .py file "
    ],
    show_tool_calls=True,
    use_json_mode=True,
    exponential_backoff=True,
    retries=2,
)