from markdown_utils import clean_markdown_response


def test_clean_markdown_response_preserves_fenced_code_blocks():
    response = (
        "Answer:\n\n"
        "```python\n"
        "****\n"
        "__ __\n"
        "***\n"
        "\n\n\n"
        "```\n\n"
        "Done."
    )

    assert clean_markdown_response(response) == (
        "Answer:\n\n"
        "```python\n"
        "****\n"
        "__ __\n"
        "***\n"
        "\n\n\n"
        "```\n\n"
        "Done."
    )


def test_clean_markdown_response_preserves_horizontal_rules_and_markers():
    response = "Before\n\n***\n****\n____\n___\n**  **\n__ __\nAfter"

    assert clean_markdown_response(response) == "Before\n\n***\n****\n____\n___\n\nAfter"


def test_clean_markdown_response_cleans_only_non_code_text():
    response = "**  **\n\n\n```text\n**  **\n\n\n```\n\n\nAfter"

    assert clean_markdown_response(response) == "```text\n**  **\n\n\n```\n\n\nAfter"
