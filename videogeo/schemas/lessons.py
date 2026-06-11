"""Persistent lesson contracts."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class Lesson(BaseModel):
    id: str
    date: str = Field(default_factory=lambda: date.today().isoformat())
    domain: str = "product_tvc"
    provider: str = ""
    stage: str = ""
    polarity: str = Field(default="positive", description="positive / negative")
    symptom: str = ""
    cause: str = ""
    fix_pattern: str = ""
    anti_pattern: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class RetrievedLessons(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    lessons: list[Lesson] = Field(default_factory=list)
