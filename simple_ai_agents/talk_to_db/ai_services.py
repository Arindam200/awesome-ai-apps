import json
import os
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_nebius import ChatNebius
DB_SCHEMA = """
Database: Ecommerce (MySQL)
Tables:
- category (id, uuid, name, description, date_created, date_updated)
- product (id, uuid, name, description, price, stock_quantity, category_id, date_created, date_updated)
- product_category (id, product_id, category_id)
- user (id, uuid, name, email, address, date_created, date_updated)
- order (id, uuid, user_id, total_amount, status, order_date, date_created, date_updated)
- order_item (id, order_id, product_id, quantity, unit_price, date_created, date_updated)

Relationships:
- product.category_id -> category.id
- product_category.product_id -> product.id
- product_category.category_id -> category.id
- order.user_id -> user.id
- order_item.order_id -> order.id
- order_item.product_id -> product.id

Note: All tables use MySQL syntax with backticks for identifiers.
"""


def get_llm():
    """Get the Nebius LLM instance"""
    return ChatNebius(
        model="zai-org/GLM-4.5-Air",
        temperature=0.1,
        top_p=0.95,
        api_key=os.getenv("NEBIUS_API_KEY"),
    )


def translate_to_sql(natural_question):
    """Translate natural language question to SQL using Qwen from Nebius"""
    try:
        # Initialize Qwen from Nebius
        llm = get_llm()

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a MySQL SQL expert. Convert natural language questions to MySQL queries.

Database Schema:
{db_schema}

Rules:
1. For SELECT queries: Use appropriate JOINs when needed, use meaningful column aliases for clarity, include LIMIT 100 for large result sets
2. Use proper MySQL syntax with backticks for table and column names
3. Use MySQL-specific functions and syntax
4. Return ONLY the SQL query, no explanations, no "SQL:" prefix
5. Do NOT include any thinking, reflection, or reasoning in your response
6. Do NOT use <think> tags or any other markup

Example SELECT queries:
Question: "What are the product categories we have?"
SELECT `id`, `name`, `description` FROM `category` ORDER BY `name`;

Question: "Show me all products with their categories"
SELECT p.`id`, p.`name`, p.`price`, c.`name` as category_name FROM `product` p LEFT JOIN `category` c ON p.`category_id` = c.`id` ORDER BY p.`name`;

Question: "How many orders do we have?"
SELECT COUNT(*) as total_orders FROM `order`;

Question: "What are the top 5 most expensive products?"
SELECT `id`, `name`, `price` FROM `product` ORDER BY `price` DESC LIMIT 5;

IMPORTANT: Return ONLY the SQL query without any prefix like "SQL:" or explanations. Do not include any thinking process or reflection.
""",
                ),
                ("human", "Question: {question}\n\nGenerate the SQL query:"),
            ]
        )

        # Create the chain
        chain = prompt | llm | StrOutputParser()

        # Generate SQL
        sql_query = chain.invoke(
            {
                "db_schema": DB_SCHEMA,
                "question": natural_question,
            }
        )

        # Clean up the SQL query - remove any unwanted prefixes and thinking parts
        sql_query = sql_query.strip()

        # Remove thinking/reflection parts (anything between <think> and </think>)
        sql_query = re.sub(r"<think>.*?</think>", "", sql_query, flags=re.DOTALL)

        # Remove common prefixes
        if sql_query.upper().startswith("SQL:"):
            sql_query = sql_query[4:].strip()
        if sql_query.upper().startswith("QUERY:"):
            sql_query = sql_query[6:].strip()

        # Clean up any remaining whitespace and newlines
        sql_query = sql_query.strip()

        return sql_query

    except Exception as e:
        return f"Error translating to SQL: {str(e)}"


def explain_results(results, original_question):
    """Use Qwen from Nebius to explain the results in plain English"""
    try:
        llm = get_llm()

        # Convert results to a readable format
        if results:
            results_text = json.dumps(results, indent=2, default=str)
        else:
            results_text = "No results found"

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful database assistant. Explain query results in plain English.

Rules:
1. Be conversational and clear
2. Summarize the key findings
3. If there are many results, provide a summary with key statistics
4. Highlight any interesting patterns or insights
5. Keep the explanation concise but informative
""",
                ),
                (
                    "human",
                    """Original Question: {question}

Query Results:
{results}

Please explain these results in plain English:""",
                ),
            ]
        )

        chain = prompt | llm | StrOutputParser()

        explanation = chain.invoke(
            {"question": original_question, "results": results_text}
        )

        # Clean up the explanation - remove any thinking parts
        explanation = explanation.strip()

        # Remove thinking/reflection parts (anything between <think> and </think>)
        explanation = re.sub(r"<think>.*?</think>", "", explanation, flags=re.DOTALL)

        # Clean up any remaining whitespace and newlines
        explanation = explanation.strip()

        return explanation

    except Exception as e:
        return f"Error generating explanation: {str(e)}"