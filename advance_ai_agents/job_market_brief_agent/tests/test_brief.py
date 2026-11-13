"""Offline tests: no network, no API keys."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

FIXTURE = ROOT / "fixtures" / "sample_jobs.json"


def records():
    return main.normalize(main.load_fixture(FIXTURE))


def test_normalize_drops_rows_without_title_and_numbers_the_rest():
    recs = records()
    assert [r.n for r in recs] == [1, 2, 3, 4, 5, 6]
    assert all(r.title for r in recs)


def test_seniority_labels():
    recs = {r.title: r.seniority for r in records()}
    assert recs["Senior Data Engineer"] == "senior"
    assert recs["Staff Data Engineer, Platform"] == "staff+"
    assert recs["Junior Data Engineer"] == "junior"
    assert recs["Data Engineer II"] == "mid"


def test_skills_are_counted_across_postings():
    s = main.summarize(records())
    top = dict(s["skills"])
    assert set(top["Python"]) == {1, 3, 4, 5}
    assert set(top["SQL"]) == {1, 4, 5, 6}
    assert "Snowflake" in top and len(top["Snowflake"]) == 2


def test_company_grouping_orders_by_count_then_name():
    s = main.summarize(records())
    assert s["companies"][0] == ("Harbor Analytics", [1, 2])
    assert s["companies"][1] == ("Pecan Street Robotics", [3, 6])


def test_extensions_fallback_and_url_cleaning():
    rows = [{
        "title": "Data Engineer",
        "company_name": "Acme",
        "location": "Austin, TX",
        "extensions": ["3 days ago", "Full-time", "Health insurance"],
        "share_link": "https://example.com/job/1?utm_campaign=google_jobs_apply&utm_source=x&ref=keep",
    }]
    r = main.normalize(rows)[0]
    assert r.posted == "3 days ago"
    assert r.schedule == "Full-time"
    assert r.url == "https://example.com/job/1?ref=keep"


def test_url_keeps_fragment_and_fields_stay_on_one_line():
    assert main.clean_url("https://example.com/apply?utm_source=jobs#opening/123") == "https://example.com/apply#opening/123"
    assert main.clean_url("https://example.com/apply?utm_source=jobs") == "https://example.com/apply"
    rows = [{
        "title": "Data\nEngineer",
        "company_name": "  Acme\n  Corp ",
        "apply_options": [{"title": "Careers page"}, {"title": "Board", "link": "https://example.com/second"}],
        "share_link": "https://example.com/share",
    }]
    r = main.normalize(rows)[0]
    assert r.title == "Data Engineer"
    assert r.company == "Acme Corp"
    assert r.url == "https://example.com/second"


def test_brief_cites_records_and_lists_them():
    brief = main.render_brief("data engineer", "Austin, TX", "7d", records())
    assert "# Job market brief: data engineer in Austin, TX" in brief
    assert "- Harbor Analytics: 2 postings [1] [2]" in brief
    assert "[1] Senior Data Engineer, Harbor Analytics; Austin, TX; 2 days ago; Full-time (https://www.linkedin.com/jobs/view/0000000001)" in brief
    assert "## Model brief" not in brief


def test_empty_result_says_so():
    brief = main.render_brief("unicorn wrangler", "Nowhere", "24h", [])
    assert "returned no postings" in brief
    assert "## Records" not in brief


def test_cli_runs_offline(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    out = tmp_path / "brief.md"
    code = main.main(["data engineer", "--location", "Austin, TX", "--fixture", str(FIXTURE), "--out", str(out), "--json"])
    assert code == 0
    printed = capsys.readouterr().out
    written = out.read_text()
    assert written.startswith("# Job market brief")
    assert "from the fixture file" in written
    tail = printed[printed.index("[\n"):]
    assert len(json.loads(tail)) == 6


def test_cli_applies_limit_to_fixture_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    big = tmp_path / "many.json"
    big.write_text(json.dumps([{"title": f"Data Engineer {i}", "company_name": "Acme"} for i in range(15)]))
    out = tmp_path / "brief.md"
    assert main.main(["data engineer", "--fixture", str(big), "--limit", "10", "--out", str(out)]) == 0
    assert "10 postings from the fixture file" in out.read_text()


def test_limit_outside_range_is_rejected_before_any_call(capsys):
    for bad in ("0", "-1", "9", "101"):
        with pytest.raises(SystemExit) as exc:
            main.main(["data engineer", "--fixture", str(FIXTURE), "--limit", bad])
        assert exc.value.code == 2
        assert "between 10 and 100" in capsys.readouterr().err


def test_live_path_sends_actor_input_and_cuts_rows_to_limit(monkeypatch, capsys):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    canned = [{"title": f"Data Engineer {i}", "company_name": "Acme", "share_link": f"https://example.com/{i}"} for i in range(12)]
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(canned).encode()

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["payload"] = json.loads(req.data.decode())
        return FakeResponse()

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    code = main.main(["data engineer", "--location", "Austin, TX", "--posted-within", "3d", "--limit", "10", "--json"])
    assert code == 0
    assert seen["payload"] == {"query": "data engineer", "location": "Austin, TX", "posted_within": "3d", "num_results": 10, "max_pagination": 1}
    assert seen["url"].startswith(main.APIFY_RUN_URL) and "token=test-token" in seen["url"]
    printed = capsys.readouterr().out
    assert "10 postings from the last 3 days" in printed
    tail = printed[printed.index("[\n"):]
    assert len(json.loads(tail)) == 10


def test_cli_without_token_or_fixture_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    assert main.main(["data engineer"]) == 2
    assert "APIFY_API_TOKEN" in capsys.readouterr().err
