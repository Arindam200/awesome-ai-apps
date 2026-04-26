# LiveKit Voice Agent with Web Search

> A real-time voice assistant that pairs Google Gemini's Live API with live web search via [Olostep](https://olostep.com), all wired into a LiveKit room — talk to a Gemini-powered agent that can fetch fresh information from the web with sources.

This project extends the basic LiveKit + Gemini realtime voice agent with a `web_search` function tool so the assistant can answer questions that require up-to-date or factual information beyond the model's training data.

## 🚀 Features

- **Real-time voice conversation**: Sub-second, streaming audio exchange with Gemini using the `gemini-3.1-flash-live-preview` realtime model
- **Web search tool**: The agent can call an `Olostep`-backed `web_search` function to fetch fresh answers with cited sources
- **LiveKit-native transport**: Runs inside a LiveKit room — works with any LiveKit-compatible frontend, mobile app, or the hosted LiveKit Playground
- **Pluggable voice**: Powered by the `Zephyr` voice by default; swap for any Gemini-supported voice in a single line
- **Minimal boilerplate**: The entire agent fits in one `main.py` — easy to extend with more tools, guardrails, or additional logic

## 🛠️ Tech Stack

- **Python 3.11+**: Core programming language
- **LiveKit Agents** (`livekit-agents[google]~=1.4`): Agent framework and WebRTC transport
- **Google Gemini Live API** (`google-genai>=1.16.0`): Multimodal realtime language model
- **Olostep** (`olostep>=1.0.4`): Web search / answers API used by the `web_search` tool
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
              ┌───────────┴───────────┐
              ▼                       ▼
     Synthesized audio          web_search tool
        response                (Olostep answers
                                  + sources)
              │                       │
              └───────────┬───────────┘
                          ▼
                 LiveKit Room  ──►  User speaker
```

1. A participant joins a LiveKit room (via the Playground or your own frontend).
2. The LiveKit Agent framework invokes the `entrypoint` function and creates an `AgentSession`.
3. Audio is streamed in real time to Gemini's Live API, which returns streamed audio back.
4. When the user asks a question that needs fresh information, Gemini calls the `web_search` tool, which queries Olostep and returns an answer with sources.
5. The agent reads the answer back into the room.

## 📦 Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys for:
  - [LiveKit Cloud](https://cloud.livekit.io) (or a self-hosted LiveKit server) — for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`
  - [Google AI Studio](https://aistudio.google.com/apikey) — for `GOOGLE_API_KEY`
  - [Olostep](https://olostep.com) — for `OLOSTEP_API_KEY`

### Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
LIVEKIT_URL=wss://<your-livekit-project>.livekit.cloud
LIVEKIT_API_KEY=<your-livekit-api-key>
LIVEKIT_API_SECRET=<your-livekit-api-secret>
GOOGLE_API_KEY=<your-google-ai-studio-api-key>
OLOSTEP_API_KEY=<your-olostep-api-key>
```

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-llm-apps.git
   cd awesome-llm-apps/voice_agents/livekit_web_search_agent
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

### Development mode (auto-reload)

```bash
python main.py dev
```

### Talk to the agent (one command)

This project uses [explicit agent dispatch](https://docs.livekit.io/agents/server/agent-dispatch/#explicit) — the agent is registered as `gemini-voice-agent` and only joins a room when dispatched. The fastest way to test it end-to-end is a single [LiveKit CLI](https://docs.livekit.io/reference/cli/) command that creates a room token with the agent dispatch embedded and opens the LiveKit Agent Console in your browser:

```bash
lk token create \
  --room gemini-agent \
  --identity me \
  --agent gemini-voice-agent \
  --join \
  --open console
```

This will:
1. Create a participant token for the room `gemini-agent`
2. Embed dispatch of `gemini-voice-agent` into the token
3. Open the Agent Console pre-connected to that room

When you join, the room is created, your agent is dispatched automatically, and you can start talking. Try a question that needs fresh information (e.g. "What's the latest news about ...?") to see the `web_search` tool in action.

> **Alternative:** dispatch manually with `lk dispatch create --agent-name gemini-voice-agent --room my-room`, then open the [LiveKit Playground](https://playground.livekit.io) and join the same room name (`my-room`).

## 📂 Project Structure

```
livekit_web_search_agent/
├── main.py          # Agent definition, web_search tool, and entry point
├── pyproject.toml   # Project metadata and dependencies
├── .env.example     # Example environment variables
└── README.md        # This file
```

## Customization

| What to change | Where |
|---|---|
| System prompt / personality | `INSTRUCTIONS` constant in `main.py` |
| Gemini model | `REALTIME_MODEL` constant in `main.py` |
| Voice | `VOICE` constant in `main.py` (e.g., `"Puck"`, `"Charon"`, `"Kore"`) |
| Search backend | `web_search` function in `main.py` (swap Olostep for any other search API) |
| Add more tools | Define more `@function_tool` functions and pass them in `tools=` to `AgentSession` |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- [LiveKit Agents](https://docs.livekit.io/agents/) for the real-time agent framework
- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live) for the multimodal realtime model
- [Olostep](https://olostep.com) for the web search / answers API
