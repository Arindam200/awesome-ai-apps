"""Main MCP server implementation for the Deep Research Agent."""

import logging

from fastmcp import FastMCP

from research.config.settings import get_settings
from research.routers.prompts import register_mcp_prompts
from research.routers.resources import register_mcp_resources
from research.routers.tools import register_mcp_tools
from research.utils.logging import setup_logging
from research.utils.okahu_utils import configure_okahu

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server instance.

    Returns:
        FastMCP: Configured MCP server instance.
    """

    settings = get_settings()

    mcp = FastMCP(
        name=settings.server_name,
        version=settings.version,
    )

    register_mcp_tools(mcp)
    register_mcp_resources(mcp)
    register_mcp_prompts(mcp)

    return mcp


# Configure logging
setup_logging(level=get_settings().log_level)

# Configure Okahu/Monocle if available
if configure_okahu():
    logger.info(
        "Okahu/Monocle tracing enabled for workflow: "
        f"{get_settings().okahu_workflow_name}"
    )

# Create the server instance (used by `fastmcp run`)
mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run()
