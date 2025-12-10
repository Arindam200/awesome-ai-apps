import asyncio
import os
from dotenv import load_dotenv
from sayna_client import SaynaClient, STTConfig, TTSConfig

load_dotenv()

# Configuration for Speech-to-Text
STT_CONFIG = STTConfig(
    provider="deepgram",
    model="nova-2"
)

# Configuration for Text-to-Speech
TTS_CONFIG = TTSConfig(
    provider="cartesia",
    voice_id="a0e99841-438c-4a64-b679-ae501e7d6091"  # Default Cartesia voice
)


def on_transcription(result):
    """Handle incoming transcription results."""
    print(f"Transcription: {result.transcript}")
    if result.is_final:
        print(f"[Final] {result.transcript}")


def on_audio_received(audio_data: bytes):
    """Handle incoming TTS audio data."""
    print(f"Received {len(audio_data)} bytes of audio")


def on_error(error):
    """Handle errors from the client."""
    print(f"Error: {error}")


def on_disconnect():
    """Handle disconnection events."""
    print("Disconnected from Sayna server")


async def main():
    """Main entry point for the Sayna voice agent."""
    api_key = os.getenv("SAYNA_API_KEY")
    sayna_url = os.getenv("SAYNA_URL", "https://api.sayna.ai")

    if not api_key:
        print("Error: SAYNA_API_KEY environment variable is required")
        print("Please set it in your .env file or environment")
        return

    print("Sayna Voice Agent Starter")
    print("=" * 40)
    print(f"Connecting to: {sayna_url}")
    print(f"STT Provider: {STT_CONFIG.provider}")
    print(f"TTS Provider: {TTS_CONFIG.provider}")
    print("=" * 40)

    # Initialize the Sayna client
    client = SaynaClient(
        url=sayna_url,
        stt_config=STT_CONFIG,
        tts_config=TTS_CONFIG,
        api_key=api_key,
    )

    # Register event handlers
    client.register_on_stt_result(on_transcription)
    client.register_on_tts_audio(on_audio_received)
    client.register_on_error(on_error)
    client.register_on_disconnect(on_disconnect)

    try:
        # Connect to Sayna
        print("\nConnecting to Sayna...")
        await client.connect()
        print("Connected successfully!")

        # Check available voices
        print("\nFetching available voices...")
        voices = await client.get_voices()
        print(f"Available voices: {len(voices)} voices found")

        # Send a test TTS message
        print("\nSending test speech...")
        await client.speak("Hello! I'm your voice-enabled AI assistant powered by Sayna.")

        # Keep the connection alive for demo purposes
        print("\nListening for audio input (press Ctrl+C to exit)...")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await client.disconnect()
        print("Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
