"""videoGEO2 command line executors."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from videogeo.audit import build_audit
from videogeo.capabilities.base import CapabilityClient
from videogeo.captions import plan_captions
from videogeo.compile import compile_plan
from videogeo.config import get_settings
from videogeo.executor import execute_assemble, execute_render, plan_to_assets
from videogeo.gates import check_assets, check_brief, check_final, check_script
from videogeo.gates.professional import (
    score_brief,
    score_captions,
    score_delivery,
    score_script,
    score_storyboard,
    score_video_assets,
)
from videogeo.hyperframes import render_hyperframes
from videogeo.iteration import (
    compare_assets,
    initialize_iterations,
    plan_targets_from_decision,
    reset_plan_for_targets,
)
from videogeo.lessons import append_lesson, consolidate_lessons, retrieve_lessons
from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.brief import CreativeBrief
from videogeo.schemas.captions import CaptionPlan
from videogeo.schemas.edit import FinalVideo
from videogeo.schemas.lessons import Lesson
from videogeo.schemas.plan import Plan
from videogeo.schemas.script import VideoScript
from videogeo.visual_review import load_visual_review, review_assets


def _capabilities() -> CapabilityClient:
    s = get_settings()
    if s.use_mocks:
        from videogeo.capabilities.mock import MockCapabilities

        return MockCapabilities()
    from videogeo.capabilities.ai_service import AiServiceCapabilities

    return AiServiceCapabilities()


def _read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def _write(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _cmd_compile(args: argparse.Namespace) -> int:
    script = VideoScript.model_validate_json(_read(args.script))
    refs = [u.strip() for u in (args.ref or "").split(",") if u.strip()]
    plan = compile_plan(
        script,
        run_id=args.run,
        ref_image_urls=refs,
        target_duration_sec=args.target,
        image_mode=args.image_mode,
    )
    out = args.out or f"runs/{args.run}/plan.json"
    _write(out, plan.model_dump_json(indent=2))
    print(plan.render_outline())
    print(f"\nOK plan written: {out} ({len(plan.steps)} steps)")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    plan = Plan.model_validate_json(_read(args.plan))
    plan = asyncio.run(execute_render(plan, _capabilities()))
    _write(args.plan, plan.model_dump_json(indent=2))
    assets = plan_to_assets(plan)
    assets_path = args.assets or str(Path(args.plan).with_name("assets.json"))
    _write(assets_path, assets.model_dump_json(indent=2))
    print(plan.render_outline())
    if plan.has_failure():
        print("\nFAILED render step; inspect plan.json for step.error.")
        return 1
    print(f"\nOK assets written: {assets_path}")
    return 0


def _cmd_assemble(args: argparse.Namespace) -> int:
    plan = Plan.model_validate_json(_read(args.plan))
    final_step = plan.step("final")
    if final_step is None:
        print("plan has no final concat step", file=sys.stderr)
        return 2
    fv: FinalVideo | None = None
    if args.final:
        fv = FinalVideo.model_validate_json(_read(args.final))
        final_step.inputs["timeline"] = [t.model_dump() for t in fv.timeline]
        final_step.inputs["audio_mix"] = fv.audio_mix
        final_step.inputs["has_subtitles"] = fv.has_subtitles
        final_step.status = "pending"
    plan = asyncio.run(execute_assemble(plan, _capabilities()))
    _write(args.plan, plan.model_dump_json(indent=2))
    out = final_step.output or {}
    print(plan.render_outline())
    if final_step.status != "done":
        print(f"\nFAILED assemble: {final_step.error}")
        return 1
    if args.final and fv is not None:
        fv.video_url = out.get("video_url", "")
        fv.duration_sec = float(out.get("duration_sec", fv.duration_sec))
        _write(args.final, fv.model_dump_json(indent=2))
    print(f"\nOK final video: {out.get('video_url', '')}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    raw = _read(args.artifact)
    if args.stage == "brief":
        verdict = check_brief(CreativeBrief.model_validate_json(raw), target_duration_sec=args.target)
        output = verdict.model_dump_json(indent=2)
        passed = verdict.passed
    elif args.stage == "script":
        verdict = check_script(VideoScript.model_validate_json(raw), target_duration_sec=args.target)
        output = verdict.model_dump_json(indent=2)
        passed = verdict.passed
    elif args.stage == "assets":
        verdict = check_assets(RenderedAssets.model_validate_json(raw))
        output = verdict.model_dump_json(indent=2)
        passed = verdict.passed
    elif args.stage == "final":
        verdict = check_final(FinalVideo.model_validate_json(raw), target_duration_sec=args.target)
        output = verdict.model_dump_json(indent=2)
        passed = verdict.passed
    elif args.stage == "captions":
        card = score_captions(CaptionPlan.model_validate_json(raw))
        output = card.model_dump_json(indent=2)
        passed = card.passed
    else:  # pragma: no cover
        print(f"unknown stage: {args.stage}", file=sys.stderr)
        return 2
    if args.out:
        _write(args.out, output)
    print(output)
    return 0 if passed else 1


def _cmd_outline(args: argparse.Namespace) -> int:
    print(Plan.model_validate_json(_read(args.plan)).render_outline())
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    raw = _read(args.artifact)
    if args.stage == "brief":
        card = score_brief(CreativeBrief.model_validate_json(raw))
    elif args.stage == "script":
        card = score_script(VideoScript.model_validate_json(raw), target_duration_sec=args.target)
    elif args.stage == "storyboard":
        card = score_storyboard(json.loads(raw))
    elif args.stage == "assets":
        card = score_video_assets(RenderedAssets.model_validate_json(raw), visual_review=load_visual_review(args.visual_review))
    elif args.stage == "captions":
        card = score_captions(CaptionPlan.model_validate_json(raw))
    elif args.stage == "delivery":
        captions = CaptionPlan.model_validate_json(_read(args.captions)) if args.captions else None
        card = score_delivery(FinalVideo.model_validate_json(raw), captions)
    else:  # pragma: no cover
        print(f"unknown score stage: {args.stage}", file=sys.stderr)
        return 2
    output = card.model_dump_json(indent=2)
    if args.out:
        _write(args.out, output)
    print(output)
    return 0 if card.passed else 1


def _cmd_captions(args: argparse.Namespace) -> int:
    final = FinalVideo.model_validate_json(_read(args.final))
    script = VideoScript.model_validate_json(_read(args.script))
    captions = plan_captions(final, script, language=args.language, enabled=not args.disabled)
    out = args.out or str(Path(args.final).with_name("captions.json"))
    _write(out, captions.model_dump_json(indent=2))
    print(captions.model_dump_json(indent=2))
    return 0


def _cmd_hyperframes(args: argparse.Namespace) -> int:
    final = FinalVideo.model_validate_json(_read(args.final))
    captions = CaptionPlan.model_validate_json(_read(args.captions))
    run_dir = Path(args.final).resolve().parent
    cap = None if args.no_upload else _capabilities()
    result = render_hyperframes(
        final=final,
        captions=captions,
        run_dir=run_dir,
        cap=cap,
        dry_run=args.dry_run,
    )
    out = args.out or str(Path(args.final).with_name("final_captioned.json"))
    _write(out, json.dumps({"final": final.model_dump(), "hyperframes": result}, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"uploaded", "rendered_local", "composition_ready"} else 1


def _cmd_iterate(args: argparse.Namespace) -> int:
    if args.execute:
        return asyncio.run(_cmd_iterate_execute(args))
    run_dir = Path(args.run_dir)
    assets_path = Path(args.assets or run_dir / "assets.json")
    assets = RenderedAssets.model_validate_json(_read(assets_path))
    cards = initialize_iterations(
        run_dir=run_dir,
        assets=assets,
        max_rounds=args.rounds,
        target_score=args.target_score,
    )
    summary = {"rounds": len(cards), "scores": [c.score for c in cards], "passed": any(c.passed for c in cards)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


async def _cmd_iterate_execute(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    root = run_dir / "iterations"
    root.mkdir(parents=True, exist_ok=True)
    assets_path = Path(args.assets or run_dir / "assets.json")
    plan_path = Path(args.plan or run_dir / "plan.json")
    script_path = Path(args.script or run_dir / "script.json")
    plan = Plan.model_validate_json(_read(plan_path))
    assets = RenderedAssets.model_validate_json(_read(assets_path))
    script = VideoScript.model_validate_json(_read(script_path)) if script_path.exists() else None
    cap = _capabilities()

    scores: list[float] = []
    accepted_rounds = 0
    for round_no in range(args.rounds):
        rdir = root / f"round_{round_no}"
        rdir.mkdir(parents=True, exist_ok=True)
        visual = None
        if args.visual_review:
            visual = await review_assets(assets=assets, script=script, run_dir=rdir)
            _write(rdir / "visual_review.json", json.dumps(visual, ensure_ascii=False, indent=2))
        card = score_video_assets(assets, visual_review=visual)
        _write(rdir / f"gate-video-{round_no}.json", card.model_dump_json(indent=2))
        _write(rdir / "assets.json", assets.model_dump_json(indent=2))
        scores.append(card.score)
        decision = _decision_from_card(round_no=round_no, card=card, target_score=args.target_score, assets=assets)
        _write(rdir / "decision.json", decision.model_dump_json(indent=2))
        if card.passed and card.score >= args.target_score:
            break

        targets = plan_targets_from_decision(plan, decision)
        if not targets:
            break
        prompt_patch = " ".join(a.prompt_patch or a.reason for a in decision.actions if a.type == "regenerate_segment")
        candidate_plan = plan.model_copy(deep=True)
        reset_plan_for_targets(candidate_plan, targets, round_no=round_no + 1, prompt_patch=prompt_patch)
        _write(rdir / "candidate.plan.before.json", candidate_plan.model_dump_json(indent=2))
        candidate_plan = await execute_render(candidate_plan, cap)
        _write(rdir / "candidate.plan.json", candidate_plan.model_dump_json(indent=2))
        candidate_assets = plan_to_assets(candidate_plan)
        _write(rdir / "candidate.assets.json", candidate_assets.model_dump_json(indent=2))
        candidate_visual = None
        if args.visual_review:
            candidate_visual = await review_assets(assets=candidate_assets, script=script, run_dir=rdir)
            _write(rdir / "candidate.visual_review.json", json.dumps(candidate_visual, ensure_ascii=False, indent=2))
        candidate_card = score_video_assets(candidate_assets, visual_review=candidate_visual)
        _write(rdir / "candidate.gate-video.json", candidate_card.model_dump_json(indent=2))
        comparison = compare_assets(
            old_card=card,
            new_card=candidate_card,
            decision=decision,
            old_assets=assets,
            new_assets=candidate_assets,
        )
        _write(rdir / "comparison.json", comparison.model_dump_json(indent=2))
        if comparison.winner == "new":
            plan = candidate_plan
            assets = candidate_assets
            accepted_rounds += 1
            _write(plan_path, plan.model_dump_json(indent=2))
            _write(assets_path, assets.model_dump_json(indent=2))

    summary = {"rounds": len(scores), "scores": scores, "accepted_rounds": accepted_rounds, "passed": any(s >= args.target_score for s in scores)}
    _write(root / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


def _decision_from_card(*, round_no: int, card: Any, target_score: float, assets: RenderedAssets):
    from videogeo.iteration import _decision_from_scorecard

    return _decision_from_scorecard(round_no=round_no, card=card, target_score=target_score, assets=assets)


def _cmd_visual_review(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    assets = RenderedAssets.model_validate_json(_read(args.assets or run_dir / "assets.json"))
    script_path = Path(args.script or run_dir / "script.json")
    script = VideoScript.model_validate_json(_read(script_path)) if script_path.exists() else None
    review = asyncio.run(review_assets(assets=assets, script=script, run_dir=run_dir))
    out = args.out or str(run_dir / "visual_review.json")
    _write(out, json.dumps(review, ensure_ascii=False, indent=2))
    print(json.dumps(review, ensure_ascii=False, indent=2))
    return 0 if review.get("status") != "fallback_needs_review" else 1


def _cmd_lessons(args: argparse.Namespace) -> int:
    if args.action == "retrieve":
        retrieved = retrieve_lessons(_parse_query_arg(args.query or "{}"), limit=args.limit)
        output = retrieved.model_dump_json(indent=2)
        if args.out:
            _write(args.out, output)
        print(output)
        return 0
    if args.action == "append":
        if not args.file:
            print("--file is required for lessons append", file=sys.stderr)
            return 2
        lesson = Lesson.model_validate_json(_read(args.file))
        append_lesson(lesson)
        print(lesson.model_dump_json(indent=2))
        return 0
    if args.action == "consolidate":
        if not args.run_dir:
            print("--run-dir is required for lessons consolidate", file=sys.stderr)
            return 2
        lessons = consolidate_lessons(Path(args.run_dir))
        print(json.dumps({"appended": len(lessons), "ids": [l.id for l in lessons]}, ensure_ascii=False, indent=2))
        return 0
    return 2


def _parse_query_arg(raw: str) -> dict[str, str]:
    raw = (raw or "{}").strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    body = raw.strip("{} ")
    out: dict[str, str] = {}
    for part in body.split(","):
        if not part.strip() or ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip().strip('"').strip("'")] = v.strip().strip('"').strip("'")
    return out


def _cmd_audit(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    final_path = Path(args.final or run_dir / "final.json")
    final = FinalVideo.model_validate_json(_read(final_path)) if final_path.exists() else None
    audit = build_audit(run_dir, final=final)
    out = args.out or str(run_dir / "audit.json")
    _write(out, audit.model_dump_json(indent=2))
    print(audit.model_dump_json(indent=2))
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    p = argparse.ArgumentParser(prog="videogeo", description="videoGEO2 executor CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile", help="VideoScript -> plan.json")
    c.add_argument("script")
    c.add_argument("--run", required=True)
    c.add_argument("--ref", default="")
    c.add_argument("--target", type=int, default=15)
    c.add_argument("--image-mode", default="ref", choices=["ref", "gen"])
    c.add_argument("--out", default="")
    c.set_defaults(func=_cmd_compile)

    r = sub.add_parser("render", help="execute render steps and write assets.json")
    r.add_argument("plan")
    r.add_argument("--assets", default="")
    r.set_defaults(func=_cmd_render)

    a = sub.add_parser("assemble", help="merge final timeline and run concat")
    a.add_argument("plan")
    a.add_argument("--final", default="")
    a.set_defaults(func=_cmd_assemble)

    v = sub.add_parser("validate", help="cheap deterministic pre-gate")
    v.add_argument("stage", choices=["brief", "script", "assets", "final", "captions"])
    v.add_argument("artifact")
    v.add_argument("--target", type=int, default=15)
    v.add_argument("--out", default="")
    v.set_defaults(func=_cmd_validate)

    o = sub.add_parser("outline", help="print plan outline")
    o.add_argument("plan")
    o.set_defaults(func=_cmd_outline)

    s = sub.add_parser("score", help="professional weighted quality scorecard")
    s.add_argument("stage", choices=["brief", "script", "storyboard", "assets", "captions", "delivery"])
    s.add_argument("artifact")
    s.add_argument("--target", type=int, default=15)
    s.add_argument("--captions", default="")
    s.add_argument("--visual-review", default="")
    s.add_argument("--out", default="")
    s.set_defaults(func=_cmd_score)

    cp = sub.add_parser("captions", help="plan subtitle cues from final.json and script.json")
    cp.add_argument("final")
    cp.add_argument("--script", required=True)
    cp.add_argument("--language", default="zh")
    cp.add_argument("--disabled", action="store_true")
    cp.add_argument("--out", default="")
    cp.set_defaults(func=_cmd_captions)

    hf = sub.add_parser("hyperframes", help="compose captioned video with HyperFrames")
    hf.add_argument("final")
    hf.add_argument("--captions", required=True)
    hf.add_argument("--out", default="")
    hf.add_argument("--dry-run", action="store_true")
    hf.add_argument("--no-upload", action="store_true")
    hf.set_defaults(func=_cmd_hyperframes)

    it = sub.add_parser("iterate", help="create four-round iteration decisions")
    it.add_argument("run_dir")
    it.add_argument("--assets", default="")
    it.add_argument("--plan", default="")
    it.add_argument("--script", default="")
    it.add_argument("--rounds", type=int, default=4)
    it.add_argument("--target-score", type=float, default=0.86)
    it.add_argument("--execute", action="store_true")
    it.add_argument("--visual-review", action="store_true")
    it.set_defaults(func=_cmd_iterate)

    vr = sub.add_parser("visual-review", help="run multimodal visual review for rendered assets")
    vr.add_argument("run_dir")
    vr.add_argument("--assets", default="")
    vr.add_argument("--script", default="")
    vr.add_argument("--out", default="")
    vr.set_defaults(func=_cmd_visual_review)

    le = sub.add_parser("lessons", help="retrieve, append, or consolidate lessons")
    le.add_argument("action", choices=["retrieve", "append", "consolidate"])
    le.add_argument("--query", default="{}")
    le.add_argument("--limit", type=int, default=12)
    le.add_argument("--file", default="")
    le.add_argument("--run-dir", default="")
    le.add_argument("--out", default="")
    le.set_defaults(func=_cmd_lessons)

    au = sub.add_parser("audit", help="write self-audit for a run")
    au.add_argument("run_dir")
    au.add_argument("--final", default="")
    au.add_argument("--out", default="")
    au.set_defaults(func=_cmd_audit)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
