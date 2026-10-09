# LiveKit + Gemini Voice Incident Commander

> A hands-free voice assistant for on-call engineers: ask for incident status, dictate updates, get runbook next steps, and get flagged for escalation, all by talking.

This project builds an **incident command voice agent** with **LiveKit Agents** and **Google Gemini's realtime model**. It tracks an incident across the whole conversation and saves a transcript plus a structured action summary when you finish.

## 🚀 Features

- **Real-time voice conversation**: Talk to Gemini with low latency through a LiveKit room, using the `gemini-3.1-flash-live-preview` realtime model
- **Incident status on demand**: Ask for severity, impact, on-call people, and the timeline
- **Dictate updates**: "Database is back up" is recorded with a timestamp and can change the incident status
- **Runbook next steps**: The agent reads the next steps for the active incident
- **Action items**: Commit to a task out loud and it is recorded with an owner
- **Escalation detection**: The agent flags escalation when you sound unsure or stuck, and a keyword safety net catches phrases like "I'm not sure" or "need help"
- **Transcript logs and structured summary**: Saved to a `logs/` folder as JSON
- **Mock incident data**: Sample incidents and runbooks in `mock_incidents.json`, so no real outage is needed

## 🛠️ Tech Stack

- **Python 3.11+**: Core programming language
- **LiveKit Agents** (`livekit-agents[google]~=1.4`): Agent framework and WebRTC transport
- **Google Gemini Live API** (`google-genai>=1.16.0`): Multimodal realtime language model
- **LiveKit Cloud / Self-hosted**: Managed media server for the WebRTC room
- **python-dotenv**: Environment variable management

## Workflow

```
On-call engineer's microphone
            │
            ▼
       LiveKit Room  ──►  Incident Commander Agent (Python)
                                  │
                                  ▼
                       Google Gemini Realtime API
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
             Function tools               Synthesized audio
   (status, updates, next steps,                 │
    action items, escalation,                    ▼
    summary)                              LiveKit Room  ──►  Engineer's speaker
            │
            ▼
      Incident state  ──►  logs/ (transcript + summary JSON)
```

1. The engineer joins a LiveKit room (via the Playground or your own frontend).
2. The agent loads a mock incident and greets the engineer with its title, severity, and status.
3. Speech is streamed to Gemini, which calls function tools to read or update the incident state.
4. Every turn is logged. Escalation intent is detected from the model's tool call and from phrase matching on the engineer's speech.
5. When the session ends, or when the engineer asks for a summary, the transcript and a structured summary are written to `logs/`.

Example summary output:

```json
{
  "incident_id": "INC-1042",
  "final_status": "monitoring",
  "escalated": true,
  "updates": [{"update": "Rolled back to v2.14.0", "status": "monitoring"}],
  "action_items": [{"action": "Post status page update", "owner": "Priya"}]
}
```

## 📦 Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys for:
  - [LiveKit Cloud](https://cloud.livekit.io) (or a self-hosted LiveKit server) for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`
  - [Google AI Studio](https://aistudio.google.com/apikey) for `GOOGLE_API_KEY`

### Environment Variables

Copy `.env.example` to `.env` in the project directory and fill in your keys:

```env
LIVEKIT_URL=wss://<your-livekit-project>.livekit.cloud
LIVEKIT_API_KEY=<your-livekit-api-key>
LIVEKIT_API_SECRET=<your-livekit-api-secret>
GOOGLE_API_KEY=<your-google-ai-studio-api-key>
```

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/voice_agents/incident_commander_agent
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   Using `uv` (recommended):
   ```bash
   uv sync
   ```

   Using `pip`:
   ```bash
   pip install -e .
   ```

## ⚙️ Usage

### Start the agent

```bash
python main.py start
```

The agent registers itself with your LiveKit server and waits for participants.

### Connect a client

Open the [LiveKit Playground](https://playground.livekit.io) and enter your LiveKit URL + credentials to join the room as a participant. Once you're connected, the agent joins automatically and you can start talking.

### Development mode (auto-reload)

```bash
python main.py dev
```

### Things to say

- "What's the current status?"
- "Update: I rolled back to the previous version. Latency is dropping."
- "What should I do next?"
- "I'll post the status page update myself."
- "Honestly, I'm not sure this is fixed." (triggers escalation)
- "Give me the summary."

## 📂 Project Structure

```
incident_commander_agent/
├── main.py               # Agent, tools, incident state, and logging
├── mock_incidents.json   # Sample incidents and runbooks
├── pyproject.toml        # Project metadata and dependencies
├── .env.example          # Environment variable template
├── .env                  # Your keys (never commit this)
├── logs/                 # Generated transcripts and summaries
└── README.md             # This file
```

## Customization

| What to change | Where |
|---|---|
| System prompt / personality | `INSTRUCTIONS` constant in `main.py` |
| Gemini model | `REALTIME_MODEL` constant in `main.py` |
| Voice | `VOICE` constant in `main.py` (e.g., `"Puck"`, `"Charon"`, `"Kore"`) |
| Incidents and runbooks | `mock_incidents.json` |
| Escalation phrases | `ESCALATION_PHRASES` in `main.py` |
| Add tools | Add a `@function_tool` method to `IncidentCommander` |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- [LiveKit Agents](https://docs.livekit.io/agents/) for the real-time agent framework
- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live) for the multimodal realtime model
