"""Plan — 脚本编排产物 VideoScript 编译后的「可执行 + 可显示」计划。

这是 Codex 大脑与薄执行器之间的交接物：
- 对 CC：steps 每条有中文 title + status，主线程读完即可渲染成一张执行清单/进度表；
- 对执行器：type + inputs + depends_on 足以照着调 chorify-ai-service（mock 同形）。

执行器原地回填每个 step 的 status / output / error，所以 plan.json 既是计划也是状态，
中断后重新加载即可断点续跑（只跑 status != done 的步骤）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StepType = Literal["image", "video", "tts", "music", "concat"]
"""image=首帧(v1 走参考图) · video=图生视频(i2v) · tts=旁白 · music=BGM · concat=拼接成片。"""

StepStatus = Literal["pending", "running", "done", "failed", "skipped"]


class PlanStep(BaseModel):
    """一个可执行步骤 —— 同时是清单上的一行。"""

    id: str = Field(description="步骤唯一 id，如 s0.img / s0.vid / s0.tts / bgm / final")
    title: str = Field(description="中文可读标题，CC 直接显示给用户")
    type: StepType = Field(description="步骤类型，决定执行器调哪个 capability")
    shot_index: int | None = Field(default=None, description="所属分镜号；bgm/concat 等全局步骤为 None")
    inputs: dict[str, Any] = Field(default_factory=dict, description="该步骤入参（prompt/时长/ref_urls 等）")
    depends_on: list[str] = Field(default_factory=list, description="前置步骤 id，全部 done 才可执行")

    # ── 执行期回填 ──
    status: StepStatus = Field(default="pending", description="执行状态")
    output: dict[str, Any] | None = Field(default=None, description="产物，如 {image_url}/{clip_url}/{audio_url}/{video_url}")
    error: str = Field(default="", description="失败原因；status=failed 时填")
    attempts: int = Field(default=0, description="已尝试次数，能力调用重试用")


class Plan(BaseModel):
    """完整执行计划：有序步骤 + 全局元信息。"""

    run_id: str = Field(description="本次运行 id，对应 runs/<run_id>/ 目录")
    title: str = Field(description="片名/工作标题")
    aspect_ratio: str = Field(default="9:16", description="画幅")
    target_duration_sec: int = Field(default=15, description="目标成片时长，门禁据此校验")
    steps: list[PlanStep] = Field(description="按依赖排序的步骤列表")

    # ── 便捷查询（执行器/门禁用）──

    def step(self, step_id: str) -> PlanStep | None:
        """按 id 取步骤。"""
        return next((s for s in self.steps if s.id == step_id), None)

    def ready_steps(self, *, include: set[str] | None = None) -> list[PlanStep]:
        """返回当前可执行的步骤：自身 pending 且所有 depends_on 已 done。

        include 限定只看某些 type（如渲染阶段排除 concat）。
        """
        done = {s.id for s in self.steps if s.status == "done"}
        out = []
        for s in self.steps:
            if s.status != "pending":
                continue
            if include is not None and s.type not in include:
                continue
            if all(dep in done for dep in s.depends_on):
                out.append(s)
        return out

    def is_done(self, *, include: set[str] | None = None) -> bool:
        """目标范围内步骤是否全部 done。"""
        return all(s.status == "done" for s in self.steps if include is None or s.type in include)

    def has_failure(self) -> bool:
        return any(s.status == "failed" for s in self.steps)

    def render_outline(self) -> str:
        """给 CC/用户显示的清单文本。✅完成 ⏳进行 ⬜待执行 ❌失败 ⏭️跳过。"""
        glyph = {"done": "✅", "running": "⏳", "pending": "⬜", "failed": "❌", "skipped": "⏭️"}
        lines = [f"📋 {self.title}  ({self.aspect_ratio}, 目标 {self.target_duration_sec}s)  run={self.run_id}"]
        for s in self.steps:
            dep = f"  ←{','.join(s.depends_on)}" if s.depends_on else ""
            lines.append(f"  {glyph.get(s.status, '?')} [{s.id}] {s.title}{dep}")
        return "\n".join(lines)
