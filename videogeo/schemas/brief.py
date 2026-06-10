"""CreativeBrief — 导演 Agent 的产物。

承载创意层面的决策：核心创意、叙事逻辑与节奏 beats、氛围基调、画质规格。
下游脚本编排 Agent 据此拆分镜。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Beat(BaseModel):
    """叙事节奏的一个节拍。整条 beats 构成故事骨架。"""

    name: str = Field(description="节拍名，如『钩子』『冲突』『转折』『落点』")
    purpose: str = Field(description="这一拍要达成的叙事目的")
    est_duration_sec: float = Field(ge=0, description="预估时长（秒）")


class VisualSpec(BaseModel):
    """画质与视觉规格。"""

    style: str = Field(description="视觉风格，如『电影感写实』『2D 扁平插画』")
    color_palette: str = Field(default="", description="主色调描述")
    camera: str = Field(default="", description="镜头语言倾向，如『手持 + 浅景深』")
    quality: str = Field(default="high", description="画质档位：draft / standard / high")


class CreativeBrief(BaseModel):
    """导演输出：创意 + 叙事节奏 + 氛围 + 画质。"""

    concept: str = Field(description="一句话核心创意（big idea）")
    narrative: str = Field(description="完整叙事/故事线描述")
    mood: str = Field(description="整体氛围基调，如『温暖、慢节奏、夜晚都市』")
    beats: list[Beat] = Field(description="叙事节奏分解，按时间顺序")
    visual: VisualSpec = Field(description="画质与视觉规格")
    audio_direction: str = Field(default="", description="配乐/音效/旁白基调方向")
