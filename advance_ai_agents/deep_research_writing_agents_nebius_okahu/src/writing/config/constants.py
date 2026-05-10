"""Constants used throughout the MCP server."""

from pathlib import Path

# File names
RESEARCH_FILE = "research.md"
GUIDELINE_FILE = "guideline.md"
POST_FILE = "post.md"
IMAGE_FILE = "post_image.png"

# Folder names
MEMORY_FOLDER = ".memory"

# Profiles directory (shipped with the module)
PROFILES_DIR = Path(__file__).parent.parent / "profiles"
