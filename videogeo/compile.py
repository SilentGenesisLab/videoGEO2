"""Compile VideoScript into an executable Plan.

New videoGEO2 scripts are global-first: storyboard shots describe rhythm and
composition, while render segments describe the actual I2V jobs. Compile uses
segments when present and falls back to legacy shots only for compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass

from videogeo.schemas.plan import Plan, PlanStep
from videogeo.schemas.script import RenderSegment, Shot, VideoScript

_VIDEO_DURATIONS = (5, 10, 15)


def quantize_duration(seconds: float) -> int:
    """Map legacy shot durations to Seedance-friendly buckets."""
    return min(_VIDEO_DURATIONS, key=lambda d: abs(d - seconds))


@dataclass(frozen=True)
class _Unit:
    index: int
    name: str
    beat: str
    duration_sec: float
    image_prompt: str
    video_prompt: str
    narration: str
    on_screen_text: str
    transition: str
    storyboard_prompt: str = ""
    shot_indices: tuple[int, ...] = ()
    feed_storyboard_seed: bool = False
    is_segment: bool = False


def _units_from_script(script: VideoScript) -> list[_Unit]:
    shot_by_index = {s.index: s for s in script.shots}
    if script.segments:
        return [_unit_from_segment(seg, shot_by_index) for seg in sorted(script.segments, key=lambda s: s.index)]
    return [_unit_from_shot(shot) for shot in sorted(script.shots, key=lambda s: s.index)]


def _unit_from_segment(seg: RenderSegment, shot_by_index: dict[int, Shot]) -> _Unit:
    refs = [shot_by_index[i] for i in seg.shot_indices if i in shot_by_index]
    image_prompt = refs[0].image_prompt if refs else seg.storyboard_prompt
    storyboard_prompt = seg.storyboard_prompt or " | ".join(s.video_prompt for s in refs)
    return _Unit(
        index=seg.index,
        name=seg.name or f"segment {seg.index}",
        beat=seg.beat,
        duration_sec=seg.duration_sec,
        image_prompt=image_prompt,
        video_prompt=seg.video_prompt,
        narration=seg.narration,
        on_screen_text=seg.on_screen_text,
        transition=seg.transition,
        storyboard_prompt=storyboard_prompt,
        shot_indices=tuple(seg.shot_indices),
        feed_storyboard_seed=seg.feed_storyboard_seed,
        is_segment=True,
    )


def _unit_from_shot(shot: Shot) -> _Unit:
    return _Unit(
        index=shot.index,
        name=f"shot {shot.index}",
        beat=shot.beat,
        duration_sec=quantize_duration(shot.duration_sec),
        image_prompt=shot.image_prompt,
        video_prompt=shot.video_prompt,
        narration=shot.narration,
        on_screen_text=shot.on_screen_text,
        transition=shot.transition,
        shot_indices=(shot.index,),
        is_segment=False,
    )


def compile_plan(
    script: VideoScript,
    *,
    run_id: str,
    ref_image_urls: list[str] | None = None,
    target_duration_sec: int = 15,
    image_mode: str = "ref",
) -> Plan:
    """Compile the creative script into deterministic media tasks."""
    refs = ref_image_urls or []
    steps: list[PlanStep] = []
    clip_ids: list[str] = []

    for unit in _units_from_script(script):
        prefix = "seg" if unit.is_segment else "s"
        i = unit.index
        beat = unit.beat or unit.name

        img_id = f"{prefix}{i}.img"
        ref_url = refs[i % len(refs)] if refs else ""
        steps.append(
            PlanStep(
                id=img_id,
                title=f"{unit.name} first frame ({beat})",
                type="image",
                shot_index=i,
                inputs={
                    "mode": image_mode,
                    "image_prompt": unit.image_prompt,
                    "ref_url": ref_url,
                    "aspect_ratio": script.aspect_ratio,
                    "storyboard_prompt": unit.storyboard_prompt,
                    "covered_shots": list(unit.shot_indices),
                },
            )
        )

        vid_id = f"{prefix}{i}.vid"
        steps.append(
            PlanStep(
                id=vid_id,
                title=f"{unit.name} I2V {unit.duration_sec:g}s",
                type="video",
                shot_index=i,
                inputs={
                    "video_prompt": unit.video_prompt,
                    "duration_sec": unit.duration_sec,
                    "aspect_ratio": script.aspect_ratio,
                    "storyboard_prompt": unit.storyboard_prompt,
                    "covered_shots": list(unit.shot_indices),
                    "feed_storyboard_seed": unit.feed_storyboard_seed,
                    "transition": unit.transition,
                    "on_screen_text": unit.on_screen_text,
                },
                depends_on=[img_id],
            )
        )
        clip_ids.append(vid_id)

        if unit.narration.strip():
            steps.append(
                PlanStep(
                    id=f"{prefix}{i}.tts",
                    title=f"{unit.name} voiceover",
                    type="tts",
                    shot_index=i,
                    inputs={"text": unit.narration, "language": "zh"},
                )
            )

    if script.bgm_direction.strip():
        steps.append(
            PlanStep(
                id="bgm",
                title="full-film BGM",
                type="music",
                inputs={
                    "prompt": script.bgm_direction,
                    "length_ms": int(script.total_duration_sec * 1000),
                },
            )
        )

    steps.append(
        PlanStep(
            id="final",
            title="assemble final timeline",
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
