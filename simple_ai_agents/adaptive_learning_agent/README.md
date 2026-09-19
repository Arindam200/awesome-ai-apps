# Adaptive Learning Agent

A minimal Streamlit app that demonstrates **knowledge-gap identification**:
it takes a student's answer to a quiz question, uses Gemini to classify
*why* an incorrect answer is wrong (the specific misconception), and
updates a simple per-topic mastery score.

This is a small proof-of-concept built for an educational AI hackathon,
showing one practical pattern for adaptive learning systems: diagnosing
*why* a student got something wrong, not just *that* they got it wrong.

## ✨ Features

- Sample multi-topic quiz bank (Fractions, Algebra, Geometry)
- LLM-based correctness check + misconception classification
- Per-topic mastery score that updates after each answer (🟢🟡🔴 indicator)
- Response history log for the session

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) — UI
- [Gemini API](https://aistudio.google.com/) (`gemini-2.0-flash`) — answer analysis
- `python-dotenv` — environment variable management

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Setup

1. **Navigate to this directory**

   ```bash
   cd simple_ai_agents/adaptive_learning_agent
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and add your Gemini API key.

4. **Run the app**

   ```bash
   streamlit run app.py
   ```

   The app will open at `http://localhost:8501`.

## 📖 How It Works

1. The student picks a question from a small sample bank and submits an answer.
2. The answer, question, and correct answer are sent to Gemini with a prompt
   asking it to (a) judge correctness, and (b) if wrong, classify the specific
   type of misconception (e.g. "added numerators and denominators separately").
3. The per-topic mastery score is nudged up or down based on the result.
4. All responses are logged in a session history panel.

## 🔮 Possible Extensions

- Replace the static question bank with a real question database
- Build a prerequisite knowledge graph so one misconception can flag
  related "upstream" topics
- Add spaced-repetition scheduling based on mastery decay over time
- Serve targeted practice questions based on the detected misconception type

## 📝 Notes

This is a deliberately minimal example meant to illustrate the core
diagnostic pattern (analyze → classify → track mastery) rather than a
production-ready system.
