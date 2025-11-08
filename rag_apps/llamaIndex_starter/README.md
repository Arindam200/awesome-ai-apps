![Banner](./banner.png)

# LlamaIndex RAG Starter

A starter project demonstrating how to use LlamaIndex with Nebius Token Factory for building RAG (Retrieval-Augmented Generation) applications.

## Overview

This project showcases the integration of LlamaIndex with Nebius Token Factory, providing access to state-of-the-art LLM models. It demonstrates how to:

- Set up and configure Nebius Token Factory with LlamaIndex
- Use different LLM endpoints (complete, chat, streaming)
- Build RAG applications with custom data

## Prerequisites

- Python 3.8+
- Nebius Token Factory API key (Get one at [studio.nebius.ai](https://studio.nebius.ai/))

## Installation

1. Install the required packages:

```bash
pip install llama-index-llms-nebius llama-index
```

## Usage

### Basic Setup

```python
from llama_index.llms.nebius import NebiusLLM

# Initialize the LLM
llm = NebiusLLM(
    model="mistralai/Mixtral-8x7B-Instruct-v0.1",
    api_key="your_api_key"
)
```

### Available Features

1. **Text Completion**

```python
response = llm.complete("Your prompt here")
```

2. **Chat Interface**

```python
from llama_index.core.llms import ChatMessage

messages = [
    ChatMessage(role="system", content="Your system prompt"),
    ChatMessage(role="user", content="Your user message"),
]
response = llm.chat(messages)
```

3. **Streaming Responses**

```python
# Streaming completion
for chunk in llm.stream_complete("Your prompt"):
    print(chunk.delta, end="")

# Streaming chat
for chunk in llm.stream_chat(messages):
    print(chunk.delta, end="")
```

## Available Models

Nebius Token Factory provides access to various state-of-the-art LLM models. Check out the full list of available models at [studio.nebius.ai](https://studio.nebius.ai/).

## Contributing

Feel free to submit issues and enhancement requests!


