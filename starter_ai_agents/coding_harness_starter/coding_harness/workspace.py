"""Strict read-only workspace access and text-file policy."""

from __future__ import annotations

from pathlib import Path, PurePath


MAX_FILE_BYTES = 256 * 1024
MAX_TOOL_OUTPUT_CHARS = 12_000
MAX_LISTED_FILES = 500
MAX_SEARCH_RESULTS = 100

ALLOWED_SUFFIXES = frozenset(
    {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".ini", ".cfg"}
)
IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "build",
        "dist",
    }
)
SENSITIVE_FILE_NAMES = frozenset(
    {
        ".env",
        "credentials",
        "credentials.json",
        "credential.json",
        "secrets.json",
        "secret.json",
        "token.json",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".pfx", ".p12", ".crt", ".cer"})


class WorkspaceError(ValueError):
    """A requested workspace access violates the fixed local policy."""


class Workspace:
    """A single, resolved workspace root with read-only inspection methods."""

    def __init__(self, root: str | Path) -> None:
        supplied_root = Path(root).expanduser()
        if not supplied_root.exists() or not supplied_root.is_dir():
            raise WorkspaceError("workspace must be an existing directory")
        self.root = supplied_root.resolve(strict=True)

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def resolve_path(
        self, relative_path: str | Path, *, require_exists: bool = False
    ) -> Path:
        """Resolve one relative path without traversing any symlink.

        The checks are repeated by callers immediately before each real access;
        ``resolve`` alone is not enough because it silently follows symlinks.
        """

        raw_path = str(relative_path)
        if "\x00" in raw_path:
            raise WorkspaceError("path cannot contain NUL bytes")
        raw = Path(relative_path)
        if (
            not raw_path
            or raw.is_absolute()
            or PurePath(relative_path).drive
            or raw.anchor
        ):
            raise WorkspaceError("path must be a non-empty relative workspace path")
        if any(part in {"", ".", ".."} for part in raw.parts):
            raise WorkspaceError("path cannot contain '.' or '..'")
        if any(_is_ignored_directory(part) for part in raw.parts[:-1]):
            raise WorkspaceError("path is inside an ignored directory")
        candidate = self.root.joinpath(*raw.parts)

        # Inspect every existing component before resolving.  A non-existent
        # leaf is valid for create, but creates are limited to an existing parent.
        current = self.root
        for part in raw.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    raise WorkspaceError(
                        "paths and parent directories cannot be symbolic links"
                    )
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.root)
        except ValueError as error:
            raise WorkspaceError(
                "path resolves outside the locked workspace"
            ) from error
        if require_exists and not candidate.exists():
            raise WorkspaceError("target file does not exist")
        return candidate

    def validate_text_path(
        self, relative_path: str | Path, *, require_exists: bool = False
    ) -> Path:
        path = self.resolve_path(relative_path, require_exists=require_exists)
        name = path.name.lower()
        if name in SENSITIVE_FILE_NAMES or name.startswith(".env."):
            raise WorkspaceError("sensitive files cannot be read or modified")
        if path.suffix.lower() in SENSITIVE_SUFFIXES:
            raise WorkspaceError(
                "credential and certificate files cannot be read or modified"
            )
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise WorkspaceError(
                "file extension is not allowed by the text-file policy"
            )
        return path

    def validate_text_content(self, content: str) -> None:
        if "\x00" in content:
            raise WorkspaceError("NUL bytes are not allowed in text files")
        try:
            encoded = content.encode("utf-8")
        except UnicodeEncodeError as error:
            raise WorkspaceError("content must be UTF-8 encodable") from error
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError(f"text file exceeds {MAX_FILE_BYTES} byte limit")

    def read_text_path(self, relative_path: str | Path) -> tuple[Path, str]:
        """Return a policy-checked full file without applying tool truncation."""

        path = self.validate_text_path(relative_path, require_exists=True)
        if not path.is_file():
            raise WorkspaceError("target must be a regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError(f"text file exceeds {MAX_FILE_BYTES} byte limit")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise WorkspaceError("only UTF-8 text files are allowed") from error
        self.validate_text_content(content)
        return path, content

    def list_files(self) -> list[str]:
        """List a bounded set of permitted relative file names."""

        files: list[str] = []
        used_chars = 0
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root)
            if any(_is_ignored_directory(part) for part in relative.parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            try:
                self.read_text_path(relative)
            except WorkspaceError:
                continue
            relative_text = relative.as_posix()
            if used_chars + len(relative_text) > MAX_TOOL_OUTPUT_CHARS:
                break
            files.append(relative_text)
            used_chars += len(relative_text)
            if len(files) >= MAX_LISTED_FILES:
                break
        return files

    def read_file(self, relative_path: str | Path) -> str:
        _, content = self.read_text_path(relative_path)
        return content[:MAX_TOOL_OUTPUT_CHARS]

    def search_text(self, query: str) -> list[dict[str, object]]:
        if not query:
            raise WorkspaceError("search text cannot be empty")
        results: list[dict[str, object]] = []
        used_chars = 0
        for relative in self.list_files():
            # Bound the returned snippets, not the inspected portion of a valid
            # file.  Otherwise a match after the read-tool display limit would
            # be silently missed.
            _, content = self.read_text_path(relative)
            for line_number, line in enumerate(content.splitlines(), start=1):
                if query not in line:
                    continue
                remaining = MAX_TOOL_OUTPUT_CHARS - used_chars
                if remaining <= 0:
                    return results
                snippet = _bounded_match_snippet(line, query, remaining)
                results.append({"path": relative, "line": line_number, "text": snippet})
                used_chars += len(snippet)
                if len(results) >= MAX_SEARCH_RESULTS:
                    return results
        return results


def _is_ignored_directory(name: str) -> bool:
    """Apply the fixed directory policy consistently on all platforms.

    Case-insensitive filesystems otherwise allow paths such as ``.GIT`` or
    ``NODE_MODULES`` to bypass a policy written with the common lowercase
    spellings.
    """

    return name.casefold() in IGNORED_DIRECTORY_NAMES


def _bounded_match_snippet(line: str, query: str, limit: int) -> str:
    """Return at most ``limit`` characters while retaining the matched text."""

    if len(line) <= limit:
        return line
    match_start = line.find(query)
    if len(query) >= limit:
        return query[:limit]
    start = max(0, match_start - (limit - len(query)))
    return line[start : start + limit]
