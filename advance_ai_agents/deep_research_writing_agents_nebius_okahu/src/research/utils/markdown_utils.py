"""Markdown processing utilities."""


def markdown_collapsible(title: str, body: str) -> str:
    """Return a Markdown collapsible block using <details> / <summary>."""

    return f"<details>\n<summary>{title}</summary>\n\n{body.strip()}\n\n</details>\n"


def build_research_results_section(
    results: list[dict],
) -> str:
    """Build the Research Results section from a list of research results.

    Args:
        results: List of dicts with 'query', 'answer', and 'sources' keys.

    Returns:
        Formatted markdown string for the research results section.
    """

    if not results:
        return "## Research Results\n\n_No research results found._\n"

    blocks: list[str] = []
    for result in results:
        query = result.get("query", "Unknown query")
        answer = result.get("answer", "")
        sources = result.get("sources", [])

        body_parts = [answer]
        if sources:
            body_parts.append("\n\n**Sources:**")
            for src in sources:
                url = src.get("url", "")
                title = src.get("title", url)
                body_parts.append(f"- [{title}]({url})")

        body = "\n".join(body_parts)
        blocks.append(markdown_collapsible(query, body))

    return "## Research Results\n\n" + "\n".join(blocks)


def build_sources_section(
    section_title: str,
    sources: list[tuple[str, str]],
    empty_message: str,
) -> str:
    """Build a sources section from a list of title-body pairs.

    Args:
        section_title: Title for the section (e.g., "## YouTube Transcripts").
        sources: List of (title, body) tuples for each source.
        empty_message: Message to show when no sources are found.

    Returns:
        Formatted markdown string for the sources section.
    """

    if sources:
        blocks = [markdown_collapsible(title, body) for title, body in sources]
        return f"{section_title}\n\n" + "\n".join(blocks)

    return f"{section_title}\n\n_{empty_message}_\n"


def combine_research_sections(*sections: str) -> str:
    """Combine all research sections into a single markdown document.

    Args:
        *sections: Variable number of markdown section strings.

    Returns:
        Complete markdown document as a single string.
    """

    return "\n\n".join(["# Research", *sections])
