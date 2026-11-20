"""Regressions for the maintainer's real-provider review failures, using offline fixtures."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import main
from review import Finding, Review, Snapshot, inline_comments, publish, review_prompt


@pytest.fixture
def snapshot():
    """Use multiple hunks, changed lines, context, removals and a literal plus prefix."""
    return Snapshot(
        "owner/repo",
        387,
        "head",
        "base",
        "Untrusted title",
        {
            "agent.py": "@@ -74,2 +75,3 @@\n context\n-old\n+new\n+++literal"
            "\n@@ -100 +110,2 @@\n-old\n+last\n+tail"
        },
    )


def finding(line=76, **overrides):
    """Build a schema-valid provider finding whose location still needs validation."""
    return Finding(
        **{
            "path": "agent.py",
            "line": line,
            "category": "bug",
            "explanation": "Fix this defect",
            **overrides,
        }
    )


def test_prompt_numbers_new_file_lines_across_hunks(snapshot):
    """Give the model explicit coordinates instead of asking it to count patch records."""
    prompt = json.loads(review_prompt(snapshot))
    assert prompt["patches"]["agent.py"] == (
        "@@ -74,2 +75,3 @@\nL75  context\n-old\nL76 +new\nL77 +++literal"
        "\n@@ -100 +110,2 @@\n-old\nL110 +last\nL111 +tail"
    )
    assert snapshot.patches["agent.py"].startswith("@@ -74,2 +75,3 @@\n context")


@pytest.mark.parametrize("separator", ["\r", "\u2028", "\x85"])
def test_numbering_keeps_source_separators_inside_one_record(separator):
    """Avoid shifting positions when code contains Unicode separators rather than LF."""
    snapshot = Snapshot("o/r", 1, "h", "b", "t", {"a": f"@@ -0,0 +1,2 @@\n+a{separator}b\n+c"})
    assert json.loads(review_prompt(snapshot))["patches"]["a"] == (
        f"@@ -0,0 +1,2 @@\nL1 +a{separator}b\nL2 +c"
    )


def test_bad_locations_do_not_discard_valid_findings(snapshot):
    """Keep a valid public-PR finding when the model also reports unchanged or absent lines."""
    review = Review(
        summary="summary",
        findings=[
            finding(75),
            finding(path="absent.py"),
            finding(),
            finding(110),
            finding(1000),
        ],
    )
    comments = inline_comments(snapshot, review)
    assert [(c["path"], c["line"]) for c in comments] == [("agent.py", 76), ("agent.py", 110)]
    assert all(c["side"] == "RIGHT" for c in comments)


def test_duplicate_locations_combine_distinct_findings_once(snapshot):
    """Send one GitHub comment per line while preserving distinct issues on that line."""
    review = Review(
        summary="summary",
        findings=[
            finding(),
            finding(category="missing-test", explanation="Add a regression test"),
            finding(),
            finding(111),
        ],
    )
    comments = inline_comments(snapshot, review)
    assert [c["line"] for c in comments] == [76, 111]
    assert comments[0]["body"].count("Fix this defect") == 1
    assert "missing-test" in comments[0]["body"]
    assert "Add a regression test" in comments[0]["body"]


@pytest.mark.parametrize("post", [False, True])
def test_preview_and_post_use_same_filtered_comments(snapshot, monkeypatch, capsys, post):
    """Expose filtering counts and ensure neither preview nor publication includes bad locations."""
    for name in ("GITHUB_TOKEN", "NEBIUS_API_KEY", "NEBIUS_MODEL"):
        monkeypatch.setenv(name, "offline-placeholder")
    client = MagicMock()
    pull = MagicMock(
        state="open", head=SimpleNamespace(sha="head"), base=SimpleNamespace(sha="base")
    )
    pull.create_review.return_value.html_url = "https://github.com/review"
    client.__enter__.return_value = client
    monkeypatch.setattr("github.Github", lambda **_: client)
    monkeypatch.setattr(main, "fetch_snapshot", lambda *_: (snapshot, pull))
    review = Review(summary="summary", findings=[finding(75), finding(), finding(), finding(111)])
    monkeypatch.setattr(main, "analyze", lambda *_: review)
    assert main.main(["https://github.com/owner/repo/pull/387"] + (["--post"] if post else [])) == 0
    output = capsys.readouterr().out
    preview, _ = json.JSONDecoder().raw_decode(output)
    assert preview["dropped_findings"] == 1
    assert preview["merged_findings"] == 1
    assert [c["line"] for c in preview["comments"]] == [76, 111]
    if post:
        pull.create_review.assert_called_once()
        kwargs = pull.create_review.call_args.kwargs
        assert kwargs["comments"] == preview["comments"]
        assert "1 findings dropped; 1 duplicate locations merged" in kwargs["body"]
        assert kwargs["event"] == "COMMENT"
    else:
        pull.create_review.assert_not_called()
        assert "No GitHub writes" in output


def test_all_invalid_findings_can_still_publish_summary(snapshot):
    """A useful summary survives even if there are no valid inline findings."""
    client = MagicMock()
    pull = MagicMock(
        state="open", head=SimpleNamespace(sha="head"), base=SimpleNamespace(sha="base")
    )
    review = Review(summary="A summary worth reviewing", findings=[finding(75)])
    publish(client, pull, snapshot, review)
    kwargs = pull.create_review.call_args.kwargs
    assert kwargs["comments"] == []
    assert review.summary in kwargs["body"]


@pytest.mark.parametrize("kind", ["value", "schema"])
def test_cli_explains_validation_errors_without_credentials_or_model_input(
    monkeypatch,
    capsys,
    kind,
):
    """Distinguish a moving PR from empty structured output without dumping private input."""
    monkeypatch.setenv("GITHUB_TOKEN", "private-github-token")
    monkeypatch.setenv("NEBIUS_API_KEY", "private-nebius-key")
    monkeypatch.setenv("NEBIUS_MODEL", "offline-model")
    if kind == "schema":
        try:
            Review.model_validate({"summary": {"private": "model-input-secret"}})
        except ValidationError as error:
            failure = error
    else:
        failure = ValueError("PR changed; private-github-token private-nebius-key")
    monkeypatch.setattr(main, "fetch_snapshot", MagicMock(side_effect=failure))
    assert main.main(["https://github.com/owner/repo/pull/387"]) == 1
    output = capsys.readouterr().out
    assert "summary" in output if kind == "schema" else "PR changed" in output
    for secret in ["private-github-token", "private-nebius-key", "model-input-secret"]:
        assert secret not in output
