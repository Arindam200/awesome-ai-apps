"""File and directory operations utilities."""

import json
import logging
from pathlib import Path
from typing import Any

from research.config.constants import MEMORY_FOLDER

logger = logging.getLogger(__name__)


def ensure_memory_dir(working_dir: str) -> Path:
    """Create the .memory/ directory if it doesn't exist and return its path."""

    memory_path = Path(working_dir) / MEMORY_FOLDER
    memory_path.mkdir(parents=True, exist_ok=True)

    return memory_path


def validate_directory(working_dir: str) -> Path:
    """Validate that the working directory exists and is a directory.

    Raises:
        ValueError: If the directory doesn't exist or is not a directory.
    """

    path = Path(working_dir)
    if not path.exists():
        msg = f"Directory does not exist: {working_dir}"
        raise ValueError(msg)
    if not path.is_dir():
        msg = f"Path is not a directory: {working_dir}"
        raise ValueError(msg)

    return path


def read_file(path: Path) -> str:
    """Read a text file, returning empty string if it doesn't exist."""

    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (IOError, OSError) as e:
        logger.error(f"Error reading file {path}: {e}")
        return ""


def write_file(path: Path, content: str) -> None:
    """Write content to a text file, creating parent directories if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON from a file, returning default if the file doesn't exist."""

    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.error(f"Error loading JSON from {path}: {e}")
        return default


def save_json(path: Path, data: Any) -> None:
    """Save data as JSON to a file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
