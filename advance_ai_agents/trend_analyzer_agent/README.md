# Analyzer Agent (AI Trends Analysis Pipeline)

A comprehensive AI analysis pipeline that analyzes AI news, benchmarks, and trends. Built using Google's Agent Development Kit (ADK) framework. Full explainer video is available on [YouTube](https://www.youtube.com/watch?v=FYhKah8FpAg). Find more Agent demos built with ADK [here](https://github.com/Astrodevil/ADK-Agent-Examples)

## Overview

This agent demonstrates a complex 5-agent sequential pipeline that:
- Fetches the latest AI news from Twitter/X using Exa search
- Retrieves AI benchmarks and analysis using Tavily search
- Scrapes and processes data from Nebius AI Studio using Firecrawl
- Synthesizes and structures this information into a comprehensive analysis
- Analyzes AI trends and provides specific Nebius model recommendations

## Technical Pattern

Uses a 5-agent sequential pipeline:
1. **ExaAgent**: Fetches latest AI news from Twitter/X
2. **TavilyAgent**: Retrieves AI benchmarks and analysis
3. **SummaryAgent**: Combines and formats information from the first two agents
4. **FirecrawlAgent**: Scrapes Nebius Studio website for model information
5. **AnalysisAgent**: Performs deep analysis using Llama-3.1-Nemotron-Ultra-253B model

## Installation

1. Clone the Repo
```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd advance_ai_agents/trend_analyzer_agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
```

4. Edit the `.env` file with your API keys:
```
NEBIUS_API_KEY="your_nebius_api_key_here"
NEBIUS_API_BASE="https://api.studio.nebius.ai/v1"
EXA_API_KEY="your_exa_api_key_here"
TAVILY_API_KEY="your_tavily_api_key_here"
FIRECRAWL_API_KEY="your_firecrawl_api_key_here"
```

## Usage

Run with ADK CLI:
```bash
# Terminal - Run directly in the terminal
adk run analyzer_agent

# Dev UI - Visual interface for testing and debugging
adk web
```

## Required API Keys

- [Nebius AI](https://dub.sh/AIStudio) - For LLM inference
- [Exa](https://exa.ai/) - For AI news search
- [Tavily](https://tavily.com/) - For specialized search
- [Firecrawl](https://firecrawl.dev/) - For web scraping 
