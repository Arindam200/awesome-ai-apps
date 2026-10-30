# Job Market Brief Agent

Give it a role and a city. It pulls the postings Google Jobs lists for that search from the last week, numbers them as evidence records, and writes a one-page brief: who is hiring, at what seniority, and which skills keep coming up. Every company and skill in the brief carries the record numbers it rests on, so you can open the posting behind any claim.

Sample output: [assets/sample_brief.md](assets/sample_brief.md).

## Features

- Collects live postings for one role and location through the Google Jobs Actor on Apify, with the result count capped so a run costs cents
- Normalizes each posting to title, company, location, posted date, schedule, qualifications and apply link, numbered `[1]`, `[2]`, ...
- Writes a deterministic brief from those records: employers by posting count, seniority mix, skills that appear in two or more postings
- Optionally asks a Nebius Token Factory model for a short narrative brief that cites the records by number
- Runs fully offline from a fixture file, so the tests need no API keys
- An empty search renders as an empty search, never as an invented summary

## Tech Stack

- Python 3.10+, standard library only (`urllib`, `argparse`, `dataclasses`)
- [Apify](https://apify.com/) Google Jobs Actor for the postings
- [Nebius Token Factory](https://tokenfactory.nebius.com/) (OpenAI-compatible chat completions) for the optional narrative
- `pytest` for the tests

## Workflow

1. `main.py` sends the role, location and posted-within window to the Actor's `run-sync-get-dataset-items` endpoint and gets the dataset back as JSON.
2. `normalize()` flattens each posting into a `Record` and tags its seniority from the title.
3. `summarize()` groups records by company, counts seniority labels, and counts skill terms across qualifications and descriptions.
4. `render_brief()` writes the Markdown brief with `[n]` citations and a records list at the end.
5. If `NEBIUS_API_KEY` is set, `model_brief()` sends the records to the model with the instruction to cite record numbers after every claim, and the result is appended as a "Model brief" section.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- An [Apify](https://console.apify.com/sign-up) account and API token for live runs (free tier works for this volume)
- A [Nebius Token Factory](https://tokenfactory.nebius.com/) API key if you want the narrative section

### Environment Variables

Copy `.env.example` to `.env` and fill in what you have:

```
APIFY_API_TOKEN=...
NEBIUS_API_KEY=...        # optional
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B
```

The script reads plain environment variables. If you keep a `.env` file, load it with your shell or `python-dotenv` before running.

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/job_market_brief_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Offline, from the bundled fixture (no keys needed):

```bash
python main.py "data engineer" --location "Austin, TX" --fixture fixtures/sample_jobs.json
```

Live, last 7 days, up to 30 postings:

```bash
export APIFY_API_TOKEN=...
python main.py "data engineer" --location "Austin, TX" --posted-within 7d --limit 30 --out brief.md
```

With the model section:

```bash
export NEBIUS_API_KEY=...
python main.py "machine learning engineer" --location "Berlin" --posted-within 30d
```

Options: `--posted-within {any,24h,3d,7d,30d}`, `--limit 10..100`, `--no-model`, `--json` to print the normalized records.

Run the tests:

```bash
pytest -q
```

## Project Structure

```
job_market_brief_agent/
├── main.py                 # collection, normalization, brief, optional model step
├── fixtures/
│   └── sample_jobs.json    # six postings in the Actor's output shape, for offline runs
├── tests/
│   └── test_brief.py       # offline tests
├── assets/
│   └── sample_brief.md     # what a run produces
├── .env.example
├── requirements.txt
└── README.md
```

## Cost and limits

The Actor bills per page of about 10 results. `--limit 30` is three pages. The script caps `num_results` at 100 per run. Google Jobs returns what it indexes for the search, so a narrow role in a small city can come back with a handful of rows or none; the brief says so instead of padding.

## Contributing

Issues and pull requests are welcome. Keep the offline tests passing and add a fixture row if you change the normalization.

## License

MIT, same as the repository.

## Acknowledgments

- [Apify](https://apify.com/) for the Actor platform
- [Nebius Token Factory](https://tokenfactory.nebius.com/) for model access
- The `macro_event_brief_agent` in this collection, whose evidence-record pattern this follows
