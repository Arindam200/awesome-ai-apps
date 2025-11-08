![Demo](./assets/demo.gif)

# 📚 Talk to Your Docs - Documentation QnA Agent

A Streamlit-based AI agent that allows you to have conversations with any documentation using MCP (Model Context Protocol) tools and Nebius Token Factory.

## Features

- 🤖 **AI-Powered Conversations**: Chat with any documentation using advanced AI models
- 🔗 **MCP Integration**: Uses Model Context Protocol for seamless tool integration
- 🌐 **Flexible Documentation Sources**: Works with any documentation URL
- 💬 **Interactive Chat Interface**: Clean and intuitive Streamlit UI
- 🔑 **Secure API Key Management**: Safe handling of API credentials
- 💡 **Example Questions**: Pre-built questions to get started quickly

## Setup

1. **Install Dependencies**:

   ```bash
   uv sync
   ```

2. **Set up Environment Variables**:
   Create a `.env` file with your Nebius API key:

   ```env
   NEBIUS_API_KEY=your_nebius_api_key_here
   ```

3. **Run the Application**:
   ```bash
   uv run streamlit run main.py
   ```

## Usage

1. **Enter API Key**: Input your Nebius API key in the sidebar
2. **Set Documentation URL**: Enter the URL of the documentation you want to query
3. **Start Chatting**: Ask questions about the documentation in the chat interface
4. **Use Examples**: Click on example questions in the sidebar for quick starts

## Configuration

- **Model**: Uses DeepSeek-V3-0324 model via Nebius
- **Transport**: Streamable HTTP for MCP connection
- **Default Documentation**: Mintlify docs (can be changed)

## Example Questions

- "How to migrate documentation from your current platform to Mintlify?"
- "What are the key features of the documentation platform?"
- "How do I set up authentication?"
- "What are the best practices for documentation?"

## Architecture

The application uses:

- **Agno Framework**: For AI agent orchestration
- **MCP Tools**: For documentation interaction
- **Nebius Token Factory**: As the language model provider
- **Streamlit**: For the web interface

## License

This project is part of the awesome-llm-apps collection.
