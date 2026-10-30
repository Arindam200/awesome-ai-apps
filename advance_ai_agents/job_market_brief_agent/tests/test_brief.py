"""Offline tests: no network, no API keys."""

import json
import sys
from pathlib import Path

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
    assert set(top["SQL"]) >= {1, 4, 5, 6}
    assert "Snowflake" in top and len(top["Snowflake"]) == 2


def test_company_grouping_orders_by_count_then_name():
    s = main.summarize(records())
    assert s["companies"][0] == ("Harbor Analytics", [1, 2])
    assert s["companies"][1] == ("Pecan Street Robotics", [3, 6])


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
    assert out.read_text().startswith("# Job market brief")
    tail = printed[printed.index("[\n"):]
    assert len(json.loads(tail)) == 6


def test_cli_without_token_or_fixture_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    assert main.main(["data engineer"]) == 2
    assert "APIFY_API_TOKEN" in capsys.readouterr().err
