# 🥊 Jailbreak Arena: NeMo Guardrails Live

> Try to break the bot. On the right side, you can't.

A split-screen demo where the **same Nemotron model** runs twice:

- 🟥 **Left (unguarded)**: a plain chat model with secrets in its system prompt
- 🟩 **Right (guarded)**: the identical model wrapped in **NVIDIA NeMo Guardrails**

Both work for the fictional **NebyBank** and both were told two secrets: a retention **promo code** and a **customer record with PII**. The audience picks attacks (or writes their own) and a live scoreboard tracks blocks vs. leaks.

Built with **NVIDIA NeMo Guardrails**, **Nemotron**, and **Nebius Token Factory**. No NVIDIA API key needed: NeMo Guardrails runs on any OpenAI-compatible endpoint, and Token Factory serves both the chat model and the embeddings model used by the dialog rails.

## 🚀 Features

- **Same model, same secrets, different outcome**: the cleanest possible proof that guardrails, not the model, do the protecting
- **Four independent defense layers**, any of which can catch an attack:
  1. **Input rail**: LLM self-check for jailbreaks, prompt injections, and secret fishing
  2. **Dialog rails**: deterministic Colang flows for internal-info requests and off-topic messages
  3. **Output rail**: LLM self-check of every bot response
  4. **Regex rail**: deterministic pattern block (promo code, SSN, email, balance) that catches leaks **even when both LLM checks miss them**
- **Six one-click attack presets**: direct extraction, DAN jailbreak, system-prompt leak, PII elicitation, indirect injection, off-topic, plus free-form attacks
- **Live scoreboard**: attacks attempted, guarded blocks, unguarded leaks, and which rail fired
- **Works with normal questions too**: ask *"What credit cards does NebyBank offer?"* and both bots answer happily; rails only stop violations
- **Everything configurable**: model, endpoint, persona, secrets, and rail rules are plain files

## 🛠️ Tech Stack

- **Python 3.10+**
- **[NVIDIA NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)** (`nemoguardrails`): input/dialog/output/regex rails, Colang 1.0
- **[Nebius Token Factory](https://dub.sh/nebius)**: serves `nvidia/Nemotron-3-Ultra-550b-a55b` (chat) and `Qwen/Qwen3-Embedding-8B` (dialog-rail embeddings) via its OpenAI-compatible API
- **langchain-openai**: the unguarded side
- **Streamlit**: the arena UI

## Why this works with Nebius Token Factory

NeMo Guardrails is model-agnostic. Its `engine: openai` provider accepts any OpenAI-compatible `base_url`, so every LLM call (the main bot, the self-check rails, and the dialog-rail embeddings) is served by Token Factory:

```yaml
models:
  - type: main
    engine: openai
    model: "nvidia/Nemotron-3-Ultra-550b-a55b"
    parameters:
      base_url: "https://api.tokenfactory.nebius.com/v1/"
      api_key: "..."
```

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A [Nebius Token Factory](https://dub.sh/nebius) API key

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/simple_ai_agents/nemo_guardrails_arena

uv sync          # or: pip install -e .
cp .env.example .env   # add your NEBIUS_API_KEY
```

## ⚙️ Usage

```bash
uv run streamlit run app.py
```

Open http://localhost:8501 and:

1. **Soften them up** (optional): ask a normal banking question, and both bots answer.
2. **Attack**: click a preset (e.g. 😈 DAN jailbreak) or type your own.
3. **Watch**: 🟥 left leaks the secret with a 🚨 badge; 🟩 right refuses with a 🛡️ badge naming the rail that fired.
4. Check the **scoreboard** in the sidebar.

## 📂 Project Structure

```
nemo_guardrails_arena/
├── config/
│   ├── config.yml   # models (chat + embeddings), rails, regex patterns, self-check prompts
│   └── rails.co     # Colang dialog flows (internal-info + off-topic)
├── arena.py         # persona, unguarded/guarded builders, outcome classifier
├── app.py           # Streamlit split-screen arena + scoreboard
├── test_guardrails_pipeline.py  # end-to-end rail tests with a local stub endpoint
├── pyproject.toml
├── .env.example
└── README.md
```

## 🔍 Technical Notes

- **Secrets never touch disk**: `config.yml` contains `{{API_KEY}}` / `{{PROMO_CODE}}` placeholders that `arena.py` fills in memory at load time.
- **Self-check prompt convention**: NeMo Guardrails parses `yes` as *block* and `no` as *allow*, so the prompts in `config.yml` are phrased accordingly.
- **Reasoning models**: `<think>` blocks are stripped from displayed replies (`arena.strip_reasoning`), so you can also point the arena at a reasoning model.
- **Tests**: `uv run python test_guardrails_pipeline.py` runs the full rail pipeline (attack block, normal answer, regex catching an LLM-missed leak) against a local stub. No API key needed.

## 🤝 Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.
