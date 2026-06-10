"""AiServiceCapabilities - real media adapter for chorify-ai-service.

The executor owns plan traversal; this adapter only maps a single PlanStep
capability call to the corresponding chorify-ai-service HTTP API. This keeps
videoGEO plan-driven: production scripts in chorify-ai-service may remain useful
for experiments, but render/assemble must enter through this file.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path
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
        self._repo = Path(s.ai_service_repo).expanduser().resolve()
        self._python = Path(s.ai_service_python).expanduser() if s.ai_service_python else self._default_ai_service_python()

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
        if self._repo.exists():
            return await self._generate_video_local(
                prompt=prompt,
                image_url=image_url,
                duration_sec=duration_sec,
                aspect_ratio=aspect_ratio,
            )

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

    async def _generate_video_local(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        if not self._python.exists():
            raise FileNotFoundError(f"ai-service python not found: {self._python}")
        payload = {
            "prompt": prompt,
            "image_url": image_url,
            "duration_sec": self._seedance_duration(duration_sec),
            "aspect_ratio": aspect_ratio,
        }
        code = r'''
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(".env")
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from app.services.seedance_service import run_full

async def main():
    req = json.loads(sys.stdin.read())
    result = await run_full(
        prompt=req["prompt"],
        image_urls=[req["image_url"]],
        duration=int(req["duration_sec"]),
        ratio=req["aspect_ratio"],
    )
    print("VIDEOGEO_RESULT_JSON=" + json.dumps({
        "oss_url": result.oss_url,
        "submit_id": result.submit_id,
        "duration": req["duration_sec"],
    }, ensure_ascii=False))

asyncio.run(main())
'''
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["HTTP_PROXY"] = ""
        env["HTTPS_PROXY"] = ""
        env["NO_PROXY"] = "localhost,127.0.0.1"
        proc = await asyncio.create_subprocess_exec(
            str(self._python),
            "-c",
            code,
            cwd=str(self._repo),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                timeout=self._video_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"local Seedance job timed out after {self._video_timeout:g}s")
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"local Seedance failed rc={proc.returncode}: {err[-2000:] or out[-2000:]}")
        for line in reversed(out.splitlines()):
            if line.startswith("VIDEOGEO_RESULT_JSON="):
                data = json.loads(line.split("=", 1)[1])
                url = data.get("oss_url")
                if not url:
                    raise RuntimeError(f"local Seedance returned no oss_url: {data}")
                return str(url)
        raise RuntimeError(f"local Seedance returned no result marker. stdout={out[-2000:]} stderr={err[-2000:]}")

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

    @staticmethod
    def _seedance_duration(duration_sec: float) -> int:
        if duration_sec <= 6.5:
            return 5
        if duration_sec <= 12.5:
            return 10
        return 15

    def _default_ai_service_python(self) -> Path:
        if sys.platform == "win32":
            return self._repo / ".venv" / "Scripts" / "python.exe"
        return self._repo / ".venv" / "bin" / "python"
