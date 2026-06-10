"""AiServiceCapabilities — 真实媒体能力，httpx 调 chorify-ai-service /v1/*。

委托关系（端点见 chorify-ai-service 的 API endpoints 文档）：
- generate_image    → storyboard 图像生成端点
- generate_video    → POST /v1/video/batch + GET /v1/video/batch/{id}/stream 轮询/订阅
- synthesize_speech → TTS（volcano/minimax/elevenlabs）端点
- assemble_video    → POST /v1/long-video/*（ffmpeg 拼接/混音）
- upload            → POST /v1/upload

⚠️ 首版状态：本类是"留接口"。真实端点的请求体/响应字段映射、视频 batch 的
异步轮询逻辑尚未联调（USE_MOCKS=false 才会走到这里）。每个方法标注了
对接 TODO，接通时按 ai-service 的 schemas/*.py 契约补齐即可。

约定：httpx client 必须 trust_env=False —— 否则本地 7888 代理会 MITM
Seedance CDN 大文件下载（见 ai-service gotchas 文档）。
"""
from __future__ import annotations

import httpx

from videogeo.config import get_settings


class AiServiceCapabilities:
    """通过 HTTP 把媒体能力委托给 chorify-ai-service。"""

    def __init__(self) -> None:
        s = get_settings()
        self._base = s.ai_service_base_url.rstrip("/")
        self._headers = {"X-Internal-Key": s.internal_api_key} if s.internal_api_key else {}

    def _client(self, *, timeout: float = 120.0) -> httpx.AsyncClient:
        # trust_env=False：避开本地 git 代理对外部 CDN 下载的 MITM
        return httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=timeout, trust_env=False
        )

    async def generate_image(self, *, prompt: str, aspect_ratio: str) -> str:
        # TODO(联调): 映射到 ai-service storyboard 图像生成端点，取回 image url
        raise NotImplementedError("AiServiceCapabilities.generate_image 待联调；当前用 USE_MOCKS=true")

    async def generate_video(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        # TODO(联调): POST /v1/video/batch → 拿 job_id → 轮询 /v1/video/job/{id}
        #            或订阅 /v1/video/batch/{id}/stream，完成后取 OSS url
        raise NotImplementedError("AiServiceCapabilities.generate_video 待联调；当前用 USE_MOCKS=true")

    async def synthesize_speech(self, *, text: str, language: str) -> str:
        if not text:
            return ""
        # TODO(联调): POST /v1/tts/speech (engine=volcano 中文)，返回 audio_url
        raise NotImplementedError("AiServiceCapabilities.synthesize_speech 待联调；当前用 USE_MOCKS=true")

    async def generate_music(self, *, prompt: str, length_ms: int) -> str:
        if not prompt:
            return ""
        # TODO(联调): POST /v1/tts/music (ElevenLabs 文生乐)，返回 audio_url
        raise NotImplementedError("AiServiceCapabilities.generate_music 待联调；当前用 USE_MOCKS=true")

    async def assemble_video(
        self, *, clip_urls: list[str], audio_urls: list[str], bgm_url: str
    ) -> str:
        # TODO(联调): POST /v1/long-video/* —— ffmpeg 拼接 clip + 混音，返回成片 url
        raise NotImplementedError("AiServiceCapabilities.assemble_video 待联调；当前用 USE_MOCKS=true")

    async def upload(self, *, data: bytes, name: str) -> str:
        async with self._client() as client:
            resp = await client.post("/v1/upload", files={"file": (name, data)})
            resp.raise_for_status()
            return str(resp.json()["url"])
