"""GateVerdict — 审核门禁的裁决结果。

每个阶段的产物都要过门禁。passed=False 时，fix_instructions 会被回传给
对应 Agent 作为下一次重试的反馈，构成阻断式重试回环。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GateIssue(BaseModel):
    """门禁发现的一个具体问题。"""

    severity: str = Field(description="严重度：blocker / major / minor")
    field: str = Field(default="", description="问题指向的字段/分镜，便于定位")
    message: str = Field(description="问题描述")


class GateVerdict(BaseModel):
    """门禁裁决。passed 决定流水线是放行还是回环重试。"""

    passed: bool = Field(description="是否通过门禁")
    score: float = Field(ge=0, le=1, description="质量评分 0~1")
    issues: list[GateIssue] = Field(default_factory=list, description="发现的问题列表")
    fix_instructions: str = Field(
        default="", description="给 Agent 的整改指令；passed=True 时通常为空"
    )

    @classmethod
    def ok(cls, score: float = 1.0) -> "GateVerdict":
        """快捷构造一个通过的裁决（mock 门禁默认用）。"""
        return cls(passed=True, score=score)
