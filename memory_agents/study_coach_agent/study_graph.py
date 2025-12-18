from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field


class LearnerProfile(BaseModel):
    name: str = Field(..., description="Learner's name or handle.")
    main_goal: str = Field(..., description="Overall study goal (e.g. pass an exam).")
    timeframe: str = Field(
        ..., description="Time horizon for the goal (e.g. 3 months)."
    )
    subjects: list[str] = Field(default_factory=list, description="Subjects or topics.")
    weekly_hours: int = Field(..., ge=1, le=80, description="Planned hours per week.")
    preferred_formats: list[str] = Field(
        default_factory=list, description="e.g. 'videos', 'docs', 'practice problems'."
    )


class StudyLog(BaseModel):
    topic: str
    duration_minutes: int = Field(..., ge=5, le=600)
    resource_type: str = Field(
        ..., description="e.g. 'video', 'article', 'course', 'problems'."
    )
    perceived_difficulty: str = Field(
        ..., description="Learner's rating, e.g. 'easy', 'medium', 'hard'."
    )
    mood: str | None = Field(
        default=None, description="Optional mood/motivation description."
    )
    free_notes: str | None = None


class QuizQuestion(BaseModel):
    question: str
    type: str = Field(
        default="short_answer", description="short_answer or multiple_choice."
    )
    options: list[str] | None = None


class VerificationResult(BaseModel):
    quiz: list[QuizQuestion]
    explanation_prompt: str
    score: int | None = None
    feedback: str | None = None
    next_step_recommendation: str | None = None


class VerificationState(TypedDict, total=False):
    profile: LearnerProfile
    log: StudyLog
    quiz: list[QuizQuestion]
    explanation_prompt: str
    user_quiz_answers: list[str]
    user_explanation: str
    score: int
    feedback: str
    next_step_recommendation: str


def _generate_quiz_node(state: VerificationState, llm_client) -> VerificationState:
    profile = state["profile"]
    log = state["log"]

    system_prompt = (
        "You are an AI study coach. Given a topic and learner context, "
        "write 3-5 focused quiz questions that test real understanding, "
        "not rote memorization."
    )
    user_prompt = (
        f"Learner goal: {profile.main_goal} over {profile.timeframe}\n"
        f"Subjects: {', '.join(profile.subjects) or 'N/A'}\n"
        f"Today's topic: {log.topic}\n"
        f"Perceived difficulty: {log.perceived_difficulty}\n\n"
        "Return the quiz as a numbered list of short-answer questions only."
    )
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content or ""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    questions: list[QuizQuestion] = []
    for line in lines:
        # Strip leading numbering if present
        if line[0].isdigit():
            # e.g. "1. Question"
            parts = line.split(".", 1)
            if len(parts) == 2:
                line = parts[1].strip()
        questions.append(QuizQuestion(question=line))

    if not questions:
        questions = [
            QuizQuestion(
                question=f"Explain the key ideas you learned today about {log.topic}."
            )
        ]

    explanation_prompt = (
        f"In a few paragraphs, explain in your own words what you learned today "
        f"about {log.topic}. Focus on intuition and why things work, not just formulas."
    )

    state["quiz"] = questions
    state["explanation_prompt"] = explanation_prompt
    return state


def _evaluate_node(state: VerificationState, llm_client) -> VerificationState:
    profile = state["profile"]
    log = state["log"]
    questions = state.get("quiz", [])
    answers = state.get("user_quiz_answers", [])
    explanation = state.get("user_explanation", "")

    qa_pairs = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else ""
        qa_pairs.append(f"Q{i + 1}: {q.question}\nA{i + 1}: {ans}")
    qa_text = "\n\n".join(qa_pairs)

    system_prompt = (
        "You are an expert tutor. Given the learner's goal, topic, quiz questions, "
        "their answers and explanation, evaluate understanding on a 0-100 scale. "
        "Be strict but encouraging. Identify misconceptions and suggest how to fix them."
    )
    user_prompt = (
        f"Learner goal: {profile.main_goal} over {profile.timeframe}\n"
        f"Today's topic: {log.topic}\n\n"
        f"Quiz and answers:\n{qa_text}\n\n"
        f"Learner's explanation:\n{explanation}\n\n"
        "1) First, provide a single integer score from 0 to 100.\n"
        "2) Then provide concise feedback and next-step advice.\n"
        "Respond in the JSON form: "
        '{"score": <int>, "feedback": "<text>", "next_step": "<text>"}'
    )
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.choices[0].message.content or ""

    # Very small and permissive JSON-ish parsing
    score = 0
    feedback = ""
    next_step = ""
    try:
        import json  # local import to keep top neat

        start = raw.find("{")
        end = raw.rfind("}")
        obj = json.loads(raw[start : end + 1])
        score = int(obj.get("score", 0))
        feedback = str(obj.get("feedback", "") or "")
        next_step = str(obj.get("next_step", "") or "")
    except Exception:
        feedback = raw
        next_step = ""

    state["score"] = score
    state["feedback"] = feedback
    state["next_step_recommendation"] = next_step
    return state


def build_verification_graph(llm_client):
    """
    Build a very small LangGraph graph with two nodes:
    - generate_quiz
    - evaluate (called after the UI has collected answers)
    The UI will typically:
      1) Run generate_quiz
      2) Show quiz & explanation prompt, collect user responses
      3) Re-run graph with answers to execute evaluate
    """
    graph = StateGraph(VerificationState)  # type: ignore[invalid-argument-type]

    def generate_quiz(state: VerificationState) -> VerificationState:
        return _generate_quiz_node(state, llm_client)

    def evaluate(state: VerificationState) -> VerificationState:
        return _evaluate_node(state, llm_client)

    graph.add_node("generate_quiz", generate_quiz)
    graph.add_node("evaluate", evaluate)

    graph.set_entry_point("generate_quiz")
    graph.add_edge("generate_quiz", "evaluate")
    graph.add_edge("evaluate", END)

    return graph.compile()


def run_initial_verification(
    profile: LearnerProfile, log: StudyLog, llm_client
) -> VerificationResult:
    """
    Convenience helper for step 1:
    - Given profile and log, generate quiz + explanation prompt.
    - Do NOT evaluate yet (no answers).
    """
    graph = build_verification_graph(llm_client)
    init_state: VerificationState = {
        "profile": profile,
        "log": log,
        "user_quiz_answers": [],
        "user_explanation": "",
    }
    result_state = graph.invoke(init_state, config={"run_evaluation": False})
    return VerificationResult(
        quiz=result_state["quiz"],
        explanation_prompt=result_state["explanation_prompt"],
    )


def run_full_evaluation(
    profile: LearnerProfile,
    log: StudyLog,
    user_quiz_answers: list[str],
    user_explanation: str,
    llm_client,
) -> VerificationResult:
    """
    Step 2:
    - Take user answers + explanation and run full graph (including evaluation).
    """
    graph = build_verification_graph(llm_client)
    init_state: VerificationState = {
        "profile": profile,
        "log": log,
        "user_quiz_answers": user_quiz_answers,
        "user_explanation": user_explanation,
    }
    result_state = graph.invoke(init_state)
    return VerificationResult(
        quiz=result_state["quiz"],
        explanation_prompt=result_state["explanation_prompt"],
        score=result_state.get("score"),
        feedback=result_state.get("feedback"),
        next_step_recommendation=result_state.get("next_step_recommendation"),
    )
