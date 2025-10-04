"""GitHub API client with authentication and error handling."""

from typing import Dict, List, Optional, Tuple
import logging
import requests

from aiohttp import ClientTimeout
import aiohttp
import asyncio
import base64

from ..core.config import settings
from ..core.exceptions import (GitHubAuthenticationError, GitHubError,
                               GitHubRateLimitError,
                               GitHubRepositoryNotFoundError)
from ..core.types import GitHubFileInfo
from .parser import build_github_api_url, parse_github_url

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client with authentication and error handling."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.github_api_key
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Doc-MCP/1.0",
        }

        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _handle_response_errors(self, response: requests.Response, repo_name: str):
        """Handle common GitHub API response errors."""
        if response.status_code == 404:
            raise GitHubRepositoryNotFoundError(f"Repository '{repo_name}' not found")
        elif response.status_code == 403:
            if "rate limit" in response.text.lower():
                raise GitHubRateLimitError("GitHub API rate limit exceeded")
            else:
                raise GitHubAuthenticationError(
                    "Access denied. Check token permissions"
                )
        elif response.status_code != 200:
            raise GitHubError(
                f"GitHub API error: {response.status_code} - {response.text}"
            )

    def get_repository_tree(
        self,
        repo_url: str,
        branch: str = "main",
        file_extensions: Optional[List[str]] = None,
        include_sha: bool = False,
    ) -> Tuple[List[str], str] | Tuple[List[Dict[str, str]], str]:
        """Get repository file tree with optional extension filtering."""

        if file_extensions is None:
            file_extensions = [".md", ".mdx"]

        try:
            owner, repo = parse_github_url(repo_url)
            repo_name = f"{owner}/{repo}"
        except Exception as e:
            raise GitHubError(f"Invalid repository URL: {e}") from e

        api_url = build_github_api_url(owner, repo, branch=branch)

        try:
            response = requests.get(
                api_url, headers=self.headers, timeout=settings.github_timeout
            )

            self._handle_response_errors(response, repo_name)

            data = response.json()
            filtered_files = []

            for item in data.get("tree", []):
                if item["type"] == "blob":
                    file_path = item["path"]
                    if any(
                        file_path.lower().endswith(ext.lower())
                        for ext in file_extensions
                    ):
                        if include_sha:
                            file_data = {"path": file_path, "sha": item["sha"]}
                            filtered_files.append(file_data)
                        else:
                            filtered_files.append(file_path)

            ext_str = ", ".join(file_extensions)
            message = f"Found {len(filtered_files)} files with extensions ({ext_str}) in {repo_name}/{branch}"

            logger.info(message)
            return filtered_files, message

        except requests.exceptions.Timeout:
            raise GitHubError(
                f"Request timeout after {settings.github_timeout} seconds"
            ) from None
        except requests.exceptions.RequestException as e:
            raise GitHubError(f"Network error: {str(e)}") from e

    async def get_file_content(
        self, repo_url: str, file_path: str, branch: str = "main"
    ) -> GitHubFileInfo:
        """Get single file content asynchronously."""

        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            raise GitHubError(f"Invalid repository URL: {e}") from e

        api_url = build_github_api_url(owner, repo, file_path, branch)

        timeout = ClientTimeout(total=settings.github_timeout)

        async with aiohttp.ClientSession(
            headers=self.headers, timeout=timeout
        ) as session:
            try:
                async with session.get(api_url) as response:
                    if response.status == 404:
                        raise GitHubRepositoryNotFoundError(
                            f"File not found: {file_path}"
                        )
                    elif response.status == 403:
                        raise GitHubRateLimitError("API rate limit exceeded")
                    elif response.status != 200:
                        raise GitHubError(
                            f"HTTP {response.status}: {await response.text()}"
                        )

                    data = await response.json()

                    if isinstance(data, list):
                        raise GitHubError(
                            f"Path {file_path} is a directory, not a file"
                        )

                    # Decode content
                    if data.get("encoding") == "base64":
                        try:
                            content_bytes = base64.b64decode(data["content"])
                            content_text = content_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            content_text = content_bytes.decode(
                                "latin-1", errors="ignore"
                            )
                    else:
                        raise GitHubError(
                            f"Unsupported encoding: {data.get('encoding')}"
                        )

                    return GitHubFileInfo(
                        path=file_path,
                        name=data.get("name", ""),
                        sha=data.get("sha", ""),
                        size=data.get("size", 0),
                        url=data.get("html_url", ""),
                        download_url=data.get("download_url", ""),
                        type=data.get("type", "file"),
                        encoding=data.get("encoding", ""),
                        content=content_text,
                    )
            except asyncio.TimeoutError:
                raise GitHubError(
                    f"Request timeout after {settings.github_timeout} seconds"
                ) from None
            except aiohttp.ClientError as e:
                raise GitHubError(f"Network error: {str(e)}") from e

    async def get_multiple_files(
        self,
        repo_url: str,
        file_paths: List[str],
        branch: str = "main",
        max_concurrent: int = None,
    ) -> Tuple[List[GitHubFileInfo], List[str]]:
        """Get multiple files concurrently."""

        if max_concurrent is None:
            max_concurrent = settings.github_concurrent_requests

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_single_file(
            file_path: str,
        ) -> Tuple[Optional[GitHubFileInfo], Optional[str]]:
            async with semaphore:
                try:
                    file_info = await self.get_file_content(repo_url, file_path, branch)
                    return file_info, None
                except Exception as e:
                    logger.error(f"Failed to fetch {file_path}: {e}")
                    return None, file_path

        # Execute all file fetches concurrently
        tasks = [fetch_single_file(path) for path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        successful_files = []
        failed_files = []

        for file_info, failed_path in results:
            if file_info:
                successful_files.append(file_info)
            elif failed_path:
                failed_files.append(failed_path)

        logger.info(
            f"Fetched {len(successful_files)} files successfully, {len(failed_files)} failed"
        )
        return successful_files, failed_files


# Global GitHub client instance
github_client = GitHubClient()