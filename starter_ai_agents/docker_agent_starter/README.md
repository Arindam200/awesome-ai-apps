# Docker Agent Stock Research Team

> A three-agent stock research team defined in one YAML file, run by Docker Agent on Nebius Token Factory models.

[Docker Agent](https://github.com/docker/docker-agent) runs AI agents from a config file, the
way `docker run` runs containers from an image. This starter takes Docker's own
[`finance.yaml`](https://github.com/docker/docker-agent/blob/main/examples/finance.yaml)
example and runs it on [Nebius Token Factory](https://tokenfactory.nebius.com) models.

No Python, no framework. One file defines three agents, their models and their tools.

## 🚀 Features

- **One YAML file, three agents**: a coordinator that plans and writes, plus a web search specialist and a stock data specialist
- **Two Nebius models, one per role**: GLM-5.3 for planning and writing, Nemotron 3.5 Lightning for fast, cheap tool calls
- **Tools are MCP servers**: DuckDuckGo search from Docker's MCP catalog and a Yahoo Finance MCP server started with `uvx`, with no tool code in this repo
- **Sourced answers**: every news item comes with its date and the URL it was read from

## 🛠️ Tech Stack

- **[Docker Agent](https://github.com/docker/docker-agent)**: agent runtime, built into Docker Desktop 4.63+
- **[Nebius Token Factory](https://tokenfactory.nebius.com)**: `zai-org/GLM-5.3` and `nvidia/Nemotron-3_5-Lightning`
- **[DuckDuckGo MCP server](https://hub.docker.com/r/mcp/duckduckgo)**: web search and page fetching, run in a container
- **[yfmcp](https://pypi.org/project/yfmcp/)**: Yahoo Finance MCP server for live stock data

## Workflow

```
                    ┌──────────────────────────┐
  "How is NVIDIA    │  root (coordinator)      │   GLM-5.3
   doing?"     ───► │  plans, delegates,       │
                    │  writes the final answer │
                    └─────┬──────────────┬─────┘
                transfer_task       transfer_task
                          ▼              ▼
          ┌──────────────────┐   ┌──────────────────┐
          │ web_search_agent │   │  finance_agent   │   Nemotron 3.5 Lightning
          │ latest news      │   │  live stock data │
          └────────┬─────────┘   └────────┬─────────┘
                   ▼                      ▼
        docker:duckduckgo (MCP)    yfmcp (MCP, via uvx)
        from Docker's catalog      Yahoo Finance
```

You ask `root` a question. It sends the search agent a one-sentence brief for recent news,
asks the finance agent for the stock data, then writes a summary with tables and sources.

## 📦 Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) **4.63 or newer** (Docker Agent and the MCP Toolkit are built in)
- [uv](https://github.com/astral-sh/uv), so `uvx` can start the Yahoo Finance MCP server
- A Nebius Token Factory API key: [tokenfactory.nebius.com](https://tokenfactory.nebius.com)

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/docker_agent_starter
```

There is nothing to install with pip. Docker Agent reads `finance.yaml` directly.

### Environment Variables

Either export the key in your shell:

```bash
export NEBIUS_API_KEY=your-nebius-api-key
```

or keep it in a file:

```bash
cp .env.example .env    # then paste your key into .env
```

## ⚙️ Usage

```bash
docker agent run finance.yaml                          # interactive terminal UI
docker agent run finance.yaml --env-from-file .env     # same, with the key from .env
```

Then ask: *"How is NVIDIA stock doing, and what's the latest news driving it?"*

Other ways to run the same file:

```bash
# no UI, just print the answer (good for scripts and CI)
docker agent run finance.yaml --exec "Compare AMD and NVIDIA valuations"

# talk to one specialist directly, skipping the coordinator
docker agent run finance.yaml -a finance_agent "NVDA price, market cap and P/E in a table"
```

## How the file works

`finance.yaml` has three parts.

**1. Agents.** Each one has a model, a description, instructions and tools. `root` comes
first, so it's the one you talk to.

**2. `sub_agents`.** Listing `finance_agent` and `web_search_agent` under `root` gives it a
`transfer_task` tool. The coordinator decides who does what. Each specialist gets only the
task, not the whole chat, does its tool calls and reports back.

**3. Tools are MCP servers.** Neither tool is code in this repo:

| toolset | what it is |
| --- | --- |
| `ref: docker:duckduckgo` | web search, pulled from Docker's MCP catalog and run in a container |
| `command: uvx, args: ["yfmcp"]` | a Yahoo Finance MCP server, started locally with `uvx` |
| `type: think` | a built-in scratchpad so the coordinator can plan before delegating |

## What changed from Docker's example

Docker's original (kept in [`original/finance.yaml`](original/finance.yaml)) runs every agent
on Claude. The main change is the `models:` block, where each role gets the Nebius model
that suits it:

```diff
 models:
-  claude:
-    provider: anthropic
-    model: claude-sonnet-4-6
+  coordinator:                       # plans and writes: a strong reasoning model
+    provider: nebius
+    model: zai-org/GLM-5.3
+
+  specialist:                        # tool calls: fast and cheap
+    provider: nebius
+    model: nvidia/Nemotron-3_5-Lightning
```

A small, fast model needs firmer instructions than Claude, so a few more things changed to
make web search reliable:

- **`web_search_agent` gets a short research recipe.** Without it, Nemotron would sometimes
  skip reading pages, or search for last year's news, and fill the gaps from memory. Now it
  must open 2-3 pages, take the year from today's date, give every item a date and a source,
  and aim for about 3 searches and 4 page reads. Nemotron treats that budget loosely, but
  it keeps a run to a minute or two and under Nebius's per-minute token limit.
- **A `permissions:` block pre-approves `search` and `fetch_content`.** DuckDuckGo's tools
  aren't marked read-only, so Docker Agent would otherwise ask before every call. In
  `--exec` mode nobody can answer, so every search was rejected.
- **The coordinator sends the search agent a one-sentence brief.** Given a long list of
  sub-topics, Nemotron researched every one of them: 30-40 searches and several
  minutes per run.
- **The coordinator's prompt names the real tool.** Docker's original says
  `transfer_to_agent`; the tool is called `transfer_task`.

`provider: nebius` is built into Docker Agent, so the only other thing it needs is
`NEBIUS_API_KEY`. To try another model, change one line, or swap it for one agent from
the command line without editing the file:

```bash
docker agent run finance.yaml --model finance_agent=nebius/zai-org/GLM-5.3-Flash
```

## Notes

- **First run is slow.** `uvx` downloads the Yahoo Finance server once, and Docker pulls the
  DuckDuckGo image. After that a single specialist answers in 10-30 seconds, and the full
  team in 1-2 minutes, because GLM-5.3 reasons before it delegates and writes.
- **The first launch of the UI shows a "take the tour" popup.** Press `N` (not now) or
  `D` (never) before typing, or your first keystrokes go to the popup.
- **Run one question at a time.** Nebius limits tokens per minute per model (400k for
  Nemotron on a default account). Single runs didn't hit it in testing, but three full-team
  runs in parallel did (HTTP 429). If you see it, wait a minute and try again.
- **The search agent is only as good as the pages it reads.** It gives a source for each
  item, so you can check a surprising claim against the page it came from.
- **`docker:duckduckgo` needs Docker Desktop's MCP Toolkit**, which ships with 4.63+. Without it, swap
  that toolset for `command: uvx` / `args: ["duckduckgo-mcp-server"]`.
- Docker Agent was previously called `cagent`. For another Docker Agent team on Nebius (a
  blog-writing pair), see [`cagent_starter`](../cagent_starter).
- This is a research demo, not financial advice. Models can misread numbers, so check
  anything you'd act on against the source.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the
[CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](../../LICENSE) file for details.
The original `finance.yaml` comes from [docker/docker-agent](https://github.com/docker/docker-agent),
licensed under Apache 2.0.
