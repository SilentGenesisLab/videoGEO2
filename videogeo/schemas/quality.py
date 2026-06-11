"""Professional quality scorecards used by semantic gates and iteration."""
from __future__ import annotations

from pydantic import BaseModel, Field


class QualityDimension(BaseModel):
    """One weighted quality dimension."""

    name: str = Field(description="Stable dimension id")
    weight: float = Field(ge=0, le=1, description="Relative weight")
    score: float = Field(ge=0, le=1, description="0-1 score")
    severity: str = Field(default="minor", description="blocker / major / minor / info")
    evidence: str = Field(default="", description="Concrete observation")
    fix: str = Field(default="", description="Actionable fix")


class QualityScorecard(BaseModel):
    """Weighted professional gate verdict."""

    stage: str = Field(description="brief / script / storyboard / video / caption / delivery")
    passed: bool = Field(description="Whether the gate passes")
    score: float = Field(ge=0, le=1, description="Weighted total")
    threshold: float = Field(ge=0, le=1, description="Required score")
    dimensions: list[QualityDimension] = Field(default_factory=list)
    regenerate_targets: list[str] = Field(default_factory=list)
    fix_instructions: str = Field(default="")

    @classmethod
    def from_dimensions(
        cls,
        *,
        stage: str,
        threshold: float,
        dimensions: list[QualityDimension],
        regenerate_targets: list[str] | None = None,
        fix_instructions: str = "",
    ) -> "QualityScorecard":
        total_weight = sum(d.weight for d in dimensions) or 1.0
        score = sum(d.weight * d.score for d in dimensions) / total_weight
        has_blocker = any(d.severity == "blocker" and d.score < threshold for d in dimensions)
        passed = score >= threshold and not has_blocker
        if not fix_instructions and not passed:
            fixes = [d.fix for d in dimensions if d.fix and d.score < threshold]
            fix_instructions = " | ".join(fixes[:5])
        return cls(
            stage=stage,
            passed=passed,
            score=round(score, 3),
            threshold=threshold,
            dimensions=dimensions,
            regenerate_targets=regenerate_targets or [],
            fix_instructions=fix_instructions,
        )
