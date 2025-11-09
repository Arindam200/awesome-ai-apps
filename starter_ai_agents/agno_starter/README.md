![Banner](./banner.png)

# HackerNews Analysis Agent

A powerful AI agent built with Agno that analyzes and provides insights about HackerNews content. This agent uses the Nebius AI model to deliver intelligent analysis of tech news, trends, and discussions.

## Features

- 🔍 **Intelligent Analysis**: Deep analysis of HackerNews content, including trending topics, user engagement, and tech trends
- 💡 **Contextual Insights**: Provides meaningful context and connections between stories
- 📊 **Engagement Analysis**: Tracks user engagement patterns and identifies interesting discussions
- 🤖 **Interactive Interface**: Easy-to-use command-line interface for natural conversations
- ⚡ **Real-time Updates**: Get the latest tech news and trends as they happen

## Prerequisites

- Python 3.10 or higher
- Nebius API key (get it from [Nebius Token Factory](https://studio.nebius.ai/))

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd starter_ai_agents/agno_starter
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your Nebius API key:

```
NEBIUS_API_KEY=your_api_key_here
```

## Usage

Run the agent:

```bash
python main.py
```

The agent will start with a welcome message and show available capabilities. You can interact with it by typing your questions or commands.

### Example Queries

- "What are the most discussed topics on HackerNews today?"
- "Analyze the engagement patterns in the top stories"
- "What tech trends are emerging from recent discussions?"
- "Compare the top stories from this week with last week"
- "Show me the most controversial stories of the day"

## Technical Details

The agent is built using:

- Agno framework for AI agent development
- Nebius AI's Qwen/Qwen3-30B-A3B model
- HackerNews Tool from Agno

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [Agno Framework](https://www.agno.com/)
- [Nebius Token Factory](https://studio.nebius.ai/)
