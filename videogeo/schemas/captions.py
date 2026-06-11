"""Caption planning contract for HyperFrames subtitle composition."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CaptionStyle(BaseModel):
    font_family: str = Field(default="Noto Sans CJK SC, Source Han Sans SC, Microsoft YaHei, sans-serif")
    font_weight: int = Field(default=600)
    position: str = Field(default="bottom_safe", description="bottom_safe / top_safe / custom")
    max_lines: int = Field(default=2, ge=1, le=3)
    max_chars_per_line_zh: int = Field(default=14, ge=4, le=30)
    max_chars_per_line_en: int = Field(default=34, ge=8, le=60)
    background: str = Field(default="soft_shadow", description="soft_shadow / translucent_plate / none")
    avoid_product_occlusion: bool = True


class CaptionCue(BaseModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    text: str = Field(description="Caption text")
    emphasis: list[str] = Field(default_factory=list)
    source: str = Field(default="")

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


class CaptionPlan(BaseModel):
    enabled: bool = True
    language: str = "zh"
    style: CaptionStyle = Field(default_factory=CaptionStyle)
    cues: list[CaptionCue] = Field(default_factory=list)
    source_video_url: str = Field(default="")
    notes: list[str] = Field(default_factory=list)
