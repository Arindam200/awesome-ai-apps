import logging
import os

from agents.mcp import MCPServerStdio
import asyncio
logger = logging.getLogger(__name__)
_mcp_server = None

async def initialize_mcp_server():
    """Initialize MCP server."""
    global _mcp_server

    if _mcp_server:
        return _mcp_server

    try:
        server = MCPServerStdio(
            cache_tools_list=False,
            params={
                "command": "npx",
                "args": ["-y", "@brightdata/mcp"],
                "env": {
                    "API_TOKEN": os.environ["BRIGHT_DATA_API_KEY"],
                    "WEB_UNLOCKER_ZONE": "mcp_unlocker",
                    "BROWSER_AUTH": os.environ["BROWSER_AUTH"],
                }
            }
        )

        await asyncio.wait_for(server.__aenter__(), timeout=10)
        _mcp_server = server
        return server

    except Exception as e:
        logger.error(f"Error initializing MCP server: {e}")
        return None

async def wait_for_initialization():
    """Wait for MCP initialization to complete."""
    return await initialize_mcp_server() is not None

def get_mcp_server():
    """Get the current MCP server instance."""
    return _mcp_server