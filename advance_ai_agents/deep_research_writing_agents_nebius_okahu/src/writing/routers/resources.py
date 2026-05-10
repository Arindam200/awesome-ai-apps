"""MCP Resources registration for configuration and profiles."""

import json

from fastmcp import FastMCP

from writing.app.profile_loader import load_profiles
from writing.config.settings import get_settings


def register_mcp_resources(mcp: FastMCP) -> None:
    """Register all MCP resources with the server instance."""

    @mcp.resource("config://settings")
    async def get_config() -> str:
        """Get the current writer configuration.

        Returns server settings including model names and review iterations.
        API key values are never exposed.
        """

        settings = get_settings()

        return json.dumps(
            {
                "server_name": settings.server_name,
                "version": settings.version,
                "writer_model": settings.writer_model,
                "reviewer_model": settings.reviewer_model,
                "image_model": settings.image_model,
                "nebius_base_url": settings.nebius_base_url,
                "num_reviews": settings.num_reviews,
                "has_nebius_api_key": settings.nebius_api_key is not None,
                "has_gemini_api_key": settings.gemini_api_key is not None,
                "has_okahu_api_key": settings.okahu_api_key is not None,
                "monocle_exporter": settings.monocle_exporter,
                "okahu_workflow_name": settings.okahu_workflow_name,
            },
            indent=2,
        )

    @mcp.resource("profiles://all")
    async def get_profiles() -> str:
        """Get all writing profiles content.

        Returns the full markdown content of all 4 profiles
        (structure, terminology, character, branding).
        """

        profiles = load_profiles()

        return json.dumps(
            {
                "structure": profiles.structure.content,
                "terminology": profiles.terminology.content,
                "character": profiles.character.content,
                "branding": profiles.branding.content,
            },
            indent=2,
        )
