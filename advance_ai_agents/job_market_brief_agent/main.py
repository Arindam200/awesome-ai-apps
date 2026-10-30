"""Job market brief agent.

Takes a role and a location, pulls the postings Google Jobs lists for that
search, turns them into numbered evidence records, and writes a short brief:
who is hiring, at what level, and which skills keep coming up. Every line of
the brief points at the record it came from, so a reader can open the posting.

Two steps, both optional in the sense that the example still runs without them:

* Collection runs the Google Jobs Actor on Apify (needs APIFY_API_TOKEN). With
  --fixture the records come from a JSON file instead and no network is used.
* Narrative runs a Nebius Token Factory chat model over the records (needs
  NEBIUS_API_KEY). Without it the brief is the deterministic one built here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

ACTOR_ID = "johnvc~Google-Jobs-Scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
NEBIUS_CHAT_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
DEFAULT_NEBIUS_MODEL = "Qwen/Qwen3-30B-A3B"
POSTED_WITHIN = ("any", "24h", "3d", "7d", "30d")

SENIORITY_RULES = (
    ("intern", re.compile(r"\b(intern|internship|co-op)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|entry[- ]level|associate|graduate)\b", re.I)),
    ("staff+", re.compile(r"\b(staff|principal|distinguished|architect|director|head of|vp)\b", re.I)),
    ("lead", re.compile(r"\b(lead|manager)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?)\b", re.I)),
)

# Terms counted when they appear in a posting's qualifications or description.
# Matched case-insensitively on word boundaries; the display form is kept.
SKILL_TERMS = (
    "Python", "Java", "TypeScript", "JavaScript", "Go", "Rust", "C++", "C#", "Scala",
    "SQL", "PostgreSQL", "MySQL", "Snowflake", "BigQuery", "Spark", "Kafka", "Airflow", "dbt",
    "AWS", "Azure", "GCP", "Kubernetes", "Docker", "Terraform", "Linux",
    "React", "Node.js", "Django", "FastAPI", "GraphQL", "REST",
    "PyTorch", "TensorFlow", "LLM", "RAG", "NLP", "Machine Learning", "Deep Learning", "MLOps",
    "Tableau", "Power BI", "Looker", "Excel",
    "Figma", "Agile", "Scrum", "CI/CD", "Git",
    "Security Clearance", "PhD", "Master's", "Bachelor's",
)


@dataclass
class Record:
    """One posting, flattened to the fields the brief uses."""

    n: int
    title: str
    company: str
    location: str
    posted: str
    schedule: str
    via: str
    seniority: str
    qualifications: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    url: str = ""


SCHEDULE_WORDS = {"full-time", "part-time", "contractor", "internship", "temporary", "per diem", "volunteer"}


def clean_url(url: str) -> str:
    """Drop tracking parameters (utm_*) so citations stay short and stable."""
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    kept = [p for p in query.split("&") if p and not p.lower().startswith("utm_")]
    return base + ("?" + "&".join(kept) if kept else "")


def read_key(name: str, environ: dict[str, str] | None = None) -> str | None:
    value = (environ if environ is not None else os.environ).get(name, "").strip()
    return value or None


def seniority_of(title: str) -> str:
    for label, pattern in SENIORITY_RULES:
        if pattern.search(title):
            return label
    return "mid"


def skills_in(text: str) -> list[str]:
    found = []
    for term in SKILL_TERMS:
        pattern = r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])"
        if re.search(pattern, text, re.I):
            found.append(term)
    return found


def normalize(rows: list[dict]) -> list[Record]:
    """Turn raw Actor rows into numbered records. Rows without a title are dropped."""
    records: list[Record] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        highlights = row.get("job_highlights") or []
        qualifications: list[str] = []
        for block in highlights:
            if str(block.get("title", "")).lower().startswith("qualif"):
                qualifications.extend(str(x).strip() for x in block.get("items", []) if str(x).strip())
        detected = row.get("detected_extensions") or {}
        posted = str(detected.get("posted_at") or "").strip()
        schedule = str(detected.get("schedule_type") or "").strip()
        # Some rows only carry the plain "extensions" strings Google shows under
        # the title, such as "3 days ago" or "Full-time". Use them as a fallback.
        for ext in row.get("extensions") or []:
            ext = str(ext).strip()
            if not posted and re.search(r"\b(ago|today|yesterday)\b", ext, re.I):
                posted = ext
            elif not schedule and ext.lower() in SCHEDULE_WORDS:
                schedule = ext
        apply_options = row.get("apply_options") or []
        url = ""
        if apply_options and isinstance(apply_options[0], dict):
            url = apply_options[0].get("link") or ""
        url = clean_url(url or row.get("share_link") or "")
        text = " ".join([title, " ".join(qualifications), row.get("description") or ""])
        records.append(
            Record(
                n=len(records) + 1,
                title=title,
                company=(row.get("company_name") or "unknown").strip(),
                location=(row.get("location") or "").strip(),
                posted=posted,
                schedule=schedule,
                via=(row.get("via") or "").replace("via ", "").strip(),
                seniority=seniority_of(title),
                qualifications=qualifications[:8],
                skills=skills_in(text),
                url=url,
            )
        )
    return records


def summarize(records: list[Record]) -> dict:
    by_company: dict[str, list[int]] = defaultdict(list)
    by_seniority: Counter[str] = Counter()
    skill_refs: dict[str, list[int]] = defaultdict(list)
    for r in records:
        by_company[r.company].append(r.n)
        by_seniority[r.seniority] += 1
        for s in r.skills:
            skill_refs[s].append(r.n)
    companies = sorted(by_company.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    skills = sorted(skill_refs.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return {
        "total": len(records),
        "companies": companies,
        "seniority": by_seniority.most_common(),
        "skills": [(s, refs) for s, refs in skills if len(refs) >= 2][:15],
    }


def cite(ns: list[int]) -> str:
    return " ".join(f"[{n}]" for n in ns)


def render_brief(role: str, location: str, posted_within: str, records: list[Record], model_text: str | None = None) -> str:
    lines = [f"# Job market brief: {role} in {location}", ""]
    window = {"any": "any time", "24h": "the last 24 hours", "3d": "the last 3 days", "7d": "the last 7 days", "30d": "the last 30 days"}[posted_within]
    if not records:
        lines += [f"Google Jobs returned no postings for this search in {window}. Nothing to summarize.", ""]
        return "\n".join(lines)
    s = summarize(records)
    lines += [f"{s['total']} postings from {window}. Numbers in brackets point at the records below.", ""]
    lines += ["## Who is hiring", ""]
    for company, ns in s["companies"][:12]:
        lines.append(f"- {company}: {len(ns)} posting{'s' if len(ns) != 1 else ''} {cite(ns)}")
    lines += ["", "## Seniority mix", ""]
    for label, count in s["seniority"]:
        lines.append(f"- {label}: {count}")
    lines += ["", "## Skills that recur", ""]
    if s["skills"]:
        for skill, ns in s["skills"]:
            lines.append(f"- {skill}: {len(ns)} postings {cite(ns)}")
    else:
        lines.append("- No skill term appears in more than one posting.")
    if model_text:
        lines += ["", "## Model brief", "", model_text.strip()]
    lines += ["", "## Records", ""]
    for r in records:
        bits = [f"[{r.n}] {r.title}, {r.company}"]
        if r.location:
            bits.append(r.location)
        if r.posted:
            bits.append(r.posted)
        if r.schedule:
            bits.append(r.schedule)
        line = "; ".join(bits)
        if r.url:
            line += f" ({r.url})"
        lines.append(f"- {line}")
    lines.append("")
    return "\n".join(lines)


def fetch_jobs(role: str, location: str, posted_within: str, limit: int, token: str, timeout: int = 300) -> list[dict]:
    """Run the Actor synchronously and return its dataset items."""
    payload = {
        "query": role,
        "location": location,
        "posted_within": posted_within,
        "num_results": max(10, min(limit, 100)),
        "max_pagination": max(1, -(-limit // 10)),
    }
    query = urllib.parse.urlencode({"token": token, "timeout": timeout, "format": "json", "clean": "true"})
    req = urllib.request.Request(
        f"{APIFY_RUN_URL}?{query}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
            rows = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise SystemExit(f"Apify returned HTTP {e.code}: {detail}") from None
    if not isinstance(rows, list):
        raise SystemExit("Unexpected Apify response shape")
    return rows[:limit]


def model_brief(role: str, location: str, records: list[Record], api_key: str, model: str, timeout: int = 120) -> str:
    evidence = "\n".join(
        f"[{r.n}] {r.title} at {r.company} ({r.location}; {r.seniority}; posted {r.posted or 'n/a'}). "
        f"Qualifications: {'; '.join(r.qualifications) or 'none listed'}"
        for r in records
    )
    prompt = (
        f"You are writing a hiring-market brief for the role '{role}' in {location}.\n"
        "Use only the numbered records below. Write at most 150 words in plain prose: which employers are "
        "hiring most, the seniority the market is asking for, and three to five skills that recur. After every "
        "claim put the record numbers it rests on in square brackets, like [3] or [3][7]. If the records do not "
        "support a claim, leave it out.\n\n" + evidence
    )
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 400}
    req = urllib.request.Request(
        NEBIUS_CHAT_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    text = data["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def load_fixture(path: Path) -> list[dict]:
    with path.open() as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("items", [])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("role", help="job title or search phrase, for example 'data engineer'")
    p.add_argument("--location", default="Austin, TX", help="city, state or country (default: Austin, TX)")
    p.add_argument("--posted-within", choices=POSTED_WITHIN, default="7d", help="how fresh the postings must be (default: 7d)")
    p.add_argument("--limit", type=int, default=30, help="most postings to collect, 10 to 100 (default: 30)")
    p.add_argument("--fixture", type=Path, help="read postings from this JSON file instead of calling Apify")
    p.add_argument("--no-model", action="store_true", help="skip the Nebius step even if NEBIUS_API_KEY is set")
    p.add_argument("--out", type=Path, help="write the brief to this file as well as stdout")
    p.add_argument("--json", action="store_true", help="also print the normalized records as JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture:
        rows = load_fixture(args.fixture)
    else:
        token = read_key("APIFY_API_TOKEN")
        if not token:
            print("Set APIFY_API_TOKEN, or pass --fixture to run offline.", file=sys.stderr)
            return 2
        rows = fetch_jobs(args.role, args.location, args.posted_within, args.limit, token)
    records = normalize(rows)

    narrative = None
    nebius_key = read_key("NEBIUS_API_KEY")
    if records and nebius_key and not args.no_model:
        model = read_key("NEBIUS_MODEL") or DEFAULT_NEBIUS_MODEL
        try:
            narrative = model_brief(args.role, args.location, records, nebius_key, model)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            print(f"Nebius step skipped: {e}", file=sys.stderr)

    brief = render_brief(args.role, args.location, args.posted_within, records, narrative)
    print(brief)
    if args.out:
        args.out.write_text(brief)
    if args.json:
        print(json.dumps([asdict(r) for r in records], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
