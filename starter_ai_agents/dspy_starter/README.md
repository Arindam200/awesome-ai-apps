# DSPy Starter Agent

A powerful AI agent built with DSPy, leveraging advanced LLMs and tool integration for reasoning, search, and computation. This starter project uses the Nebius AI model and DSPy’s ReAct framework to answer complex questions and perform multi-step tasks.

## Features

- 🤖 **LLM-Powered Reasoning**: Uses Meta-Llama-3.1-70B-Instruct via Nebius AI for intelligent responses
- 🧮 **Tool Integration**: Access to Python interpreter and Wikipedia search for multi-step reasoning
- 🔗 **ReAct Framework**: Combines retrieval, action, and computation in a single agent
- ⚡ **Easy Customization**: Add your own tools and workflows
- 📊 **Structured Output**: Clear, interpretable answers

## Prerequisites

- Python 3.10 or higher
- Nebius API key (get it from [Nebius Token Factory](https://studio.nebius.ai/))

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd starter_ai_agents/dspy_starter
```

2. Install dependencies:

```bash
uv sync
```

3. Create a `.env` file in the project root and add your Nebius API key:

```
NEBIUS_API_KEY=your_api_key_here
```

## Usage

Run the DSPy agent:

```bash
uv run main.py
```

The agent will answer questions using Wikipedia search and Python math evaluation.

### Example Tasks

- "What is the population of France multiplied by the number of Nobel Prizes won by Marie Curie?"
- "Calculate the square root of the year the Eiffel Tower was built."
- "Find the capital of Japan and its population."
- "Who won the Nobel Prize in Physics in 1921 and what was their age at the time?"

## Technical Details

The agent is built using:

- DSPy framework for LLM orchestration and tool use
- Nebius AI's Meta-Llama-3.1-70B-Instruct model
- ReAct module for multi-step reasoning
- Python interpreter and Wikipedia search tools

### Workflow Structure

Tasks are processed by:

- Defining a question
- Using tools (search, math) as needed
- Returning a structured answer

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [DSPy Framework](https://github.com/stanfordnlp/dspy)
- [Nebius AI](https://dub.sh/nebius)
