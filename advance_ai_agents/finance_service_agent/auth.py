"""Simple API key authentication dependency for FastAPI routes."""
import os
import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_EXPECTED_KEY = os.environ.get("API_KEY", "")


def require_api_key(key: str = Security(_API_KEY_HEADER)) -> str:
    """FastAPI dependency that validates the X-API-Key header."""
    if not _EXPECTED_KEY:
        # No key configured — warn but allow through in dev mode
        import warnings
        warnings.warn(
            "API_KEY environment variable not set. Endpoint is unprotected.",
            stacklevel=2,
        )
        return ""
    if not key or not secrets.compare_digest(key, _EXPECTED_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Set X-API-Key header.",
        )
    return key
