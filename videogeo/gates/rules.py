"""Deterministic pre-gate rules.

These checks catch structural problems before the semantic gate-reviewer is
asked to judge creative quality.
"""
from __future__ import annotations

from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.brief import CreativeBrief
from videogeo.schemas.edit import FinalVideo
from videogeo.schemas.gate import GateIssue, GateVerdict
from videogeo.schemas.script import VideoScript


def _verdict(issues: list[GateIssue], fix: str) -> GateVerdict:
    blockers = [i for i in issues if i.severity == "blocker"]
    passed = not blockers
    score = 1.0 if not issues else max(0.0, 1.0 - 0.25 * len(issues))
    return GateVerdict(passed=passed, score=score, issues=issues, fix_instructions="" if passed else fix)


def check_brief(brief: CreativeBrief, *, target_duration_sec: int) -> GateVerdict:
    issues: list[GateIssue] = []
    total = sum(b.est_duration_sec for b in brief.beats)
    if not brief.beats:
        issues.append(GateIssue(severity="blocker", field="beats", message="beats is empty"))
    elif target_duration_sec and abs(total - target_duration_sec) / target_duration_sec > 0.30:
        issues.append(
            GateIssue(
                severity="blocker",
                field="beats",
                message=f"beat duration total {total}s is too far from target {target_duration_sec}s",
            )
        )
    if not brief.concept.strip():
        issues.append(GateIssue(severity="blocker", field="concept", message="concept is empty"))
    return _verdict(issues, "Fix beat duration and fill the core concept.")


def check_script(script: VideoScript, *, target_duration_sec: int) -> GateVerdict:
    issues: list[GateIssue] = []
    if not script.global_narrative.logline.strip() and not script.global_narrative.arc.strip():
        issues.append(
            GateIssue(
                severity="blocker",
                field="global_narrative",
                message="global narrative is missing; write the whole-film story before shots",
            )
        )
    if not script.shots:
        issues.append(GateIssue(severity="blocker", field="shots", message="storyboard shots are empty"))
    else:
        _check_indices("shots", [s.index for s in sorted(script.shots, key=lambda s: s.index)], issues)
        for s in script.shots:
            if not s.image_prompt.strip():
                issues.append(GateIssue(severity="blocker", field=f"shots[{s.index}].image_prompt", message="empty"))
            if not s.video_prompt.strip():
                issues.append(GateIssue(severity="blocker", field=f"shots[{s.index}].video_prompt", message="empty"))

    if script.segments:
        _check_indices("segments", [s.index for s in sorted(script.segments, key=lambda s: s.index)], issues)
        shot_ids = {s.index for s in script.shots}
        covered: set[int] = set()
        for seg in script.segments:
            if seg.duration_sec > 15:
                issues.append(
                    GateIssue(
                        severity="blocker",
                        field=f"segments[{seg.index}].duration_sec",
                        message="render segment exceeds 15s",
                    )
                )
            if not seg.video_prompt.strip():
                issues.append(GateIssue(severity="blocker", field=f"segments[{seg.index}].video_prompt", message="empty"))
            if not seg.shot_indices:
                issues.append(
                    GateIssue(
                        severity="major",
                        field=f"segments[{seg.index}].shot_indices",
                        message="segment does not reference storyboard shots",
                    )
                )
            missing = [i for i in seg.shot_indices if i not in shot_ids]
            if missing:
                issues.append(
                    GateIssue(
                        severity="blocker",
                        field=f"segments[{seg.index}].shot_indices",
                        message=f"unknown storyboard shots: {missing}",
                    )
                )
            covered.update(i for i in seg.shot_indices if i in shot_ids)
        uncovered = sorted(shot_ids - covered)
        if uncovered:
            issues.append(
                GateIssue(
                    severity="major",
                    field="segments",
                    message=f"storyboard shots not covered by render segments: {uncovered}",
                )
            )
        if target_duration_sec == 25 and len(script.segments) != 2:
            issues.append(
                GateIssue(
                    severity="blocker",
                    field="segments",
                    message="25s TVC must use exactly two render segments",
                )
            )
    else:
        issues.append(
            GateIssue(
                severity="major",
                field="segments",
                message="legacy mode: no render segments; compile will render each shot",
            )
        )

    total = script.total_duration_sec
    if target_duration_sec and abs(total - target_duration_sec) / target_duration_sec > 0.20:
        issues.append(
            GateIssue(
                severity="major",
                field="duration",
                message=f"script total {total}s is too far from target {target_duration_sec}s",
            )
        )
    return _verdict(
        issues,
        "Write global_narrative, storyboard shots, and render segments; for 25s use two <=15s segments covering all shots.",
    )


def _check_indices(field: str, indices: list[int], issues: list[GateIssue]) -> None:
    if indices != list(range(len(indices))):
        issues.append(GateIssue(severity="blocker", field=field, message=f"indices must start at 0 and be continuous: {indices}"))


def check_assets(assets: RenderedAssets) -> GateVerdict:
    issues: list[GateIssue] = []
    if not assets.shots:
        issues.append(GateIssue(severity="blocker", field="shots", message="no rendered segment assets"))
    missing = [a.shot_index for a in assets.shots if not a.clip_url]
    if missing:
        issues.append(GateIssue(severity="blocker", field=f"shots{missing}", message="missing video clips"))
    return _verdict(issues, f"Re-run render for segments {missing}." if missing else "Re-run render.")


def check_final(final: FinalVideo, *, target_duration_sec: int) -> GateVerdict:
    issues: list[GateIssue] = []
    if not final.timeline:
        issues.append(GateIssue(severity="blocker", field="timeline", message="timeline is empty"))
    tl = sorted(final.timeline, key=lambda t: t.start_sec)
    for a, b in zip(tl, tl[1:]):
        if b.start_sec < a.end_sec - 0.01:
            issues.append(GateIssue(severity="major", field="timeline", message=f"overlap: {a.shot_index}/{b.shot_index}"))
        elif b.start_sec > a.end_sec + 0.01:
            issues.append(GateIssue(severity="minor", field="timeline", message=f"gap: {a.shot_index}/{b.shot_index}"))
    if target_duration_sec and final.duration_sec and abs(final.duration_sec - target_duration_sec) / target_duration_sec > 0.20:
        issues.append(
            GateIssue(
                severity="major",
                field="duration",
                message=f"final duration {final.duration_sec}s is too far from target {target_duration_sec}s",
            )
        )
    return _verdict(issues, "Fix timeline continuity and final duration.")
