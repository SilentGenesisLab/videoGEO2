"""Rendered assets produced by the render stage."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ShotAssets(BaseModel):
    """One rendered segment asset."""

    shot_index: int = Field(ge=0, description="Rendered segment index")
    image_url: str = Field(default="", description="First-frame/reference image URL")
    clip_url: str = Field(default="", description="Rendered video clip URL")
    narration_audio_url: str = Field(default="", description="External TTS URL when audio_mode=external")
    duration_sec: float = Field(gt=0, description="Actual clip duration")
    native_audio: bool = Field(default=False, description="VO/BGM were requested inside Seedance prompt")
    narration_text: str = Field(default="", description="Native Seedance voiceover text")
    bgm_direction: str = Field(default="", description="Native Seedance music/sound direction")


class RenderedAssets(BaseModel):
    """All rendered segment assets for one video."""

    shots: list[ShotAssets] = Field(description="Rendered segment assets sorted by shot_index")
    bgm_url: str = Field(default="", description="External BGM URL when audio_mode=external")

    def is_complete(self) -> bool:
        return bool(self.shots) and all(s.clip_url for s in self.shots)
