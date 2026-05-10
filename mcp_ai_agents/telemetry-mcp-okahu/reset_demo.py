#!/usr/bin/env python3
"""
Reset Demo - Restores analyst.py to its buggy state

Run this before each self-healing demo to ensure the agent
starts with broken code that needs fixing via MCP trace analysis.

Usage:
    python reset_demo.py
"""

BUGGY_ANALYST = '''"""
Text-to-SQL Analyst - Converts natural language queries to SQL

NOTE: This file has bugs that need to be fixed using trace analysis.
"""

import os
import logging
import sqlite3
from openai import OpenAI
from monocle_apptrace import setup_monocle_telemetry
from dotenv import load_dotenv

load_dotenv()

# Suppress ALL local logging - traces go ONLY to Okahu Cloud
# This forces debugging via MCP trace analysis, no local logs to cheat with
logging.getLogger("monocle_apptrace").setLevel(logging.CRITICAL)
logging.getLogger("opentelemetry").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)

# Initialize Monocle Telemetry FIRST (before any client creation)
# This exports traces to Okahu Cloud when MONOCLE_EXPORTER=okahu
setup_monocle_telemetry(workflow_name="text_to_sql_analyst_v3")

# Create OpenAI client AFTER telemetry is initialized
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database schema description (used in prompts)
# BUG: This schema is WRONG - actual tables are users/orders, not customers/products
DB_SCHEMA = """
Database Schema:
Table: customers
  - customer_id (INTEGER PRIMARY KEY)
  - name (TEXT)
  - email (TEXT)

Table: products
  - product_id (INTEGER PRIMARY KEY)
  - customer_id (INTEGER, foreign key to customers)
  - price (REAL)
  - purchase_date (TEXT)
"""


def generate_sql(natural_language_query: str) -> str:
    """
    Generate SQL from natural language using GPT-4o.

    Args:
        natural_language_query: The question in plain English

    Returns:
        Generated SQL query string
    """
    prompt = f"""Convert the following natural language query into a valid SQL query.
Use the database schema provided. Return ONLY the SQL query, no explanation.

{DB_SCHEMA}

Natural Language Query: {natural_language_query}

SQL Query:"""

    # BUG: Invalid chat model name to force model_not_found and keep traces inspectable
    response = client.chat.completions.create(
        model="gpt-5.4-typo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
    )

    # BUG: Using .text instead of .message.content (wrong for chat models)
    content = response.choices[0].text
    if content is None:
        raise ValueError("API response content is None. Check API call.")
    sql_query = content.strip()

    # Clean up markdown formatting if present
    if sql_query.startswith("```"):
        lines = sql_query.split("\\n")
        sql_query = "\\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    return sql_query.strip()


def execute_query(sql_query: str):
    """
    Execute SQL query on the sales.db database.

    Args:
        sql_query: Valid SQL query string

    Returns:
        Query results as list of tuples
    """
    conn = sqlite3.connect("sales.db")
    cursor = conn.cursor()

    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        return results
    finally:
        conn.close()


def text_to_sql(natural_language_query: str):
    """
    Main entry point: Convert natural language to SQL and execute.

    Args:
        natural_language_query: Question in plain English

    Returns:
        Query results
    """
    sql_query = generate_sql(natural_language_query)
    results = execute_query(sql_query)
    return results


if __name__ == "__main__":
    # Test query
    query = "Find all users who have made orders over $100"
    try:
        result = text_to_sql(query)
        print(f"Results: {result}")
    except Exception as e:
        print(f"Error: {e}")
'''

def main():
    with open("analyst.py", "w") as f:
        f.write(BUGGY_ANALYST)
    print("✓ Reset analyst.py to buggy state")
    print()
    print("Bugs introduced:")
    print("  1. Invalid model: client.chat.completions.create() uses gpt-5.4-typo")
    print("  2. Wrong response: .text instead of .message.content")
    print("  3. Wrong schema: customers/products instead of users/orders")
    print()
    print("Run tests with: pytest test_analyst.py -v")


if __name__ == "__main__":
    main()
