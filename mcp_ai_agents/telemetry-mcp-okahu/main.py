"""
FastAPI server for Text-to-SQL Analyst
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from analyst import generate_sql, execute_query, text_to_sql
from sql_validator import SQLValidationError

app = FastAPI(title="Text-to-SQL API", version="1.0.0")

allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


class QueryRequest(BaseModel):
    query: str


class SQLResponse(BaseModel):
    sql_query: str


class ResultsResponse(BaseModel):
    sql_query: str
    results: list


@app.post("/generate-sql", response_model=SQLResponse)
async def api_generate_sql(request: QueryRequest):
    """
    Generate SQL from natural language (without executing).
    """
    try:
        sql_query = generate_sql(request.query)
        return SQLResponse(sql_query=sql_query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=ResultsResponse)
async def api_query(request: QueryRequest):
    """
    Generate SQL from natural language and execute it.
    Returns both the SQL and the results.
    """
    try:
        sql_query = generate_sql(request.query)
        results = text_to_sql(request.query)
        return ResultsResponse(sql_query=sql_query, results=results)
    except SQLValidationError as e:
        raise HTTPException(status_code=400, detail=f"Query rejected: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
