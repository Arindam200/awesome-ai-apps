# CrewAI Starter Agent 🤖

![banner](./banner.png)

> A beginner-friendly multi-agent AI research crew built with CrewAI that demonstrates collaborative AI agent workflows.

This starter project showcases how to build intelligent multi-agent systems using the CrewAI framework. It features specialized agents working together to discover and analyze groundbreaking technologies, powered by Nebius AI's advanced language models.

## 🚀 Features

- 🔬 **Specialized Research**: Dedicated researcher agent focused on discovering groundbreaking technologies
- 👥 **Multi-Agent Collaboration**: Multiple agents working together with defined roles
- 🤖 **Intelligent Analysis**: Powered by Meta-Llama-3.1-70B-Instruct model for deep insights
- 📊 **Structured Output**: Well-defined tasks with clear expected outputs and deliverables
- ⚡ **Sequential Processing**: Organized task execution for optimal results
- 💡 **Customizable Crew**: Easy to extend with additional agents and tasks
- 🎓 **Learning-Focused**: Well-commented code perfect for understanding multi-agent patterns

## 🛠️ Tech Stack

- **Python 3.10+**: Core programming language
- **[uv](https://github.com/astral-sh/uv)**: Modern Python package management
- **[CrewAI](https://crewai.com)**: Multi-agent AI framework for building collaborative AI teams
- **[Nebius AI](https://dub.sh/nebius)**: LLM provider (Meta-Llama-3.1-70B-Instruct model)
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Environment variable management

## 🔄 Workflow

How the multi-agent crew processes research tasks:

1. **Task Assignment**: Research task is distributed to specialized agents
2. **Agent Collaboration**: Researcher agent investigates the topic thoroughly
3. **Analysis**: AI processes and synthesizes findings from multiple sources
4. **Report Generation**: Structured output with insights and recommendations
5. **Quality Review**: Results are validated and formatted for presentation

## 📦 Prerequisites

- **Python 3.10+** - [Download here](https://python.org/downloads/)
- **uv** - [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** - [Download here](https://git-scm.com/downloads)

### API Keys Required

- **Nebius AI** - [Get your key](https://studio.nebius.ai/api-keys) (Free tier available)

## ⚙️ Installation

### Using uv (Recommended)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/starter_ai_agents/crewai_starter

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

1. **Run the research crew:**

   ```bash
   uv run python main.py

   ```

2. **Follow the prompts** to specify your research topic

3. **Review results** - the crew will provide comprehensive research analysis

### Example Research Topics

Try these example topics to see the multi-agent crew in action:

- "Identify the next big trend in AI and machine learning"
- "Analyze emerging technologies in quantum computing"
- "Research breakthroughs in sustainable technology"
- "Investigate the future of human-AI collaboration"
- "Explore cutting-edge developments in robotics"

## 📂 Project Structure

```text
crewai_starter/
├── main.py              # Main application entry point
├── crew.py              # CrewAI crew and agent definitions
├── .env.example         # Environment template
├── requirements.txt     # Dependencies
├── pyproject.toml       # Modern Python project config
├── banner.png           # Project banner
└── README.md            # This file
```

## 🎓 Learning Objectives

After working with this project, you'll understand:

- **CrewAI Framework**: How to build and coordinate multi-agent systems
- **Agent Roles**: Defining specialized agents with specific responsibilities
- **Task Management**: Creating and sequencing tasks for optimal workflow
- **Multi-Agent Collaboration**: How agents can work together effectively
- **LLM Integration**: Using advanced language models in agent workflows
- **Structured Output**: Generating consistent, high-quality results

## 🔧 Customization

### Define Custom Agents

```python
# Example: Add a new specialist agent
analyst_agent = Agent(
    role="Data Analyst", 
    goal="Analyze quantitative data and trends",
    backstory="Expert in statistical analysis and data interpretation",
    model="nebius/meta-llama-3.1-70b-instruct"
)
```

### Create New Tasks

```python
# Example: Add a data analysis task
analysis_task = Task(
    description="Analyze market data for emerging technology trends",
    expected_output="Statistical report with key insights and recommendations",
    agent=analyst_agent
)
```

### Extend the Crew

- **Add More Agents**: Specialist roles like data analyst, market researcher, technical writer
- **Complex Workflows**: Multi-step research processes with dependencies
- **Output Formats**: Generate reports, presentations, or structured data
- **Integration**: Connect with external APIs and data sources

## 🐛 Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError` related to CrewAI
**Solution**: Ensure all dependencies are installed correctly

```bash
cd awesome-ai-apps/starter_ai_agents/crewai_starter
uv sync
```

**Issue**: API key authentication failure
**Solution**: Verify your Nebius API key and check network connectivity

```bash
cat .env  # Check your API key configuration
```

**Issue**: Crew execution hangs or fails
**Solution**: Check task definitions and agent configurations for conflicts

**Issue**: Poor research quality
**Solution**: Refine agent backstories and task descriptions for better context

### Getting Help

- **Documentation**: [CrewAI Documentation](https://docs.crewai.com)
- **Examples**: [CrewAI Examples](https://github.com/joaomdmoura/crewAI-examples)
- **Issues**: [GitHub Issues](https://github.com/Arindam200/awesome-ai-apps/issues)
- **Community**: Join discussions or start a new issue for support

## 🤝 Contributing

Want to improve this CrewAI starter project?

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/crew-improvement`)
3. **Add** new agents, tasks, or capabilities
4. **Test** thoroughly with different research topics
5. **Submit** a pull request

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for detailed guidelines.

## 📚 Next Steps

### Beginner Path

- Try different research topics to understand agent behavior
- Modify agent roles and backstories
- Experiment with task sequencing and dependencies

### Intermediate Path

- Add new specialized agents (data analyst, fact-checker, writer)
- Implement conditional task execution
- Create custom output formats and templates

### Advanced Path

- Build industry-specific research crews
- Integrate external APIs and data sources
- Implement memory and learning capabilities
- Create web interfaces for crew management

### Related Projects

- [`simple_ai_agents/`](../../simple_ai_agents/) - Single-agent examples
- [`advance_ai_agents/`](../../advance_ai_agents/) - Complex multi-agent systems
- [`rag_apps/`](../../rag_apps/) - Knowledge-enhanced agents

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🙏 Acknowledgments

- **[CrewAI Framework](https://crewai.com)** for enabling powerful multi-agent AI systems
- **[Nebius AI](https://dub.sh/nebius)** for providing advanced language model capabilities
- **Community contributors** who help improve these examples

---

**Built with ❤️ as part of the [Awesome AI Apps](https://github.com/Arindam200/awesome-ai-apps) collection**
