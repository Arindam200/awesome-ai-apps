"""
Test suite for Text-to-SQL Analyst using Monocle Test Tools

These tests validate agent behavior through trace analysis.
The agent MUST use Okahu MCP traces to debug failures.
NO local logs are available - traces only exist in Okahu Cloud.

Monocle Test Tools validates:
- Inference spans exist (OpenAI API was called correctly)
- Response similarity (SQL output matches expected patterns)
- Agent behavior matches expected interaction patterns
"""

import logging
import pytest
from monocle_test_tools import TestCase, MonocleValidator

# Suppress ALL local output - force MCP-only debugging
logging.disable(logging.CRITICAL)

from analyst import generate_sql, execute_query, text_to_sql


# Test cases for monocle validation
sql_generation_test_cases: list[TestCase] = [
    {
        # Test 1: Basic SQL generation - verify inference span exists
        "test_input": ["Show all users"],
        "test_spans": [
            {
                "span_type": "inference",
                "entities": [
                    {"type": "inference", "name": "openai"}
                ],
            }
        ]
    },
    {
        # Test 2: Complex query - verify SQL output similarity
        "test_input": ["Find all users who have made orders with amount greater than 100"],
        "test_output": "SELECT users.* FROM users JOIN orders ON users.user_id = orders.user_id WHERE orders.amount > 100",
        "comparer": "similarity",
    },
]


@MonocleValidator().monocle_testcase(sql_generation_test_cases)
def test_generate_sql_with_monocle(my_test_case: TestCase):
    """
    Test SQL generation using Monocle validator.
    
    This validates:
    - OpenAI inference spans are generated correctly
    - SQL output matches expected patterns (similarity check)
    
    If this fails, check Okahu MCP traces for:
    - Missing inference spans (wrong API method used)
    - Incorrect SQL generation (schema mismatch)
    """
    MonocleValidator().test_workflow(generate_sql, my_test_case)


# Direct database tests (no monocle validation needed - these test the DB itself)
def test_execute_query_users_table():
    """
    Test direct SQL execution on the actual database.
    This verifies the users table exists and has data.
    """
    sql = "SELECT * FROM users LIMIT 3"
    results = execute_query(sql)
    
    assert len(results) == 3, "Should return 3 users"
    # Verify column structure: (user_id, username, email)
    assert len(results[0]) == 3, "Each user row should have 3 columns"


def test_execute_query_orders_table():
    """
    Test direct SQL execution on orders table.
    This verifies the orders table exists and has data.
    """
    sql = "SELECT * FROM orders WHERE amount > 100 LIMIT 5"
    results = execute_query(sql)
    
    assert len(results) > 0, "Should find orders over $100"
    # Verify column structure: (order_id, user_id, amount, order_date)
    assert len(results[0]) == 4, "Each order row should have 4 columns"


# End-to-end test using monocle
e2e_test_cases: list[TestCase] = [
    {
        # End-to-end: Natural language to SQL execution
        "test_input": ["Find all users who have made orders with amount greater than 100"],
        "test_spans": [
            {
                "span_type": "inference",
                "entities": [
                    {"type": "inference", "name": "openai"}
                ],
            }
        ]
    },
]


@MonocleValidator().monocle_testcase(e2e_test_cases)
def test_text_to_sql_e2e(my_test_case: TestCase):
    """
    End-to-end test: natural language query to SQL results.
    
    Validates the full pipeline including:
    - OpenAI inference call exists in traces
    - Query executes successfully against database
    """
    MonocleValidator().test_workflow(text_to_sql, my_test_case)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
