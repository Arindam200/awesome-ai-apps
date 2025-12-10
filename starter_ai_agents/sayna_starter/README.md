# Sayna Voice Agent Starter

> Real-time voice infrastructure for AI agents with Speech-to-Text and Text-to-Speech capabilities.

A starter example demonstrating how to use [Sayna](https://github.com/SaynaAI/sayna) for building voice-enabled AI applications. Sayna provides real-time bidirectional audio streaming with multi-provider support for STT/TTS.

## Features

- **Real-time Voice Streaming**: WebSocket-based bidirectional audio communication
- **Multi-Provider Support**: Deepgram, ElevenLabs, Google Cloud, Microsoft Azure, Cartesia
- **Speech-to-Text**: Real-time transcription with configurable providers and models
- **Text-to-Speech**: Voice synthesis with customizable voices
- **REST API**: Simple HTTP endpoints for one-shot TTS operations
- **LiveKit Integration**: Optional WebRTC room-based communication

## Tech Stack

- **Python**: Core programming language
- **Sayna Client**: Official Python SDK for Sayna voice infrastructure
- **asyncio**: Asynchronous I/O for real-time streaming
- **STT Providers**: Deepgram (Nova-2), Google Cloud, Azure Speech
- **TTS Providers**: ElevenLabs, Cartesia, Google Cloud, Azure Speech

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) or pip for package management
- API keys for your chosen providers:
  - [Sayna API](https://sayna.ai) (or self-hosted instance)
  - [Deepgram](https://deepgram.com) for STT (optional)
  - [ElevenLabs](https://elevenlabs.io) or [Cartesia](https://cartesia.ai) for TTS (optional)

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
SAYNA_API_KEY="your_sayna_api_key"
SAYNA_URL="https://api.sayna.ai"
```

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/starter_ai_agents/sayna_starter
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

## Usage

1. **Run the application:**

   ```bash
   python main.py
   ```

2. **Interact with the agent:**
   - The agent will connect to Sayna and start listening
   - Speak into your microphone to send audio
   - Receive real-time transcriptions and TTS responses

### Example Code

```python
import asyncio
from sayna_client import SaynaClient, STTConfig, TTSConfig

async def main():
    client = SaynaClient(
        url="https://api.sayna.ai",
        stt_config=STTConfig(provider="deepgram", model="nova-2"),
        tts_config=TTSConfig(provider="cartesia", voice_id="your-voice-id"),
        api_key="your-api-key",
    )

    # Register event handlers
    client.register_on_stt_result(lambda r: print(f"Transcript: {r.transcript}"))
    client.register_on_tts_audio(lambda audio: print(f"Received {len(audio)} bytes"))

    await client.connect()
    await client.speak("Hello! I'm your voice-enabled AI assistant.")
    await asyncio.sleep(5)
    await client.disconnect()

asyncio.run(main())
```

## Project Structure

```
sayna_starter/
├── .env.example        # Example environment variables
├── main.py             # Main application entry point
├── pyproject.toml      # Project dependencies
├── requirements.txt    # Pip dependencies
└── README.md           # Project documentation
```

## Technical Details

The agent is built using:

- [Sayna](https://github.com/SaynaAI/sayna) - Real-time voice processing server
- [sayna-client](https://pypi.org/project/sayna-client/) - Official Python SDK
- WebSocket streaming for low-latency audio

## Resources

- [Sayna Documentation](https://docs.sayna.ai/)
- [Sayna GitHub Repository](https://github.com/SaynaAI/sayna)
- [Python SDK Reference](https://docs.sayna.ai/sdks/python)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [Sayna](https://sayna.ai/) for the voice infrastructure
- [Deepgram](https://deepgram.com/) for STT capabilities
- [ElevenLabs](https://elevenlabs.io/) for TTS capabilities
