"""Professional scorecards for videoGEO artifacts.

These checks are intentionally deterministic and conservative. A multimodal
reviewer can later replace or enrich each dimension, while keeping the same
QualityScorecard contract.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from videogeo.schemas.assets import RenderedAssets
from videogeo.schemas.brief import CreativeBrief
from videogeo.schemas.captions import CaptionPlan
from videogeo.schemas.edit import FinalVideo
from videogeo.schemas.quality import QualityDimension, QualityScorecard
from videogeo.schemas.script import VideoScript


def score_brief(brief: CreativeBrief) -> QualityScorecard:
    dims = [
        _dim("single_minded_concept", 0.12, _has_words(brief.concept, 8), "Concept should be a memorable one-line idea."),
        _dim("product_truth", 0.14, _claims_are_tempered(brief.narrative), "Remove medical or absolute efficacy claims."),
        _dim("audience_market_fit", 0.10, _has_words(brief.mood, 4), "Define buyer/platform tone more concretely."),
        _dim("narrative_arc", 0.14, min(1.0, len(brief.beats) / 4), "Add hook/build/proof/landing beats."),
        _dim("visual_ownability", 0.14, _has_words(brief.visual.style + brief.visual.color_palette, 10), "Specify ownable motif, light, material, palette."),
        _dim("feasibility", 0.12, _has_words(brief.visual.camera, 4), "Make camera language executable."),
        _dim("reference_adaptation", 0.10, _has_words(brief.narrative, 20), "Explain how references are adapted, not copied."),
        _dim("risk_control", 0.14, _risk_score(brief.narrative + " " + brief.concept), "Add risk controls and soften unsafe claims."),
    ]
    return QualityScorecard.from_dimensions(stage="brief", threshold=0.86, dimensions=dims)


def score_script(script: VideoScript, *, target_duration_sec: int) -> QualityScorecard:
    total = script.total_duration_sec
    segments_ok = bool(script.segments) and all(s.duration_sec <= 15 for s in script.segments)
    if target_duration_sec == 25:
        segments_ok = segments_ok and len(script.segments) == 2
    if target_duration_sec == 45:
        segments_ok = segments_ok and len(script.segments) in (3, 4)
    dims = [
        _dim("global_continuity", 0.14, _has_words(script.global_narrative.arc, 18), "Strengthen global_narrative.arc."),
        _dim("shot_concreteness", 0.12, _avg([_prompt_score(s.image_prompt + " " + s.video_prompt) for s in script.shots]), "Add subject/composition/light/material/camera constraints."),
        _dim("segment_renderability", 0.12, 1.0 if segments_ok else 0.45, "Use valid segment count and <=15s segment durations."),
        _dim("audio_visual_sync", 0.10, _avg([_has_words(s.narration, 3) for s in script.segments]) if script.segments else 0.5, "Add concise narration per segment."),
        _dim("abcd_ad_quality", 0.14, _abcd_score(script), "Ensure attention, branding, connection, and direction are all present."),
        _dim("product_visibility", 0.10, _product_visibility_score(script), "Show product early and again in landing."),
        _dim("rhythm_pacing", 0.10, _duration_score(total, target_duration_sec), "Adjust script duration to target and improve hook/build/proof/landing cadence."),
        _dim("constraint_compliance", 0.10, _constraint_score(_script_text(script)), "Add no subtitle/no watermark constraints and remove forbidden claims."),
        _dim("iteration_hooks", 0.08, 1.0 if _indices_continuous([s.index for s in script.shots]) and _indices_continuous([s.index for s in script.segments]) else 0.4, "Use continuous shot and segment indexes."),
        _dim("longer_video_coherence", 0.10, _long_video_score(script, target_duration_sec), "For >30s, add act structure and continuity anchors."),
    ]
    targets = [f"segment:{s.index}" for s in script.segments if s.duration_sec > 15]
    return QualityScorecard.from_dimensions(stage="script", threshold=0.88, dimensions=dims, regenerate_targets=targets)


def score_storyboard(data: dict[str, Any]) -> QualityScorecard:
    storyboards = data.get("storyboards") if isinstance(data, dict) else None
    storyboards = storyboards if isinstance(storyboards, list) else []
    done = [s for s in storyboards if isinstance(s, dict) and s.get("status") == "done" and s.get("oss_url")]
    text = json.dumps(data, ensure_ascii=False)
    dims = [
        _dim("narrative_coverage", 0.12, min(1.0, len(done) / max(1, len(storyboards) or 1)), "Generate storyboard images for all segments."),
        _dim("shot_variety", 0.12, _keyword_score(text, ["person", "product", "texture", "hero", "macro", "人物", "产品", "质地", "特写"]), "Use product/person/texture/proof alternation."),
        _dim("product_fidelity", 0.14, _keyword_score(text, ["product_image_url", "product", "bottle", "box", "产品"]), "Anchor storyboard to product image."),
        _dim("composition_quality", 0.10, _keyword_score(text, ["framing", "camera", "composition", "景别", "构图"]), "Specify framing and camera variety."),
        _dim("lighting_material", 0.10, _keyword_score(text, ["light", "gold", "glass", "skin", "光", "金", "玻璃", "肌肤"]), "Make lighting/material explicit."),
        _dim("character_consistency", 0.10, _keyword_score(text, ["same woman", "同一", "一致"]), "Require character consistency where people appear."),
        _dim("text_cleanliness", 0.10, 0.9 if "watermark" not in text.lower() or "no watermark" in text.lower() else 0.5, "Reject random text and watermarks."),
        _dim("render_usefulness", 0.10, _has_words(text, 80), "Record storyboard prompts/notes so render can use them."),
        _dim("reference_fit", 0.06, 1.0 if data.get("rhythm_grid_url") else 0.6, "Attach rhythm/reference grid when applicable."),
        _dim("risk_flags", 0.06, _risk_score(text), "Flag deformation, unsafe claims, problem-skin exploitation."),
    ]
    return QualityScorecard.from_dimensions(stage="storyboard", threshold=0.84, dimensions=dims)


def score_video_assets(assets: RenderedAssets, *, visual_review: dict[str, Any] | None = None) -> QualityScorecard:
    complete = assets.is_complete()
    total = sum(s.duration_sec for s in assets.shots)
    text = " ".join((s.narration_text + " " + s.bgm_direction + " " + s.clip_url) for s in assets.shots)
    review_dims = visual_review.get("dimensions", {}) if isinstance(visual_review, dict) else {}
    review_targets = visual_review.get("regenerate_targets", []) if isinstance(visual_review, dict) else []
    targets = [str(t) for t in review_targets if isinstance(t, str)]
    extend_scores = []
    for shot in assets.shots:
        if shot.shot_index == 0:
            continue
        score = 1.0 if shot.generation_mode == "extend" and shot.extend_seed_url else 0.45
        if shot.generation_mode == "extend" and not shot.face_blurred_for_extend:
            score = min(score, 0.75)
        extend_scores.append(score)
    dims = [
        _dim("technical_validity", 0.08, 1.0 if complete else 0.2, "Missing clip URLs."),
        _dim("product_recognizability", 0.14, _review_score(review_dims, "product_recognizability", _keyword_score(text, ["product", "MEIXU", "瓶", "产品", "hero"])), "Review sampled frames for product readability."),
        _dim("motion_realism", 0.10, _review_score(review_dims, "motion_realism", 0.75), "Requires visual review: check hands/liquid/camera physics."),
        _dim("frame_aesthetics", 0.10, _review_score(review_dims, "frame_aesthetics", 0.75), "Requires visual review: check color/contrast/premium feel."),
        _dim("continuity", 0.10, _review_score(review_dims, "continuity", 0.8 if len(assets.shots) > 1 else 0.7), "Check segment handoff and character/prop consistency."),
        _dim("extend_chain", 0.08, _avg(extend_scores) if extend_scores else 0.9, "Use EXTEND seed chain for segment continuity and BGM linkage."),
        _dim("prompt_adherence", 0.09, _review_score(review_dims, "prompt_adherence", 0.75), "Requires frame sampling against script."),
        _dim("audio_quality", 0.08, 0.9 if any(s.native_audio or s.narration_audio_url for s in assets.shots) else 0.55, "Check audio stream, silence, clipping."),
        _dim("audio_visual_sync", 0.08, _review_score(review_dims, "audio_visual_sync", 0.75), "Review voice moments against visuals."),
        _dim("ad_effectiveness", 0.08, _review_score(review_dims, "ad_effectiveness", _keyword_score(text, ["MEIXU", "brand", "product", "每序", "产品"])), "Brand and product should be memorable."),
        _dim("safety_compliance", 0.06, _risk_score(text), "Remove unsafe claims or visuals."),
        _dim("caption_readiness", 0.06, _review_score(review_dims, "caption_readiness", 0.75), "Check safe zones on sampled frames."),
    ]
    if total <= 0:
        dims[0].severity = "blocker"
    return QualityScorecard.from_dimensions(stage="video", threshold=0.86, dimensions=dims, regenerate_targets=targets)


def score_captions(plan: CaptionPlan) -> QualityScorecard:
    cue_scores = [_cue_score(c.text, plan.language) for c in plan.cues]
    duration_scores = [1.0 if 1.2 <= c.duration_sec <= 4.0 else 0.55 if 0.8 <= c.duration_sec <= 6.0 else 0.2 for c in plan.cues]
    line_scores = [_line_score(c.text, plan.language, plan.style.max_chars_per_line_zh, plan.style.max_chars_per_line_en) for c in plan.cues]
    dims = [
        _dim("timing_readability", 0.18, _avg(duration_scores), "Use 1.2-4.0s cue durations."),
        _dim("line_length", 0.12, _avg(line_scores), "Shorten long caption lines."),
        _dim("line_count", 0.10, 1.0 if plan.style.max_lines <= 2 else 0.7, "Use max two lines."),
        _dim("audio_alignment", 0.14, 0.75 if plan.cues else 0.2, "Align cues to narration or ASR."),
        _dim("visual_occlusion", 0.14, 0.85 if plan.style.avoid_product_occlusion else 0.55, "Avoid product/face/key texture occlusion."),
        _dim("contrast", 0.10, 0.9 if plan.style.background != "none" else 0.65, "Use shadow or plate for contrast."),
        _dim("brand_tone", 0.08, _avg(cue_scores), "Use premium concise wording."),
        _dim("language_correctness", 0.08, _mojibake_score(" ".join(c.text for c in plan.cues)), "Fix typos/mojibake."),
        _dim("platform_safe_area", 0.06, 0.9 if plan.style.position.endswith("safe") else 0.65, "Use platform safe area."),
    ]
    return QualityScorecard.from_dimensions(stage="caption", threshold=0.90, dimensions=dims)


def score_delivery(final: FinalVideo, captions: CaptionPlan | None = None) -> QualityScorecard:
    dims = [
        _dim("story_continuity", 0.12, 1.0 if final.timeline else 0.2, "Fix final timeline."),
        _dim("brand_memory", 0.12, _keyword_score(final.title + " " + final.audio_mix, ["MEIXU", "brand", "product", "每序", "产品"]), "Ensure brand/product memory in title or ending."),
        _dim("emotional_finish", 0.08, _keyword_score(final.audio_mix, ["ending", "final", "landing", "结尾", "落版"]), "Make ending intentional."),
        _dim("technical_delivery", 0.12, 0.95 if final.video_url else 0.45, "Assemble final video URL."),
        _dim("caption_integration", 0.12, 0.95 if (captions and captions.enabled and captions.cues) or not final.has_subtitles else 0.4, "Generate and render captions when enabled."),
        _dim("cut_rhythm", 0.10, _timeline_score(final), "Fix gaps/overlaps/jarring cut plan."),
        _dim("commercial_usefulness", 0.12, 0.8 if final.duration_sec >= 10 else 0.4, "Delivery should be usable as product ad."),
        _dim("defect_scan", 0.14, 0.75, "Requires final visual scan for AI artifacts."),
        _dim("evidence_completeness", 0.08, 0.8, "Ensure gates/logs/audit are present."),
    ]
    return QualityScorecard.from_dimensions(stage="delivery", threshold=0.88, dimensions=dims)


def write_scorecard(path: str | Path, scorecard: QualityScorecard) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(scorecard.model_dump_json(indent=2), encoding="utf-8")


def _dim(name: str, weight: float, score: float, fix: str) -> QualityDimension:
    score = max(0.0, min(1.0, score))
    severity = "info" if score >= 0.92 else "minor" if score >= 0.78 else "major" if score >= 0.40 else "blocker"
    return QualityDimension(name=name, weight=weight, score=round(score, 3), severity=severity, fix=fix)


def _has_words(text: str, count: int) -> float:
    text = text or ""
    words = re.findall(r"[A-Za-z0-9_]+", text)
    han = re.findall(r"[\u4e00-\u9fff]", text)
    units = len(words) + len(han) / 2.0
    return min(1.0, units / max(1, count))


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _keyword_score(text: str, keywords: list[str]) -> float:
    low = (text or "").lower()
    hits = sum(1 for k in keywords if k.lower() in low)
    return min(1.0, hits / max(1, min(len(keywords), 4)))


def _review_score(review_dims: Any, key: str, default: float) -> float:
    if isinstance(review_dims, dict):
        try:
            return float(review_dims.get(key, default))
        except (TypeError, ValueError):
            return default
    return default


def _claims_are_tempered(text: str) -> float:
    risky = ["治愈", "治疗", "永久", "100%", "第一", "最强", "medical cure", "guaranteed"]
    hits = sum(1 for w in risky if w.lower() in (text or "").lower())
    return max(0.35, 1.0 - 0.18 * hits)


def _risk_score(text: str) -> float:
    text = text or ""
    safe_phrases = [
        "无医学治疗符号",
        "不出现医学治疗",
        "no medical claim",
        "无乱码",
        "no garbled text",
        "无 before after",
        "no before after",
    ]
    for phrase in safe_phrases:
        text = text.replace(phrase, "")
    risky = ["治疗", "治愈", "永久", "无效退款", "problem skin", "before after", "畸形", "乱码"]
    hits = sum(1 for w in risky if w.lower() in (text or "").lower())
    return max(0.2, 1.0 - 0.16 * hits)


def _prompt_score(text: str) -> float:
    return _keyword_score(
        text,
        [
            "subject",
            "camera",
            "light",
            "material",
            "motion",
            "composition",
            "macro",
            "slow",
            "product",
            "skin",
            "镜头",
            "光",
            "材质",
            "构图",
            "产品",
            "肌肤",
        ],
    )


def _script_text(script: VideoScript) -> str:
    return script.model_dump_json()


def _abcd_score(script: VideoScript) -> float:
    text = _script_text(script)
    return _keyword_score(text, ["hook", "brand", "product", "CTA", "钩子", "品牌", "产品", "落版"])


def _product_visibility_score(script: VideoScript) -> float:
    shots = sorted(script.shots, key=lambda s: s.index)
    if not shots:
        return 0.0
    early = "产品" in (shots[0].video_prompt + shots[min(1, len(shots) - 1)].video_prompt) or "product" in (
        shots[0].video_prompt + shots[min(1, len(shots) - 1)].video_prompt
    ).lower()
    late = "产品" in shots[-1].video_prompt or "product" in shots[-1].video_prompt.lower()
    return 1.0 if early and late else 0.75 if late else 0.45


def _duration_score(total: float, target: int) -> float:
    if not target:
        return 0.8
    ratio = abs(total - target) / target
    return 1.0 if ratio <= 0.05 else 0.85 if ratio <= 0.15 else 0.55 if ratio <= 0.30 else 0.25


def _constraint_score(text: str) -> float:
    low = (text or "").lower()
    has_no_subtitle = "no subtitle" in low or "无字幕" in text
    has_no_watermark = "no watermark" in low or "无水印" in text
    clean = 1.0 if has_no_subtitle and has_no_watermark else 0.7 if has_no_subtitle or has_no_watermark else 0.35
    return min(clean, _risk_score(text))


def _indices_continuous(values: list[int]) -> bool:
    return values == list(range(len(values)))


def _long_video_score(script: VideoScript, target: int) -> float:
    if target <= 30:
        return 0.9
    if len(script.segments) not in (3, 4):
        return 0.35
    anchors = [s for s in script.segments if s.entry_state and s.exit_state and s.continuity_anchor]
    act_text = script.global_narrative.arc.lower()
    act_score = _keyword_score(act_text, ["act", "hook", "proof", "landing", "幕", "钩子", "证明", "落版"])
    return min(1.0, 0.4 + 0.4 * len(anchors) / len(script.segments) + 0.2 * act_score)


def _cue_score(text: str, language: str) -> float:
    if not text.strip():
        return 0.0
    if _mojibake_score(text) < 0.8:
        return 0.4
    length = len(text.strip())
    if language.lower().startswith("zh"):
        return 1.0 if 4 <= length <= 18 else 0.75 if length <= 28 else 0.45
    return 1.0 if 8 <= length <= 70 else 0.7


def _line_score(text: str, language: str, zh_limit: int, en_limit: int) -> float:
    limit = zh_limit if language.lower().startswith("zh") else en_limit
    lines = [line.strip() for line in text.splitlines() if line.strip()] or [text.strip()]
    return 1.0 if all(len(line) <= limit for line in lines) else 0.55


def _mojibake_score(text: str) -> float:
    bad = sum(text.count(ch) for ch in ["�", "鐨", "姘", "鍝", "乱码"])
    return max(0.0, 1.0 - 0.2 * bad)


def _timeline_score(final: FinalVideo) -> float:
    tl = sorted(final.timeline, key=lambda t: t.start_sec)
    if not tl:
        return 0.0
    score = 1.0
    for a, b in zip(tl, tl[1:]):
        if b.start_sec < a.end_sec - 0.01:
            score -= 0.25
        elif b.start_sec > a.end_sec + 0.01:
            score -= 0.12
    return max(0.0, score)
