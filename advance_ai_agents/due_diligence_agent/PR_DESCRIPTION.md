# PR: Add Due Diligence Agent (AG2 + TinyFish)

## Why add this example to awesome-ai-apps?

1. **New framework coverage** — This repo has zero AG2 examples. It covers Agno, OpenAI SDK, LangChain, CrewAI, AWS Strands, etc., but AG2 (AutoGen's successor) is a major multi-agent framework that's missing entirely.

2. **Showcases a distinct multi-agent pattern** — Most advanced examples here use sequential workflows (agent A → B → C). This example demonstrates parallel agent execution with 6 specialist agents running concurrently via ThreadPoolExecutor, plus a validation/synthesis pipeline — a pattern not represented in the current projects.

3. **Practical, real-world use case** — Due diligence is a concrete, high-value task (investors, founders, analysts all do it). It's more tangible than generic "research agent" examples and shows how multi-agent systems solve actual business problems.

4. **TinyFish tool integration** — Demonstrates AG2's experimental tool system (TinyFishTool) for deep web scraping, which is a different approach from the ScrapeGraph integration used elsewhere in the repo.

5. **Interactive Q&A post-pipeline** — The report + Q&A pattern (generate structured data, then query it conversationally) is a useful architectural pattern not shown in other examples.

## How this benefits users

This example gives developers a complete, runnable AG2 project that goes beyond basic tutorials — demonstrating ConversableAgent pairs, parallel execution with thread-safe state, termination conditions, and tool registration in a real application. For anyone doing company research, it turns hours of manual work across Crunchbase, LinkedIn, press, and GitHub into a single command that produces structured JSON and a markdown report with interactive Q&A. It also fills a framework gap in the repo, giving the community a concrete AG2 reference to compare against CrewAI, Agno, and LangGraph, with a reusable parallel-specialists architecture adaptable to other research domains.

## PR Template

### 🔗 Linked Issue

Closes #160

### ✅ Type of Change

- [x] ✨ New Project/Feature
- [ ] 🐞 Bug Fix
- [ ] 📚 Documentation Update
- [ ] 🔨 Refactor or Other

### 📝 Summary

Adds a new AG2 example to `advance_ai_agents/` — a multi-agent due diligence pipeline that researches a company from a single URL. Uses AG2 ConversableAgents with TinyFish for deep web scraping, running 6 specialist agents in parallel (founders, investors, press, financials, tech stack, social signals), followed by validation and synthesis stages that produce a structured markdown report with interactive Q&A.

This is the first AG2 example in the repo, filling a framework gap alongside the existing Agno, CrewAI, LangChain, and AWS Strands examples.

### 📖 README Checklist

- [x] I have created a `README.md` file for my project.
- [x] My `README.md` follows the official `.github/README_TEMPLATE.md`.
- [x] I have included clear installation and usage instructions in my `README.md`.
- [ ] I have added a GIF or screenshot to the `assets` folder and included it in my `README.md`.

### ✔️ Contributor Checklist

- [x] I have read the [**CONTRIBUTING.md**](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) document.
- [x] My code follows the project's coding standards.
- [x] I have placed my project in the correct directory (e.g., `advance_ai_agents`, `rag_apps`).
- [x] I have included a `requirements.txt` or `pyproject.toml` for dependencies.
- [x] I have added a `.env.example` file if environment variables are needed and ensured no secrets are committed.
- [x] My pull request is focused on a single project or change.

### 💬 Additional Comments

Inspired by [ag2ai/build-with-ag2/due-diligence-with-tinyfish](https://github.com/ag2ai/build-with-ag2/tree/main/due-diligence-with-tinyfish). The architecture has been adapted to fit the awesome-ai-apps project structure while preserving the core AG2 patterns (ConversableAgent pairs, TinyFishTool registration, TASK_COMPLETE termination, parallel ThreadPoolExecutor execution).
