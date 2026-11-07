# Prompt-Injection Red-Team Agent

> Defensive use only — test your OWN agent with prompt-injection attacks and report which ones succeed. Only ever run this against agents you own.

A plain-Python red-team harness that automatically attacks your own agent with prompt-injection / jailbreak tests — direct injection, indirect injection via tool output, and data exfiltration — and reports the success rate per category with example transcripts.

## 🚀 Features

- **Attack category library**: direct injection, indirect injection via tool output, and data exfiltration, plus benign cases that must not be flagged
- **Attacker generates variants**: each seed case is reframed into several distinct prompts, so the target is tested against more than one phrasing
- **Rule-based judge, offline by default**: an attack counts as succeeded when the target leaks the planted fake secret or repeats the injected instruction — no API key needed
- **Pluggable target**: any callable `(prompt, tool_output=None) -> str` works as a target, so you can point the harness at your own agent
- **Two demo targets included**: a deliberately vulnerable `DemoTarget` (to show what success looks like) and a `HardenedTarget` that refuses every injected instruction
- **Per-category report**: success rate per category plus example transcripts, as Markdown and JSON

## 🛠️ Tech Stack

- **Python**: Core programming language (3.10+, standard library only)
- **pytest**: Test runner (dev dependency only)
- **Ruff**: Formatter / linter (dev dependency only)
- **LLM Provider (optional, not required)**: Nebius Token Factory or OpenAI, only if you later wire in an LLM judge — the default offline judge needs no key

## Workflow

1. Load attack cases from `attacks.json` (seed cases per category).
2. Generate prompt variants for each case.
3. Feed every variant to the target agent (your own agent, or a demo target).
4. Judge each reply with the rule-based judge (fake-secret leak or verbatim injected instruction).
5. Write a Markdown + JSON report with the per-category success rate and example transcripts.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) or pip for package management
- No API key is required to run the demo. An LLM judge is optional and not implemented in this offline build.

### Environment Variables

Create a `.env` file in the project root and add the following variables. Refer to `.env.example` for the exact names.

```env
LLM_PROVIDER=offline
NEBIUS_API_KEY=
OPENAI_API_KEY=
```

**Note:** `LLM_PROVIDER=offline` is the default. The keys above are placeholders only — never commit a real key. No real secrets are used anywhere in this project; the only secret string is the harmless fake marker `FAKE-SECRET-DEMO-1234`.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/agent_red_team
   ```

2. **Create and activate a virtual environment:**

   - **Using `venv`:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
     ```

3. **Install dependencies:**

   - **Using `uv` (recommended):**
     ```bash
     uv sync --extra dev
     ```
   - **Using `pip`:**
     ```bash
     pip install -e ".[dev]"
     ```

   The runtime itself needs no third-party packages — only the standard library. `pytest` and `ruff` are dev-only.

## ⚙️ Usage

1. **Run the red-team suite against the vulnerable demo target:**

   ```bash
   python main.py
   ```

   Or check the hardened target instead:

   ```bash
   python main.py --target hardened
   ```

   Options: `--attacks attacks.json`, `--report reports/report.md`, `--json reports/report.json`, `--variants 3`.

2. **Read the report** in `reports/report.md` (and `reports/report.json`). It lists the success rate per category and one example transcript per case.

3. **Point it at your own agent** by passing a callable to `Runner` in `red_team.py` (see `tests/test_red_team.py` for an example of a custom target).

## 📂 Project Structure

```text
agent_red_team/
├── main.py               # CLI entry point: run attacks, print summary, write reports
├── red_team.py           # Core: attack cases, variants, judge, demo targets, runner, reports
├── attacks.json          # Seed attack library (direct / indirect / exfiltration / benign)
├── tests/
│   └── test_red_team.py  # pytest suite (offline, stdlib + pytest only)
├── reports/
│   └── .gitkeep          # Generated reports go here; they are git-ignored
├── pyproject.toml        # Project metadata and dev dependencies
├── .env.example          # Environment variables (placeholders only, no real keys)
├── .gitignore
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the [Jailbreak Arena (NeMo Guardrails)](https://github.com/Arindam200/awesome-ai-apps/tree/main/simple_ai_agents/nemo_guardrails_arena) example in this collection.
- Built for [Arindam200/awesome-ai-apps #362](https://github.com/Arindam200/awesome-ai-apps/issues/362).
