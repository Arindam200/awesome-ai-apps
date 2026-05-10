"""
nebius_agent.py — Nebius-powered AutoResearch agent.

Autonomously optimises solve.py by calling DeepSeek-R1 on Nebius to propose
code changes, running the benchmark for real scores, and keeping only the
improvements. Same loop pattern as Karpathy's autoresearch, different domain.

Usage:
    export NEBIUS_API_KEY="your-key"

    python nebius_agent.py --setup-branch mar30 --n-experiments 20
    python nebius_agent.py                      # run indefinitely
    python nebius_agent.py --dry-run             # see proposals without running
    python nebius_agent.py --batch --n-experiments 10   # 50% cheaper via batch API
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from openai import OpenAI
import subprocess, os, re, time, argparse, ast, json, uuid

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY")
)

MODEL       = "Qwen/Qwen3-235B-A22B-Thinking-2507"
SOLVE_PY    = "solve.py"
RESULTS_TSV = "results.tsv"
RUN_LOG     = "run.log"
RUN_TIMEOUT = 120  # seconds: 30s budget + data gen + overhead
MAX_TOKENS  = 16384  # R1 needs ~3K for thinking + ~4K for full solve.py

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*",          "", text, flags=re.DOTALL)
    return text.strip()

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def parse_metric(log: str, key: str) -> float | None:
    m = re.search(rf"^{re.escape(key)}:\s+(\S+)", log, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────────────────────────────────────

def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()

def git_commit(message: str) -> str:
    git("add", SOLVE_PY)
    git("commit", "-m", message)
    return git("rev-parse", "--short", "HEAD")

def git_reset_hard() -> None:
    git("reset", "--hard", "HEAD~1")

def setup_branch(tag: str) -> None:
    branch = f"autoresearch/{tag}"
    git("checkout", "-b", branch)
    print(f"✅ Created branch: {branch}")

# ─────────────────────────────────────────────────────────────────────────────
# Results log
# ─────────────────────────────────────────────────────────────────────────────

HEADER = "commit\tscore\tprocessing_time\tstatus\tdescription\n"

def ensure_results_tsv() -> None:
    if not os.path.exists(RESULTS_TSV):
        write_file(RESULTS_TSV, HEADER)

def append_result(commit: str, score: float, proc_time: float,
                  status: str, description: str) -> None:
    with open(RESULTS_TSV, "a", encoding="utf-8") as f:
        f.write(f"{commit}\t{score:.1f}\t{proc_time:.3f}\t{status}\t{description}\n")

def read_results() -> list[dict]:
    if not os.path.exists(RESULTS_TSV):
        return []
    rows = []
    for line in read_file(RESULTS_TSV).strip().splitlines()[1:]:
        parts = line.split("\t", 4)
        if len(parts) == 5:
            rows.append({
                "commit": parts[0], "score": float(parts[1]),
                "processing_time": float(parts[2]),
                "status": parts[3], "description": parts[4],
            })
    return rows

def best_score(history: list[dict]) -> float:
    valid = [r["score"] for r in history if r["score"] > 0]
    return max(valid) if valid else 0.0

def format_history(history: list[dict]) -> str:
    if not history:
        return "  (none yet — this will be the baseline run)"
    lines = []
    for r in history[-20:]:
        lines.append(
            f"  {r['commit']}  score={r['score']:.1f}  "
            f"time={r['processing_time']:.3f}s  [{r['status']}]  {r['description']}"
        )
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Nebius agent: propose a change
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(history: list[dict], variation: int = 0) -> str:
    """Build the proposal prompt. variation > 0 adds a nudge for diversity in batch mode."""
    current_solve = read_file(SOLVE_PY)
    program       = read_file("program.md") if os.path.exists("program.md") else ""

    best = best_score(history)
    status_str = f"Best score so far: {best:.1f} trips/second"

    diversity_hint = ""
    if variation > 0:
        hints = [
            "Focus on reducing memory allocations.",
            "Focus on using better data structures (Counter, tuples, arrays).",
            "Focus on reducing the number of passes over the data.",
            "Focus on optimising string parsing and type conversions.",
            "Focus on using heapq or partial sorts instead of full sorts.",
            "Focus on combining multiple computations into a single loop.",
            "Focus on eliminating intermediate data structures entirely.",
            "Focus on using list comprehensions or generator expressions.",
            "Focus on caching or precomputing repeated values.",
            "Focus on algorithmic improvements to the statistical calculations.",
        ]
        diversity_hint = f"\n\nHINT: {hints[variation % len(hints)]}"

    return f"""You are an expert Python performance engineer running autonomous
