# Speed-to-Lead Voice Agent

A voice agent that calls a lead the moment they submit a web form, routes them
to the right specialist, qualifies the request, and logs it to a mock CRM.

Inspired by the Vapi "Squad" pattern, rebuilt on **LiveKit Agents** with
**Nebius Token Factory** for LLM inference.

## What it does

1. **Form submission** hits the FastAPI webhook (`/submit`).
2. Within seconds, a LiveKit room is created and the agent is dispatched into
   it. The form payload is passed as job metadata so the agent greets the
   lead by name.
3. **Router agent** confirms the caller and classifies intent:
   `quote | schedule | emergency`.
4. A **specialist agent** takes over via LiveKit's handoff mechanism (return a
   new `Agent` from a function tool) and qualifies the lead — address, problem,
   severity.
5. On completion, `finalize_lead` appends the record to `leads.json` (mock CRM).

## Pipeline

```
form POST  ->  FastAPI dispatch  ->  LiveKit room
                                        |
                 Deepgram STT -> Nebius LLM -> Cartesia TTS
                                        |
                         Router -> {Quote | Schedule | Emergency}
                                        |
                                   leads.json
```

## Prerequisites

- Python 3.10+
- Accounts / API keys: LiveKit, Nebius Token Factory, Deepgram, Cartesia

## Install

```bash
cd voice_agents/speed_to_lead_agent
uv pip install -e .      # or: pip install -e .
cp .env.example .env     # fill in your keys
```

## Run

Two processes. In one terminal, start the agent worker:

```bash
python agent.py dev
```

In another, start the form webhook server:

```bash
uvicorn dispatch:app --reload --port 8000
```

Trigger a call by posting a form submission:

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"name": "Jordan", "phone": "+15551234567", "message": "leaky pipe"}'
```

The response includes a `room` and `token`. Open the LiveKit
[Agents Playground](https://agents-playground.livekit.io/) and paste the URL
and token to join the room and talk to the agent.

## Going to real phone calls

For actual outbound PSTN, add a LiveKit SIP trunk (Twilio works well) and,
after `agent_dispatch.create_dispatch`, call `sip.create_sip_participant` to
dial the `form.phone` number into the same room. See
[LiveKit SIP docs](https://docs.livekit.io/sip/).

## Files

| File          | Purpose                                          |
| ------------- | ------------------------------------------------ |
| `agent.py`    | LiveKit agent: router + qualifier handoffs       |
| `dispatch.py` | FastAPI webhook that dispatches the agent        |
| `crm.py`      | Mock CRM — appends leads to `leads.json`         |

## Tech

- **LiveKit Agents 1.4** — session orchestration + agent handoff
- **Nebius Token Factory** — Llama 3.1 70B via `openai.LLM.with_nebius`
- **Deepgram Nova-3** — STT
- **Cartesia** — TTS
- **Silero VAD** — turn detection
