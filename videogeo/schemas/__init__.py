"""产物契约 —— Agent（Codex subagents）之间传递的 Pydantic 模型。

流水线契约链（每一环是上一环的下游消费）：
    Requirement → CreativeBrief → VideoScript → Plan → RenderedAssets → FinalVideo

GateVerdict 是横切契约：gate-reviewer subagent 对任意阶段产物的裁决结构。
这些 schema 是 Codex 大脑与薄执行器之间唯一的硬契约；编排逻辑写在 AGENTS.md，不在这里。
"""
from __future__ import annotations

from videogeo.schemas.assets import RenderedAssets, ShotAssets
from videogeo.schemas.brief import Beat, CreativeBrief, VisualSpec
from videogeo.schemas.edit import FinalVideo, TimelineEntry
from videogeo.schemas.gate import GateIssue, GateVerdict
from videogeo.schemas.plan import Plan, PlanStep, StepStatus, StepType
from videogeo.schemas.requirement import Requirement
from videogeo.schemas.script import Shot, VideoScript

__all__ = [
    "Requirement",
    "CreativeBrief",
    "Beat",
    "VisualSpec",
    "VideoScript",
    "Shot",
    "Plan",
    "PlanStep",
    "StepType",
    "StepStatus",
    "RenderedAssets",
    "ShotAssets",
    "FinalVideo",
    "TimelineEntry",
    "GateVerdict",
    "GateIssue",
]
