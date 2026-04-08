"""
FastAPI server for Text-to-SQL Analyst
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from analyst import generate_sql, execute_query, text_to_sql

app = FastAPI(title="Text-to-SQL API", version="1.0.0")


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
        results = execute_query(sql_query)
        return ResultsResponse(sql_query=sql_query, results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
