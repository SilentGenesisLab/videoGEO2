"""Capability protocol for media-heavy work."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CapabilityClient(Protocol):
    async def generate_image(self, *, prompt: str, aspect_ratio: str) -> str:
        """Generate an image and return its URL."""
        ...

    async def generate_video(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        """Generate an I2V clip and return its URL.

        In the default `seedance_native` audio mode, prompt already contains
        voiceover and music instructions.
        """
        ...

    async def synthesize_speech(self, *, text: str, language: str) -> str:
        """External TTS fallback for `VIDEOGEO_AUDIO_MODE=external`."""
        ...

    async def generate_music(self, *, prompt: str, length_ms: int) -> str:
        """External BGM fallback for `VIDEOGEO_AUDIO_MODE=external`."""
        ...

    async def assemble_video(
        self, *, clip_urls: list[str], audio_urls: list[str], bgm_url: str
    ) -> str:
        """Join clips and optionally mix external audio."""
        ...

    async def upload(self, *, data: bytes, name: str) -> str:
        """Upload bytes to OSS and return a public URL."""
        ...
