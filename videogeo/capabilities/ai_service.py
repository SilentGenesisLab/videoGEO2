"""AiServiceCapabilities - real media adapter for chorify-ai-service.

The executor owns plan traversal; this adapter only maps a single PlanStep
capability call to the corresponding chorify-ai-service HTTP API. This keeps
videoGEO plan-driven: production scripts in chorify-ai-service may remain useful
for experiments, but render/assemble must enter through this file.
"""
from __future__ import annotations

import asyncio
import mimetypes
import time
import uuid
from typing import Any

import httpx

from videogeo.config import get_settings


class AiServiceCapabilities:
    """Delegate media work to chorify-ai-service over HTTP."""

    def __init__(self) -> None:
        s = get_settings()
        self._base = s.ai_service_base_url.rstrip("/")
        self._headers = {"X-Internal-Key": s.internal_api_key} if s.internal_api_key else {}
        self._timeout = s.ai_service_http_timeout_sec
        self._video_poll_interval = s.ai_service_video_poll_interval_sec
        self._video_timeout = s.ai_service_video_timeout_sec

    def _client(self, *, timeout: float | None = None) -> httpx.AsyncClient:
        # trust_env=False avoids local proxy interference with OSS/CDN downloads.
        return httpx.AsyncClient(
            base_url=self._base,
            headers=self._headers,
            timeout=timeout or self._timeout,
            trust_env=False,
        )

    async def _post_json(self, path: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        async with self._client(timeout=timeout) as client:
            resp = await client.post(path, json=payload)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"{path} returned non-object JSON")
        return data

    async def generate_image(self, *, prompt: str, aspect_ratio: str) -> str:
        """Image generation is intentionally explicit.

        The current stable videoGEO path uses reference images (`image_mode=ref`).
        When `image_mode=gen` is enabled, wire this to the ai-service storyboard
        endpoint and keep the plan contract unchanged.
        """
        raise RuntimeError(
            "generate_image is not wired yet; compile with --image-mode ref and provide --ref URLs"
        )

    async def generate_video(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        if not image_url:
            raise ValueError("generate_video requires an image_url from the image step")

        duration_hint = self._direction_duration_for_seedance(duration_sec)
        direction = {
            "direction_id": "A",
            "title": "videoGEO",
            "tags": ["plan", "seedance"],
            "summary": self._clip(prompt, 80) or "Plan-driven product video shot",
            "vibe": prompt or "High quality cinematic product shot",
            "rhythm": f"{duration_sec:g}s shot",
            "voiceover_tone": "No voiceover baked into visual generation",
            "sound": "",
            "duration": duration_hint,
            "ratio": aspect_ratio,
            "recommended": True,
        }
        payload = {
            "conversation_id": f"videogeo-{uuid.uuid4().hex[:12]}",
            "message_id": f"msg-{uuid.uuid4().hex[:12]}",
            "brief": {
                "audience": "videoGEO",
                "hook": self._clip(prompt, 30) or "Product hero shot",
                "rhythm": f"{duration_sec:g}s",
                "avoid": "no subtitle, no watermark",
            },
            "selections": [{"direction": direction, "count": 1}],
            "image_urls": [image_url],
        }
        data = await self._post_json("/v1/video/batch", payload)
        job_ids = data.get("job_ids") or []
        if not job_ids:
            raise RuntimeError(f"/v1/video/batch returned no job_ids: {data}")
        return await self._poll_video_job(str(job_ids[0]))

    async def _poll_video_job(self, job_id: str) -> str:
        deadline = time.monotonic() + self._video_timeout
        last_status = ""
        last_percent = 0
        async with self._client(timeout=self._timeout) as client:
            while time.monotonic() < deadline:
                resp = await client.get(f"/v1/video/job/{job_id}")
                resp.raise_for_status()
                job = resp.json()
                status = str(job.get("status", ""))
                last_status = status
                last_percent = int(job.get("percent") or 0)
                if status == "done":
                    url = job.get("oss_url")
                    if not url:
                        raise RuntimeError(f"video job {job_id} done without oss_url")
                    return str(url)
                if status == "failed":
                    reason = job.get("failure_reason") or "unknown failure"
                    raise RuntimeError(f"video job {job_id} failed: {reason}")
                await asyncio.sleep(self._video_poll_interval)
        raise TimeoutError(
            f"video job {job_id} timed out after {self._video_timeout:g}s "
            f"(last_status={last_status}, percent={last_percent})"
        )

    async def synthesize_speech(self, *, text: str, language: str) -> str:
        if not text:
            return ""
        engine = "volcano" if language.lower().startswith("zh") else "elevenlabs"
        payload: dict[str, Any] = {"engine": engine, "text": text, "upload": True}
        data = await self._post_json("/v1/tts/speech", payload, timeout=max(self._timeout, 180.0))
        return str(data.get("audio_url") or "")

    async def generate_music(self, *, prompt: str, length_ms: int) -> str:
        if not prompt:
            return ""
        payload = {"prompt": prompt, "music_length_ms": length_ms, "upload": True}
        data = await self._post_json("/v1/tts/music", payload, timeout=max(self._timeout, 300.0))
        return str(data.get("audio_url") or "")

    async def assemble_video(
        self, *, clip_urls: list[str], audio_urls: list[str], bgm_url: str
    ) -> str:
        if not clip_urls:
            raise ValueError("assemble_video requires at least one clip")
        if len(clip_urls) == 1 and not audio_urls and not bgm_url:
            return clip_urls[0]

        # Current ai-service concat endpoint joins video segments. Audio mixing is
        # tracked in final.json and can be upgraded here when a mix endpoint lands.
        data = await self._post_json(
            "/v1/long-video/concat",
            {"source_urls": clip_urls},
            timeout=max(self._timeout, 300.0),
        )
        return str(data["oss_url"])

    async def upload(self, *, data: bytes, name: str) -> str:
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        async with self._client(timeout=max(self._timeout, 300.0)) as client:
            resp = await client.post(
                "/v1/upload",
                files={"file": (name, data, content_type)},
            )
            resp.raise_for_status()
            body = resp.json()
        return str(body["url"])

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        text = " ".join((text or "").split())
        return text[:limit]

    @staticmethod
    def _direction_duration_for_seedance(duration_sec: float) -> int:
        """Work around ai-service's short-video mapping.

        /v1/video/batch maps direction.duration 5->5, 8->10, all other values->15.
        videoGEO plans already quantize to 5/10/15, so 10s must be submitted as 8.
        """
        if duration_sec <= 6.5:
            return 5
        if duration_sec <= 12.5:
            return 8
        return 15
