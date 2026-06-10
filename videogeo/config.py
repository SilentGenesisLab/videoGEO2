"""Global settings loaded from environment variables and .env."""
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

    use_mocks: bool = True
    max_retries_per_stage: int = 2

    render_concurrency: int = 4
    video_concurrency: int = 2

    ai_service_base_url: str = "http://localhost:8544"
    internal_api_key: str = ""
    ai_service_repo: str = "../chorify-ai-service"
    ai_service_python: str = ""
    ai_service_http_timeout_sec: float = 120.0
    ai_service_video_poll_interval_sec: float = 8.0
    ai_service_video_timeout_sec: float = 1800.0

    volcano_api_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volcano_api_key: str = ""
    volcano_model: str = ""
    volcano_thinking_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