experiments to optimise a log-processing pipeline for maximum throughput.

## Instructions
{program}

## Current status
{status_str}

## Experiment history (recent)
{format_history(history)}

## Current solve.py (the ONLY file you modify)
```python
{current_solve}
```

## Your task
Propose ONE focused optimisation. Do NOT repeat failed experiments.{diversity_hint}

CRITICAL RULES:
1. Keep the function signature: process(csv_data: str) -> dict
2. All 9 output keys must remain correct — benchmark verifies every value
3. Only use Python standard library (plus numpy if you want)
4. Make ONE change with a clear performance rationale
5. The returned code MUST be complete and syntactically valid Python
6. Do NOT truncate the code. Every function must have a complete body.
7. Every opening parenthesis, bracket, and brace must be closed.

Output EXACTLY this format — nothing else after the code:

DESCRIPTION: <one sentence describing the change>
CODE:
<the COMPLETE modified solve.py as raw Python — no markdown fences, no ``` markers>"""


def _parse_proposal(raw: str) -> tuple[str, str]:
    """Extract (code, description) from a model response."""
    raw = strip_thinking(raw)

    desc_match = re.search(r"DESCRIPTION:\s*(.+?)(?:\n|$)", raw)
    description = desc_match.group(1).strip() if desc_match else "experiment"

    code_match = re.search(r"CODE:\s*\n(.*)", raw, re.DOTALL)
    if not code_match:
        raise ValueError("Could not parse CODE section from model response")
    code = code_match.group(1).strip()
    code = re.sub(r"^```(?:python)?\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$",             "", code)

    return code, description


def propose_change(history: list[dict]) -> tuple[str, str]:
    """Real-time mode: single API call, returns one (code, description)."""
    prompt = _build_prompt(history)
    result = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
        temperature=0.6,
    )
    return _parse_proposal(result.choices[0].message.content)


# ─────────────────────────────────────────────────────────────────────────────
# Batch inference (Nebius skill: 50% cheaper, no rate-limit impact)
# ─────────────────────────────────────────────────────────────────────────────

BATCH_REQUESTS_FILE = "batch_requests.jsonl"
BATCH_POLL_INTERVAL = 30  # seconds


def batch_build_requests(history: list[dict], n: int) -> str:
    """Build a JSONL batch file with n proposal requests, each with a diversity hint."""
    with open(BATCH_REQUESTS_FILE, "w", encoding="utf-8") as f:
        for i in range(n):
            request = {
                "custom_id": f"proposal-{i}",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL,
                    "messages": [{"role": "user", "content": _build_prompt(history, variation=i)}],
                    "max_tokens": MAX_TOKENS,
                    "temperature": 0.6,
                },
            }
            f.write(json.dumps(request) + "\n")
    print(f"📄 Batch file written: {BATCH_REQUESTS_FILE}  ({n} requests)")
    return BATCH_REQUESTS_FILE


def batch_submit(path: str) -> str:
    """Upload JSONL file and create a batch job. Returns batch ID."""
    with open(path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    print(f"📤 Uploaded: {file_obj.id}")

    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": "autoresearch-proposals"},
    )
    print(f"🚀 Batch created: {batch.id}  status={batch.status}")
    return batch.id


def batch_poll(batch_id: str) -> object:
    """Poll until the batch job finishes. Returns the batch object."""
    print(f"⏳ Waiting for batch {batch_id} ...", flush=True)
    while True:
        batch = client.batches.retrieve(batch_id)
        counts = batch.request_counts
        done  = counts.completed if counts else "?"
        fail  = counts.failed    if counts else "?"
        total = counts.total     if counts else "?"
        print(f"   status={batch.status}  completed={done}  failed={fail}  total={total}",
              flush=True)
        if batch.status in ("completed", "failed", "cancelled", "expired"):
            return batch
        time.sleep(BATCH_POLL_INTERVAL)


