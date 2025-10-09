# Agno Starter Agent 🚀

![Banner](./banner.png)

> A beginner-friendly AI agent built with Agno that analyzes HackerNews content and demonstrates core AI agent development patterns.

This starter project showcases how to build intelligent AI agents using the Agno framework. It provides a solid foundation for learning AI agent development while delivering practical HackerNews analysis capabilities powered by Nebius AI.

## 🚀 Features

- 🔍 **Intelligent Analysis**: Deep analysis of HackerNews content, including trending topics and user engagement
- 💡 **Contextual Insights**: Provides meaningful context and connections between tech stories  
- 📊 **Engagement Tracking**: Analyzes user engagement patterns and identifies interesting discussions
- 🤖 **Interactive Interface**: Easy-to-use command-line interface for natural conversations
- ⚡ **Real-time Updates**: Get the latest tech news and trends as they happen
- 🎓 **Learning-Focused**: Well-commented code perfect for understanding AI agent patterns

## 🛠️ Tech Stack

- **Python 3.10+**: Core programming language
- **[uv](https://github.com/astral-sh/uv)**: Modern Python package management
- **[Agno](https://agno.com)**: AI agent framework for building intelligent agents
- **[Nebius AI](https://dub.sh/nebius)**: LLM provider (Qwen/Qwen3-30B-A3B model)
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Environment variable management
- **HackerNews API**: Real-time tech news data source

## 🔄 Workflow

How the agent processes your requests:

1. **Input**: User asks a question about HackerNews trends
2. **Data Retrieval**: Agent fetches relevant HackerNews content via API
3. **AI Analysis**: Nebius AI processes and analyzes the content
4. **Insight Generation**: Agent generates contextual insights and patterns
5. **Response**: Formatted analysis delivered to user

## 📦 Prerequisites

- **Python 3.10+** - [Download here](https://python.org/downloads/)
- **uv** - [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** - [Download here](https://git-scm.com/downloads)

### API Keys Required

- **Nebius AI** - [Get your key](https://studio.nebius.ai/api-keys) (Free tier: 100 requests/minute)

## ⚙️ Installation

### Using uv (Recommended)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/starter_ai_agents/agno_starter

   ```

2. **Install dependencies:**

   ```bash
   uv sync

   ```

3. **Set up environment:**

   ```bash
   cp .env.example .env
   # Edit .env file with your API keys

   ```

### Alternative: Using pip

```bash
pip install -r requirements.txt
```

> **Note**: uv provides faster installations and better dependency resolution

## 🔑 Environment Setup

Create a `.env` file in the project root:

```env
# Required: Nebius AI API Key
NEBIUS_API_KEY="your_nebius_api_key_here"
```

Get your Nebius API key:

1. Visit [Nebius Studio](https://studio.nebius.ai/api-keys)
2. Sign up for a free account  
3. Generate a new API key
4. Copy the key to your `.env` file

## 🚀 Usage

### Basic Usage

1. **Run the application:**

   ```bash
   uv run python main.py

   ```

2. **Follow the prompts** to interact with the AI agent

3. **Experiment** with different queries to see how Agno processes requests

### Example Queries

Try these example queries to see the agent in action:

- "What are the most discussed topics on HackerNews today?"
- "Analyze the engagement patterns in the top stories"
- "What tech trends are emerging from recent discussions?"
- "Compare the top stories from this week with last week"
- "Show me the most controversial stories of the day"

## 📂 Project Structure

```text
agno_starter/
├── main.py              # Main application entry point
├── .env.example         # Environment template
├── requirements.txt     # Dependencies
├── banner.png           # Project banner
├── README.md            # This file
└── assets/              # Additional documentation
```

## 🎓 Learning Objectives

After working with this project, you'll understand:

- **Agno Framework Basics**: Core concepts and agent development patterns
- **AI Agent Architecture**: How to structure and configure intelligent agents
- **API Integration**: Working with external APIs and LLM providers
- **Environment Management**: Secure configuration and API key handling
- **Modern Python**: Using contemporary tools and best practices

## 🔧 Customization

### Modify Agent Behavior

The agent can be customized by modifying the configuration:

```python
# Example customizations you can make
agent_config = {
    "model": "openai/gpt-4",  # Try different models
    "temperature": 0.7,       # Adjust creativity (0.0-1.0)
    "max_tokens": 1000,       # Control response length
}
```

### Add New Features

- **Memory**: Implement conversation history
- **Tools**: Add custom tools and functions  
- **Workflows**: Create multi-step analysis processes
- **UI**: Build a web interface with Streamlit

## 🐛 Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError` after installation  
**Solution**: Ensure you're in the right directory and dependencies are installed

```bash
cd awesome-ai-apps/starter_ai_agents/agno_starter
uv sync
```

**Issue**: API key error or authentication failure  
**Solution**: Check your .env file and verify the API key is correct

```bash
cat .env  # Check the file contents
```

**Issue**: Network/connection errors  
**Solution**: Verify internet connection and check Nebius AI service status

**Issue**: Agent not responding as expected  
**Solution**: Check the model configuration and try adjusting parameters

### Getting Help

- **Documentation**: [Agno Framework Docs](https://docs.agno.com)
- **Issues**: Search [GitHub Issues](https://github.com/Arindam200/awesome-ai-apps/issues)
- **Community**: Join discussions or start a new issue for support

## 🤝 Contributing

Want to improve this starter project?

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/improvement`)
3. **Make** your improvements
4. **Test** thoroughly
5. **Submit** a pull request

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for detailed guidelines.

## 📚 Next Steps

### Beginner Path

- Try other starter projects to compare AI frameworks
- Build a simple chatbot using the patterns learned
- Experiment with different AI models and parameters

### Intermediate Path

- Combine multiple frameworks in one project
- Add memory and conversation state management
- Build a web interface with Streamlit or FastAPI

### Advanced Path

- Create multi-agent systems
- Implement custom tools and functions
- Build production-ready applications with monitoring

### Related Projects

- [`simple_ai_agents/`](../../simple_ai_agents/) - More focused examples
- [`rag_apps/`](../../rag_apps/) - Retrieval-augmented generation
- [`advance_ai_agents/`](../../advance_ai_agents/) - Complex multi-agent systems

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🙏 Acknowledgments

- **[Agno Framework](https://agno.com)** for creating an excellent AI agent development platform
- **[Nebius AI](https://dub.sh/nebius)** for providing reliable and powerful LLM services
- **Community contributors** who help improve these examples

---

**Built with ❤️ as part of the [Awesome AI Apps](https://github.com/Arindam200/awesome-ai-apps) collection**
