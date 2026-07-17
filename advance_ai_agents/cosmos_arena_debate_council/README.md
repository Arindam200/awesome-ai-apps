# 🪐 Cosmos Arena: Multi-Agent Debate Council

A multi-agent **debate council** built with [LangGraph](https://langchain-ai.github.io/langgraph/) and powered by **`nvidia/Cosmos3-Super-Reasoner`** served by **[Nebius Token Factory](https://dub.sh/nebius)**.

Give it a motion and the council convenes: an Advocate argues *for*, a Skeptic argues *against*, an optional Pragmatist stress-tests both, and an Arbiter delivers a scored verdict, all streamed live in a Streamlit UI.

## How It Works

The app is a **LangGraph state machine** (`StateGraph`). Each council member is a node that calls the Cosmos model with a role-specific prompt, and a shared `DebateState` carries the motion, the current round, and the growing transcript between nodes:

| Node | Role |
|------|------|
| 🧭 **Graph routing** | A `StateGraph` orchestrates the debate: opening cases → alternating rebuttal rounds → optional Pragmatist → Arbiter. Conditional edges decide when to loop another round vs. proceed to the verdict |
| 🟢 **The Advocate** (`proponent`) | Argues **for** the motion; rebuts the opposition each round |
| 🔴 **The Skeptic** (`opponent`) | Argues **against** the motion; rebuts the proponent each round |
| 🟡 **The Pragmatist** (`pragmatist`) | Independent realist who stress-tests both sides *(optional)* |
| ⚖️ **The Arbiter** (`judge`) | Scores each side on logic, evidence, and rebuttal, then delivers a verdict |

The flow runs `START → proponent → opponent →` then either `increment_round → proponent` for another round, or on to `pragmatist`/`judge`. Each node reads the opponent's latest turn from the shared transcript, so rebuttals genuinely respond to prior points, making it a real exchange rather than parallel monologues. Every node reasons on the same NVIDIA Cosmos model.

## Features

- Structured, multi-round debate (1–4 rounds) on any motion
- Specialized council member nodes orchestrated by a LangGraph `StateGraph`
- Shared debate state (motion, round, transcript) threaded across nodes, with conditional routing between rounds
- Impartial judge with a transparent scorecard and verdict
- Live streaming of each council member's actual argument in the UI
- Powered by `nvidia/Cosmos3-Super-Reasoner` via the OpenAI-compatible Nebius Token Factory API
- Streamlit-based UI

## Prerequisites

- Python 3.11+
- [Nebius Token Factory](https://dub.sh/nebius) account
- [Nebius API Key](https://dub.sh/nebius)
- `uv` installed (for dependency management):

  ```bash
  pip install uv
  ```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/cosmos_arena_debate_council
   ```

2. Install dependencies using [`uv`](https://github.com/astral-sh/uv):

   ```bash
   uv sync
   ```

3. Set up environment variables. Create a `.env` file in the project root:

   ```env
   NEBIUS_API_KEY=your_api_key_here
   ```

   Optional overrides are documented in `.env.example`.

## Usage

Start the Streamlit application:

```bash
uv run streamlit run app.py
```

Then open your browser at: [http://localhost:8501](http://localhost:8501)

1. Paste your Nebius API key in the sidebar (or set `NEBIUS_API_KEY` in `.env`).
2. Choose the number of debate rounds and whether to include The Pragmatist.
3. Enter a motion (e.g. *"This house believes AGI will arrive before 2035."*).
4. Click **🪐 Convene the Council** and watch the debate unfold.

## Architecture

- **Orchestration:** LangGraph (`StateGraph`) — one node per council member, with conditional edges for rounds
- **Model:** `nvidia/Cosmos3-Super-Reasoner` via Nebius Token Factory
- **LLM integration:** `langchain-nebius` (`ChatNebius`), OpenAI-compatible
- **Frontend:** Streamlit
- **Env handling:** `python-dotenv`
- **Dependencies:** managed via [`uv`](https://github.com/astral-sh/uv)

## Project Structure

```
cosmos_arena_debate_council/
├── app.py              # Streamlit UI + live debate streaming
├── cosmos_council.py   # LangGraph debate graph: council nodes + routing + model
├── pyproject.toml      # Dependencies
├── .env.example        # Environment variable template
└── assets/             # NVIDIA + Nebius logos
```

## Contributing

Found a bug or want to improve the app? Open an issue or submit a pull request.
