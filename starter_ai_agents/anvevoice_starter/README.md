# AnveVoice Starter - AI Voice Agent for Websites

A starter example showing how to integrate [AnveVoice](https://anvevoice.app) — an AI voice agent that trains on your website content, navigates pages, fills forms, books appointments, and talks to visitors in 50+ languages with sub-700ms latency.

## Features

- **One-line embed** — Add a voice AI agent to any website with a single script tag
- **Auto-trains on your site** — Crawls and indexes your pages for context-aware conversations
- **Multi-language** — Supports 50+ languages out of the box
- **Low latency** — Sub-700ms response time for natural conversations
- **Page navigation** — Guides visitors to relevant pages during conversation
- **Form filling** — Helps users complete forms hands-free
- **Appointment booking** — Schedules meetings directly through voice

## Quick Start

### Option 1: Static HTML

Open `index.html` in your browser. It includes the AnveVoice embed script that adds a voice agent widget to the page.

### Option 2: Python Server

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:8000` in your browser.

## How It Works

1. Sign up at [anvevoice.app](https://anvevoice.app) and get your agent embed script
2. Add the one-line script tag to your website
3. AnveVoice crawls your site and trains on your content
4. Visitors can talk to the AI agent via the voice widget

## Project Structure

```
anvevoice_starter/
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── app.py              # Simple Python HTTP server
└── index.html          # Static HTML with AnveVoice embed
```

## Environment Variables

No API keys are needed for the basic embed. The agent is configured through the AnveVoice dashboard.

## Learn More

- [AnveVoice Website](https://anvevoice.app)
- [Documentation](https://anvevoice.app/docs)
