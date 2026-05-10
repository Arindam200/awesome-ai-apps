# Nebius AutoResearch — NYC Taxi Analytics Pipeline Optimizer

An autonomous AI agent that iteratively rewrites a Python data analytics pipeline, benchmarks it against **500,000 real NYC Yellow Taxi trip records**, and keeps only the changes that make it faster — without breaking correctness.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), but applied to **real-world data engineering** instead of ML training loops.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTORESEARCH LOOP                            │
│                                                                 │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │ Agent    │───▶│ Propose code │───▶│ Write solve.py + │     │
│   │ reads    │    │ change via   │    │ git commit       │     │
│   │ solve.py │    │ Nebius LLM   │    └────────┬─────────┘     │
│   │ + history│    └──────────────┘             │               │
│   └──────────┘                                 ▼               │
│        ▲                              ┌──────────────────┐     │
│        │                              │ Run benchmark.py │     │
│        │                              │ against 500K real│     │
│        │                              │ taxi records     │     │
│        │                              └────────┬─────────┘     │
│        │                                       │               │
│        │         ┌─────────────┐      ┌────────▼─────────┐     │
│        │         │ Revert      │◀─NO──│ Score improved?  │     │
│        │         │ git reset   │      └────────┬─────────┘     │
│        │         └─────────────┘          YES  │               │
│        │                                       ▼               │
│        │                              ┌──────────────────┐     │
│        └──────────────────────────────│ Keep commit,     │     │
│                                       │ log to results   │     │
│                                       └──────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
advance_ai_agents/nebius-autoresearch-autoresearch-mar30/
├── nebius_agent.py    # Autonomous optimization loop (Nebius AI + git)
├── benchmark.py       # Fixed evaluation harness — DO NOT MODIFY
├── solve.py           # Analytics pipeline — the ONLY file the agent touches
├── prepare_data.py    # Downloads real NYC taxi data (run once)
├── dashboard.py       # Live web dashboard (Flask + Chart.js)
├── program.md         # Standing instructions for the agent
├── data/
│   └── taxi_trips.csv # 500K real trip records (~34 MB, generated)
├── templates/
│   └── index.html     # Dashboard UI
├── results.tsv        # Experiment log (auto-generated, gitignored)
├── run.log            # Last benchmark output
├── requirements.txt   # Python dependencies
└── .env.example       # Environment variable template
```

## Quick Start

### 1. Clone and install

From the [awesome-ai-apps](https://github.com/Arindam200/awesome-ai-apps) repo root (or your fork):

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/nebius-autoresearch-autoresearch-mar30
pip install -r requirements.txt
```

### 2. Get a Nebius API key

Sign up at [Nebius Token Factory](https://tokenfactory.nebius.com/) and create a **project-scoped** API key ([docs](https://docs.tokenfactory.nebius.com/api-reference/introduction#authentication)).

```bash
# Linux / macOS
export NEBIUS_API_KEY="your-key-here"

# Windows (PowerShell)
$env:NEBIUS_API_KEY = "your-key-here"
```

### 3. Prepare the data (one-time, ~40 seconds)

```bash
python prepare_data.py
```

Downloads January 2024 Yellow Taxi trip records from the [NYC TLC open data portal](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), samples 500K clean rows, and saves as CSV.

### 4. Run the baseline benchmark

```bash
python benchmark.py
```

### 5. Start the agent

```bash
# Run 20 experiments with real-time API calls
python nebius_agent.py --setup-branch run1 --n-experiments 20

# Run with batch inference (50% cheaper)
python nebius_agent.py --n-experiments 50 --batch

# Run indefinitely (Ctrl-C to stop)
python nebius_agent.py
```

### 6. (Optional) Launch the live dashboard

```bash
python dashboard.py
# Open http://localhost:5000
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--n-experiments N` | Number of experiments to run (default: infinite) |
| `--batch` | Use Nebius batch inference — 50% cheaper, async |
| `--dry-run` | Show proposals without executing them |
| `--setup-branch TAG` | Create `autoresearch/TAG` branch before starting |

## What the Pipeline Computes

The `solve.py` pipeline processes 500K taxi trip rows and computes 9 business analytics metrics:

| # | Metric | Description |
|---|--------|-------------|
| 1 | `payment_revenue` | Total revenue per payment type |
| 2 | `hourly_avg_tip` | Average tip per hour (0-23) |
| 3 | `passenger_distribution` | Trip count per passenger count (capped at 7) |
| 4 | `distance_stats` | Mean, P50, P95 of trip distances |
| 5 | `duration_p95_minutes` | P95 trip duration in minutes |
| 6 | `busiest_hours` | Top 5 hours by trip count |
| 7 | `top_routes` | Top 10 pickup-dropoff location pairs |
| 8 | `avg_fare_per_mile_by_hour` | Average fare/mile per hour (trips > 0.5 mi) |
| 9 | `daily_revenue` | Total revenue per date, sorted |

All values are verified against a golden reference. Score = 0 if any output is wrong.

## Scoring

```
score = num_trips / processing_time_seconds
```

Higher is better. The agent's goal is to maximize throughput while keeping every output numerically correct.

## Model

Uses **Qwen3-235B-A22B-Thinking** via [Nebius Token Factory](https://docs.tokenfactory.nebius.com/quickstart) — a reasoning model that thinks through performance bottlenecks before proposing fixes. OpenAI-compatible API (`https://api.tokenfactory.nebius.com/v1/`), no new SDK required.

## Batch Inference

The `--batch` flag submits all proposals as a single async JSONL job via the Nebius Batch API — **50% cheaper** with no rate-limit impact.

```bash
python nebius_agent.py --n-experiments 50 --batch
```

| Run size | Real-time cost | Batch cost | Saving |
|----------|---------------|------------|--------|
| 20 rounds | ~$0.40 | ~$0.20 | 50% |
| 50 rounds | ~$1.00 | ~$0.50 | 50% |
| 200 rounds | ~$4.00 | ~$2.00 | 50% |

## Dashboard

The Flask dashboard provides real-time monitoring:

- **Score progression chart** with keep/discard/crash color coding
- **Stats panel** showing baseline, best score, speedup, experiment counts
- **Live code viewer** for the current `solve.py`
- **Run log** with colorized output
- **Agent controls** — start/stop from the browser

```bash
python dashboard.py
# Open http://localhost:5000
```

## License

MIT — see [LICENSE](LICENSE).
