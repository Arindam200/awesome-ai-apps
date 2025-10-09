import json
import logging

from config import settings
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions
from starlette.middleware.base import BaseHTTPMiddleware
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()

# Initialize ScaleKit client
scalekit_client = ScalekitClient(
    settings.SCALEKIT_ENVIRONMENT_URL,
    settings.SCALEKIT_CLIENT_ID,
    settings.SCALEKIT_CLIENT_SECRET
)

# Authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

            token = auth_header.split(" ")[1]

            request_body = await request.body()

            # Parse JSON from bytes
            try:
                request_data = json.loads(request_body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data = {}

            validation_options = TokenValidationOptions(
              issuer=settings.SCALEKIT_ENVIRONMENT_URL,
              audience=[settings.SCALEKIT_AUDIENCE_NAME],
            )

            is_tool_call = request_data.get("method") == "tools/call"

            required_scopes = []
            if is_tool_call:
                required_scopes = ["gnews:read"] # get required scope for your tool
                validation_options.required_scopes = required_scopes

            try:
                scalekit_client.validate_token(token, options=validation_options)

            except Exception as e:
                raise HTTPException(status_code=401, detail="Token validation failed")

        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"error": "unauthorized" if e.status_code == 401 else "forbidden", "error_description": e.detail},
                headers={
                    "WWW-Authenticate": f'Bearer realm="OAuth", resource_metadata="{settings.SCALEKIT_RESOURCE_METADATA_URL}"'
                }
            )

        return await call_next(request)