"""
FastAPI server for Text-to-SQL Analyst
"""

import re

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


DISALLOWED_SQL_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "replace",
    "grant",
    "revoke",
    "commit",
    "rollback",
    "attach",
    "detach",
    "vacuum",
    "pragma",
)


def validate_sql_query(sql_query: str) -> str:
    normalized_query = " ".join(sql_query.strip().split())
    if not normalized_query:
        raise HTTPException(status_code=400, detail="Generated SQL query is empty")
    if "--" in normalized_query or "/*" in normalized_query or "*/" in normalized_query:
        raise HTTPException(status_code=400, detail="Generated SQL query contains blocked SQL patterns")
    if ";" in normalized_query[:-1]:
        raise HTTPException(status_code=400, detail="Only single-statement SQL queries are allowed")
    if normalized_query.endswith(";"):
        normalized_query = normalized_query[:-1].strip()
    lowered_query = normalized_query.lower()
    if not re.match(r"^(select|with)\b", lowered_query):
        raise HTTPException(status_code=400, detail="Only read-only SELECT queries are allowed")
    for keyword in DISALLOWED_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered_query):
            raise HTTPException(status_code=400, detail=f"Generated SQL query contains blocked keyword: {keyword}")
    return normalized_query


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
        sql_query = validate_sql_query(sql_query)
        results = execute_query(sql_query)
        return ResultsResponse(sql_query=sql_query, results=results)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
