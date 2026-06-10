"""Requirement — Leader 把用户原始需求归一化后的结构化需求。

这是整条流水线的输入。Leader 负责从一句自然语言（或带素材链接）抽出
可被下游 Agent 消费的字段：题材、平台、时长、卖点、语气等。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """归一化后的视频生成需求。"""

    raw: str = Field(description="用户原始需求文本，原样保留供回溯")
    goal: str = Field(description="一句话目标，如『为国产咖啡做种草短视频』")
    platform: str = Field(default="通用", description="投放平台：抖音 / 视频号 / 小红书 / YouTube / 通用")
    duration_sec: int = Field(default=15, ge=3, le=600, description="目标成片时长（秒）")
    aspect_ratio: str = Field(default="9:16", description="画幅：9:16 / 16:9 / 1:1")
    language: str = Field(default="zh", description="旁白/字幕语言")
    audience: str = Field(default="", description="目标受众画像")
    selling_points: list[str] = Field(default_factory=list, description="核心卖点/信息点")
    tone: str = Field(default="", description="期望语气/调性，如『轻松治愈』")
    reference_image_urls: list[str] = Field(default_factory=list, description="参考素材图链接")
    constraints: list[str] = Field(default_factory=list, description="硬性约束，如『不得出现真人脸』")