def batch_download(batch: object) -> list[tuple[str, str]]:
    """Download batch results and parse into list of (code, description)."""
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        print("❌ No output file — batch may have failed entirely.")
        return []

    content = client.files.content(output_file_id)
    results_raw = [json.loads(line) for line in content.text.strip().splitlines() if line.strip()]

    # Sort by custom_id to preserve proposal order
    results_raw.sort(key=lambda r: r.get("custom_id", ""))

    proposals = []
    for rec in results_raw:
        cid = rec.get("custom_id", "?")
        try:
            body = rec["response"]["body"]
            text = body["choices"][0]["message"]["content"]
            code, desc = _parse_proposal(text)
            proposals.append((code, desc))
            print(f"   ✅ {cid}: {desc[:60]}")
        except Exception as e:
            print(f"   ❌ {cid}: parse failed — {e}")

    print(f"📥 Downloaded {len(proposals)} valid proposals out of {len(results_raw)} results.")
    return proposals


def batch_propose_changes(history: list[dict], n: int) -> list[tuple[str, str]]:
    """Full batch pipeline: build → upload → submit → poll → download."""
    print(f"\n{'─' * 60}")
    print(f"BATCH MODE — requesting {n} proposals at 50% cost")
    print(f"{'─' * 60}")

    path = batch_build_requests(history, n)
    batch_id = batch_submit(path)
    batch = batch_poll(batch_id)

    if batch.status != "completed":
        print(f"❌ Batch ended with status: {batch.status}")
        error_fid = getattr(batch, "error_file_id", None)
        if error_fid:
            errors = client.files.content(error_fid)
            print(f"   Errors: {errors.text[:1000]}")
        return []

    return batch_download(batch)

# ─────────────────────────────────────────────────────────────────────────────
# Run the benchmark
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark() -> tuple[float | None, float | None]:
    """Run benchmark.py, return (score, processing_time) or (None, None) on failure."""
    print("  ⚙️  Running benchmark...", flush=True)
    t0 = time.time()

    try:
        with open(RUN_LOG, "w", encoding="utf-8", errors="replace") as log_f:
            proc = subprocess.Popen(
                ["python", "-u", "benchmark.py"],
                stdout=log_f, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            proc.wait(timeout=RUN_TIMEOUT)
        elapsed = time.time() - t0

        if proc.returncode != 0:
            log_tail = "\n".join(read_file(RUN_LOG).strip().splitlines()[-15:])
            print(f"  ❌ Exit code {proc.returncode} after {elapsed:.0f}s")
            print(f"  Last lines:\n{log_tail}")
            return None, None

        print(f"  ✅ Finished in {elapsed:.0f}s")
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"  ❌ Timed out after {RUN_TIMEOUT}s")
        return None, None

    log = read_file(RUN_LOG)
    return parse_metric(log, "score"), parse_metric(log, "processing_time")

# ─────────────────────────────────────────────────────────────────────────────
# Main agent loop
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_proposal(new_solve: str, description: str, history: list[dict],
                       dry_run: bool = False) -> list[dict]:
    """Validate, commit, benchmark, and keep/revert a single proposal. Returns updated history."""
    original_solve = read_file(SOLVE_PY)

    print(f"📝 Proposed: {description}")
    orig_lines = set(original_solve.splitlines())
    new_lines  = set(new_solve.splitlines())
    print(f"   Diff: +{len(new_lines - orig_lines)} / -{len(orig_lines - new_lines)} lines")

    if dry_run:
        print("   [DRY RUN] Skipping execution.")
        return history

    try:
        ast.parse(new_solve)
    except SyntaxError as e:
        print(f"❌ Proposed code has syntax error: {e}")
        append_result("-------", 0.0, 0.0, "crash", f"[syntax error] {description}")
        return read_results()

    write_file(SOLVE_PY, new_solve)
    try:
        commit_hash = git_commit(f"experiment: {description}")
    except subprocess.CalledProcessError:
        print("❌ Git commit failed (no changes?)")
        write_file(SOLVE_PY, original_solve)
        return history
    print(f"📦 Committed: {commit_hash}")

    score, proc_time = run_benchmark()
    proc_time = proc_time or 0.0
    current_best = best_score(history)

    if score is None or score == 0.0:
        print("💥 CRASH or FAIL — reverting")
        git_reset_hard()
        append_result(commit_hash, 0.0, proc_time, "crash", description)
    elif score > current_best:
        delta = score - current_best
        pct = 100 * delta / current_best if current_best > 0 else 0
        print(f"✅ IMPROVED  {current_best:.1f} → {score:.1f}  (+{pct:.1f}%)")
        append_result(commit_hash, score, proc_time, "keep", description)
    else:
        print(f"❌ NO IMPROVEMENT  got={score:.1f}  best={current_best:.1f} — reverting")
        git_reset_hard()
        append_result(commit_hash, score, proc_time, "discard", description)

    return read_results()


