"""Structured outputs requested from the LLM. All fields are required (nullable where noted)
so the same models work as Gemini response schemas and as Pydantic validators."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TextDiagnosis(BaseModel):
    correct: bool
    misconception_tag: str = Field(description="One tag from the allowed list")
    error_step: str | None = Field(description="The step or part of the answer that went wrong, or null")
    confidence: float = Field(description="0 to 1")
    feedback_student: str = Field(description="At most 30 words, second person, kind")


class PhotoDiagnosis(BaseModel):
    steps: list[str] = Field(description="Each written step, transcribed exactly, in order")
    final_answer_read: str | None
    correct: bool
    error_step: int | None = Field(description="1-based index into steps of the first wrong step, or null")
    misconception_tag: str
    confidence: float
    feedback_student: str


class PracticeItem(BaseModel):
    stem: str
    answer: str


class Lesson(BaseModel):
    language: str
    lesson_md: str = Field(description="At most 150 words with one worked example")
    practice: list[PracticeItem] = Field(description="Exactly 3 short practice items")


class TeacherRecommendation(BaseModel):
    group_label: str
    concept_id: str
    misconception_tag: str
    headline: str = Field(description="At most 15 words")
    plan_5min: list[str] = Field(description="3 to 5 concrete steps")
    worked_example: str
    why: str = Field(description="At most 40 words, cites the numbers given")


class StudentNextSteps(BaseModel):
    student_id: str
    items: list[str]


class CoachProposal(BaseModel):
    recommendations: list[TeacherRecommendation]
    student_next_steps: list[StudentNextSteps]


class Critique(BaseModel):
    recommendation_index: int
    verdict: str = Field(description="accept or revise")
    reason: str = Field(description="At most 40 words, cites the numbers")


class CritiqueSet(BaseModel):
    critiques: list[Critique]


class ParentMessage(BaseModel):
    language: str
    message: str = Field(description="At most 80 words")
