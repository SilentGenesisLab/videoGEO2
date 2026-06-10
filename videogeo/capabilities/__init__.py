"""媒体能力层 —— 图像/视频/语音/剪辑/上传，委托给 chorify-ai-service。"""
from videogeo.capabilities.base import CapabilityClient
from videogeo.capabilities.mock import MockCapabilities

__all__ = ["CapabilityClient", "MockCapabilities"]