def _print_summary(exp_num: int, history: list[dict]) -> None:
    kept    = sum(1 for r in history if r["status"] == "keep")
    crashed = sum(1 for r in history if r["status"] == "crash")
    b = best_score(history)
    if b > 0:
        print(f"\n📊 {exp_num} experiments | kept={kept} discard={exp_num-kept-crashed} "
              f"crash={crashed} | best score={b:.1f}")


def _print_final(history: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("AUTORESEARCH COMPLETE")
    baseline = next((r for r in history if "baseline" in r["description"].lower()), None)
    b = best_score(history)
    if baseline and baseline["score"] > 0 and b > 0:
        speedup = b / baseline["score"]
        print(f"Baseline : {baseline['score']:.1f} trips/sec  ({baseline['processing_time']:.3f}s)")
        print(f"Best     : {b:.1f} trips/sec")
        print(f"Speedup  : {speedup:.2f}x")
    elif b > 0:
        print(f"Best score: {b:.1f} trips/sec")
    print(f"Full log : {RESULTS_TSV}")
    print("=" * 60)


def run_agent(n_experiments: int | None = None, dry_run: bool = False,
              batch: bool = False) -> None:
    mode_str = "BATCH (50% cheaper)" if batch else "real-time"
    print("=" * 60)
    print("NEBIUS AUTORESEARCH AGENT — Log Processing Pipeline")
    print(f"Model:       {MODEL}")
    print(f"Mode:        {mode_str}")
    print(f"Experiments: {'∞ (Ctrl-C to stop)' if n_experiments is None else n_experiments}")
    print(f"Dry run:     {dry_run}")
    print("=" * 60)

    ensure_results_tsv()
    history = read_results()

    # Run baseline if no experiments have been recorded yet
    if not history:
        print("\n-- BASELINE RUN (no API call, just measuring current solve.py) --")
        commit_hash = git("rev-parse", "--short", "HEAD")
        score, proc_time = run_benchmark()
        if score and score > 0:
            append_result(commit_hash, score, proc_time or 0.0, "keep", "baseline")
            print(f">> Baseline score: {score:.1f} trips/sec ({proc_time:.3f}s)")
        else:
            print(">> WARNING: baseline failed!")
            append_result(commit_hash, 0.0, 0.0, "crash", "baseline")
        history = read_results()

    # ── Batch mode ────────────────────────────────────────────────────────
    if batch:
        if n_experiments is None:
            n_experiments = 10
            print(f"(Batch mode requires --n-experiments, defaulting to {n_experiments})")

        proposals = batch_propose_changes(history, n_experiments)
        if not proposals:
            print("❌ No proposals received from batch job.")
            _print_final(read_results())
            return

        for i, (code, desc) in enumerate(proposals, 1):
            print(f"\n{'─' * 60}")
            print(f"EVALUATING BATCH PROPOSAL {i}/{len(proposals)}")
            print(f"{'─' * 60}")
            history = _evaluate_proposal(code, desc, history, dry_run)
            _print_summary(i, history)

        _print_final(read_results())
        return

    # ── Real-time mode ────────────────────────────────────────────────────
    exp_num = 0
    while n_experiments is None or exp_num < n_experiments:
        exp_num += 1
        print(f"\n{'─' * 60}")
        print(f"EXPERIMENT {exp_num}" + (f"/{n_experiments}" if n_experiments else ""))
        print(f"{'─' * 60}")

        print("🤖 Asking Nebius for a change...", flush=True)
        try:
            new_solve, description = propose_change(history)
        except Exception as e:
            print(f"❌ Nebius API error: {e}")
            continue

        history = _evaluate_proposal(new_solve, description, history, dry_run)
        _print_summary(exp_num, history)

    _print_final(read_results())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nebius AutoResearch Agent")
    parser.add_argument("--n-experiments", type=int, default=None,
                        help="Number of experiments (default: run forever)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Propose changes without running the benchmark")
    parser.add_argument("--batch", action="store_true",
                        help="Use Nebius batch inference (50%% cheaper, async, no rate limits)")
    parser.add_argument("--setup-branch", type=str, default=None, metavar="TAG",
                        help="Create autoresearch/<TAG> branch before starting")
    args = parser.parse_args()

    if args.setup_branch:
        setup_branch(args.setup_branch)

    run_agent(n_experiments=args.n_experiments, dry_run=args.dry_run,
              batch=args.batch)
