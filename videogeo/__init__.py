"""videoGEO — 多 Agent 视频生成编排框架。

Leader orchestrator 驱动：导演 → 脚本编排 → 渲染 → 剪辑，
每一阶段输出都过一道审核门禁（阻断式 + 自动重试回环）。

媒体重活（图像/视频/剪辑/TTS/OSS）通过 HTTP 调 chorify-ai-service /v1/*；
本框架只负责"大脑"——Agent 编排与质量门禁。
"""

__version__ = "0.1.0"
