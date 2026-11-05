"""Offline regression coverage for snapshot, review, and publishing boundaries."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from agno.models.nebius import Nebius
from github.Commit import Commit
from github.PullRequest import PullRequest
from openai import OpenAI
from pydantic import ValidationError

import main
import review as module
from review import Finding, Review, Snapshot, added_lines, fetch_snapshot, inline_comments, publish

PATCH = "@@ -10,2 +10,3 @@\n context\n-old\n+new\n+++literal\n\\ No newline at end of file"


@pytest.fixture
def snapshot():
    return Snapshot("owner/repo", 1, "head", "base", "title", {"code.py": PATCH})


@pytest.fixture
def finding():
    return Finding(path="code.py", line=11, category="bug", explanation="A concrete defect")


@pytest.fixture
def github_client():
    client = MagicMock()
    pull = client.get_repo.return_value.get_pull.return_value
    pull.state = "open"
    pull.title = "title"
    pull.head.sha = "head"
    pull.base.sha = "base"
    pull.changed_files = 1
    pull.get_files.return_value = [SimpleNamespace(filename="code.py", patch=PATCH, additions=2)]
    return client, pull


def test_diff_hunk_offsets_removed_context_and_literal_plus():
    assert added_lines(PATCH) == {11, 12}
    assert added_lines("@@ -0,0 +1 @@\n+first\n@@ -30 +40 @@\n-old\n+last") == {1, 40}
    with pytest.raises(ValueError, match="hunk"):
        added_lines("@@ invalid @@")


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/o/r/pull/1",
        "https://github.com.evil.test/o/r/pull/1",
        "https://token@github.com/o/r/pull/1",
        "https://github.com/o/r/issues/1",
        "https://github.com/o/r/pull/0",
        "https://github.com/o/r/pull/1?secret=x",
    ],
)
def test_reject_noncanonical_urls(url):
    with pytest.raises(ValueError):
        module.parse_pr_url(url)


def test_fetch_snapshot_is_read_only_and_tracks_head_and_base(github_client):
    client, pull = github_client
    result, fetched = fetch_snapshot(client, "https://github.com/owner/repo/pull/1")
    assert result.patches == {"code.py": PATCH}
    assert result.head_sha == "head" and result.base_sha == "base"
    assert fetched is pull
    pull.create_review.assert_not_called()


@pytest.mark.parametrize(
    "change", ["closed", "files", "missing", "budget", "truncated", "file-list", "head", "base"]
)
def test_reject_incomplete_or_moving_snapshot(github_client, change):
    client, pull = github_client
    if change == "closed":
        pull.state = "closed"
    elif change == "files":
        pull.changed_files = 61
    elif change == "missing":
        pull.get_files.return_value[0].patch = None
    elif change == "budget":
        pull.get_files.return_value[0].patch = "+" * 100_001
    elif change == "truncated":
        pull.get_files.return_value[0].additions = 99
    elif change == "file-list":
        pull.changed_files = 2
    else:
        pull.update.side_effect = lambda: setattr(getattr(pull, change), "sha", "new")
    with pytest.raises(ValueError):
        fetch_snapshot(client, "https://github.com/owner/repo/pull/1")
    pull.create_review.assert_not_called()


def test_validate_only_added_right_side_and_no_duplicate_locations(snapshot, finding):
    review = Review(summary="summary", findings=[finding])
    assert inline_comments(snapshot, review)[0] == {
        "path": "code.py",
        "line": 11,
        "side": "RIGHT",
        "body": "**AI review · bug**\n\nA concrete defect",
    }
    for invalid in [
        finding.model_copy(update={"path": "absent.py"}),
        finding.model_copy(update={"line": 10}),
    ]:
        with pytest.raises(ValueError, match="outside"):
            inline_comments(snapshot, Review(summary="s", findings=[invalid]))
    with pytest.raises(ValueError, match="Duplicate"):
        inline_comments(snapshot, Review(summary="s", findings=[finding, finding]))


@pytest.mark.parametrize("change", ["head", "base", "closed"])
def test_recheck_before_publish(github_client, snapshot, finding, change):
    client, pull = github_client
    if change == "closed":
        pull.state = "closed"
    else:
        getattr(pull, change).sha = "new"
    with pytest.raises(ValueError, match="changed"):
        publish(client, pull, snapshot, Review(summary="s", findings=[finding]))
    pull.create_review.assert_not_called()


def test_publish_one_comment_review_on_exact_commit(github_client, snapshot, finding):
    client, pull = github_client
    pull.create_review.return_value.html_url = "https://github.com/review"
    result = publish(client, pull, snapshot, Review(summary="s", findings=[finding]))
    assert result == "https://github.com/review"
    client.get_repo.return_value.get_commit.assert_called_once_with("head")
    kwargs = pull.create_review.call_args.kwargs
    assert kwargs["event"] == "COMMENT"
    assert kwargs["comments"][0]["side"] == "RIGHT"
    assert "Tests were not executed" in kwargs["body"]


def test_real_pygithub_serializes_pinned_inline_review(snapshot, finding):
    requester = MagicMock()
    requester.requestJsonAndCheck.return_value = ({}, {"html_url": "https://github.com/review"})
    actual_pull = PullRequest(
        requester, {}, {"url": "https://api.github.com/repos/owner/repo/pulls/1"}, completed=True
    )
    commit = Commit(requester, {}, {"sha": "head"}, completed=True)
    actual_pull.create_review(
        commit=commit,
        body="AI-assisted review",
        event="COMMENT",
        comments=inline_comments(snapshot, Review(summary="s", findings=[finding])),
    )
    call = requester.requestJsonAndCheck.call_args
    assert call.args == ("POST", "https://api.github.com/repos/owner/repo/pulls/1/reviews")
    assert call.kwargs["input"]["commit_id"] == "head"
    assert call.kwargs["input"]["comments"][0]["line"] == 11


@pytest.mark.parametrize("post", [False, True])
def test_cli_default_no_write_post_explicit(
    monkeypatch, capsys, github_client, snapshot, finding, post
):
    client, pull = github_client
    monkeypatch.setenv("GITHUB_TOKEN", "test-only-token")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-only-key")
    monkeypatch.setenv("NEBIUS_MODEL", "test-model")
    monkeypatch.setattr("github.Github", lambda **_: client)
    client.__enter__.return_value = client
    monkeypatch.setattr(main, "fetch_snapshot", lambda *_: (snapshot, pull))
    monkeypatch.setattr(main, "analyze", lambda *_: Review(summary="s", findings=[finding]))
    publisher = MagicMock(return_value="https://github.com/review")
    monkeypatch.setattr(main, "publish", publisher)
    argv = ["https://github.com/owner/repo/pull/1"] + (["--post"] if post else [])
    assert main.main(argv) == 0
    assert publisher.call_count == int(post)
    if not post:
        assert "No GitHub writes" in capsys.readouterr().out


def test_offline_demo_rejects_post_and_never_uses_model(monkeypatch, capsys):
    monkeypatch.setattr(main, "analyze", MagicMock(side_effect=AssertionError("No model")))
    assert main.main(["--demo"]) == 0
    assert "offline fixture" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main.main(["--demo", "--post"])


def test_provider_exception_does_not_print_secret(monkeypatch, capsys):
    for key in ["GITHUB_TOKEN", "NEBIUS_API_KEY", "NEBIUS_MODEL"]:
        monkeypatch.setenv(key, "test-value")
    monkeypatch.setattr(main, "fetch_snapshot", MagicMock(side_effect=RuntimeError("secret-123")))
    assert main.main(["https://github.com/o/r/pull/1"]) == 1
    assert "secret-123" not in capsys.readouterr().out


def test_real_agno_provider_path_with_mock_http(monkeypatch, snapshot):
    """Exercise Agno's actual response parser/provider adapter without a paid model call."""
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        payload = {
            "id": "offline-response",
            "object": "chat.completion",
            "created": 0,
            "model": "offline-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": '{"summary":"Offline HTTP fixture","findings":[]}',
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        sdk = OpenAI(api_key="offline-key", http_client=transport)
        model = Nebius(id="offline-model", api_key="offline-key", client=sdk)
        monkeypatch.setattr("agno.models.nebius.Nebius", lambda **_: model)
        result = module.analyze(snapshot, "offline-key", "offline-model")
    assert result.summary == "Offline HTTP fixture"
    assert len(calls) == 1
    assert not calls[0].get("tools")
    assert snapshot.head_sha in json.dumps(calls[0]["messages"])


def test_response_rejects_unexpected_fields_or_invalid_location_types():
    fixture = json.loads(Path("demo.json").read_text())
    fixture["review"]["findings"][0]["line"] = "2"
    with pytest.raises(ValidationError):
        Review.model_validate(fixture["review"])
