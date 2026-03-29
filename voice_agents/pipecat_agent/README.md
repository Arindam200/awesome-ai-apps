# Pipecat + Sarvam Voice Agent

> A minimal real-time voice assistant: **Sarvam** for speech-to-text and text-to-speech, with an OpenAI-compatible chat model (**OpenAI** or **Nebius Token Factory**), orchestrated with **Pipecat**.

This example runs a single Pipecat pipeline (mic → STT → LLM → TTS → speaker) and uses the Pipecat **development runner** so you can try it in the browser over WebRTC or connect via **Daily**.

## Features

- **Streaming voice loop**: Sarvam streaming STT and TTS with configurable OpenAI-compatible LLM (`OpenAI` or `Nebius Token Factory`)
- **Indian languages**: Sarvam models are aimed at Indic speech; swap STT/TTS `model` and `voice_id` in `main.py` as needed
- **Two transports**: Local **WebRTC** client (default) or **Daily** rooms for remote testing
- **Provider switch via env vars**: Use `LLM_PROVIDER=openai` or `LLM_PROVIDER=nebius`
- **Small codebase**: One `main.py` entrypoint plus `pyproject.toml`

## Tech stack

- **Python 3.11+**
- **[Pipecat](https://docs.pipecat.ai)** (`pipecat-ai` with `daily`, `openai`, `runner`, `sarvam`, `webrtc` extras)
- **[Sarvam AI](https://docs.sarvam.ai)** — STT and TTS APIs
- **[OpenAI](https://platform.openai.com/docs)** or **[Nebius Token Factory](https://studio.nebius.com/)** — Chat Completions for replies
- **FastAPI + uvicorn** — Served by the Pipecat runner (default port **7860**)

## How it works

```
User microphone
      │
      ▼
  Transport (WebRTC or Daily)
      │
      ▼
  Sarvam STT  ──►  OpenAI-compatible LLM  ──►  Sarvam TTS
      │                    │              │
      └────────────────────┴──────────────┘
                    context aggregator
```

1. Audio enters through the runner’s transport.
2. **SarvamSTTService** turns speech into text.
3. **OpenAILLMService** generates a short reply from the conversation context.
4. **SarvamTTSService** synthesizes speech and sends it back through the transport.

## Getting started

### Prerequisites

- Python **3.11** or newer
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys:
  - [Sarvam](https://www.sarvam.ai/) — `SARVAM_API_KEY`
  - [OpenAI](https://platform.openai.com/api-keys) — `OPENAI_API_KEY` (if `LLM_PROVIDER=openai`)
  - [Nebius AI Studio](https://studio.nebius.com/) — `NEBIUS_API_KEY` (if `LLM_PROVIDER=nebius`)
- For **Daily** transport only: [Daily](https://www.daily.co/) — `DAILY_API_KEY` (optional: `DAILY_ROOM_URL` to reuse a room)

### Environment variables

Create a `.env` file in this directory:

```env
SARVAM_API_KEY=your_sarvam_api_key

# Choose LLM provider: openai (default) or nebius
LLM_PROVIDER=openai

# OpenAI mode
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Nebius mode (OpenAI-compatible endpoint)
NEBIUS_API_KEY=your_nebius_api_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
NEBIUS_MODEL=deepseek-ai/DeepSeek-V3-0324

# Only if you use Daily (-t daily)
# DAILY_API_KEY=your_daily_api_key
# DAILY_ROOM_URL=https://your-domain.daily.co/your-room   # optional
```

To run with Nebius, set `LLM_PROVIDER=nebius` in your `.env` and restart the bot.

### Install and run

From the repository root:

```bash
cd voice_agents/pipecat_agent
uv sync
```

**WebRTC (default)** — opens a local server and a browser test client:

```bash
uv run python main.py
# or explicitly:
uv run python main.py -t webrtc
```

Then open **http://localhost:7860/client** (the runner prints the URL).

**Daily** — bot joins a Daily room (set `DAILY_API_KEY` first):

```bash
uv run python main.py -t daily
```

Use `uv run python main.py --help` for more runner options (host, port, etc.).

### Selecting models

In `main.py` you can pass **`model`** (and for Sarvam TTS, **`voice_id`**) into the service constructors. Examples:

- **STT**: e.g. `saarika:v2.5` (default in Pipecat if omitted), `saaras:v2.5`, `saaras:v3` (with `mode` where applicable)
- **TTS**: e.g. `bulbul:v2` (default), `bulbul:v3`, `bulbul:v3-beta`
- **LLM**:
  - OpenAI mode: any OpenAI chat model your key supports (e.g. `gpt-4o-mini`, `gpt-4o`)
  - Nebius mode: any Nebius chat model id (e.g. `deepseek-ai/DeepSeek-V3-0324`, `Qwen/Qwen3-32B`)

See Pipecat’s `pipecat.services.sarvam` modules and [Sarvam API docs](https://docs.sarvam.ai) for the exact identifiers.

### Note on “PyTorch was not found”

If you see a line from **Hugging Face / transformers** about PyTorch missing, it is usually harmless for this demo: the app uses Sarvam and OpenAI over the network, not local HF checkpoints. Install `torch` only if you add code that needs it.

## Project layout

| File | Role |
|------|------|
| `main.py` | `bot()` pipeline: transport, Sarvam STT/TTS, OpenAI LLM, context |
| `pyproject.toml` | Dependencies and Python version |

## Learn more

- [Pipecat documentation](https://docs.pipecat.ai)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
