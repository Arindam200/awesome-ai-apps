from __future__ import annotations

from pydantic import BaseModel, Field


class GameSpec(BaseModel):
    title: str = Field(description="Short, playful game title.")
    genre: str = Field(description="Simple browser game genre.")
    visual_style: str = Field(description="Concise art direction using CSS/canvas only.")
    controls: list[str] = Field(description="Player controls, such as arrow keys or mouse click.")
    rules: list[str] = Field(description="Core gameplay rules.")
    objective: str = Field(description="What the player is trying to do.")
    win_condition: str = Field(description="How the player wins, survives, or completes the game.")
    lose_condition: str = Field(description="How the player loses or restarts.")
    entities: list[str] = Field(description="Important game objects or characters.")
    tone: str = Field(description="Mood of the game.")


class GameReview(BaseModel):
    approved: bool = Field(description="Whether the game is ready to render.")
    issues: list[str] = Field(default_factory=list, description="Concrete issues to fix.")
    fix_instructions: str = Field(default="", description="Specific instructions for a repair pass.")


class GeneratedGame(BaseModel):
    prompt: str
    spec: GameSpec
    html: str
    review: GameReview
    repaired: bool = False
    safety_issues: list[str] = Field(default_factory=list)
