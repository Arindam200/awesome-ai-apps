# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a comprehensive collection of practical LLM-powered application examples, tutorials, and recipes organized by complexity and use case. The repository contains 70+ example projects demonstrating various AI frameworks and patterns.

## Project Categories

Projects are organized into six main categories:

1. **starter_ai_agents/** - Quick-start boilerplate examples for learning different AI frameworks (Agno, OpenAI SDK, LlamaIndex, CrewAI, PydanticAI, LangChain, AWS Strands, Camel AI, DSPy, Google ADK)
2. **simple_ai_agents/** - Straightforward, single-purpose agents (finance tracking, web automation, newsletter generation, calendar scheduling, etc.)
3. **mcp_ai_agents/** - Projects using Model Context Protocol for semantic RAG, database interactions, and external tool integrations
4. **memory_agents/** - Agents with persistent memory capabilities using frameworks like GibsonAI Memori
5. **rag_apps/** - Retrieval-Augmented Generation examples with vector databases and document processing
6. **advance_ai_agents/** - Complex multi-agent workflows and production-ready applications (research agents, job finders, meeting assistants, etc.)
7. **course/** - Structured learning materials, including the complete AWS Strands course (8 lessons)

## Common Development Commands

### Running Individual Projects

Each project is self-contained with its own dependencies. Navigate to the specific project directory first:

```bash
cd <category>/<project_name>
```

### Installing Dependencies

Projects use either `requirements.txt` or `pyproject.toml`:

```bash
# For requirements.txt projects
pip install -r requirements.txt

# For pyproject.toml projects (newer projects)
pip install -e .
# or with uv (preferred for faster installs)
uv pip install -e .
```

### Running Projects

Most projects use simple Python execution:

```bash
python main.py
# or
python app.py
```

Some projects (especially RAG and advanced agents) use Streamlit:

```bash
streamlit run app.py
```

### Environment Configuration

All projects require environment variables for API keys. Each project has a `.env.example` file. Copy it to `.env` and add your keys:

```bash
cp .env.example .env
# Then edit .env with your API keys
```

Common API keys used across projects:
- `NEBIUS_API_KEY` - Nebius Token Factory inference provider (used extensively)
- `OPENAI_API_KEY` - OpenAI models
- `GITHUB_PERSONAL_ACCESS_TOKEN` - For GitHub MCP agents
- `SGAI_API_KEY` - ScrapeGraph AI for web scraping agents
- `MEMORI_API_KEY` - GibsonAI Memori for memory-enabled agents

## High-Level Architecture

### Multi-Stage Workflow Pattern

Advanced agents (in `advance_ai_agents/`) typically use a multi-stage workflow pattern with specialized sub-agents:

```python
class ResearchWorkflow(Workflow):
    searcher: Agent  # Gathers information
    analyst: Agent   # Analyzes findings
    writer: Agent    # Produces final output
```

Example: `advance_ai_agents/deep_researcher_agent/agents.py`

### MCP Integration Pattern

MCP agents use the Model Context Protocol to integrate external tools:

```python
async with MCPServerStdio(
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["TOKEN"]}
    }
) as server:
    agent = Agent(mcp_servers=[server], ...)
```

Example: `mcp_ai_agents/github_mcp_agent/main.py`, `mcp_ai_agents/mcp_starter/main.py`

### Framework-Specific Patterns

**Agno Framework** (most common):
- Uses `Agent` class with tools, model, and instructions
- Supports workflow orchestration via `Workflow` class
- Examples: `starter_ai_agents/agno_starter/`, `advance_ai_agents/deep_researcher_agent/`

**OpenAI Agents SDK**:
- Uses async `Runner.run()` with agents
- Examples: `starter_ai_agents/openai_agents_sdk/`, `mcp_ai_agents/mcp_starter/`

**AWS Strands**:
- Complete course available in `course/aws_strands/`
- Covers basic agents, session management, MCP, multi-agent patterns, observability, and guardrails

**LangChain/LangGraph**:
- Graph-based workflows with state management
- Examples: `starter_ai_agents/langchain_langgraph_starter/`

## Contributing Guidelines

### Adding New Projects

1. Create an issue describing the project first
2. Submit ONE project per Pull Request
3. Place in appropriate category folder (see `CONTRIBUTING.md:46-52`)
4. Use snake_case naming (e.g., `finance_agent`, `blog_writing_agent`)
5. Must include a `README.md` following the template in `.github/README_TEMPLATE.md`
6. Include either `requirements.txt` or `pyproject.toml` (pyproject.toml preferred)
7. Provide `.env.example` file - never commit secrets
8. Use code formatter (Black or Ruff) for consistent style

### Project README Requirements

Each project README must include:
- Clear description of what the agent does
- Prerequisites (Python version, required API keys)
- Installation steps
- Usage instructions with example queries/commands
- Technical details (frameworks used, models)

## AWS Strands Course Structure

Located in `course/aws_strands/`, this is an 8-lesson progressive course:

1. **01_basic_agent** - First agent with simple tools
2. **02_session_management** - Persistent conversations and state
3. **03_structured_output** - Extract structured data with Pydantic
4. **04_mcp_agent** - External tool integration via MCP
5. **05_human_in_the_loop_agent** - Request human input/approval
6. **06_multi_agent_pattern/** - Advanced multi-agent systems
   - `06_1_agent_as_tools` - Orchestrator with specialized agents
   - `06_2_swarm_agent` - Dynamic agent handoffs
   - `06_3_graph_agent` - Graph-based workflows
   - `06_4_workflow_agent` - Sequential pipelines
7. **07_observability** - OpenTelemetry and Langfuse monitoring
8. **08_guardrails** - Safety measures and content filtering

Each lesson builds on the previous, with complete working examples.

## Key Technical Notes

- **Python Version**: Requires Python 3.10 or higher (specified in most pyproject.toml files)
- **Primary AI Provider**: Nebius Token Factory is used extensively across examples for inference
- **Dependency Management**: Newer projects use `uv` for faster package installation
- **MCP Tools**: Many agents integrate with external services via MCP (GitHub, databases, custom servers)
- **Streaming UI**: Streamlit is the standard for web-based agent interfaces
- **Memory Systems**: GibsonAI Memori is the primary memory provider for context retention
- **Web Scraping**: ScrapeGraph AI is used for intelligent web data extraction

## Common Frameworks by Category

- **Starter**: Agno, OpenAI SDK, LlamaIndex, CrewAI, PydanticAI, LangChain, AWS Strands, Camel AI, DSPy, Google ADK
- **Simple**: Agno (most common), Mastra AI, browser-use
- **MCP**: OpenAI SDK, AWS Strands, custom MCP servers
- **Memory**: Agno with GibsonAI Memori, AWS Strands with Memori
- **RAG**: LlamaIndex, LangChain, Agno, CrewAI with Qdrant/vector stores
- **Advanced**: Agno workflows, CrewAI multi-agent, Google ADK, FastAPI services
