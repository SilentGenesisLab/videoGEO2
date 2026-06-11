"""Self-audit generation."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from videogeo.schemas.audit import SelfAudit
from videogeo.schemas.edit import FinalVideo


def build_audit(run_dir: Path, *, final: FinalVideo | None = None) -> SelfAudit:
    artifacts = {
        "requirement": (run_dir / "requirement.json").exists(),
        "brief": (run_dir / "brief.json").exists(),
        "script": (run_dir / "script.json").exists(),
        "storyboards": (run_dir / "storyboards.json").exists(),
        "plan": (run_dir / "plan.json").exists(),
        "assets": (run_dir / "assets.json").exists(),
        "final": (run_dir / "final.json").exists(),
        "captions": (run_dir / "captions.json").exists(),
        "audit": True,
    }
    gate_summary = _gate_summary(run_dir)
    technical = _technical_checks(final)
    return SelfAudit(
        run_id=run_dir.name,
        delivered_video_url=final.video_url if final else "",
        artifact_presence=artifacts,
        gate_summary=gate_summary,
        iteration_summary=_iteration_summary(run_dir),
        technical_checks=technical,
        known_risks=_known_risks(run_dir),
        secrets_check=_secrets_check(run_dir),
        git_check=_git_check(),
    )


def _gate_summary(run_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("gate-*.json")) + sorted((run_dir / "iterations").glob("round_*/gate-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append(
            {
                "file": str(path.relative_to(run_dir)),
                "stage": data.get("stage") or path.stem,
                "passed": data.get("passed"),
                "score": data.get("score"),
                "threshold": data.get("threshold"),
            }
        )
    return out


def _iteration_summary(run_dir: Path) -> dict[str, Any]:
    root = run_dir / "iterations"
    if not root.exists():
        return {"rounds_attempted": 0}
    rounds = sorted(p for p in root.glob("round_*") if p.is_dir())
    scores: list[float] = []
    for gate in root.glob("round_*/gate-video-*.json"):
        try:
            scores.append(float(json.loads(gate.read_text(encoding="utf-8")).get("score", 0)))
        except Exception:  # noqa: BLE001
            pass
    return {"rounds_attempted": len(rounds), "best_score": max(scores) if scores else 0}


def _technical_checks(final: FinalVideo | None) -> dict[str, Any]:
    if final is None:
        return {}
    return {
        "duration_sec": final.duration_sec,
        "has_video_url": bool(final.video_url),
        "has_subtitles": final.has_subtitles,
        "ffprobe": "not_run_by_audit",
    }


def _known_risks(run_dir: Path) -> list[str]:
    risks: list[str] = []
    if not (run_dir / "captions.json").exists():
        risks.append("captions.json missing; captioned delivery may not exist")
    if not (run_dir / "hyperframes" / "captioned.mp4").exists() and not (run_dir / "final_captioned.json").exists():
        risks.append("HyperFrames MP4 not found; clean no-subtitle video may be the only delivery")
    return risks


def _secrets_check(run_dir: Path) -> str:
    suspicious = []
    for path in run_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text.lower() for token in ["gho_", "access_key_secret", "password=", "authorization: bearer"]):
            suspicious.append(path.name)
    return "possible secrets in " + ",".join(suspicious) if suspicious else "no obvious secrets in run json"


def _git_check() -> str:
    try:
        proc = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=15)
    except Exception as exc:  # noqa: BLE001
        return f"git status unavailable: {exc}"
    generated = [line for line in proc.stdout.splitlines() if "runs/" in line or ".env" in line]
    return "generated files visible in git status: " + "; ".join(generated) if generated else "no generated files staged"
