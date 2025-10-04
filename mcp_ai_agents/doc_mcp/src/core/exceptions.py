"""Custom exceptions for Doc-MCP application."""


class DocMCPError(Exception):
    """Base exception for Doc-MCP."""

    pass


class GitHubError(DocMCPError):
    """GitHub-related errors."""

    pass


class GitHubRateLimitError(GitHubError):
    """GitHub rate limit exceeded."""

    pass


class GitHubAuthenticationError(GitHubError):
    """GitHub authentication failed."""

    pass


class GitHubRepositoryNotFoundError(GitHubError):
    """GitHub repository not found."""

    pass


class VectorStoreError(DocMCPError):
    """Vector store operation errors."""

    pass


class IngestionError(DocMCPError):
    """Document ingestion errors."""

    pass


class QueryError(DocMCPError):
    """Query processing errors."""

    pass