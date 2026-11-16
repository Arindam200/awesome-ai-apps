![Proactive On-Call Agent dashboard at 09:15: the agent has paged, opened an incident and asked for a rollback](./assets/dashboard.jpg)

# Proactive On-Call Agent

> An agent that acts on events without being asked. A cron server wakes Kimi K3.1 Pro on [Nebius Token Factory](https://dub.sh/nebius) to triage a live event stream; it pages a human, asks for a rollback, and schedules its own follow-ups until the incident is closed.

Most agents sit in a chat box and wait. This one has no chat box. It implements LangChain's [proactive agents](https://www.langchain.com/blog/proactive-agents) idea on one concrete use case, an on-call shift for a checkout team: a cron server wakes the agent every 5 minutes to read what happened, and the agent decides for itself what matters, who needs to hear about it, and when it should wake up again.

Watch it work a scripted morning. A bad deploy breaks checkout at 09:12, and three minutes later the agent has paged you with the evidence, asked you to approve a rollback, and set itself a follow-up. It keeps checking back until checkout is healthy, resolves the incident, and saves the lesson. Meanwhile it puts a slowly filling database disk on a recurring watch, cancels that watch when a teammate fixes the cause, and stays quiet about team chatter and healthy deploys.

Built with **LangChain** (`create_agent`, middleware, `ToolRuntime`), **Kimi K3.1 Pro** on **Nebius Token Factory**, and **Streamlit**.

## 🚀 Features

- **No prompts, only triggers**: every run starts from a schedule firing. The user message just says which schedule fired and why
- **Static schedules in `schedules/`**: one file per schedule with `define_schedule(cron=..., prompt=...)`, the same shape as Managed Deep Agents
- **Schedules the agent makes itself**: `follow_up_in` (one-off, continues the same thread) and `schedule_recurring` (cron, fresh thread each run), plus `list_schedules` and `cancel_schedule`
- **Smart triage that stays quiet**: when nothing new arrived, the triage run is skipped without calling the model at all. Noise gets no notification
- **Human-gated actions**: the agent can't roll back on its own. `request_rollback` puts an Approve/Deny card on your phone panel, and the decision comes back as an event
- **Incidents as shared working memory**: open, update and resolve incidents, so separate runs don't page twice for the same problem
- **Long-term memory**: `remember` saves durable lessons to `state/memory.md`, loaded into every future run. A static end-of-shift schedule writes the handoff and consolidates lessons
- **A world that reacts**: the simulated checkout service isn't a fixed recording. A bad version raises the error rate, an approved rollback brings it back down, and a payments-provider outage hurts checkout whatever version runs
- **Make trouble live**: inject a bad deploy, a provider outage, a customer ticket or chatter from the sidebar and watch the next wake-up handle it
- **Two ways to watch**: a Streamlit dashboard with Approve/Deny buttons, or a terminal run of the whole shift
- **Optional Slack delivery**: set `SLACK_WEBHOOK_URL` and every notification is also posted to Slack

## 🛠️ Tech Stack

- **Python 3.10+**
- **[LangChain](https://docs.langchain.com/oss/python/langchain/agents)**: `create_agent`, `@dynamic_prompt` middleware, tools with `ToolRuntime` context, LangGraph checkpointer for follow-up threads
- **[Nebius Token Factory](https://dub.sh/nebius)**: serves `moonshotai/Kimi-K3.1-Pro` through its OpenAI-compatible API
- **[croniter](https://github.com/kiorky/croniter)**: cron expressions for the in-process cron server
- **Streamlit**: live dashboard
- **Rich**: terminal view

## Workflow

```mermaid
flowchart LR
    W[Simulated world<br/>deploys, alerts, chat,<br/>tickets, metrics] -->|events| Q[(Event stream)]
    C[Cron server<br/>schedules/ + agent-made] -->|fires| R{New events?}
    R -- no --> Z[Skip: no model call]
    R -- yes --> A[Kimi K3.1 Pro agent<br/>LangChain create_agent]
    Q --> A
    A -->|notify, request_rollback| H[You: phone panel<br/>Approve / Deny]
    H -->|approval event| W
    A -->|follow_up_in<br/>schedule_recurring| C
    A -->|incidents, remember| M[(Incidents +<br/>long-term memory)]
    M -->|situation in every prompt| A
```

1. **Tick**: the simulated clock moves one minute. The world produces that minute's events and metrics. The clock stops while the agent works, so a slow model call never makes it miss an event.
2. **Fire**: the cron server runs every schedule that's due: the agent's own follow-ups first, then its recurring watches, then the static ones from `schedules/`.
3. **Wake**: each due schedule starts an agent run. A `@dynamic_prompt` middleware rebuilds the system prompt before every model call with the current situation: open incidents, pending approvals, active schedules, the messages already sent and long-term memory.
4. **Act**: the agent calls tools to look (`get_new_events`, `get_metrics`, `get_deploy_history`), to act (`notify`, `request_rollback`, incidents, `remember`) and to schedule itself (`follow_up_in`, `schedule_recurring`, `cancel_schedule`).
5. **Repeat**: you approve or deny on the phone panel, the world reacts, and the agent finds out at its next wake-up.

### The two building blocks

LangChain's post argues that most proactive agents are "agent runs as cron tasks", and that you need two things to build one. Here is where each lives:

| Building block | In this project |
| --- | --- |
| A cron server that runs a prompt on a schedule | `cron.py`: static schedules from `schedules/*.py`, runtime schedules with `cron` or `at`, 20-schedule limit per owner |
| An interface for the agent to create and manage its own schedules | `agent.py`: `follow_up_in`, `schedule_recurring`, `list_schedules`, `cancel_schedule`, all reaching the cron server through `runtime.context` |

Thread behavior follows Managed Deep Agents: a one-off follow-up continues the thread of the run that set it, so the agent remembers what it was checking, while cron runs start on a fresh thread.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A [Nebius Token Factory](https://dub.sh/nebius) API key

### Environment Variables

```bash
cp .env.example .env
```

```env
NEBIUS_API_KEY="your_nebius_token_factory_api_key"

# Optional
# NEBIUS_MODEL="moonshotai/Kimi-K3.1-Pro"
# REASONING_EFFORT="medium"
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/proactive_oncall_agent
   ```

2. **Install dependencies:**

   - **Using `uv` (recommended):**
     ```bash
     uv sync
     ```
   - **Using `pip`:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # On Windows: .venv\Scripts\activate
     pip install -e .
     ```

## ⚙️ Usage

### Dashboard

```bash
uv run streamlit run app.py
```

Open `http://localhost:8501` and press **Start shift**. Don't type anything; there is nowhere to type. Watch three columns:

- **Event stream**: what happens in the world, marked new until a triage run reads it
- **Agent wake-ups**: every run with what woke it (a schedule, its own follow-up or its own recurring watch), each tool call as it happens, and its one-line log. Skipped triages show as a single grey line
- **Your phone**: the agent's pages, warnings and notes, and Approve/Deny buttons for rollback requests

Below them: the checkout error rate and database disk charts, the schedule table (the static ones and every one the agent made, with who made it), and incidents.

In the sidebar, set how many real seconds a simulated minute takes, turn on **Simulate the on-call human** to approve rollbacks automatically after 2 minutes, and use **Make trouble** to inject events. The sidebar also shows long-term memory as the agent writes it. After the scripted morning ends at 09:48, try a bad deploy, then a payments-provider outage: the agent should roll back the first and refuse to roll back the second. **Download shift log (JSON)** at the bottom of the page saves everything that happened.

The background loop pauses itself when no browser tab has been watching for 30 seconds, so a forgotten tab doesn't keep spending tokens.

### Terminal

```bash
uv run python main.py                   # 09:00-09:48 shift, rollbacks approved after 2 min
uv run python main.py --approve ask     # you approve or deny each rollback
uv run python main.py --approve never   # nobody answers: watch the agent escalate
uv run python main.py --fresh-memory    # forget lessons from earlier shifts
```

A full shift wakes the agent around 15 to 20 times (plus a few skipped triages) and takes a few minutes. It ends with a summary: events, wake-ups, messages sent, incidents, approvals and long-term memory.

### Offline checks

```bash
uv run python test_offline.py
```

Covers the cron server, schedule validation, the simulated world (bad deploy, rollback, disk story, provider outage) and the runtime's skip-when-quiet rule, with a stub in place of the model. No API key needed.

## The scripted morning

| Time | What happens | What a good agent does |
| --- | --- | --- |
| 09:00 | Shift starts, nothing has happened | Nothing. The triage is skipped without a model call |
| 09:03 | orders-db disk crosses 70%, growing about 0.5%/min | Warns, and sets itself a recurring disk watch |
| 09:04, 09:08 | A search-api deploy, team chatter | Nothing |
| 09:12 | checkout-api v2.14.0 ships a new payment retry policy | |
| 09:13 | Checkout 5xx above 2% | |
| 09:15 | Triage wakes the agent | Opens an incident, pages you, requests a rollback to v2.13.2, schedules a follow-up |
| 09:16-09:17 | Provider status page says all clear; a customer reports a double charge | Links the ticket to the incident, rules out the provider |
| After approval | Rollback runs, errors fall back to baseline | Follows up every few minutes, resolves the incident, saves the lesson |
| 09:24 | Disk crosses 80% | Keeps watching without repeating itself |
| 09:30 | A teammate turns off debug logging; disk drops to 58% | Cancels its own disk watch |
| 09:35 | v2.14.1 fixes the retry policy | Checks the new deploy stays healthy |
| 09:47 | End-of-shift schedule | Sends the handoff and saves durable lessons |

## 📂 Project Structure

```
proactive_oncall_agent/
├── schedules/
│   ├── triage.py          # every 5 min: triage the event stream (skipped when quiet)
│   └── shift_handoff.py   # end of shift: handoff note + long-term memory
├── agent.py               # Kimi K3.1 Pro agent: tools, dynamic situation prompt, run loop
├── cron.py                # in-process cron server and define_schedule()
├── desk.py                # notifications, incidents, long-term memory, Slack delivery
├── world.py               # simulated checkout service, monitoring rules, approvals
├── runtime.py             # clock + world + cron + agent, background loop for the UI
├── app.py                 # Streamlit dashboard
├── main.py                # terminal run of a shift
├── test_offline.py        # offline checks, no API key needed
├── .streamlit/config.toml # Nebius Token Factory colors
├── pyproject.toml
└── .env.example
```

## Make it yours

- **Real events**: `World` is the only simulated part. Replace `get_new_events`, `get_metrics` and `get_deploy_history` with calls to your alerting, metrics and CI systems, and `request_rollback` with your deploy tool's approval flow.
- **Wall-clock time**: the cron server takes `now` as an argument. Call `cron.due(datetime.now())` once a minute instead of advancing the simulated clock, and set `schedules/shift_handoff.py` to something like `cron="0 17 * * 1-5"`.
- **Managed Deep Agents**: the schedule files and tools are shaped like LangSmith's [Managed Deep Agents schedules](https://docs.langchain.com/langsmith/python/managed-deep-agents-schedules). To deploy there, import `define_schedule` from `managed_deepagents`, and call `runtime.schedules.create(owner={"type": "user"}, cron=... or at=..., prompt=...)` inside the schedule tools.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- [Why aren't you building proactive agents yet?](https://www.langchain.com/blog/proactive-agents) from LangChain, for the idea and its two building blocks
- [Nebius Token Factory](https://dub.sh/nebius) for serving Kimi K3.1 Pro
