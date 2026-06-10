"""Plan executor.

The executor is deterministic: it walks ready plan steps, calls capabilities,
and writes status back into plan.json. Render steps are concurrent by default.
In the default seedance_native audio mode, VO/BGM are already embedded in video
prompts, so no separate TTS/BGM steps are needed.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from videogeo.capabilities.base import CapabilityClient
from videogeo.config import get_settings
from videogeo.schemas.assets import RenderedAssets, ShotAssets
from videogeo.schemas.plan import Plan, PlanStep

RENDER_TYPES = {"image", "video", "tts", "music"}
ASSEMBLE_TYPES = {"concat"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _run_step(step: PlanStep, plan: Plan, cap: CapabilityClient) -> None:
    """Run one step and record failure on the step instead of raising."""
    step.status = "running"
    step.error = ""
    step.attempts += 1
    step.started_at = _now()
    start = time.perf_counter()
    try:
        if step.type == "image":
            mode = step.inputs.get("mode", "ref")
            ref_url = step.inputs.get("ref_url", "")
            if mode == "ref" and ref_url:
                url = ref_url
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
            step.output = {
                "clip_url": url,
                "duration_sec": float(step.inputs.get("duration_sec", 5)),
                "native_audio": bool(step.inputs.get("native_audio", False)),
                "narration": step.inputs.get("narration", ""),
                "bgm_direction": step.inputs.get("bgm_direction", ""),
            }

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

        else:  # pragma: no cover
            raise ValueError(f"Unknown step type: {step.type}")

        step.status = "done"
    except Exception as exc:  # noqa: BLE001 - persisted into plan for resumable recovery
        step.status = "failed"
        step.error = f"{type(exc).__name__}: {exc}"
    finally:
        step.finished_at = _now()
        step.elapsed_sec = round(time.perf_counter() - start, 3)


async def _run_step_limited(
    step: PlanStep,
    plan: Plan,
    cap: CapabilityClient,
    total_sem: asyncio.Semaphore,
    video_sem: asyncio.Semaphore,
) -> None:
    async with total_sem:
        if step.type == "video":
            async with video_sem:
                await _run_step(step, plan, cap)
        else:
            await _run_step(step, plan, cap)


def _dep_output(step: PlanStep, plan: Plan, key: str) -> str:
    for dep_id in step.depends_on:
        dep = plan.step(dep_id)
        if dep and dep.output and key in dep.output:
            return str(dep.output[key])
    return ""


def _ordered_clip_urls(concat_step: PlanStep, plan: Plan) -> list[str]:
    timeline = concat_step.inputs.get("timeline") or []
    if timeline:
        order = [int(t["shot_index"]) for t in timeline]
        by_segment = {
            s.shot_index: s.output["clip_url"]
            for s in plan.steps
            if s.type == "video" and s.output and s.output.get("clip_url")
        }
        return [by_segment[i] for i in order if i in by_segment]
    return [
        plan.step(dep).output["clip_url"]  # type: ignore[union-attr,index]
        for dep in concat_step.depends_on
        if plan.step(dep) and plan.step(dep).output  # type: ignore[union-attr]
    ]


async def execute(plan: Plan, cap: CapabilityClient, *, include: set[str]) -> Plan:
    """Run all pending steps in include until done or blocked."""
    settings = get_settings()
    total_sem = asyncio.Semaphore(max(1, settings.render_concurrency))
    video_sem = asyncio.Semaphore(max(1, settings.video_concurrency))

    while not plan.is_done(include=include):
        ready = plan.ready_steps(include=include)
        if not ready:
            break
        await asyncio.gather(*(_run_step_limited(s, plan, cap, total_sem, video_sem) for s in ready))
        if plan.has_failure():
            break
    return plan


async def execute_render(plan: Plan, cap: CapabilityClient) -> Plan:
    return await execute(plan, cap, include=RENDER_TYPES)


async def execute_assemble(plan: Plan, cap: CapabilityClient) -> Plan:
    return await execute(plan, cap, include=ASSEMBLE_TYPES)


def plan_to_assets(plan: Plan) -> RenderedAssets:
    """Collect render outputs into assets.json for gates and editor."""
    shots: dict[int, ShotAssets] = {}
    for step in plan.steps:
        if step.shot_index is None or not step.output:
            continue
        cur = shots.get(step.shot_index)
        if cur is None:
            cur = ShotAssets(shot_index=step.shot_index, duration_sec=1.0)
            shots[step.shot_index] = cur
        if step.type == "image":
            cur.image_url = step.output.get("image_url", "")
        elif step.type == "video":
            cur.clip_url = step.output.get("clip_url", "")
            cur.duration_sec = float(step.output.get("duration_sec", cur.duration_sec))
            cur.native_audio = bool(step.output.get("native_audio", False))
            cur.narration_text = str(step.output.get("narration", ""))
            cur.bgm_direction = str(step.output.get("bgm_direction", ""))
        elif step.type == "tts":
            cur.narration_audio_url = step.output.get("audio_url", "")
    bgm = next((s.output["audio_url"] for s in plan.steps if s.type == "music" and s.output), "")
    return RenderedAssets(shots=[shots[k] for k in sorted(shots)], bgm_url=bgm)
