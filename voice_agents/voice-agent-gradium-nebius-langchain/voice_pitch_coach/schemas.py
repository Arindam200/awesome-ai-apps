from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DeliveryScores(BaseModel):
    clarity: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    concision: int = Field(ge=0, le=100)
    audience_fit: int = Field(ge=0, le=100)


class CoachTurn(BaseModel):
    mode: Literal["pitch", "interview", "storytelling", "sales"]
    overall_score: int = Field(ge=0, le=100)
    scores: DeliveryScores
    transcript_summary: str
    strengths: list[str]
    improvements: list[str]
    suggested_rewrite: str
    spoken_feedback: str
    next_question: str
    practice_drill: str
