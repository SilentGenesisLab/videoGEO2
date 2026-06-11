"""Four-round iteration scaffolding."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from videogeo.gates.professional import score_video_assets
from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.iteration import CandidateComparison, IterationAction, IterationDecision
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


def _decision_from_scorecard(
    *, round_no: int, card: QualityScorecard, target_score: float, assets: RenderedAssets
) -> IterationDecision:
    if card.passed:
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
