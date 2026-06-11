"""Self-audit contract for completed runs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SelfAudit(BaseModel):
    run_id: str
    delivered_video_url: str = ""
    artifact_presence: dict[str, bool] = Field(default_factory=dict)
    gate_summary: list[dict[str, Any]] = Field(default_factory=list)
    iteration_summary: dict[str, Any] = Field(default_factory=dict)
    technical_checks: dict[str, Any] = Field(default_factory=dict)
    known_risks: list[str] = Field(default_factory=list)
    secrets_check: str = ""
    git_check: str = ""
