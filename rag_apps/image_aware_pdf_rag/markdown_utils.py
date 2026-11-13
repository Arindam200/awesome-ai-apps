"""Helpers for cleaning model-generated Markdown responses."""

import re


def clean_markdown_response(text: str) -> str:
    """Remove empty bold markers outside fenced code and normalize excess blank lines."""
    if not text:
        return ""

    parts: list[tuple[bool, str]] = []
    plain_lines: list[str] = []
    code_lines: list[str] = []
    fence_char = ""
    fence_length = 0

    for line in text.splitlines(keepends=True):
        if not fence_char:
            opening_fence = re.match(r" {0,3}(`{3,}|~{3,})", line)
            if opening_fence:
                if plain_lines:
                    parts.append((False, "".join(plain_lines)))
                    plain_lines.clear()
                fence = opening_fence.group(1)
                fence_char = fence[0]
                fence_length = len(fence)
                code_lines.append(line)
            else:
                plain_lines.append(line)
            continue

        code_lines.append(line)
        closing_pattern = (
            rf" {{0,3}}{re.escape(fence_char)}{{{fence_length},}}"
            r"[ \t]*(?:\r?\n)?$"
        )
        if re.match(closing_pattern, line):
            parts.append((True, "".join(code_lines)))
            code_lines.clear()
            fence_char = ""
            fence_length = 0

    if code_lines:
        parts.append((True, "".join(code_lines)))
    if plain_lines:
        parts.append((False, "".join(plain_lines)))

    cleaned_parts: list[str] = []
    for index, (is_code, part) in enumerate(parts):
        if is_code:
            cleaned_parts.append(part)
            continue

        part = re.sub(
            r"(?<!\S)\*\*[ \t]+\*\*(?!\S)|(?<!\S)__[ \t]+__(?!\S)",
            "",
            part,
        )
        part = re.sub(r"\n{3,}", "\n\n", part)
        if index == 0:
            part = part.lstrip()
        if index == len(parts) - 1:
            part = part.rstrip()
        cleaned_parts.append(part)

    return "".join(cleaned_parts)
