"""Multimodal visual review for rendered assets."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from videogeo.config import get_settings
from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.script import VideoScript


DEFAULT_DIMENSIONS = {
    "product_recognizability": 0.72,
    "motion_realism": 0.72,
    "frame_aesthetics": 0.72,
    "continuity": 0.72,
    "prompt_adherence": 0.72,
    "audio_visual_sync": 0.72,
    "ad_effectiveness": 0.72,
    "caption_readiness": 0.72,
}


async def review_assets(
    *,
    assets: RenderedAssets,
    script: VideoScript | None,
    run_dir: Path,
) -> dict[str, Any]:
    """Review rendered clips and return a JSON-serializable verdict.

    Real mode calls chorify-ai-service `/v1/understand` with video URLs. Mock
    mode returns a deterministic high-confidence review so CI can exercise the
    contract without external model calls.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    if settings.use_mocks:
        return _mock_review(assets)
    try:
        return await _understand_review(assets=assets, script=script)
    except Exception as exc:  # noqa: BLE001 - persisted as review evidence
        return _fallback_review(assets, error=f"{type(exc).__name__}: {exc}")


def load_visual_review(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _mock_review(assets: RenderedAssets) -> dict[str, Any]:
    segments = []
    targets: list[str] = []
    for shot in assets.shots:
        score = 0.93 if shot.clip_url else 0.2
        if score < 0.86:
            targets.append(f"segment:{shot.shot_index}")
        segments.append(
            {
                "segment_index": shot.shot_index,
                "clip_url": shot.clip_url,
                "generation_mode": shot.generation_mode,
                "extend_seed_url": shot.extend_seed_url,
                "face_blurred_for_extend": shot.face_blurred_for_extend,
                "overall_score": score,
                "scores": {k: score for k in DEFAULT_DIMENSIONS},
                "issues": [] if score >= 0.86 else ["missing clip url"],
                "regenerate": score < 0.86,
                "evidence": "mock visual review",
            }
        )
    return {
        "status": "mock_reviewed",
        "model": "mock",
        "dimensions": {k: _avg([s["scores"][k] for s in segments]) for k in DEFAULT_DIMENSIONS},
        "segments": segments,
        "regenerate_targets": targets,
        "raw_answer": "",
    }


async def _understand_review(*, assets: RenderedAssets, script: VideoScript | None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.internal_api_key:
        raise RuntimeError("VIDEOGEO_INTERNAL_API_KEY is required for /v1/understand visual review")
    video_urls = [s.clip_url for s in assets.shots if s.clip_url][:4]
    if not video_urls:
        raise RuntimeError("visual review requires at least one clip_url")
    prompt = _review_prompt(assets, script)
    headers = {"X-Internal-Key": settings.internal_api_key}
    payload = {
        "text": prompt,
        "image_urls": [],
        "video_urls": video_urls,
        "include_reasoning": False,
    }
    async with httpx.AsyncClient(
        base_url=settings.ai_service_base_url.rstrip("/"),
        headers=headers,
        timeout=max(settings.ai_service_http_timeout_sec, 240.0),
        trust_env=False,
    ) as client:
        resp = await client.post("/v1/understand", json=payload)
        resp.raise_for_status()
        body = resp.json()
    answer = str(body.get("answer") or "")
    parsed = _parse_json_object(answer)
    parsed.setdefault("status", "model_reviewed")
    parsed.setdefault("model", body.get("model") or "unknown")
    parsed.setdefault("raw_answer", answer)
    parsed.setdefault("segments", [])
    parsed.setdefault("dimensions", DEFAULT_DIMENSIONS)
    parsed.setdefault("regenerate_targets", _targets_from_segments(parsed.get("segments", [])))
    return parsed


def _review_prompt(assets: RenderedAssets, script: VideoScript | None) -> str:
    script_hint = ""
    if script is not None:
        script_hint = script.model_dump_json()
    asset_hint = assets.model_dump_json()
    return f"""
You are the professional video quality gate for a premium beauty TVC.
Review the attached rendered clips in order. Return ONLY valid JSON.

Score each dimension from 0 to 1:
- product_recognizability: MEIXU/product packaging readable and not deformed.
- motion_realism: hands, liquid, face, camera, and physics are natural.
- frame_aesthetics: premium lighting, color, composition, no muddy darkness.
- continuity: segment handoff, model/product/light consistency.
- prompt_adherence: visual follows the intended script.
- audio_visual_sync: narration/music feel coherent with visuals.
- ad_effectiveness: brand memory, product desire, ending intent.
- caption_readiness: lower safe area suitable for subtitles.

Mark regenerate=true for any segment below 0.86 or with severe defects.
JSON schema:
{{
  "status": "model_reviewed",
  "dimensions": {{"product_recognizability": 0.0, "motion_realism": 0.0, "frame_aesthetics": 0.0, "continuity": 0.0, "prompt_adherence": 0.0, "audio_visual_sync": 0.0, "ad_effectiveness": 0.0, "caption_readiness": 0.0}},
  "segments": [
    {{"segment_index": 0, "overall_score": 0.0, "scores": {{}}, "issues": [], "regenerate": false, "evidence": "brief concrete observation"}}
  ],
  "regenerate_targets": ["segment:1"],
  "summary": "short overall judgement"
}}

Assets:
{asset_hint}

Script:
{script_hint}
""".strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("visual review response must be a JSON object")
    return data


def _fallback_review(assets: RenderedAssets, *, error: str) -> dict[str, Any]:
    segments = []
    for shot in assets.shots:
        segments.append(
            {
                "segment_index": shot.shot_index,
                "clip_url": shot.clip_url,
                "generation_mode": shot.generation_mode,
                "extend_seed_url": shot.extend_seed_url,
                "face_blurred_for_extend": shot.face_blurred_for_extend,
                "overall_score": 0.72,
                "scores": dict(DEFAULT_DIMENSIONS),
                "issues": [f"multimodal review unavailable: {error}"],
                "regenerate": True,
                "evidence": "fallback review; requires human or model visual QA",
            }
        )
    return {
        "status": "fallback_needs_review",
        "model": "",
        "dimensions": dict(DEFAULT_DIMENSIONS),
        "segments": segments,
        "regenerate_targets": [f"segment:{s.shot_index}" for s in assets.shots],
        "raw_answer": "",
        "error": error,
    }


def _targets_from_segments(segments: list[Any]) -> list[str]:
    targets: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict) or not seg.get("regenerate"):
            continue
        idx = seg.get("segment_index")
        if isinstance(idx, int):
            targets.append(f"segment:{idx}")
    return targets


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0
