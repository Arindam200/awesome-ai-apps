# Context Engineering Pipeline

> A prompt-format benchmark harness that measures how XML, JSON, and Markdown prompt structures affect accuracy, latency, and token usage on the same task.

Built on [Nebius Token Factory](https://tokenfactory.nebius.com/) for inference. Compare the *same* instructions expressed in three different formats across two task types (structured extraction and sentiment classification) and see which format your chosen model handles best.

## 🚀 Features

- **Three prompt formats**: XML tags, JSON schema, and Markdown sections — identical semantics, different structure.
- **Two task types**: contact-info extraction (structured output) and sentiment classification (label output).
- **Automated grading**: exact-match field accuracy for extraction, label accuracy for classification.
- **Metrics dashboard**: accuracy, latency, and prompt/completion tokens per format.
- **Model picker**: swap between Qwen, Llama, and DeepSeek models served by Nebius.
- **CLI + Streamlit UI**: run from the command line for scripting or from the browser for exploration.

## 🛠️ Tech Stack

- **Python 3.10+**
- **Streamlit** — interactive dashboard
- **OpenAI Python SDK** — pointed at Nebius Token Factory
- **Nebius Token Factory** — inference provider (Qwen3, Llama 3.1, DeepSeek-V3)
- **pandas** — results tabulation

## Workflow

1. Pick a model and the tasks/formats to evaluate.
2. Runner loads each prompt template, fills in the item text, and calls Nebius.
3. Each response is parsed and graded against ground truth.
4. Accuracy, latency, and tokens are aggregated per `(task, format)` pair and rendered as tables and charts.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) or pip
- A Nebius Token Factory API key — [get one here](https://tokenfactory.nebius.com/)

### Environment Variables

Copy `.env.example` to `.env` and fill in your key:

```env
NEBIUS_API_KEY="your_nebius_token_factory_api_key"
```

### Install

```bash
cd advance_ai_agents/context_engineering_pipeline
uv pip install -e .
# or
pip install -e .
```

### Run (Streamlit)

```bash
streamlit run app.py
```

Then open the printed URL, pick a model + tasks + formats in the sidebar, and click **Run evaluation**.

### Run (CLI)

```bash
python runner.py --model Qwen/Qwen3-30B-A3B --task all --limit 10
```

Flags:
- `--model` — any Nebius-supported chat model (default `Qwen/Qwen3-30B-A3B`)
- `--task` — `extraction`, `classification`, or `all`
- `--limit` — cap items per task for quick runs

## 📁 Project Layout

```
context_engineering_pipeline/
├── app.py                    # Streamlit dashboard
├── runner.py                 # Core eval loop + grading + CLI entry
├── prompts/
│   ├── extraction_xml.txt
│   ├── extraction_json.txt
│   ├── extraction_markdown.txt
│   ├── classification_xml.txt
│   ├── classification_json.txt
│   └── classification_markdown.txt
├── data/
│   ├── extraction_eval.jsonl
│   └── classification_eval.jsonl
├── pyproject.toml
└── .env.example
```

## 🧪 Extending

- **Add a task**: drop three prompt files (`<task>_xml.txt`, `_json.txt`, `_markdown.txt`) into `prompts/`, a `<task>_eval.jsonl` into `data/`, then register it in `runner.TASKS` with a grader function.
- **Add a format**: add a prompt file per task and append the format name to `runner.FORMATS`.
- **Swap models**: edit the model list in `app.py` or pass `--model` via CLI.

## 📝 Notes

- Temperature is pinned to `0.0` for deterministic grading.
- Each prompt carries the same role, instructions, field definitions, and output contract — only the serialization changes. This isolates format as the independent variable.
- The eval sets are small (20 items each) by design; the goal is signal on format sensitivity, not a publication-grade benchmark. Extend the JSONL files for stronger statistics.
