"""Deterministic mock media capabilities."""
from __future__ import annotations

import hashlib

_BASE = "https://mock.videogeo.local"


def _tag(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


class MockCapabilities:
    async def generate_image(self, *, prompt: str, aspect_ratio: str) -> str:
        return f"{_BASE}/img/{_tag(prompt, aspect_ratio)}.png"

    async def generate_video(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        return f"{_BASE}/clip/{_tag(prompt, image_url, str(duration_sec), aspect_ratio)}.mp4"

    async def synthesize_speech(self, *, text: str, language: str) -> str:
        if not text:
            return ""
        return f"{_BASE}/tts/{_tag(text, language)}.mp3"

    async def generate_music(self, *, prompt: str, length_ms: int) -> str:
        if not prompt:
            return ""
        return f"{_BASE}/bgm/{_tag(prompt, str(length_ms))}.mp3"

    async def assemble_video(
        self, *, clip_urls: list[str], audio_urls: list[str], bgm_url: str
    ) -> str:
        return f"{_BASE}/final/{_tag(*clip_urls, *audio_urls, bgm_url)}.mp4"

    async def upload(self, *, data: bytes, name: str) -> str:
        return f"{_BASE}/oss/{_tag(name, str(len(data)))}/{name}"
