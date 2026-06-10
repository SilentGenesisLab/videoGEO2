"""全局配置 — pydantic-settings，从环境变量 / .env 读取。

前缀统一 VIDEOGEO_。USE_MOCKS=true（默认）时 LLM 与媒体能力都走 mock，
不需要任何密钥或网络即可端到端跑通骨架。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIDEOGEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 运行模式 ──
    use_mocks: bool = True
    """true → MockLLM + MockCapabilities；false → 真实豆包 + HTTP 调 ai-service。"""

    max_retries_per_stage: int = 2
    """门禁不通过时每阶段最大自动重试次数。0 = 只跑一次，不重试。"""

    # ── chorify-ai-service（媒体能力来源）──
    ai_service_base_url: str = "http://localhost:8544"
    internal_api_key: str = ""
    """对应 ai-service 的 X-Internal-Key；空字符串时 ai-service dev 模式跳过鉴权。"""

    # ── 豆包 Volcano Ark（Agent/门禁推理）──
    volcano_api_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volcano_api_key: str = ""
    volcano_model: str = ""
    volcano_thinking_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    """单例配置。lru_cache 保证整个进程只解析一次 .env。"""
    return Settings()
