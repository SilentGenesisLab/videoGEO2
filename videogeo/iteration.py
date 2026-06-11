"""Four-round executable iteration for rendered assets."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from videogeo.gates.professional import score_video_assets
from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.iteration import CandidateComparison, IterationAction, IterationDecision
from videogeo.schemas.plan import Plan
from videogeo.schemas.quality import QualityScorecard


def initialize_iterations(
    *,
    run_dir: Path,
    assets: RenderedAssets,
    max_rounds: int = 4,
    target_score: float = 0.86,
) -> list[QualityScorecard]:
    """Create iteration directories and score the current assets as round 0.

    This command does not blindly regenerate media. It writes the decisions that
    the Leader/executor can act on, preserving good segments.
    """
    root = run_dir / "iterations"
    root.mkdir(parents=True, exist_ok=True)
    cards: list[QualityScorecard] = []
    current = assets
    for round_no in range(max_rounds):
        rdir = root / f"round_{round_no}"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "assets.json").write_text(current.model_dump_json(indent=2), encoding="utf-8")
        card = score_video_assets(current)
        (rdir / f"gate-video-{round_no}.json").write_text(card.model_dump_json(indent=2), encoding="utf-8")
        cards.append(card)
        decision = _decision_from_scorecard(round_no=round_no, card=card, target_score=target_score, assets=current)
        (rdir / "decision.json").write_text(decision.model_dump_json(indent=2), encoding="utf-8")
        if round_no > 0:
            comparison = CandidateComparison(
                winner="old",
                why=["No regenerated candidate attached yet; preserve previous accepted assets."],
            )
            (rdir / "comparison.json").write_text(comparison.model_dump_json(indent=2), encoding="utf-8")
        if card.passed:
            for future in range(round_no + 1, max_rounds):
                fdir = root / f"round_{future}"
                fdir.mkdir(parents=True, exist_ok=True)
                skipped = IterationDecision(
                    round=future,
                    previous_score=card.score,
                    target_score=target_score,
                    actions=[IterationAction(type="keep", reason="Previous round already passed target score.")],
                    keep=[f"segment:{s.shot_index}" for s in current.shots],
                    budget_note="Early stop: gate passed.",
                )
                (fdir / "decision.json").write_text(skipped.model_dump_json(indent=2), encoding="utf-8")
            break
    return cards


def copy_best_assets(*, run_dir: Path, assets_path: Path) -> None:
    best = run_dir / "iterations" / "round_0" / "assets.json"
    if best.exists():
        shutil.copyfile(best, assets_path)


def plan_targets_from_decision(plan: Plan, decision: IterationDecision) -> set[int]:
    """Return segment indexes to regenerate, including downstream EXTEND clips."""
    requested = {a.segment_index for a in decision.actions if a.type == "regenerate_segment" and a.segment_index is not None}
    if not requested:
        return set()
    extend_mode = any(s.type == "prepare_extend" for s in plan.steps)
    if not extend_mode:
        return {int(i) for i in requested}
    first = min(int(i) for i in requested)
    return {
        int(s.shot_index)
        for s in plan.steps
        if s.type == "video" and s.shot_index is not None and int(s.shot_index) >= first
    }


def reset_plan_for_targets(plan: Plan, targets: set[int], *, round_no: int, prompt_patch: str) -> Plan:
    """Reset target/downstream render steps and append iteration feedback."""
    for step in plan.steps:
        if step.shot_index is None or int(step.shot_index) not in targets:
            continue
        if step.type not in {"prepare_extend", "video"}:
            continue
        step.status = "pending"
        step.output = None
        step.error = ""
        step.started_at = ""
        step.finished_at = ""
        step.elapsed_sec = 0.0
        if step.type == "video":
            patch = (
                f"\n\niteration round {round_no} fix: {prompt_patch.strip()} "
                "Preserve accepted product identity, lighting family, narration continuity, and avoid new subtitles/watermarks."
            )
            step.inputs["video_prompt"] = str(step.inputs.get("video_prompt", "")).rstrip() + patch
            step.inputs["iteration_round"] = round_no
    final = plan.step("final")
    if final is not None:
        final.status = "pending"
        final.output = None
        final.error = ""
    return plan


def compare_assets(
    *,
    old_card: QualityScorecard,
    new_card: QualityScorecard,
    decision: IterationDecision,
    old_assets: RenderedAssets,
    new_assets: RenderedAssets,
) -> CandidateComparison:
    targets = {a.segment_index for a in decision.actions if a.segment_index is not None}
    old_urls = {s.shot_index: s.clip_url for s in old_assets.shots}
    new_urls = {s.shot_index: s.clip_url for s in new_assets.shots}
    changed = [idx for idx in sorted(targets) if old_urls.get(idx) != new_urls.get(idx)]
    delta = round(new_card.score - old_card.score, 3)
    winner = "new" if delta > 0.005 or (not old_card.passed and new_card.passed) else "old"
    why = [
        f"score_delta={delta}",
        f"old_score={old_card.score}",
        f"new_score={new_card.score}",
        f"changed_segments={changed}",
    ]
    regressions = [] if winner == "new" else [new_card.fix_instructions or "candidate did not improve score"]
    return CandidateComparison(
        segment_index=min(changed) if changed else None,
        old_url=old_urls.get(min(changed), "") if changed else "",
        new_url=new_urls.get(min(changed), "") if changed else "",
        score_delta=delta,
        winner=winner,
        why=why,
        regressions=regressions,
    )


def _decision_from_scorecard(
    *, round_no: int, card: QualityScorecard, target_score: float, assets: RenderedAssets
) -> IterationDecision:
    if card.passed and card.score >= target_score:
        return IterationDecision(
            round=round_no,
            previous_score=card.score,
            target_score=target_score,
            actions=[IterationAction(type="keep", reason="Quality gate passed.")],
            keep=[f"segment:{s.shot_index}" for s in assets.shots],
            budget_note="No regeneration required.",
        )
    targets = card.regenerate_targets or [f"segment:{s.shot_index}" for s in assets.shots]
    actions = []
    for target in targets:
        idx = int(target.split(":", 1)[1]) if ":" in target and target.split(":", 1)[1].isdigit() else None
        actions.append(
            IterationAction(
                type="regenerate_segment",
                segment_index=idx,
                reason=card.fix_instructions or "Quality score below target.",
                prompt_patch="Apply gate fix_instructions; preserve accepted visual identity and improve the failing dimension.",
            )
        )
    return IterationDecision(
        round=round_no,
        previous_score=card.score,
        target_score=target_score,
        actions=actions,
        keep=[f"segment:{s.shot_index}" for s in assets.shots if f"segment:{s.shot_index}" not in targets],
        reject=targets,
        budget_note="Regenerate only failing targets; do not discard accepted segments.",
    )
