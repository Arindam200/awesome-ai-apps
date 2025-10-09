"""GitHub URL and repository parsing utilities."""

from typing import Optional, Tuple
from urllib.parse import urlparse
import re

from ..core.exceptions import GitHubError
def parse_github_url(url: str) -> Tuple[str, str]:
    """
    Parse GitHub URL to extract owner and repository name.

    Args:
        url: GitHub URL in various formats

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        GitHubError: If URL format is invalid
    """
    if not url or not url.strip():
        raise GitHubError("Empty URL provided")

    url = url.strip()

    # Handle different URL formats
    patterns = [
        # https://github.com/owner/repo
        r"https?://github\.com/([^/]+)/([^/]+)/?",
        # github.com/owner/repo
        r"github\.com/([^/]+)/([^/]+)/?",
        # owner/repo
        r"^([^/]+)/([^/]+)/?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            # Clean up repo name (remove .git suffix if present)
            repo = repo.rstrip(".git")
            return owner, repo

    raise GitHubError(f"Invalid GitHub URL format: {url}")


def build_github_api_url(
    owner: str, repo: str, path: str = "", branch: str = "main"
) -> str:
    """
    Build GitHub API URL for repository operations.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Optional path within repository
        branch: Branch name (default: main)

    Returns:
        Formatted GitHub API URL
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}"

    if path:
        return f"{base_url}/contents/{path.strip('/')}?ref={branch}"
    else:
        return f"{base_url}/git/trees/{branch}?recursive=1"


def build_github_web_url(
    owner: str, repo: str, path: str = "", branch: str = "main"
) -> str:
    """
    Build GitHub web URL for files.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Optional path within repository
        branch: Branch name (default: main)

    Returns:
        Formatted GitHub web URL
    """
    base_url = f"https://github.com/{owner}/{repo}"

    if path:
        return f"{base_url}/blob/{branch}/{path}"
    else:
        return f"{base_url}/tree/{branch}"


def is_valid_github_repo_format(repo_string: str) -> bool:
    """
    Check if string is in valid GitHub repo format.

    Args:
        repo_string: String to validate

    Returns:
        True if valid format, False otherwise
    """
    try:
        parse_github_url(repo_string)
        return True
    except GitHubError:
        return False