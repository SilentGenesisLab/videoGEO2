"""videogeo CLI —— 薄执行器的命令行入口。

Codex 大脑（AGENTS.md 编排）在各阶段产物落盘后，调这些子命令做确定性工作：
    compile   script.json (+refs)        → plan.json（可执行 + 可显示）
    render    plan.json                  → 跑渲染步骤，回填 plan.json，导出 assets.json
    assemble  plan.json + final.json     → 把剪辑 timeline 并入并跑 concat，回填成片 url
    validate  <stage> artifact.json      → 规则预校验，打印 GateVerdict，不过则退出码 1
    outline   plan.json                  → 打印执行清单（给用户看进度）

能力实现按 VIDEOGEO_USE_MOCKS 选择：true→MockCapabilities；false→AiServiceCapabilities。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from videogeo.capabilities.base import CapabilityClient
from videogeo.compile import compile_plan
from videogeo.config import get_settings
from videogeo.executor import execute_assemble, execute_render, plan_to_assets
from videogeo.gates import check_assets, check_brief, check_final, check_script
from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.brief import CreativeBrief
from videogeo.schemas.edit import FinalVideo
from videogeo.schemas.plan import Plan
from videogeo.schemas.script import VideoScript


def _capabilities() -> CapabilityClient:
    s = get_settings()
    if s.use_mocks:
        from videogeo.capabilities.mock import MockCapabilities

        return MockCapabilities()
    from videogeo.capabilities.ai_service import AiServiceCapabilities

    return AiServiceCapabilities()


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def _write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


# ── compile ───────────────────────────────────────────────


def _cmd_compile(args: argparse.Namespace) -> int:
    script = VideoScript.model_validate_json(_read(args.script))
    refs = [u for u in (args.ref or "").split(",") if u.strip()]
    plan = compile_plan(
        script,
        run_id=args.run,
        ref_image_urls=refs,
        target_duration_sec=args.target,
        image_mode=args.image_mode,
    )
    out = args.out or f"runs/{args.run}/plan.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    _write(out, plan.model_dump_json(indent=2))
    print(plan.render_outline())
    print(f"\n✅ plan 已写入 {out}（{len(plan.steps)} 步）")
    return 0


# ── render ────────────────────────────────────────────────


def _cmd_render(args: argparse.Namespace) -> int:
    plan = Plan.model_validate_json(_read(args.plan))
    cap = _capabilities()
    plan = asyncio.run(execute_render(plan, cap))
    _write(args.plan, plan.model_dump_json(indent=2))

    assets = plan_to_assets(plan)
    assets_path = args.assets or str(Path(args.plan).with_name("assets.json"))
    _write(assets_path, assets.model_dump_json(indent=2))

    print(plan.render_outline())
    if plan.has_failure():
        print("\n❌ 有渲染步骤失败，见上方 ❌；修复后重跑可断点续（已 done 的步骤会跳过）")
        return 1
    print(f"\n✅ 渲染完成；assets 写入 {assets_path}")
    return 0


# ── assemble ──────────────────────────────────────────────


def _cmd_assemble(args: argparse.Namespace) -> int:
    plan = Plan.model_validate_json(_read(args.plan))
    final_step = plan.step("final")
    if final_step is None:
        print("plan 里没有 final/concat 步骤", file=sys.stderr)
        return 2

    # 把剪辑 subagent 的 timeline / 混音 / 字幕决策并入 concat 步骤
    if args.final:
        fv = FinalVideo.model_validate_json(_read(args.final))
        final_step.inputs["timeline"] = [t.model_dump() for t in fv.timeline]
        final_step.inputs["audio_mix"] = fv.audio_mix
        final_step.inputs["has_subtitles"] = fv.has_subtitles
        final_step.status = "pending"  # 允许重跑

    cap = _capabilities()
    plan = asyncio.run(execute_assemble(plan, cap))
    _write(args.plan, plan.model_dump_json(indent=2))

    out = final_step.output or {}
    print(plan.render_outline())
    if final_step.status != "done":
        print(f"\n❌ 合成失败: {final_step.error}")
        return 1

    # 回填成片 url 到 final.json
    if args.final:
        fv.video_url = out.get("video_url", "")
        fv.duration_sec = float(out.get("duration_sec", fv.duration_sec))
        _write(args.final, fv.model_dump_json(indent=2))
    print(f"\n✅ 成片: {out.get('video_url', '(无)')}")
    return 0


# ── validate ──────────────────────────────────────────────


def _cmd_validate(args: argparse.Namespace) -> int:
    raw = _read(args.artifact)
    if args.stage == "brief":
        verdict = check_brief(CreativeBrief.model_validate_json(raw), target_duration_sec=args.target)
    elif args.stage == "script":
        verdict = check_script(VideoScript.model_validate_json(raw), target_duration_sec=args.target)
    elif args.stage == "assets":
        verdict = check_assets(RenderedAssets.model_validate_json(raw))
    elif args.stage == "final":
        verdict = check_final(FinalVideo.model_validate_json(raw), target_duration_sec=args.target)
    else:  # pragma: no cover
        print(f"未知阶段: {args.stage}", file=sys.stderr)
        return 2
    output = verdict.model_dump_json(indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        _write(args.out, output)
    print(output)
    return 0 if verdict.passed else 1


# ── outline ───────────────────────────────────────────────


def _cmd_outline(args: argparse.Namespace) -> int:
    print(Plan.model_validate_json(_read(args.plan)).render_outline())
    return 0


def main() -> None:
    # Windows 控制台默认 GBK，清单里的 emoji/中文会编码报错 —— 强制 UTF-8 输出
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    p = argparse.ArgumentParser(prog="videogeo", description="videoGEO 薄执行器 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile", help="VideoScript → plan.json")
    c.add_argument("script", help="script.json 路径")
    c.add_argument("--run", required=True, help="run_id")
    c.add_argument("--ref", default="", help="参考图 url，逗号分隔（v1 首帧用）")
    c.add_argument("--target", type=int, default=15, help="目标时长秒")
    c.add_argument("--image-mode", default="ref", choices=["ref", "gen"], help="首帧来源")
    c.add_argument("--out", default="", help="plan.json 输出路径")
    c.set_defaults(func=_cmd_compile)

    r = sub.add_parser("render", help="跑渲染步骤，回填 plan.json + 导出 assets.json")
    r.add_argument("plan", help="plan.json 路径")
    r.add_argument("--assets", default="", help="assets.json 输出路径")
    r.set_defaults(func=_cmd_render)

    a = sub.add_parser("assemble", help="并入剪辑 timeline 并跑 concat")
    a.add_argument("plan", help="plan.json 路径")
    a.add_argument("--final", default="", help="剪辑 subagent 产出的 final.json")
    a.set_defaults(func=_cmd_assemble)

    v = sub.add_parser("validate", help="规则预校验，打印 GateVerdict")
    v.add_argument("stage", choices=["brief", "script", "assets", "final"])
    v.add_argument("artifact", help="待校验产物 json 路径")
    v.add_argument("--target", type=int, default=15, help="目标时长秒")
    v.add_argument("--out", default="", help="把 GateVerdict 同步写入 gate-*.json")
    v.set_defaults(func=_cmd_validate)

    o = sub.add_parser("outline", help="打印执行清单")
    o.add_argument("plan", help="plan.json 路径")
    o.set_defaults(func=_cmd_outline)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
