# AgentTrace Nebius Session Reviewer

> A small, local-first example that turns an AgentTrace JSON report into an actionable operations review with Nebius Token Factory.

This project sends the aggregated report only. It does not upload the original coding-agent session logs.

## 🚀 Features

- Reads an AgentTrace JSON report or the included sample report.
- Uses Nebius chat completions to identify risk and next actions.
- Supports a dry run for inspecting the prompt without an API key.
- Keeps the report format open so it can consume future AgentTrace exports.

## 🛠️ Tech Stack

- Python 3.10+
- `requests`
- Nebius Token Factory chat completions
- AgentTrace JSON output

## 📦 Getting Started

```bash
cd simple_ai_agents/agenttrace_nebius_reviewer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `NEBIUS_API_KEY` in `.env` or export it in the shell. The default model is `Qwen/Qwen3-30B-A3B`; override it with `NEBIUS_MODEL` or `--model`.

## ⚙️ Usage

Run the included sample without making a network request:

```bash
python main.py --dry-run
```

Generate a report with AgentTrace, then review it with Nebius:

```bash
agenttrace --overview -f json -o agenttrace-overview.json
python main.py --input agenttrace-overview.json
```

The model is instructed to return one verdict, three evidence-backed risks, and two next actions. Missing fields are reported as unavailable rather than guessed.

## 🔐 Environment Variables

```env
NEBIUS_API_KEY=your-nebius-api-key
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B
```

Get a key from [Nebius Token Factory](https://dub.sh/nebius). Keep `.env` local and never commit credentials.

## 📄 License

This example follows the repository license.
