# Meeting-to-Action Voice Agent

> A self-contained Python agent that turns a meeting transcript (or audio recording) into structured action items, owners, deadlines, risks, blockers, and follow-ups.

Extract operational outputs from raw meeting notes using an LLM. Built with **Python**, the **OpenAI SDK**, **Nebius Token Factory**, and **Faster-Whisper**.

## 🚀 Features

- Reads a raw meeting transcript or audio file.
- Extracts structured data: action items, owners, deadlines, risks, blockers, follow-ups, and open questions.
- **Uncertainty Handling:** Explicitly marks missing owners or deadlines as "Uncertain" instead of hallucinating.
- Exports pure JSON to `output.json` for downstream enterprise tools.

## 🛠️ Tech Stack

- **Python 3.10+**: Core programming language
- **OpenAI SDK**: For structured LLM completions
- **Nebius Token Factory**: Default provider for language model access
- **Faster-Whisper**: For local audio-to-text transcription (`--audio`)
- **python-dotenv**: For loading environment variables

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- A Nebius API key (see [Environment Variables](#environment-variables))

### Environment Variables

This project uses a `.env.example` file in the project root. Copy it to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

The key variable is `NEBIUS_API_KEY`. All supported variables are documented in `.env.example`:

```env
NEBIUS_API_KEY="your-api-key-here"
NEBIUS_API_BASE="https://api.tokenfactory.nebius.com/v1/"
MODEL_NAME="Qwen/Qwen3-30B-A3B-Instruct-2507"
```

### Installation

```bash
pip install -r requirements.txt
```

### Usage

Run the agent with a transcript file:

```bash
python main.py --transcript my_meeting.txt
```

Or transcribe an audio file and process it:

```bash
python main.py --audio meeting.wav
```

To try the bundled samples, run `python main.py` (reads `sample_transcript.txt` by default) or copy the sample WAV into place first:

```bash
cp sample_audio.wav meeting.wav
python main.py --audio meeting.wav
```

The generated `output.json` contains the structured results.

## 📂 Project Structure

```
meeting_to_action_agent/
├── main.py                # Core logic / CLI entry point (--transcript and --audio)
├── requirements.txt       # Python dependencies
├── sample_transcript.txt  # Sample meeting transcript used by default
└── sample_audio.wav       # Sample 1-second WAV audio for the --audio path
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.
