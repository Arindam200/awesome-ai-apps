# 🚀 Starter AI Agents - Quick Start Guide

> Get up and running with AI agent development in under 5 minutes

Welcome to the Starter AI Agents category! These projects are designed to introduce you to different AI agent frameworks and provide a solid foundation for building your own intelligent applications.

## 🎯 What You'll Learn

- **Core AI Agent Concepts**: Understanding agents, tasks, and workflows
- **Framework Comparison**: Hands-on experience with different AI frameworks
- **Best Practices**: Modern Python development with uv, type hints, and proper structure
- **LLM Integration**: Working with various language model providers
- **Environment Management**: Secure configuration and API key handling

## 📦 Prerequisites

Before starting, ensure you have:

- **Python 3.10+** - [Download here](https://python.org/downloads/)
- **uv** - [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** - [Download here](https://git-scm.com/downloads/)
- **API Keys** - [Nebius AI](https://studio.nebius.ai/api-keys) (free tier available)

### Quick Setup Check

```bash
# Verify prerequisites
python --version    # Should be 3.10+
uv --version       # Should be installed
git --version      # Should be installed
```

## 🚀 30-Second Start

```bash
# 1. Clone the repository
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents

# 2. Choose your framework and navigate to it
cd agno_starter  # or crewai_starter, langchain_langgraph_starter, etc.

# 3. Install dependencies
uv sync

# 4. Set up environment
cp .env.example .env
# Edit .env with your API key

# 5. Run the agent
uv run python main.py
```

## 🎓 Learning Path

### Step 1: Start with Agno (Recommended)
**Project**: `agno_starter`
**Why**: Simple, beginner-friendly, excellent documentation
**Time**: 15 minutes

```bash
cd agno_starter
uv sync
cp .env.example .env
# Add your Nebius API key
uv run python main.py
```

**What you'll learn**: Basic agent concepts, API integration, environment setup

### Step 2: Try Multi-Agent Systems
**Project**: `crewai_starter`
**Why**: Introduces collaborative AI agents
**Time**: 20 minutes

```bash
cd ../crewai_starter
uv sync
cp .env.example .env
# Add your API key
uv run python main.py
```

**What you'll learn**: Multi-agent coordination, task distribution, specialized roles

### Step 3: Explore LangChain Ecosystem
**Project**: `langchain_langgraph_starter`
**Why**: Industry-standard framework with advanced features
**Time**: 25 minutes

```bash
cd ../langchain_langgraph_starter
uv sync
cp .env.example .env
# Add your API key
uv run python main.py
```

**What you'll learn**: LangChain patterns, graph-based workflows, advanced orchestration

### Step 4: Compare Other Frameworks
Try these projects to understand different approaches:

- **`llamaindex_starter`**: RAG-focused framework
- **`pydantic_starter`**: Type-safe AI development
- **`dspy_starter`**: Programming with language models
- **`openai_agents_sdk`**: OpenAI's official agent framework

## 🛠️ Framework Comparison

| Framework | Best For | Learning Curve | Use Cases |
|-----------|----------|----------------|-----------|
| **Agno** | Beginners, rapid prototyping | Easy | Simple agents, quick demos |
| **CrewAI** | Multi-agent systems | Medium | Research, collaborative tasks |
| **LangChain** | Production applications | Medium-Hard | Complex workflows, integrations |
| **LlamaIndex** | RAG applications | Medium | Document analysis, knowledge bases |
| **PydanticAI** | Type-safe development | Medium | Production code, validation |
| **DSPy** | Research, optimization | Hard | Academic research, model tuning |

## 🔧 Development Setup

### Recommended IDE Setup

1. **VS Code** with extensions:
   - Python
   - Pylance
   - Python Docstring Generator
   - GitLens

2. **Environment Configuration**:
   ```bash
   # Create a global .env template
   cp starter_ai_agents/agno_starter/.env.example ~/.env.ai-template
   ```

3. **Common Development Commands**:
   ```bash
   # Install dependencies
   uv sync
   
   # Add new dependency
   uv add package-name
   
   # Run with specific Python version
   uv run --python 3.11 python main.py
   
   # Update all dependencies
   uv sync --upgrade
   ```

### Code Quality Setup

```bash
# Install development tools
uv add --dev black ruff mypy pytest

# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy .

# Run tests
uv run pytest
```

## 🐛 Common Issues & Solutions

### Issue: "ModuleNotFoundError"
**Solution**: Ensure you're in the project directory and dependencies are installed
```bash
cd starter_ai_agents/your_project
uv sync
```

### Issue: "API key error"
**Solution**: Check your .env file configuration
```bash
# Verify your .env file
cat .env

# Check if the key is valid (example)
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key loaded:', bool(os.getenv('NEBIUS_API_KEY')))"
```

### Issue: "uv command not found"
**Solution**: Install uv package manager
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Issue: "Port already in use" (for web apps)
**Solution**: Kill the process or use a different port
```bash
# Find process using port 8501
lsof -i :8501

# Kill process
kill -9 <PID>

# Or use different port
streamlit run app.py --server.port 8502
```

## 📚 Next Steps

### After Completing Starter Projects

1. **Build Your Own Agent**:
   - Choose a framework you liked
   - Pick a specific use case
   - Start with a simple implementation

2. **Explore Advanced Features**:
   - Move to [`simple_ai_agents/`](../simple_ai_agents/) for focused examples
   - Try [`rag_apps/`](../rag_apps/) for knowledge-enhanced agents
   - Challenge yourself with [`advance_ai_agents/`](../advance_ai_agents/)

3. **Join the Community**:
   - Star the repository
   - Share your creations
   - Contribute improvements
   - Help other learners

### Project Ideas for Practice

- **Personal Assistant**: Schedule management, email drafting
- **Research Agent**: Automated literature review, trend analysis  
- **Content Creator**: Blog post generation, social media management
- **Data Analyst**: Report generation, insight extraction
- **Code Assistant**: Documentation, code review, testing

## 🤝 Getting Help

### Resources
- **Documentation**: Each project has comprehensive README
- **Examples**: Working code with detailed comments
- **Community**: [GitHub Discussions](https://github.com/Arindam200/awesome-ai-apps/discussions)

### Support Channels
- **Issues**: [GitHub Issues](https://github.com/Arindam200/awesome-ai-apps/issues) for bugs
- **Questions**: GitHub Discussions for general questions
- **Framework-Specific**: Check official documentation links in each project

### Contributing Back
- **Improvements**: Submit PRs for documentation, code, or features
- **New Examples**: Add projects demonstrating different patterns
- **Bug Reports**: Help identify and fix issues
- **Documentation**: Improve guides and tutorials

---

**Ready to start building AI agents? Pick your first project and dive in! 🚀**

---

*This guide is part of the [Awesome AI Apps](https://github.com/Arindam200/awesome-ai-apps) collection - a comprehensive resource for AI application development.*