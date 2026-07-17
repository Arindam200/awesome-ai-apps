# Pydantic Game Agent

## One-prompt browser game studio

Generate tiny playable browser games from one prompt using Pydantic AI agents and GLM-5.2 via Nebius Token Factory. The app is a local FastAPI project with a Spotify-style single-page UI. It streams agent progress while a game is being generated, previews the finished game in a sandboxed iframe, and saves successful games as standalone HTML files you can reopen later.

Project path: `advance_ai_agents/pydantic_game_agent`

## Features

- One-prompt game generation with named Pydantic AI agents.
- Live run stream in the preview area while agents work.
- Sandboxed iframe preview for the generated game.
- Local generated-game library with one-click open links.
- Safety checks for blocked browser APIs and incomplete game output.
- Saved games exposed via `GET /play/latest`, `GET /games/{game_id}`, and `GET /api/games` (`generated-games/` is gitignored local output).

## Tech stack

- **Python 3.11+**
- **FastAPI**: web UI and SSE streaming routes
- **Pydantic AI**: typed multi-agent workflow
- **GLM-5.2 / Nebius Token Factory**: OpenAI-compatible game generation

## How it works

The workflow uses Pydantic AI `Agent` objects with static `instructions` and typed `output_type` models where structured data is needed.

1. **Game Designer Agent** creates a typed `GameSpec` from the prompt.
2. **Game Builder Agent** generates a standalone HTML/CSS/JS game.
3. **Game Reviewer Agent** reviews the generated HTML text plus the spec.
4. **Repair Agent** runs one targeted repair pass only if review or static safety checks fail.

The reviewer reads the generated HTML/CSS/JS and the typed spec, then returns a structured review with approval, issues, and fix instructions.

## Getting started

### Prerequisites

- Python 3.11+
- [Nebius Token Factory](https://dub.sh/nebius) API key

### Install

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/pydantic_game_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set your Nebius key in `.env`:

```bash
NEBIUS_API_KEY=your-nebius-token-factory-key
NEBIUS_MODEL=zai-org/GLM-5.2
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
```

`NEBIUS_MODEL` defaults to `zai-org/GLM-5.2`. The demo does not require token or temperature tuning.

### Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Test

```bash
pytest
```

## Safety

The app rejects or asks the model to repair generated HTML that contains external script tags, network calls, page navigation, browser storage APIs, or embedded frames. The preview iframe uses `sandbox="allow-scripts"` so generated games run JavaScript without full page privileges.

## Troubleshooting

**Missing API key**: set `NEBIUS_API_KEY` in `.env` and restart the server.

**Wrong model**: use `NEBIUS_MODEL=zai-org/GLM-5.2` without unquoted spaces.

**Empty model response**: GLM-5.2 can return reasoning before final content; try a shorter prompt or run generation again.

## Project structure

```text
pydantic_game_agent/
  app/
    agents.py       # Pydantic AI agents and Nebius model setup
    main.py         # FastAPI routes and SSE stream
    models.py       # Pydantic data models
    safety.py       # Generated HTML safety checks
    storage.py      # Local generated-game persistence
    static/         # CSS and logos
    templates/      # FastAPI/Jinja HTML UI
  tests/            # Route, safety, and storage tests
  .env.example
  pyproject.toml
```

## Provider links

- [Nebius Token Factory GLM-5.2](https://dub.sh/nebius)
- [Pydantic AI overview](https://pydantic.dev/docs/ai/overview/)
- [Pydantic AI OpenAI provider](https://pydantic.dev/docs/ai/models/openai/)
