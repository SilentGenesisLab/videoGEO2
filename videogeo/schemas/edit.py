"""FinalVideo — 剪辑 Agent 的产物：成片 + 时间线。

剪辑 Agent 用 LLM 规划 timeline（顺序、转场、配音/字幕轨），再调
capabilities.assemble_video 合成最终视频，url 落在这里。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineEntry(BaseModel):
    """时间线上的一个片段安排。"""

    shot_index: int = Field(ge=0, description="引用的分镜")
    start_sec: float = Field(ge=0, description="在成片中的起点")
    end_sec: float = Field(gt=0, description="在成片中的终点")
    transition_in: str = Field(default="cut", description="入场转场")


class FinalVideo(BaseModel):
    """剪辑输出：成片地址 + 时间线 + 字幕/混音说明。"""

    title: str = Field(description="成片标题")
    video_url: str = Field(description="合成后的成片 url（mock 模式为占位）")
    duration_sec: float = Field(gt=0, description="成片总时长")
    timeline: list[TimelineEntry] = Field(description="时间线编排")
    has_subtitles: bool = Field(default=False, description="是否烧入字幕")
    audio_mix: str = Field(default="", description="混音说明：旁白 + BGM 的处理")
