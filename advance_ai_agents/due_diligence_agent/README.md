# Due Diligence Agent System: AG2 + TinyFish

- Created by [John Marshall](https://github.com/jsun-m)
- Last revision: 03/11/2026

A multi-agent due diligence pipeline that automatically researches a company from a single URL. It uses AG2 to orchestrate specialist agents in parallel threads, each powered by [TinyFish](https://tinyfish.ai) for deep web scraping.

## Overview

Given a company URL, the system runs a 4-stage pipeline:

1. **Seed Crawler** — Scrapes the company website to build an initial profile (name, description, team pages, press pages, job URLs, etc.)
2. **Parallel Specialists** — Spawns 6 specialist agents concurrently, each using TinyFish to deep-scrape relevant sources:
   - **Founders & Team** — LinkedIn, about/team pages
   - **Investors & Funding** — Crunchbase, investor pages
   - **Press Coverage** — Google News, company press pages
   - **Financials** — Yahoo Finance, Crunchbase
   - **Technology Stack** — BuiltWith, GitHub, job postings, engineering blogs
   - **Social Signals** — LinkedIn, Twitter/X, GitHub
3. **Validator** — Cross-checks all collected data for contradictions, gaps, and low-confidence fields
4. **Synthesis** — Produces a structured markdown due diligence report

After the pipeline completes, an interactive Q&A mode lets you ask follow-up questions grounded in the collected data.

## AG2 Features

- [ConversableAgent](https://docs.ag2.ai/latest/docs/user-guide/basic-concepts/conversable-agent) — Each specialist is an AssistantAgent with a focused system prompt
- [TinyFishTool](https://docs.ag2.ai/latest/docs/user-guide/reference-tools/tinyfish/) [API](https://docs.ag2.ai/latest/docs/api-reference/autogen/tools/experimental/TinyFishTool) — AG2's built-in TinyFish integration registered as a callable tool for agents

## Tags

TAGS: due-diligence, multi-agent, web-scraping, tinyfish, parallel-agents, research-assistant, company-research, automation

## Installation

### Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [TinyFish API key](https://tinyfish.ai)

### Setup

1. Clone and navigate to the folder:

   ```bash
   git clone https://github.com/ag2ai/build-with-ag2.git
   cd build-with-ag2/due-diligence-with-tinyfish
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:

   ```bash
   export OPENAI_API_KEY=your-openai-key
   export TINYFISH_API_KEY=your-tinyfish-key
   ```

## Usage

### Run the full pipeline

```bash
python main.py --url https://example.com
```

This will:
- Run all 4 stages of the pipeline
- Save structured JSON outputs and a final report to a timestamped directory (e.g., `due_diligence_acme_20260311_120000/`)
- Enter interactive Q&A mode

### Q&A on an existing report

```bash
python main.py --report-path ./due_diligence_acme_20260311_120000/
```

Skip the pipeline and jump straight into Q&A over a previously generated report.

### Output Structure

```
due_diligence_acme_20260311_120000/
├── company_profile.json      # Seed crawl results
├── founders_team/
│   ├── founders.json
│   ├── executives.json
│   └── headcount.json
├── investors.json
├── press/
│   ├── articles.json
│   └── sentiment.json
├── financials.json
├── tech_stack.json
├── social.json
├── validation_notes.json
├── report.md                 # Final synthesized report
└── references.md             # Index of all output files
```

## Contact

For more information or any questions, please refer to the documentation or reach out to us!

- View Documentation at: https://docs.ag2.ai/latest/
- Find AG2 on GitHub: https://github.com/ag2ai/ag2
- Join us on Discord: https://discord.gg/pAbnFJrkgZ

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](../LICENSE) for details.
