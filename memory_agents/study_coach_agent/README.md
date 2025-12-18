### AI Study Coach with Memori & LangGraph

An AI-powered **Study Coach** that uses **Memori v3** as long-term memory and **LangGraph** for multi-step verification of understanding.

- **Plans & tracks** your learning via a Streamlit UI.
- Uses **LangGraph** to generate quizzes and evaluate real understanding.
- Stores **structured learner profiles and study sessions in Memori** (SQLite/Postgres/MySQL/MongoDB, configurable).
- Provides a **Memori-powered chat** to reflect on progress, weak topics, and learning patterns.

---

### Features

- 🧭 **Study Plan tab**
  - Capture a structured learner profile:
    - Name / handle
    - Main goal (e.g. “Pass AWS SAA”, “Master LangGraph”)
    - Timeframe
    - Subjects / topics
    - Weekly study hours
    - Preferred formats (videos, docs, practice problems, etc.)
  - Profile is saved into **Memori** as a tagged JSON document and automatically reused across sessions.

- 📅 **Today’s Session tab**
  - Log each study session:
    - Topic, duration, resource type, perceived difficulty, mood, notes.
  - Runs a **LangGraph-powered verification flow**:
    - Generates 3–5 quiz questions.
    - Prompts you to explain the topic “in your own words”.
    - Evaluates understanding (0–100), surfaces feedback, and suggests a next step.
  - Writes a summarised study session into **Memori** (topic, score, difficulty, mood, feedback, next step).

- 📈 **Progress & Memory tab (chat)**
  - Chat with a Memori-backed assistant about your learning history:
    - “What are my weakest topics right now?”
    - “When do I usually perform best?”
    - “Do I learn better from videos or practice problems?”
  - Uses the same Memori store that holds your profile + session summaries.

- ⚙️ **Configurable storage**
  - By default uses **SQLite** (`./memori_study.sqlite`).
  - Optional **Database URL** in the sidebar to point Memori at:
    - SQLite via SQLAlchemy: `sqlite:///memori_study.sqlite`
    - PostgreSQL: `postgresql+psycopg://user:password@host:5432/database`
    - MySQL: `mysql+pymysql://user:password@host:3306/database`
    - MongoDB: `mongodb://host:27017/memori`

---

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- `OPENAI_API_KEY` (Memori registers this OpenAI client)
- Optional:
  - `MEMORI_DB_URL` for custom DB (otherwise SQLite is used)
  - `MEMORI_API_KEY` for Memori advanced augmentation / quotas

---

### Install & Run

From the repo root:

```bash
cd memory_agents/study_coach_agent
uv sync
```

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_key_here
# Optional:
# MEMORI_DB_URL=postgresql+psycopg://user:password@host:5432/database
# MEMORI_API_KEY=your_memori_key_here
```

Run the app:

```bash
uv run streamlit run app.py
```

Or with plain pip:

```bash
pip install -e .
streamlit run app.py
```

If `MEMORI_DB_URL` is not set, the app will create/use `./memori_study.sqlite` for Memori v3.

## License

See the main repository LICENSE file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Made with ❤️ by [Studio1](https://www.Studio1hq.com) Team
