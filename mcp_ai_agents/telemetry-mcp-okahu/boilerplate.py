import os
import sqlite3
from openai import OpenAI
from monocle_apptrace import setup_monocle_telemetry  # NOTE: Import from monocle_apptrace, NOT monocle_apptrace.api
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# THIS IS A BOILERPLATE REFERENCE FOR THE AGENT.
# COPY THIS PATTERN EXACTLY IN YOUR analyst.py
# =============================================================================

# CRITICAL RULES FOR THE AGENT:
# 1. Import: `from monocle_apptrace import setup_monocle_telemetry` (NOT from monocle_apptrace.api)
# 2. Call setup_monocle_telemetry() BEFORE creating the OpenAI client
# 3. Use OpenAI SDK chat completions: `client.chat.completions.create()` (NOT client.Completion.create)
# 4. Do NOT use raw requests.post() - Monocle cannot instrument those


def get_analyst_client():
    # 1. Initialize Monocle Telemetry FIRST (before any client creation)
    # DO NOT REMOVE THIS LINE - telemetry will not work without it
    setup_monocle_telemetry(workflow_name="text_to_sql_analyst_v3")

    # 2. Setup OpenAI Client AFTER telemetry is initialized
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return client


def get_model_name():
    """Returns the model name to use for completions."""
    return os.getenv("OPENAI_MODEL", "gpt-4o")


# EXAMPLE: How to call OpenAI (copy this pattern)
def example_generate_sql(client, prompt: str) -> str:
    """
    Example of correct OpenAI SDK usage with chat completions.
    Use client.chat.completions.create(), NOT client.Completion.create()
    """
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": "You are a SQL expert. Generate only valid SQL."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


def execute_query(sql_query):
    # Connection to the seeded sales.db
    conn = sqlite3.connect("sales.db")
    cursor = conn.cursor()
    cursor.execute(sql_query)
    result = cursor.fetchall()
    conn.close()
    return result


# NOTE TO AGENT: In your analyst.py, do not print SQL or Errors.
# Let Monocle handle the instrumentation silently.
