# LiveKit RSVP Confirmation Agent

> An outbound voice agent that calls every "pending" attendee for an event, confirms whether they are still coming (and how many guests), and updates a JSON-backed database. Built with **LiveKit Agents** for telephony, **Cartesia** for STT/TTS, and **Nebius Token Factory** for the LLM.

## What it does

For an event in `data/event.json` and a list of RSVPs in `data/attendees.json`:

1. The dispatcher (`dispatch.py`) finds every attendee with `status: "pending"`.
2. For each one, it creates a LiveKit room, dispatches the RSVP agent into it, and places an outbound SIP call to the attendee's phone.
3. The agent (`agent.py`) reads the attendee record, has a short conversation, and updates their status to `confirmed`, `declined`, `maybe`, or `no_answer` via tool calls.
4. Failed dials are retried up to `MAX_ATTEMPTS`; after that the record is marked `no_answer`.

## Tech stack

- **Python 3.10+**
- **[LiveKit Agents](https://docs.livekit.io/agents/)** — voice pipeline orchestration
- **[LiveKit Telephony / SIP](https://docs.livekit.io/telephony/)** — outbound PSTN calls via a SIP trunk
- **[Nebius Token Factory](https://api.tokenfactory.nebius.com/)** — LLM (`meta-llama/Meta-Llama-3.1-70B-Instruct`)
- **[Deepgram](https://deepgram.com)** — streaming STT (`nova-3`)
- **[Cartesia](https://cartesia.ai)** — streaming TTS (`sonic-3`)
- **Silero** — VAD

## Architecture

```
dispatch.py ──► LiveKit Room ◄── SIP outbound call ──► attendee's phone
       │                ▲
       └─ create_dispatch
                        │
                  agent.py worker
                  ├── Deepgram STT
                  ├── Nebius LLM (with tools)
                  │     ├── confirm_attendance
                  │     ├── decline_attendance
                  │     ├── mark_maybe
                  │     └── end_call
                  ├── Cartesia TTS
                  └── Silero VAD
```

## Prerequisites

- Python 3.10+ and [uv](https://github.com/astral-sh/uv) (recommended)
- A **LiveKit Cloud** project (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`)
- A **SIP outbound trunk** configured in LiveKit Cloud → Telephony → Trunks. You need a SIP provider (Twilio, Telnyx, Plivo, Exotel, or Wavix) with a real phone number to dial out from. Save the trunk ID as `SIP_OUTBOUND_TRUNK_ID`.
- API keys for Nebius, Deepgram, and Cartesia.

See [LiveKit's outbound calls guide](https://docs.livekit.io/telephony/making-calls/outbound-calls) for trunk setup.

## Setup

```bash
cd voice_agents/livekit_rsvp_agent
cp .env.example .env
# fill in keys, especially SIP_OUTBOUND_TRUNK_ID
uv sync
```

Edit `data/event.json` with your event details and `data/attendees.json` with real names and phone numbers (E.164 format, e.g. `+14155550101`).

## Run

In one terminal, start the agent worker (it stays up and accepts dispatched jobs):

```bash
uv run python agent.py dev
```

In another terminal, fire the dispatcher:

```bash
# Dial every pending attendee
uv run python dispatch.py

# Or dial just one attendee for testing
uv run python dispatch.py --id A1
```

Each attendee's phone rings; the agent greets them by name, confirms attendance and guest count, and writes the result back to `data/attendees.json`.

## Conversation script

The agent's system prompt enforces a short flow:

1. Greet by first name; identify the event by name and date.
2. Ask if they are still planning to attend.
3. Branch:
   - **Yes** → confirm guest count → `confirm_attendance(guests_count)`
   - **No** → ask brief reason → `decline_attendance(reason)`
   - **Unsure** → `mark_maybe(follow_up_note)`
4. Thank them and `end_call`.

Voicemail / long silence → leave a brief message and `end_call`.

## Project layout

| File | Role |
|---|---|
| `agent.py` | LiveKit agent worker; defines `RSVPAgent` with 4 function tools |
| `dispatch.py` | One-shot script that creates rooms, dispatches the agent, and places SIP calls |
| `tools.py` | Thread-safe JSON read/write helpers for the mock DB |
| `data/event.json` | Event metadata (name, date, venue, host) |
| `data/attendees.json` | Mock RSVP DB; statuses: `pending`, `confirmed`, `declined`, `maybe`, `no_answer` |
| `.env.example` | Required env vars |
| `pyproject.toml` | Dependencies |

## Customizing

- **Voice** — change `CARTESIA_VOICE` in `agent.py` to any Cartesia voice id.
- **LLM** — swap the Nebius model in `agent.py` (e.g. `openai/gpt-oss-120b`, `meta-llama/Meta-Llama-3.1-8B-Instruct`).
- **Retry policy** — tune `MAX_ATTEMPTS` in `dispatch.py`.
- **Real DB** — replace `tools.py` JSON ops with calls to your event-management backend (Eventbrite, Hubspot, Postgres, etc.).
- **Scheduling** — wire `dispatch.py` to a cron / Celery beat / GitHub Action to run at, say, 24h before the event.

## Learn more

- [LiveKit Telephony overview](https://docs.livekit.io/telephony/)
- [Outbound calls guide](https://docs.livekit.io/telephony/making-calls/outbound-calls)
- [LiveKit Agents — sessions](https://docs.livekit.io/agents/logic/sessions)
- [Function tools](https://docs.livekit.io/agents/logic/tools/definition)
- [Nebius Token Factory](https://api.tokenfactory.nebius.com/)
