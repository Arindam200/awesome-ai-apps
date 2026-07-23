# Customer Support Voice Agent

A real-time customer support assistant built with LiveKit Agents and Nebius
Token Factory. Customers speak with Maya, a concise frontline support agent,
who can pass the conversation to Olivia, an AI support manager, without losing
the conversation history.

## Features

- Real-time speech-to-speech support in a LiveKit room
- Nebius-hosted `MiniMaxAI/MiniMax-M3` language model
- Cartesia speech recognition and text-to-speech through LiveKit Inference
- AI agent handoff with conversation context preserved
- Silero voice activity detection and turn detection
- Background voice cancellation
- Inactivity check-ins followed by automatic session shutdown
- Voice-specific safety guidance for credentials, refunds, and unsupported claims

## How it works

```text
Customer microphone
        |
        v
   LiveKit room
        |
        v
CustomerSupportAgent (Maya) ---- transfer_to_manager ----> ManagerAgent (Olivia)
        |                                                    |
        +---------------- Nebius LLM -------------------------+
        |
        +-- Cartesia STT/TTS
        +-- Silero VAD and turn detection
        +-- background voice cancellation
```

Maya offers a manager transfer when the customer requests one or when an issue
remains unresolved. The tool returns a new `ManagerAgent` with the existing chat
context, so the customer does not need to repeat the problem.

The manager in this example is another AI agent. Connecting a caller to a real
person requires an additional SIP or contact-center integration.

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)
- A [LiveKit Cloud](https://cloud.livekit.io/) project
- A [Nebius Token Factory](https://dub.sh/nebius) API key

## Setup

Clone the repository and open this example:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/voice_agents/customer_support_agent
```

Install the dependencies:

```bash
uv sync
```

Copy the environment template:

```bash
cp .env.example .env
```

Add your credentials to `.env`:

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
NEBIUS_API_KEY=your_nebius_api_key

# Optional
LLM_MODEL=MiniMaxAI/MiniMax-M3
```

Download the local Silero model files before the first run:

```bash
uv run main.py download-files
```

## Run the agent

For a local terminal-based conversation:

```bash
uv run main.py console
```

To register a development worker with LiveKit:

```bash
uv run main.py dev
```

The worker registers as `customer-support-agent` and uses explicit dispatch.
With the [LiveKit CLI](https://docs.livekit.io/home/cli/cli-setup/) installed,
create a room token, dispatch the agent, and open the Agent Console:

```bash
lk token create \
  --room customer-support-demo \
  --identity customer \
  --agent customer-support-agent \
  --join \
  --open console
```

For a production worker, run:

```bash
uv run main.py start
```

## Configuration

| Setting | Default | Where to change it |
| --- | --- | --- |
| LLM | `MiniMaxAI/MiniMax-M3` | Set `LLM_MODEL` in `.env` |
| Support behavior | Maya support prompt | `SUPPORT_PROMPT` in `main.py` |
| Manager behavior | Olivia manager prompt | `ManagerAgent` in `main.py` |
| Speech recognition | `cartesia/ink-whisper` | `AgentSession` in `main.py` |
| Voice | Cartesia Sonic 3 voice ID | `AgentSession` in `main.py` |
| Away timeout | 12.5 seconds | `user_away_timeout` in `main.py` |

## Project structure

```text
customer_support_agent/
├── .env.example       # Required credentials and optional model override
├── main.py            # Agents, handoff tool, and LiveKit worker
├── pyproject.toml     # Project metadata and dependencies
└── README.md
```

## Production considerations

This project is a focused example rather than a complete help-desk system.
Before using it in production, connect the agents to verified knowledge and
customer systems, add authentication and audit logging, define escalation and
data-retention policies, and replace the AI-manager handoff with a real human
handoff where appropriate.

## License

This example is part of
[Awesome AI Apps](https://github.com/Arindam200/awesome-ai-apps) and is
available under the repository's MIT License.
