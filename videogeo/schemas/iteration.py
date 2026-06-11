"""Iteration contracts for multi-round video generation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IterationAction(BaseModel):
    type: str = Field(description="regenerate_segment / regenerate_storyboard / regenerate_caption / keep")
    segment_index: int | None = None
    reason: str = ""
    prompt_patch: str = ""


class IterationDecision(BaseModel):
    round: int = Field(ge=0)
    previous_score: float = Field(default=0.0, ge=0, le=1)
    target_score: float = Field(default=0.86, ge=0, le=1)
    actions: list[IterationAction] = Field(default_factory=list)
    keep: list[str] = Field(default_factory=list)
    reject: list[str] = Field(default_factory=list)
    budget_note: str = ""


class CandidateComparison(BaseModel):
    segment_index: int | None = None
    old_url: str = ""
    new_url: str = ""
    score_delta: float = 0.0
    winner: str = "old"
    why: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
