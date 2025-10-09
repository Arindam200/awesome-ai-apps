"""
Agentroutes

Module description goes here.
"""

from typing import List, Dict, Optional, Union, Any
import json
import logging
import os
import requests

from agno.agent import RunResponse, Agent
from agno.models.nebius import Nebius
from controllers.agents import multi_ai
from controllers.ask import chat_agent
from fastapi import FastAPI, APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import datetime
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


router = APIRouter()

dotenv.load_dotenv()
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
templates = Jinja2Templates(directory="templates")

@router.get("/health", response_class=HTMLResponse)
async def health_check(request: Request):
    """Health check endpoint to verify the API server status and connections."""
    try:
        response_data = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime": "OK",
            "api": {
                "nebius_api": "connected" if NEBIUS_API_KEY else "not configured",
            },
            "ip": requests.get('https://api.ipify.org').text,
            "services": {
                "chat": router.url_path_for("chat"),
                "agent": router.url_path_for("ask"),
            },
        }

        # Check if request is from a browser or format is explicitly set to html
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            current_year = datetime.datetime.now().year
            return templates.TemplateResponse(
                "route.html",
                {
                    "request": request,
                    "route_path": "/health",
                    "method": "GET",
                    "full_path": str(request.url).split("?")[0],
                    "description": "Health check endpoint to verify the API server status and connections.",
                    "parameters": [
                        {"name": "format", "type": "string", "description": "Response format (html or json)"}
                    ],
                    "example_query": "",
                    "example_response": json.dumps(response_data, indent=2),
                    "current_year": current_year
                }
            )

        return JSONResponse(content=response_data)

    except Exception as e:
        error_response = {
            "status": "unhealthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "error": str(e)
        }

        # Check if request is from a browser or format is explicitly set to html
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            current_year = datetime.datetime.now().year
            return templates.TemplateResponse(
                "route.html",
                {
                    "request": request,
                    "route_path": "/health",
                    "method": "GET",
                    "full_path": str(request.url).split("?")[0],
                    "description": "Health check endpoint to verify the API server status and connections.",
                    "parameters": [
                        {"name": "format", "type": "string", "description": "Response format (html or json)"}
                    ],
                    "example_query": "",
                    "example_response": json.dumps(error_response, indent=2),
                    "current_year": current_year
                }
            )

        return JSONResponse(content=error_response)

@router.get("/chat", response_class=HTMLResponse)
def chat(request: Request, query: str = None):
    """
    API endpoint to handle user investment-related questions and return AI-generated insights.
    """
    # Check if request is from a browser or format is explicitly set to html
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        current_year = datetime.datetime.now().year
        example_response = {
            "question": "What are good tech stocks to invest in?",
            "answer": "Some popular tech stocks to consider include Apple (AAPL), Microsoft (MSFT), Google (GOOGL), and Amazon (AMZN). However, you should always do your own research and consider your investment goals and risk tolerance before investing."
        }

        return templates.TemplateResponse(
            "route.html",
            {
                "request": request,
                "route_path": "/chat",
                "method": "GET",
                "full_path": str(request.url).split("?")[0],
                "description": "Chat endpoint that uses Nebius's LLaMa model to answer investment questions.",
                "parameters": [
                    {"name": "query", "type": "string", "description": "The investment question to ask"},
                    {"name": "format", "type": "string", "description": "Response format (html or json)"}
                ],
                "example_query": "What are good tech stocks to invest in?",
                "example_response": json.dumps(example_response, indent=2),
                "current_year": current_year
            }
        )

    # Handle regular API calls
    if not query:
        return JSONResponse(content={"error": "Query parameter is required"})

    try:
        response = chat_agent.run(query)
        answer = response.content
        return JSONResponse(content={"question": query, "answer": answer})

    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@router.get("/agent", response_class=HTMLResponse)
def ask(request: Request, query: str = None):
    """
    API endpoint to handle user investment-related questions and return AI-generated insights.
    """
    # Check if request is from a browser or format is explicitly set to html
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        current_year = datetime.datetime.now().year
        example_response = {
            "question": "Should I invest in index funds?",
            "answer": "Index funds are often a good choice for passive investors looking for broad market exposure with low fees. They offer diversification and typically outperform actively managed funds in the long term. However, the suitability depends on your investment goals, time horizon, and risk tolerance."
        }

        return templates.TemplateResponse(
            "route.html",
            {
                "request": request,
                "route_path": "/agent",
                "method": "GET",
                "full_path": str(request.url).split("?")[0],
                "description": "Agent endpoint that uses a multi-AI system to provide sophisticated investment advice.",
                "parameters": [
                    {"name": "query", "type": "string", "description": "The investment question to ask"},
                    {"name": "format", "type": "string", "description": "Response format (html or json)"}
                ],
                "example_query": "Should I invest in index funds?",
                "example_response": json.dumps(example_response, indent=2),
                "current_year": current_year
            }
        )

    # Handle regular API calls
    if not query:
        return JSONResponse(content={"error": "Query parameter is required"})

    try:
        response: RunResponse = multi_ai.run(query)
        answer = response.content

        return JSONResponse(content={"question": query, "answer": answer})

    except Exception as e:
        return JSONResponse(content={"error": str(e)})