"""MCP Resources registration for configuration exposure."""

import json

from fastmcp import FastMCP

from research.config.settings import get_settings


def register_mcp_resources(mcp: FastMCP) -> None:
    """Register all MCP resources with the server instance."""

    @mcp.resource("resource://config/research")
    async def get_research_config() -> str:
        """Get the current research agent configuration.

        Exposes research configuration including model names and feature flags.
        API key values are never exposed — only their presence is indicated.
        """

        settings = get_settings()

        return json.dumps(
            {
                "server_name": settings.server_name,
                "version": settings.version,
                "llm_model": settings.llm_model,
                "youtube_transcription_model": settings.youtube_transcription_model,
                "nebius_base_url": settings.nebius_base_url,
                "has_nebius_api_key": settings.nebius_api_key is not None,
                "has_exa_api_key": settings.exa_api_key is not None,
                "has_okahu_api_key": settings.okahu_api_key is not None,
                "monocle_exporter": settings.monocle_exporter,
                "okahu_workflow_name": settings.okahu_workflow_name,
            },
            indent=2,
        )
