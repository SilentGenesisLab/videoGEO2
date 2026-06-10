"""VideoScript — 脚本编排 Agent 的产物：可执行的分镜 JSON 序列。

每个 Shot 是渲染层可直接消费的指令：图像 prompt、视频 prompt、旁白文本、
时长、转场。Renderer 遍历这些 Shot 逐一调媒体能力生成素材。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Shot(BaseModel):
    """单个分镜 —— 渲染层的最小可执行单元。"""

    index: int = Field(ge=0, description="分镜序号，从 0 起，决定时间线顺序")
    beat: str = Field(default="", description="所属叙事节拍名（关联 CreativeBrief.beats）")
    duration_sec: float = Field(gt=0, description="该分镜时长（秒）")
    image_prompt: str = Field(description="首帧/参考图的图像生成 prompt")
    video_prompt: str = Field(description="视频生成 prompt（运动、镜头、内容）")
    narration: str = Field(default="", description="旁白文本；空则该镜无旁白")
    on_screen_text: str = Field(default="", description="屏幕字幕/标题文字")
    transition: str = Field(default="cut", description="进入下一镜的转场：cut / fade / dissolve")


class VideoScript(BaseModel):
    """完整分镜脚本：有序 Shot 序列 + 全局元信息。"""

    title: str = Field(description="片名/工作标题")
    aspect_ratio: str = Field(default="9:16", description="画幅，沿用 Requirement")
    shots: list[Shot] = Field(description="按 index 有序的分镜列表")
    bgm_direction: str = Field(default="", description="背景音乐方向描述")

    @property
    def total_duration_sec(self) -> float:
        """所有分镜时长之和。门禁据此校验是否贴合目标时长。"""
        return sum(s.duration_sec for s in self.shots)
