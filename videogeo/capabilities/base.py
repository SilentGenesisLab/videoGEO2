"""CapabilityClient 协议 — 媒体"重活"统一接口。

videoGEO 自己不生成像素/音频、不跑 ffmpeg；这些通过本接口委托给 chorify-ai-service。
薄执行器（executor.py）遍历 plan.json 的步骤，按 step.type 调这里的方法。两个实现：
- AiServiceCapabilities（真实，httpx 调 /v1/*；真实端点是异步 job，实现内部负责轮询）
- MockCapabilities（返回确定性占位 url，全程 mock 端到端可跑）

执行器只依赖这个 Protocol，不关心底层是 mock 还是 HTTP，也不关心 job 轮询细节。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CapabilityClient(Protocol):
    """图像 / 视频 / 语音 / 音乐 / 剪辑 / 上传 六类媒体能力。"""

    async def generate_image(self, *, prompt: str, aspect_ratio: str) -> str:
        """文生图，返回图片 url。v1 多走参考图，不一定调到。"""
        ...

    async def generate_video(
        self, *, prompt: str, image_url: str, duration_sec: float, aspect_ratio: str
    ) -> str:
        """图生视频片段（i2v），返回视频 url。真实端点异步，实现内部提交+轮询直到完成。"""
        ...

    async def synthesize_speech(self, *, text: str, language: str) -> str:
        """旁白 TTS，返回音频 url。text 为空应返回空串。"""
        ...

    async def generate_music(self, *, prompt: str, length_ms: int) -> str:
        """文生 BGM，返回音频 url。prompt 为空应返回空串。"""
        ...

    async def assemble_video(
        self, *, clip_urls: list[str], audio_urls: list[str], bgm_url: str
    ) -> str:
        """按顺序拼接片段 + 混音，返回成片 url。"""
        ...

    async def upload(self, *, data: bytes, name: str) -> str:
        """上传任意字节到 OSS，返回可访问 url。"""
        ...
