# Pipecat + Sarvam Voice Agent

> A minimal real-time voice assistant: **Sarvam** for speech-to-text and text-to-speech, **Nebius Token Factory** for the chat model, orchestrated with **Pipecat**.

This example runs a single Pipecat pipeline (mic → STT → LLM → TTS → speaker) and uses the Pipecat **development runner** so you can try it in the browser over WebRTC or connect via **Daily**.

## Features

- **Streaming voice loop**: Sarvam streaming STT and TTS with Nebius `openai/gpt-oss-120b` (configurable)
- **Indian languages**: Sarvam models are aimed at Indic speech; swap STT/TTS `model` and `voice_id` in `main.py` as needed
- **Two transports**: Local **WebRTC** client (default) or **Daily** rooms for remote testing
- **Small codebase**: One `main.py` entrypoint plus `pyproject.toml`

## Tech stack

- **Python 3.11+**
- **[Pipecat](https://docs.pipecat.ai)** (`pipecat-ai` with `daily`, `nebius`, `runner`, `sarvam`, `webrtc` extras)
- **[Sarvam AI](https://docs.sarvam.ai)** — STT and TTS APIs
- **[Nebius Token Factory](https://api.tokenfactory.nebius.com/)** — OpenAI-compatible Chat Completions for replies
- **FastAPI + uvicorn** — Served by the Pipecat runner (default port **7860**)

## How it works

The pipeline runs **Advanced Voice Agent** style: audio in through Daily or WebRTC, Sarvam STT → user context → Nebius LLM → Sarvam TTS → audio out, with assistant context closed for the next turn.

![Voice pipeline: transport, STT, LLM, TTS, and context aggregation](flow.png)

1. Audio enters through the runner’s transport.
2. **SarvamSTTService** turns speech into text.
3. **NebiusLLMService** generates a short reply from the conversation context.
4. **SarvamTTSService** synthesizes speech and sends it back through the transport.

## Getting started

### Prerequisites

- Python **3.11** or newer
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys:
  - [Sarvam](https://www.sarvam.ai/) — `SARVAM_API_KEY`
  - [Nebius Token Factory](https://api.tokenfactory.nebius.com/) — `NEBIUS_API_KEY`
- For **Daily** transport only: [Daily](https://www.daily.co/) — `DAILY_API_KEY` (optional: `DAILY_ROOM_URL` to reuse a room)

### Environment variables

Create a `.env` file in this directory:

```env
SARVAM_API_KEY=your_sarvam_api_key
NEBIUS_API_KEY=your_nebius_api_key

# Only if you use Daily (-t daily)
# DAILY_API_KEY=your_daily_api_key
# DAILY_ROOM_URL=https://your-domain.daily.co/your-room   # optional
```

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
- **LLM**: any Nebius Token Factory model id (e.g. `openai/gpt-oss-120b`, `openai/gpt-oss-20b`) — browse available models at [api.tokenfactory.nebius.com](https://api.tokenfactory.nebius.com/)

See Pipecat’s `pipecat.services.sarvam` modules and [Sarvam API docs](https://docs.sarvam.ai) for the exact identifiers.

### Note on “PyTorch was not found”

If you see a line from **Hugging Face / transformers** about PyTorch missing, it is usually harmless for this demo: the app uses Sarvam and Nebius over the network, not local HF checkpoints. Install `torch` only if you add code that needs it.

## Project layout

| File | Role |
|------|------|
| `main.py` | `bot()` pipeline: transport, Sarvam STT/TTS, Nebius LLM, context |
| `flow.png` | Architecture diagram for the voice pipeline (see **How it works**) |
| `pyproject.toml` | Dependencies and Python version |

## Learn more

- [Pipecat documentation](https://docs.pipecat.ai)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
