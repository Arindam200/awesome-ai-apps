# LiveKit + Gemini Realtime Voice Agent

> A real-time voice assistant that connects Google Gemini's Live API to a LiveKit room — talk to Gemini with ultra-low latency, directly in your browser or any LiveKit-compatible client.

This quick-start project wires together **LiveKit Agents** and **Google Gemini's multimodal live (realtime) model** so you can hold a natural voice conversation with a Gemini-powered assistant in just a few lines of Python.

## 🚀 Features

- **Real-time voice conversation**: Sub-second, streaming audio exchange with Gemini using the `gemini-3.1-flash-live-preview` realtime model
- **LiveKit-native transport**: Runs inside a LiveKit room — works with any LiveKit-compatible frontend, mobile app, or the hosted LiveKit Playground
- **Pluggable voice**: Powered by the `Zephyr` voice by default; swap for any Gemini-supported voice in a single line
- **Minimal boilerplate**: The entire agent fits in one `main.py` — easy to extend with tools, guardrails, or additional logic
- **Auto-reconnect & room lifecycle**: LiveKit Agents framework handles participant joining/leaving, reconnections, and graceful shutdown

## 🛠️ Tech Stack

- **Python 3.11+**: Core programming language
- **LiveKit Agents** (`livekit-agents[google,images]~=1.4`): Agent framework and WebRTC transport
- **Google Gemini Live API** (`google-genai>=1.16.0`): Multimodal realtime language model
- **LiveKit Cloud / Self-hosted**: Managed media server for the WebRTC room
- **python-dotenv**: Environment variable management

## How It Works

```
User microphone
      │
      ▼
 LiveKit Room  ──►  LiveKit Agent (Python)
                          │
                          ▼
               Google Gemini Realtime API
               (gemini-3.1-flash-live-preview)
                          │
                          ▼
               Synthesized audio response
                          │
                          ▼
                 LiveKit Room  ──►  User speaker
```

1. A participant joins a LiveKit room (via the Playground or your own frontend).
2. The LiveKit Agent framework invokes the `entrypoint` function and creates an `AgentSession`.
3. Audio is streamed in real time to Gemini's Live API, which returns streamed audio back.
4. The agent plays the response back into the room as the participant hears it.

## 📦 Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys for:
  - [LiveKit Cloud](https://cloud.livekit.io) (or a self-hosted LiveKit server) — for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`
  - [Google AI Studio](https://aistudio.google.com/apikey) — for `GOOGLE_API_KEY`

### Environment Variables

Copy the example below into a `.env` file in the project directory:

```env
LIVEKIT_URL=wss://<your-livekit-project>.livekit.cloud
LIVEKIT_API_KEY=<your-livekit-api-key>
LIVEKIT_API_SECRET=<your-livekit-api-secret>
GOOGLE_API_KEY=<your-google-ai-studio-api-key>
```

> You can also use a `.env.local` file — it takes precedence over `.env`.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-llm-apps.git
   cd awesome-llm-apps/voice_agents/livekit_gemini_agents
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

## 📂 Project Structure

```
livekit_gemini_agents/
├── main.py          # Agent definition and entry point
├── pyproject.toml   # Project metadata and dependencies
├── .env             # Environment variables (never commit this)
└── README.md        # This file
```

## Customization

| What to change | Where |
|---|---|
| System prompt / personality | `INSTRUCTIONS` constant in `main.py` |
| Gemini model | `REALTIME_MODEL` constant in `main.py` |
| Voice | `VOICE` constant in `main.py` (e.g., `"Puck"`, `"Charon"`, `"Kore"`) |
| Add tools | Override methods on `VoiceAgent` or pass `tools=` to `AgentSession` |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- [LiveKit Agents](https://docs.livekit.io/agents/) for the real-time agent framework
- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live) for the multimodal realtime model
