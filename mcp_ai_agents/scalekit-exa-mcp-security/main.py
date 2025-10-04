import json

from auth import AuthMiddleware
from config import settings
from exa import mcp as exa_mcp_server
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import contextlib
import uvicorn
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with exa_mcp_server.session_manager.run():
        yield

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your actual origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# MCP well-known endpoint
@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """
    OAuth 2.0 Protected Resource Metadata endpoint for MCP client discovery.
    Required by the MCP specification for authorization server discovery.
    """

    response = json.loads(settings.METADATA_JSON_RESPONSE)
    return response

# Create and mount the MCP server with authentication
mcp_server = exa_mcp_server.streamable_http_app()
app.add_middleware(AuthMiddleware)
app.mount("/", mcp_server)

def main():
    """Main entry point for the MCP server."""
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT, log_level="debug")

if __name__ == "__main__":
    main()