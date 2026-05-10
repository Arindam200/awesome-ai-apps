# PitchLoop Voice Coach

PitchLoop is a conversational voice-agent example powered by **Gradium**, **Nebius Token Factory**, and **LangChain**.

- **Gradium STT** transcribes the user's recorded answer.
- **LangChain + Nebius** scores the answer and decides the next coaching question.
- **Gradium TTS** speaks the feedback and the next prompt back to the user.
- **FastAPI + browser audio APIs** provide a lightweight conversational UI.
- **Streamlit** is included as an alternate analysis UI.

The use case is practical: founders, developers, and operators can rehearse spoken pitches, interviews, demos, and sales answers in short conversational loops.

## Project structure

```text
.
├── app.py                         # Streamlit voice-agent UI
├── voice_agent_server.py          # FastAPI conversational voice UI
├── static/                        # Browser recorder + conversation frontend
├── voice_pitch_coach/
│   ├── coach.py                   # LangChain + Nebius coaching agent
│   ├── gradium_audio.py           # Gradium STT/TTS wrapper
│   ├── cli.py                     # WAV-file command-line workflow
│   ├── schemas.py                 # Structured feedback model
│   └── settings.py                # Environment loading
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Setup

This project needs Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill:

```text
GRADIUM_API_KEY=...
NEBIUS_API_KEY=...
```

## Run the conversational voice agent

```bash
uvicorn voice_agent_server:app --host 127.0.0.1 --port 8501
```

Open the local URL, click **Start speaking**, answer the coach prompt, then click **Stop and send**. The agent will transcribe your turn, respond in the conversation, and play the Gradium voice reply automatically.

## Run the Streamlit analysis UI

```bash
streamlit run app.py
```

## Run from a WAV file

```bash
python -m voice_pitch_coach.cli samples/my_pitch.wav \
  --scenario "startup pitch" \
  --audience "seed investors" \
  --goal "earn a second meeting"
```

The CLI prints the transcript, score, feedback, rewrite, and next question. It also writes spoken feedback to `outputs/coach-feedback.wav`.
