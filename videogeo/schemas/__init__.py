"""Pydantic contracts exchanged between Codex agents and the executor."""
from __future__ import annotations

from videogeo.schemas.assets import RenderedAssets, ShotAssets
from videogeo.schemas.audit import SelfAudit
from videogeo.schemas.brief import Beat, CreativeBrief, VisualSpec
from videogeo.schemas.captions import CaptionCue, CaptionPlan, CaptionStyle
from videogeo.schemas.edit import FinalVideo, TimelineEntry
from videogeo.schemas.gate import GateIssue, GateVerdict
from videogeo.schemas.iteration import CandidateComparison, IterationAction, IterationDecision
from videogeo.schemas.lessons import Lesson, RetrievedLessons
from videogeo.schemas.plan import Plan, PlanStep, StepStatus, StepType
from videogeo.schemas.quality import QualityDimension, QualityScorecard
from videogeo.schemas.requirement import Requirement
from videogeo.schemas.script import GlobalNarrative, RenderSegment, Shot, VideoScript

__all__ = [
    "Requirement",
    "CreativeBrief",
    "Beat",
    "VisualSpec",
    "VideoScript",
    "GlobalNarrative",
    "Shot",
    "RenderSegment",
    "Plan",
    "PlanStep",
    "StepType",
    "StepStatus",
    "RenderedAssets",
    "ShotAssets",
    "FinalVideo",
    "TimelineEntry",
    "CaptionPlan",
    "CaptionStyle",
    "CaptionCue",
    "GateVerdict",
    "GateIssue",
    "QualityScorecard",
    "QualityDimension",
    "IterationDecision",
    "IterationAction",
    "CandidateComparison",
    "Lesson",
    "RetrievedLessons",
    "SelfAudit",
]
