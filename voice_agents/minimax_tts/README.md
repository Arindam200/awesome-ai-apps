# MiniMax Text-to-Speech Tool

This example provides a dependency-free Python client and command-line tool for synchronous text-to-speech generation. It supports the global and China regional APIs, uses `speech-2.8-hd` by default, and can decode inline hex audio or validate a temporary audio URL.

## Prerequisites

- Python 3.11 or newer
- A MiniMax API key

## Setup

```bash
cd voice_agents/minimax_tts
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Export the values from `.env`, or set the variables directly in your shell:

```bash
export MINIMAX_API_KEY="your-api-key"
export MINIMAX_REGION="global_en"
export MINIMAX_VOICE_ID="English_expressive_narrator"
```

Use `MINIMAX_REGION=cn_zh` to send requests to the China endpoint. The supported audio formats are `mp3`, `wav`, `flac`, and `pcm`.

## Usage

Create an MP3 file with the default `speech-2.8-hd` model:

```bash
minimax-tts "Welcome to the voice assistant." --output welcome.mp3
```

Select another model, region, or audio format:

```bash
minimax-tts "Welcome to the regional voice assistant." \
  --region cn_zh \
  --model speech-2.8-turbo \
  --audio-format wav \
  --output welcome.wav
```

The `MiniMaxSpeechClient.synthesize` method also exposes `language_boost`, `output_format`, `voice_setting`, `pronunciation_dict`, `audio_setting`, `voice_modify`, and `subtitle_enable` for application integrations.

## Tests

The tests use a local recording transport and do not make network requests:

```bash
python -m unittest discover -s tests -v
```

## API documentation

- [Global synchronous speech API](https://platform.minimax.io/docs/api-reference/speech-t2a-http)
- [China synchronous speech API](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)
