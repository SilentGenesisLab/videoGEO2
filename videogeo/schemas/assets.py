"""RenderedAssets — Renderer 执行 VideoScript 后产出的素材清单。

Renderer 是确定性执行器（非 LLM）：逐分镜调 capabilities 生成图像/视频/旁白音频，
把 url 收集到这里，交给剪辑 Agent 组装时间线。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ShotAssets(BaseModel):
    """单分镜渲染产物。url 在 mock 模式下是占位假链接。"""

    shot_index: int = Field(ge=0, description="对应 Shot.index")
    image_url: str = Field(default="", description="首帧/参考图 url")
    clip_url: str = Field(default="", description="生成的视频片段 url")
    narration_audio_url: str = Field(default="", description="旁白 TTS 音频 url；无旁白则空")
    duration_sec: float = Field(gt=0, description="实际片段时长")


class RenderedAssets(BaseModel):
    """整片所有分镜的渲染产物集合。"""

    shots: list[ShotAssets] = Field(description="按 shot_index 排列的分镜素材")
    bgm_url: str = Field(default="", description="背景音乐 url；可空")

    def is_complete(self) -> bool:
        """每个分镜至少要有 clip_url，否则剪辑无法进行。门禁/Renderer 自检用。"""
        return bool(self.shots) and all(s.clip_url for s in self.shots)
