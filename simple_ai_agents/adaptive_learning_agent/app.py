"""
Adaptive Learning Agent
------------------------
A minimal Streamlit app that demonstrates knowledge-gap identification:

1. A student answers a quiz question.
2. Gemini classifies whether the answer is correct, and if not,
   what *type* of misconception it likely reflects.
3. A simple per-topic mastery score updates based on the result.

This is intentionally small and self-contained so it's easy to read,
run, and extend.
"""

import os
import json
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error(
        "GEMINI_API_KEY not found. Copy .env.example to .env and add your "
        "free key from https://aistudio.google.com/app/apikey"
    )
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# --- A tiny sample question bank -------------------------------------------
# Each question is tagged with a topic so we can track per-topic mastery.
QUESTIONS = [
    {
        "topic": "Fractions",
        "question": "What is 1/2 + 1/3?",
        "correct_answer": "5/6",
    },
    {
        "topic": "Algebra",
        "question": "Solve for x: 2x + 4 = 12",
        "correct_answer": "x = 4",
    },
    {
        "topic": "Geometry",
        "question": "What is the sum of interior angles in a triangle?",
        "correct_answer": "180 degrees",
    },
]

# --- Session state -----------------------------------------------------------
if "mastery" not in st.session_state:
    # mastery score per topic, starts neutral at 50
    st.session_state.mastery = {q["topic"]: 50 for q in QUESTIONS}
if "history" not in st.session_state:
    st.session_state.history = []


def classify_response(question: str, correct_answer: str, student_answer: str) -> dict:
    """
    Ask Gemini to judge correctness and, if wrong, classify the
    likely misconception. Returns a dict with keys:
    is_correct (bool), misconception_type (str), explanation (str)
    """
    prompt = f"""
You are an expert tutor analyzing a student's answer.

Question: {question}
Correct answer: {correct_answer}
Student's answer: {student_answer}

Determine:
1. Whether the student's answer is correct (true/false).
2. If incorrect, classify the TYPE of misconception in a few words
   (e.g. "added numerators and denominators separately",
   "sign error", "arithmetic slip", "misapplied formula").
   If correct, set this to "none".
3. A one-sentence, encouraging explanation suitable to show the student.

Respond ONLY with valid JSON in this exact shape, no markdown fences:
{{"is_correct": true or false, "misconception_type": "...", "explanation": "..."}}
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    # Defensive cleanup in case the model wraps the JSON in fences anyway
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "is_correct": False,
            "misconception_type": "unknown (could not parse model response)",
            "explanation": text,
        }


def update_mastery(topic: str, is_correct: bool):
    """Simple mastery update: nudge score up or down, clamped to [0, 100]."""
    delta = 10 if is_correct else -10
    st.session_state.mastery[topic] = max(
        0, min(100, st.session_state.mastery[topic] + delta)
    )


def mastery_color(score: int) -> str:
    if score >= 70:
        return "🟢"
    if score >= 40:
        return "🟡"
    return "🔴"


# --- UI -----------------------------------------------------------------
st.set_page_config(page_title="Adaptive Learning Agent", page_icon="🧠")
st.title("🧠 Adaptive Learning Agent")
st.caption(
    "A small demo of knowledge-gap identification: answer a question and "
    "watch the mastery dashboard update based on your response."
)

st.subheader("📊 Current Mastery")
cols = st.columns(len(QUESTIONS))
for col, q in zip(cols, QUESTIONS):
    score = st.session_state.mastery[q["topic"]]
    col.metric(f"{mastery_color(score)} {q['topic']}", f"{score}/100")

st.divider()

st.subheader("✏️ Answer a Question")
q_index = st.selectbox(
    "Pick a question",
    range(len(QUESTIONS)),
    format_func=lambda i: f"{QUESTIONS[i]['topic']}: {QUESTIONS[i]['question']}",
)
current_q = QUESTIONS[q_index]

student_answer = st.text_input("Your answer:")

if st.button("Submit Answer", type="primary") and student_answer.strip():
    with st.spinner("Analyzing your response..."):
        result = classify_response(
            current_q["question"], current_q["correct_answer"], student_answer
        )
    update_mastery(current_q["topic"], result["is_correct"])
    st.session_state.history.append(
        {"topic": current_q["topic"], **result, "student_answer": student_answer}
    )

    if result["is_correct"]:
        st.success(f"✅ Correct! {result['explanation']}")
    else:
        st.error(f"❌ Not quite. {result['explanation']}")
        st.info(f"**Detected misconception:** {result['misconception_type']}")

if st.session_state.history:
    st.divider()
    st.subheader("🕘 Response History")
    for entry in reversed(st.session_state.history):
        icon = "✅" if entry["is_correct"] else "❌"
        st.write(
            f"{icon} **{entry['topic']}** — your answer: `{entry['student_answer']}` "
            f"— {entry['misconception_type'] if not entry['is_correct'] else 'Correct'}"
        )
