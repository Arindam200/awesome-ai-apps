"""
Stockagent

Module description goes here.
"""

from typing import List, Dict, Optional, Union, Any
import json
import logging
import os
import re

from agno.agent import Agent, RunResponse
from agno.models.nebius import Nebius
from agno.tools.yfinance import YFinanceTools
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import dotenv
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


dotenv.load_dotenv()
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

if not NEBIUS_API_KEY:
    raise ValueError("Please provide a NEBIUS API key")

app = FastAPI(
    title="Stock Analysis API",
    description="API for fetching detailed stock analysis information",
    version="1.0.0"
)

# Create detailed instructions for response formatting
detailed_instructions = [
    "You are a Wall Street analyst expert. Your task is to retrieve financial data about stocks.",
    "For each stock, you MUST format your response as a valid JSON object that follows this exact structure:",
    """{
        "symbol": "TICKER",
        "company_name": "Full Company Name",
        "current_price": stock_price,
        "market_cap": 1234567890,
        "financial_ratios": {
            "pe_ratio": 15.6,
            "pb_ratio": 3.2,
            "ev_ebitda": 12.3,
            "roe": 22.5,
            "roa": 10.8,
            "operating_margin": 24.5,
            "net_margin": 18.2
        },
        "financial_health": {
            "debt_to_equity": 1.2,
            "current_ratio": 2.5,
            "quick_ratio": 1.8,
            "interest_coverage": 15.6
        },
        "per_share_metrics": {
            "eps": 5.67,
            "book_value": 45.32,
            "dividend_yield": 1.2,
            "fifty_two_week_low": 120.5,
            "fifty_two_week_high": 180.75
        }
    }""",
    "Do not include any additional text or explanations outside the JSON object.",
    "All numeric values should be actual numbers, not strings."
]

# Initialize the agent with YFinance tools
stock_analyzer_agent = Agent(
    model=Nebius(id="deepseek-ai/DeepSeek-R1-0528", api_key=NEBIUS_API_KEY),
    markdown=True,
    tools=[YFinanceTools(
        stock_price=True,
        company_info=True,
        analyst_recommendations=True,
        stock_fundamentals=True,
        income_statements=True,
        historical_prices=True,
        key_financial_ratios=True,
        company_news=True,
        technical_indicators=True)],
    instructions=detailed_instructions,
)

def extract_json_from_response(response_content):
    """Extract JSON from response content, handling markdown code blocks."""
    if not response_content:
        return None

    # If response is already a dict, return it
    if isinstance(response_content, dict):
        return response_content

    # If response is a string, try to extract JSON
    if isinstance(response_content, str):
        # Case 1: Check if content is wrapped in markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_content)
        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                print(f"Failed to parse JSON from markdown code block")

        # Case 2: Check if the entire string is JSON
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            pass

        # Case 3: Look for JSON object pattern in text
        json_match = re.search(r'\{[\s\S]*\}', response_content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                print(f"Failed to parse JSON from pattern match")

    return None

def create_default_stock_data(symbol):
    """Create default stock data structure with the given symbol."""
    return {
        "symbol": symbol.upper(),
        "company_name": f"{symbol.upper()} Inc.",
        "current_price": 0.0,
        "market_cap": 0,
        "financial_ratios": {
            "pe_ratio": 0.0,
            "pb_ratio": 0.0,
            "ev_ebitda": 0.0,
            "roe": 0.0,
            "roa": 0.0,
            "operating_margin": 0.0,
            "net_margin": 0.0
        },
        "financial_health": {
            "debt_to_equity": 0.0,
            "current_ratio": 0.0,
            "quick_ratio": 0.0,
            "interest_coverage": 0.0
        },
        "per_share_metrics": {
            "eps": 0.0,
            "book_value": 0.0,
            "dividend_yield": 0.0,
            "fifty_two_week_low": 0.0,
            "fifty_two_week_high": 0.0
        }
    }

def merge_stock_data(default_data, api_data):
    """Merge API data into default data structure, handling type conversions."""
    if not api_data:
        return default_data

    result = default_data.copy()

    # Update top-level fields
    for field in ["symbol", "company_name"]:
        if field in api_data:
            result[field] = api_data[field]

    # Update numeric top-level fields with type conversion
    for field in ["current_price", "market_cap"]:
        if field in api_data:
            try:
                value = api_data[field]
                if field == "current_price":
                    result[field] = float(value)
                elif field == "market_cap":
                    result[field] = int(float(value)) if isinstance(value, (int, float, str)) else value
            except (ValueError, TypeError):
                print(f"Failed to convert {field} value: {api_data[field]}")

    # Update nested objects
    for section in ["financial_ratios", "financial_health", "per_share_metrics"]:
        if section in api_data and isinstance(api_data[section], dict):
            for key in result[section].keys():
                if key in api_data[section]:
                    try:
                        result[section][key] = float(api_data[section][key])
                    except (ValueError, TypeError):
                        print(f"Failed to convert {section}.{key} value: {api_data[section][key]}")

    return result