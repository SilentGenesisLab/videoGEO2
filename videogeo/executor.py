"""executor —— 薄执行器：遍历 Plan 的步骤，调 capabilities 生成素材，原地回填状态。

这是整个框架里唯一"干活"的确定性组件（非 LLM、无创意）。它：
- 按依赖就绪顺序跑步骤（ready_steps），每步 running→done/failed，输出回填到 step.output；
- 因 plan.json 同时是状态，中断后重新加载只跑未完成步骤即可断点续跑；
- 分两相：render（image/video/tts/music）→ 交剪辑 subagent 排时间线 → assemble（concat）。

真实 ai-service 的视频是异步 job，但轮询细节封在 AiServiceCapabilities 内部，
执行器只看到"调用返回最终 url"，因此对 mock / 真实一视同仁。
"""
from __future__ import annotations

from videogeo.capabilities.base import CapabilityClient
from videogeo.schemas.assets import RenderedAssets, ShotAssets
from videogeo.schemas.plan import Plan, PlanStep

RENDER_TYPES = {"image", "video", "tts", "music"}
ASSEMBLE_TYPES = {"concat"}


async def _run_step(step: PlanStep, plan: Plan, cap: CapabilityClient) -> None:
    """跑单个步骤；异常不抛出，记到 step.error 让上层决定阻断。"""
    step.status = "running"
    step.attempts += 1
    try:
        if step.type == "image":
            mode = step.inputs.get("mode", "ref")
            ref_url = step.inputs.get("ref_url", "")
            if mode == "ref" and ref_url:
                url = ref_url  # v1：直接用参考图，不消耗生成能力
            else:
                url = await cap.generate_image(
                    prompt=step.inputs.get("image_prompt", ""),
                    aspect_ratio=step.inputs.get("aspect_ratio", "9:16"),
                )
            step.output = {"image_url": url}

        elif step.type == "video":
            image_url = _dep_output(step, plan, "image_url")
            url = await cap.generate_video(
                prompt=step.inputs.get("video_prompt", ""),
                image_url=image_url,
                duration_sec=float(step.inputs.get("duration_sec", 5)),
                aspect_ratio=step.inputs.get("aspect_ratio", "9:16"),
            )
            step.output = {"clip_url": url, "duration_sec": step.inputs.get("duration_sec", 5)}

        elif step.type == "tts":
            url = await cap.synthesize_speech(
                text=step.inputs.get("text", ""),
                language=step.inputs.get("language", "zh"),
            )
            step.output = {"audio_url": url}

        elif step.type == "music":
            url = await cap.generate_music(
                prompt=step.inputs.get("prompt", ""),
                length_ms=int(step.inputs.get("length_ms", 30000)),
            )
            step.output = {"audio_url": url}

        elif step.type == "concat":
            clip_urls = _ordered_clip_urls(step, plan)
            audio_urls = [
                s.output["audio_url"]
                for s in plan.steps
                if s.type == "tts" and s.output and s.output.get("audio_url")
            ]
            bgm = next(
                (s.output["audio_url"] for s in plan.steps if s.type == "music" and s.output),
                "",
            )
            url = await cap.assemble_video(clip_urls=clip_urls, audio_urls=audio_urls, bgm_url=bgm)
            total = sum(
                float(s.output.get("duration_sec", 0))
                for s in plan.steps
                if s.type == "video" and s.output
            )
            step.output = {"video_url": url, "duration_sec": total}

        else:  # pragma: no cover - schema 已约束 type
            raise ValueError(f"未知步骤类型: {step.type}")

        step.status = "done"
        step.error = ""
    except Exception as e:  # noqa: BLE001 - 故意吞掉，转成 failed 状态供门禁/重跑
        step.status = "failed"
        step.error = f"{type(e).__name__}: {e}"


def _dep_output(step: PlanStep, plan: Plan, key: str) -> str:
    """从 step 的前置依赖里取某个输出字段（如 video 取其 image 的 image_url）。"""
    for dep_id in step.depends_on:
        dep = plan.step(dep_id)
        if dep and dep.output and key in dep.output:
            return str(dep.output[key])
    return ""


def _ordered_clip_urls(concat_step: PlanStep, plan: Plan) -> list[str]:
    """concat 的片段顺序：优先用剪辑 subagent 填的 timeline，否则按 depends_on 原序。"""
    timeline = concat_step.inputs.get("timeline") or []
    if timeline:
        order = [int(t["shot_index"]) for t in timeline]
        by_shot = {
            s.shot_index: s.output["clip_url"]
            for s in plan.steps
            if s.type == "video" and s.output and s.output.get("clip_url")
        }
        return [by_shot[i] for i in order if i in by_shot]
    return [
        plan.step(dep).output["clip_url"]  # type: ignore[union-attr,index]
        for dep in concat_step.depends_on
        if plan.step(dep) and plan.step(dep).output  # type: ignore[union-attr]
    ]


async def execute(plan: Plan, cap: CapabilityClient, *, include: set[str]) -> Plan:
    """跑 include 范围内所有可执行步骤直到完成或阻塞。原地修改 plan。"""
    while not plan.is_done(include=include):
        ready = plan.ready_steps(include=include)
        if not ready:
            break  # 还有 pending 但没就绪（前置失败）→ 阻断，交上层处理
        for step in ready:
            await _run_step(step, plan, cap)
    return plan


async def execute_render(plan: Plan, cap: CapabilityClient) -> Plan:
    """渲染相：image/video/tts/music。完成后交剪辑 subagent 排时间线。"""
    return await execute(plan, cap, include=RENDER_TYPES)


async def execute_assemble(plan: Plan, cap: CapabilityClient) -> Plan:
    """合成相：concat。须在剪辑 subagent 把 timeline 写进 final 步骤 inputs 后调用。"""
    return await execute(plan, cap, include=ASSEMBLE_TYPES)


def plan_to_assets(plan: Plan) -> RenderedAssets:
    """从已执行的渲染步骤汇总成 RenderedAssets，喂给 assets 阶段门禁/剪辑 subagent。"""
    shots: dict[int, ShotAssets] = {}
    for s in plan.steps:
        if s.shot_index is None or not s.output:
            continue
        cur = shots.get(s.shot_index)
        if cur is None:
            cur = ShotAssets(shot_index=s.shot_index, duration_sec=1.0)
            shots[s.shot_index] = cur
        if s.type == "image":
            cur.image_url = s.output.get("image_url", "")
        elif s.type == "video":
            cur.clip_url = s.output.get("clip_url", "")
            cur.duration_sec = float(s.output.get("duration_sec", cur.duration_sec))
        elif s.type == "tts":
            cur.narration_audio_url = s.output.get("audio_url", "")
    bgm = next((s.output["audio_url"] for s in plan.steps if s.type == "music" and s.output), "")
    return RenderedAssets(shots=[shots[k] for k in sorted(shots)], bgm_url=bgm)
