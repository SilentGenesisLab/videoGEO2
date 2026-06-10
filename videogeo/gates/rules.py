"""rules —— 确定性规则预校验，每阶段一个函数，返回 GateVerdict。

便宜、无 LLM、可在 CLI（videogeo validate）里跑。语义层面的好坏交给 gate-reviewer
subagent；这里只拦"机器能判死"的硬伤，省 token 也防 LLM 漏判。
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
    """beats 时长之和应贴近目标（偏差 > 30% 视为 blocker）。"""
    issues: list[GateIssue] = []
    total = sum(b.est_duration_sec for b in brief.beats)
    if not brief.beats:
        issues.append(GateIssue(severity="blocker", field="beats", message="beats 为空"))
    elif target_duration_sec and abs(total - target_duration_sec) / target_duration_sec > 0.30:
        issues.append(
            GateIssue(
                severity="blocker",
                field="beats",
                message=f"beats 时长之和 {total}s 偏离目标 {target_duration_sec}s 超过 30%",
            )
        )
    if not brief.concept.strip():
        issues.append(GateIssue(severity="blocker", field="concept", message="核心创意为空"))
    return _verdict(issues, "调整 beats 时长使之贴近目标，并补全核心创意。")


def check_script(script: VideoScript, *, target_duration_sec: int) -> GateVerdict:
    """index 从 0 连续；prompt 非空；总时长偏差 > 20% 视为 blocker。"""
    issues: list[GateIssue] = []
    if not script.shots:
        issues.append(GateIssue(severity="blocker", field="shots", message="无分镜"))
        return _verdict(issues, "至少产出 1 个分镜。")

    indices = [s.index for s in sorted(script.shots, key=lambda s: s.index)]
    if indices != list(range(len(indices))):
        issues.append(
            GateIssue(severity="blocker", field="shots", message=f"index 非从 0 连续递增: {indices}")
        )
    for s in script.shots:
        if not s.image_prompt.strip():
            issues.append(GateIssue(severity="blocker", field=f"shots[{s.index}].image_prompt", message="为空"))
        if not s.video_prompt.strip():
            issues.append(GateIssue(severity="blocker", field=f"shots[{s.index}].video_prompt", message="为空"))

    total = script.total_duration_sec
    if target_duration_sec and abs(total - target_duration_sec) / target_duration_sec > 0.20:
        issues.append(
            GateIssue(
                severity="major",
                field="duration",
                message=f"分镜总时长 {total}s 偏离目标 {target_duration_sec}s 超过 20%",
            )
        )
    return _verdict(issues, "修正 index 连续性、补全空 prompt、调整总时长贴近目标。")


def check_assets(assets: RenderedAssets) -> GateVerdict:
    """渲染完整性：每个分镜必须有 clip_url（纯规则，assets 阶段主门禁）。"""
    issues: list[GateIssue] = []
    if not assets.shots:
        issues.append(GateIssue(severity="blocker", field="shots", message="无任何分镜素材"))
    missing = [a.shot_index for a in assets.shots if not a.clip_url]
    if missing:
        issues.append(
            GateIssue(severity="blocker", field=f"shots{missing}", message="缺少视频片段，无法剪辑")
        )
    return _verdict(issues, f"重跑分镜 {missing} 的图生视频步骤。" if missing else "重跑渲染。")


def check_final(final: FinalVideo, *, target_duration_sec: int) -> GateVerdict:
    """成片时间线连续无重叠、总时长贴近目标。

    注意：本门禁在 concat **之前**审剪辑的 timeline，video_url 此时本就为空（由 assemble
    填充），因此不校验 url —— 只判时间线与时长。
    """
    issues: list[GateIssue] = []
    if not final.timeline:
        issues.append(GateIssue(severity="blocker", field="timeline", message="时间线为空"))
    tl = sorted(final.timeline, key=lambda t: t.start_sec)
    for a, b in zip(tl, tl[1:]):
        if b.start_sec < a.end_sec - 0.01:
            issues.append(
                GateIssue(severity="major", field="timeline", message=f"片段重叠: {a.shot_index}/{b.shot_index}")
            )
        elif b.start_sec > a.end_sec + 0.01:
            issues.append(
                GateIssue(severity="minor", field="timeline", message=f"片段间空洞: {a.shot_index}/{b.shot_index}")
            )
    if target_duration_sec and final.duration_sec and abs(final.duration_sec - target_duration_sec) / target_duration_sec > 0.20:
        issues.append(
            GateIssue(severity="major", field="duration", message=f"成片 {final.duration_sec}s 偏离目标 {target_duration_sec}s 超过 20%")
        )
    return _verdict(issues, "修正时间线连续性与总时长。")
