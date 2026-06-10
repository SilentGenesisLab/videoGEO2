"""Plan contract.

Plan is the deterministic bridge between the Codex leader and the thin Python
executor. It is both an execution list and a resumable status file.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StepType = Literal["image", "video", "tts", "music", "concat"]
StepStatus = Literal["pending", "running", "done", "failed", "skipped"]


class PlanStep(BaseModel):
    """One executable step."""

    id: str = Field(description="Unique step id, e.g. seg0.img / seg0.vid / bgm / final")
    title: str = Field(description="Human-readable title for progress display")
    type: StepType = Field(description="Capability type")
    shot_index: int | None = Field(default=None, description="Render segment index; global steps use None")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Capability inputs")
    depends_on: list[str] = Field(default_factory=list, description="Prerequisite step ids")

    status: StepStatus = Field(default="pending", description="Execution status")
    output: dict[str, Any] | None = Field(default=None, description="Generated outputs")
    error: str = Field(default="", description="Failure reason")
    attempts: int = Field(default=0, description="Attempt count")
    started_at: str = Field(default="", description="UTC ISO timestamp")
    finished_at: str = Field(default="", description="UTC ISO timestamp")
    elapsed_sec: float = Field(default=0.0, description="Wall-clock runtime for the latest attempt")


class Plan(BaseModel):
    """Complete executable plan."""

    run_id: str = Field(description="Run id; maps to runs/<run_id>/")
    title: str = Field(description="Working title")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    target_duration_sec: int = Field(default=15, description="Target final duration")
    steps: list[PlanStep] = Field(description="Dependency-sorted steps")

    def step(self, step_id: str) -> PlanStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def ready_steps(self, *, include: set[str] | None = None) -> list[PlanStep]:
        done = {s.id for s in self.steps if s.status == "done"}
        out: list[PlanStep] = []
        for s in self.steps:
            if s.status != "pending":
                continue
            if include is not None and s.type not in include:
                continue
            if all(dep in done for dep in s.depends_on):
                out.append(s)
        return out

    def is_done(self, *, include: set[str] | None = None) -> bool:
        return all(s.status == "done" for s in self.steps if include is None or s.type in include)

    def has_failure(self) -> bool:
        return any(s.status == "failed" for s in self.steps)

    def render_outline(self) -> str:
        glyph = {"done": "ok", "running": "run", "pending": "wait", "failed": "fail", "skipped": "skip"}
        lines = [f"[plan] {self.title} ({self.aspect_ratio}, target {self.target_duration_sec}s) run={self.run_id}"]
        for s in self.steps:
            dep = f" <- {','.join(s.depends_on)}" if s.depends_on else ""
            elapsed = f" {s.elapsed_sec:.1f}s" if s.elapsed_sec else ""
            lines.append(f"  {glyph.get(s.status, '?')} [{s.id}] {s.title}{elapsed}{dep}")
        return "\n".join(lines)
