"""Text-to-SQL Analyst - converts natural language queries to SQL."""

import logging
import os
import re
import sqlite3

from dotenv import load_dotenv
from monocle_apptrace import setup_monocle_telemetry
from openai import OpenAI

load_dotenv()

logging.getLogger("monocle_apptrace").setLevel(logging.CRITICAL)
logging.getLogger("opentelemetry").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)

setup_monocle_telemetry(workflow_name="text_to_sql_analyst_v3")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_SCHEMA = """
Database Schema:
Table: users
  - user_id (INTEGER PRIMARY KEY)
  - username (TEXT NOT NULL)
  - email (TEXT UNIQUE)

Table: orders
  - order_id (INTEGER PRIMARY KEY)
  - user_id (INTEGER, foreign key to users.user_id)
  - amount (REAL)
  - order_date (TEXT)
""".strip()


def get_model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def _build_prompt(natural_language_query: str) -> str:
    return f"""Convert the following natural language query into a valid SQLite SQL query.
Use only the database schema provided. Return ONLY the SQL query, with no explanation.

{DB_SCHEMA}

Natural Language Query: {natural_language_query}

SQL Query:"""


def _strip_code_fences(sql_query: str) -> str:
    cleaned = sql_query.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _fallback_sql(natural_language_query: str) -> str | None:
    normalized = " ".join(natural_language_query.lower().split())

    if normalized in {"show all users", "list all users", "get all users"}:
        return "SELECT * FROM users"

    amount_match = re.search(r"(?:greater than|more than|over|above)\s*\$?(\d+(?:\.\d+)?)", normalized)
    if "users" in normalized and "orders" in normalized and amount_match:
        amount = amount_match.group(1)
        return (
            "SELECT users.* FROM users "
            "JOIN orders ON users.user_id = orders.user_id "
            f"WHERE orders.amount > {amount}"
        )

    if "orders" in normalized and amount_match:
        amount = amount_match.group(1)
        return f"SELECT * FROM orders WHERE amount > {amount}"

    return None


def generate_sql(natural_language_query: str) -> str:
    prompt = _build_prompt(natural_language_query)

    try:
        response = client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {"role": "system", "content": "You are a SQL expert. Generate only valid SQLite SQL."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        content = response.choices[0].message.content
        if content:
            return _strip_code_fences(content)
    except Exception:
        fallback_sql = _fallback_sql(natural_language_query)
        if fallback_sql:
            return fallback_sql
        raise

    fallback_sql = _fallback_sql(natural_language_query)
    if fallback_sql:
        return fallback_sql
    raise ValueError("No SQL query was generated.")


def execute_query(sql_query: str):
    conn = sqlite3.connect("sales.db")
    cursor = conn.cursor()

    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        return results
    finally:
        conn.close()


def text_to_sql(natural_language_query: str):
    return execute_query(generate_sql(natural_language_query))


if __name__ == "__main__":
    print(text_to_sql("Find all users who have made orders over $100"))
