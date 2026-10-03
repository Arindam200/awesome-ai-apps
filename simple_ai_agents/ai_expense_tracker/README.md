# AI Expense Tracker

A chat-based expense tracker that provisions its own database on first run. Tell it what you spent, ask it questions about your spending — the backend sets itself up.

## 🚀 Features

- **Natural-language input**: "Spent $45 on dinner with friends" → parsed, categorized, stored.
- **Spending queries**: "How much did I spend on food this month?" → answered with live data.
- **Self-provisioning backend**: The database is created automatically on first run — no account required.

## 🛠️ Tech Stack

- **Python**: Core language
- **Streamlit**: Chat UI
- **Nebius Token Factory**: LLM inference (Llama 3.3 70B) for parsing and query generation
- **Cohesivity**: Database provisioning and SQL over HTTP — no account or API keys required to start

## Workflow

1. On first run, [Cohesivity](https://cohesivity.ai?ref=gh-awesome-ai-apps) bootstraps a project and provisions a Postgres database.
2. You type a message in the chat.
3. Nebius Token Factory classifies it as either an expense ("spent $20 on coffee") or a question ("what did I spend this week?").
4. Expenses are stored in the database. Questions become SQL queries that run against it.
5. Results are formatted and shown in the chat.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- Node.js (for the one-time Cohesivity bootstrap) or `curl`
- [Nebius Token Factory](https://studio.nebius.com/) API key

### Environment Variables

Create a `.env` file:

```env
NEBIUS_API_KEY=your_nebius_api_key_here
```

That's the only key you need. The database backend provisions itself.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/simple_ai_agents/ai_expense_tracker
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your Nebius API key
   ```

## ⚙️ Usage

```bash
streamlit run main.py
```

On first run the app will:
1. Bootstrap a Cohesivity project (creates `.cohesivity` with credentials).
2. Provision a Postgres database.
3. Create the `expenses` table.

Then start chatting:

- **Add expenses**: "Spent $12 on lunch", "Paid $50 for electricity yesterday", "$200 on flights to NYC"
- **Ask questions**: "How much did I spend this week?", "What's my top category this month?", "Show me all food expenses"

## 📂 Project Structure

```
ai_expense_tracker/
├── main.py             # Everything: Streamlit UI, Nebius LLM, Cohesivity backend
├── .env.example        # Environment template (one key)
├── requirements.txt    # Python dependencies
└── README.md
```

## About Cohesivity

[Cohesivity](https://cohesivity.ai?ref=gh-awesome-ai-apps) is backend infrastructure for AI agents — one HTTP API to provision databases, storage, auth, hosting, and AI services without account creation or provider keys. The agent bootstraps a project, provisions what it needs, and builds. The user claims ownership when the project works.

In this example, Cohesivity handles the Postgres database. The app calls `npx @cohesivity/init` on first run, which creates a 72-hour ephemeral project. One POST provisions the database, and all queries go through a plain HTTP endpoint.

## 🤝 Contributing

See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for details.

## 📄 License

MIT — see [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE).
