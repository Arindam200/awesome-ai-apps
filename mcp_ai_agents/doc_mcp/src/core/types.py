"""Type definitions for Doc-MCP application."""

from enum import Enum
from pydantic import BaseModel
class QueryMode(str, Enum):
    """Available query modes for document retrieval."""

    DEFAULT = "default"
    TEXT_SEARCH = "text_search"
    HYBRID = "hybrid"


class ProcessingStatus(str, Enum):
    """Processing status indicators."""

    PENDING = "pending"
    LOADING = "loading"
    LOADED = "loaded"
    VECTORIZING = "vectorizing"
    COMPLETE = "complete"
    ERROR = "error"


class DocumentMetadata(BaseModel):
    """Document metadata structure."""

    file_path: str
    file_name: str
    file_extension: str
    directory: str
    repo: str
    branch: str
    sha: str
    size: int
    url: str
    raw_url: str
    type: str = "file"


class GitHubFileInfo(BaseModel):
    """GitHub file information."""

    path: str
    name: str
    sha: str
    size: int
    url: str
    download_url: str
    type: str
    encoding: str
    content: str