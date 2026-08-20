![Several LLMs taking turns debating a topic](./assets/demo.gif)

# H2AI Chat — Multi-Model Debate

> Several **different** LLMs debate a topic in turns, and a human moderates — optionally without a single byte leaving your machine.

Most multi-agent debates are one model wearing several hats. This one puts **models from different vendors in the same room**: Llama on Nebius, Claude on OpenRouter and a local Llama on Ollama can argue with each other in the same conversation, each with its own persona. Between rounds the debate stops and asks *you* what to do next, so you steer it instead of watching it run.

It is a small, self-contained taste of [**H2AI Chat**](https://h2aichat.com), an open-source turn-based platform for human-moderated debates between AIs.

## 🚀 Features

- **Genuinely multi-vendor**: each debater has its own model, base URL and API key, so a single debate can span several providers at once.
- **Human in the loop**: after every round you can steer the next one in plain language, let them carry on, or stop.
- **Runs fully offline**: point every agent at Ollama or LM Studio and the whole debate happens on your machine — nothing is sent anywhere.
- **Rotating turn order**: whoever opened the last round speaks last in the next one, so no model always gets the final word.
- **Roster as data**: add, remove or re-cast debaters by editing `agents.json`. No code changes.
- **Survives a flaky provider**: if one model fails or times out, that turn is lost and the debate carries on.

## 🛠️ Tech Stack

- **Python 3.10+**: core language
- **OpenAI SDK**: one client per agent, pointed at any OpenAI-compatible endpoint
- **Nebius Token Factory / OpenRouter / Ollama / LM Studio**: interchangeable model providers
- **Rich**: console rendering of the debate
- **python-dotenv**: keys out of the code
- **pytest**: 13 tests covering the conversation flow, with no network needed

## Workflow

```
topic ──▶ round 1 ──▶ Ada speaks ──▶ Kant answers Ada ──▶ Vera answers both
                                                              │
                       ┌──── moderator steers, or stays quiet ─┘
                       ▼
          round 2 ──▶ Kant opens ──▶ Vera ──▶ Ada  ──▶ ... ──▶ transcript
```

Every debater is handed the **full transcript so far** plus the round number and who else is in the room, then asked to answer the points actually made rather than restate its own. One detail worth knowing if you build on this: the history is replayed with `role="user"`, never `role="assistant"`. Several OpenAI-compatible providers reject or mangle an `assistant` history that their own model did not produce — and in a cross-vendor debate, it never did.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- An API key for each provider you use. The shipped roster uses:
  - [Nebius Token Factory](https://dub.sh/nebius)
  - [OpenRouter](https://openrouter.ai/keys)
  - [Ollama](https://ollama.com) running locally (no key needed)

You do not need all three. Edit `agents.json` to point every agent at the one provider you have — or at a local one, and then you need no key at all.

### Environment Variables

```bash
cp .env.example .env
```

```env
NEBIUS_API_KEY="your_nebius_api_key"
OPENROUTER_API_KEY="your_openrouter_api_key"
LOCAL_API_KEY="not-needed"
```

**Note:** local servers such as Ollama and LM Studio ignore the key, but the OpenAI client refuses to start without one, so any non-empty string works.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/h2ai_chat_debate
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   - **Using `uv` (recommended):**
     ```bash
     uv pip install -e .
     ```
   - **Using `pip`:**
     ```bash
     pip install -r requirements.txt
     ```

## ⚙️ Usage

```bash
python main.py --topic "Should an AI system be allowed to refuse a task?"
```

Between rounds the debate pauses and hands you the floor:

```
Moderator — say something to steer the next round, Enter to let them carry on, or 'q' to stop.
> Kant, you dodged the cost question. Answer it.
```

Useful flags:

| Flag | What it does |
|------|--------------|
| `--topic` | What they argue about (required) |
| `--rounds` | Turns each model takes. Default: 3 |
| `--agents` | Use a different roster file |
| `--auto` | Never stop for the moderator — good for scripting |

**Run it entirely on your own machine:**

```bash
ollama pull llama3.2
# point every agent in agents.json at http://localhost:11434/v1
python main.py --topic "Is remote work bad for junior developers?"
```

### Tests

```bash
pip install pytest
pytest tests/
```

## 📂 Project Structure

```
h2ai_chat_debate/
├── assets/               # Demo GIF
├── tests/                # Unit tests for the conversation flow
├── .env.example          # API keys, one per provider
├── agents.json           # Who debates, on which model, via which provider
├── conftest.py           # Puts the project on sys.path for the tests
├── debate.py             # Core logic: roster, transcript, prompts, turn order
├── main.py               # CLI entry point and moderator loop
├── pyproject.toml        # Dependencies
└── requirements.txt      # Dependencies, pip flavour
```

`debate.py` holds no network calls and no console output, which is why the whole conversation flow can be tested without a single API key.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md).

Issues about the wider platform belong in the [H2AI Chat repository](https://github.com/Tonterias/h2aichat).

## 📄 License

**This example is MIT licensed**, like the rest of this repository — use it however you like.

The full H2AI Chat platform it comes from is a separate project released under **AGPL-3.0**. The two are deliberately kept apart: nothing in this folder is derived from AGPL code, so nothing here carries that obligation.

## 🙏 Acknowledgments

- Built on the [OpenAI Python SDK](https://github.com/openai/openai-python), which turns "any OpenAI-compatible endpoint" into one line of configuration.
- The full platform, with a web interface, saved debates and a public gallery, lives at [h2aichat.com](https://h2aichat.com) — source at [Tonterias/h2aichat](https://github.com/Tonterias/h2aichat).
- [Research suggests](https://arxiv.org/abs/2601.10825) that simulated debate between opposing views produces better reasoning than a single model alone. That is the whole idea.
