"""compile —— 把脚本编排产物 VideoScript 编译成「可执行 + 可显示」的 Plan。

这是 Codex 大脑（脚本编排 subagent 产出 script.json）与薄执行器之间的桥：
确定性地把每个分镜展开成 image→video(+tts) 步骤，再加全局 bgm 与 concat 终点，
连好依赖。不含任何创意决策，纯机械展开，便于审计与断点续跑。
"""
from __future__ import annotations

from videogeo.schemas.plan import Plan, PlanStep
from videogeo.schemas.script import VideoScript

# Seedance 接受的视频时长档位（见 chorify-ai-service video.py：5/8→10/其余→15）
_VIDEO_DURATIONS = (5, 10, 15)


def quantize_duration(seconds: float) -> int:
    """把任意秒数吸附到最近的 Seedance 档位 5/10/15。"""
    return min(_VIDEO_DURATIONS, key=lambda d: abs(d - seconds))


def compile_plan(
    script: VideoScript,
    *,
    run_id: str,
    ref_image_urls: list[str] | None = None,
    target_duration_sec: int = 15,
    image_mode: str = "ref",
) -> Plan:
    """VideoScript → Plan。

    image_mode="ref"（v1 默认）：首帧用参考图，不做文生图——因 ai-service 暂无独立
    文生图端点。每个分镜按序拿一张 ref（轮转），没有 ref 时执行器回退占位。
    image_mode="gen"：调 generate_image 真正出图（待 ai-service 补端点后启用）。
    """
    refs = ref_image_urls or []
    steps: list[PlanStep] = []
    clip_ids: list[str] = []

    for shot in sorted(script.shots, key=lambda s: s.index):
        i = shot.index
        beat = shot.beat or "镜头"

        img_id = f"s{i}.img"
        ref_url = refs[i % len(refs)] if refs else ""
        steps.append(
            PlanStep(
                id=img_id,
                title=f"分镜{i} · 首帧图（{beat}）",
                type="image",
                shot_index=i,
                inputs={
                    "mode": image_mode,
                    "image_prompt": shot.image_prompt,
                    "ref_url": ref_url,
                    "aspect_ratio": script.aspect_ratio,
                },
            )
        )

        vid_id = f"s{i}.vid"
        dur = quantize_duration(shot.duration_sec)
        steps.append(
            PlanStep(
                id=vid_id,
                title=f"分镜{i} · 图生视频 {dur}s",
                type="video",
                shot_index=i,
                inputs={
                    "video_prompt": shot.video_prompt,
                    "duration_sec": dur,
                    "aspect_ratio": script.aspect_ratio,
                },
                depends_on=[img_id],
            )
        )
        clip_ids.append(vid_id)

        if shot.narration.strip():
            steps.append(
                PlanStep(
                    id=f"s{i}.tts",
                    title=f"分镜{i} · 旁白配音",
                    type="tts",
                    shot_index=i,
                    inputs={"text": shot.narration, "language": "zh"},
                )
            )

    if script.bgm_direction.strip():
        steps.append(
            PlanStep(
                id="bgm",
                title="全片 · 背景音乐",
                type="music",
                inputs={
                    "prompt": script.bgm_direction,
                    "length_ms": int(script.total_duration_sec * 1000),
                },
            )
        )

    # concat 终点：依赖所有视频片段；时间线顺序/转场由剪辑 subagent 填进 inputs.timeline
    steps.append(
        PlanStep(
            id="final",
            title="剪辑 · 按时间线拼接成片",
            type="concat",
            inputs={"timeline": [], "audio_mix": "", "has_subtitles": False},
            depends_on=clip_ids,
        )
    )

    return Plan(
        run_id=run_id,
        title=script.title,
        aspect_ratio=script.aspect_ratio,
        target_duration_sec=target_duration_sec,
        steps=steps,
    )
