"""Caption planning utilities."""
from __future__ import annotations

import re

from videogeo.schemas.captions import CaptionCue, CaptionPlan, CaptionStyle
from videogeo.schemas.edit import FinalVideo
from videogeo.schemas.script import VideoScript


def plan_captions(
    final: FinalVideo,
    script: VideoScript,
    *,
    language: str = "zh",
    enabled: bool = True,
) -> CaptionPlan:
    """Create a conservative caption plan from approved segment narration."""
    style = CaptionStyle()
    cues: list[CaptionCue] = []
    segments = {s.index: s for s in script.segments}
    for item in sorted(final.timeline, key=lambda t: t.start_sec):
        seg = segments.get(item.shot_index)
        if not seg or not seg.narration.strip():
            continue
        phrases = _split_caption_phrases(seg.narration, language=language)
        if not phrases:
            continue
        usable_start = item.start_sec + 0.35
        usable_end = max(usable_start + 0.8, item.end_sec - 0.25)
        span = usable_end - usable_start
        slot = min(3.6, span / len(phrases))
        for idx, phrase in enumerate(phrases):
            start = usable_start + (slot + 0.15) * idx
            if start > usable_end - 0.8:
                start = max(usable_start, usable_end - 0.8)
            end = start + min(3.6, max(1.2, slot - 0.08))
            if end - start < 0.8:
                end = start + 0.8
            cues.append(
                CaptionCue(
                    start_sec=round(start, 3),
                    end_sec=round(min(end, item.end_sec - 0.05), 3),
                    text=_wrap_caption(phrase, language=language, style=style),
                    emphasis=_emphasis(phrase),
                    source=f"script.segments[{seg.index}].narration",
                )
            )
    return CaptionPlan(
        enabled=enabled,
        language=language,
        style=style,
        cues=cues,
        source_video_url=final.video_url,
        notes=["Generated from approved script segment narration; adjust with ASR if Seedance native speech timing drifts."],
    )


def _split_caption_phrases(text: str, *, language: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"[。！？!?；;，,]", text) if p.strip()]
    if not language.lower().startswith("zh"):
        return parts
    out: list[str] = []
    for part in parts:
        if len(part) <= 14:
            out.append(part)
        else:
            for i in range(0, len(part), 12):
                out.append(part[i : i + 12])
    return out


def _wrap_caption(text: str, *, language: str, style: CaptionStyle) -> str:
    limit = style.max_chars_per_line_zh if language.lower().startswith("zh") else style.max_chars_per_line_en
    text = text.strip()
    if len(text) <= limit:
        return text
    if language.lower().startswith("zh"):
        return "\n".join(text[i : i + limit] for i in range(0, len(text), limit))
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        if len(candidate) > limit and cur:
            lines.append(cur)
            cur = word
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _emphasis(text: str) -> list[str]:
    keywords = ["轻盈", "修护", "紧致", "透亮", "鎏金", "奢宠", "MEIXU", "每序"]
    return [kw for kw in keywords if kw in text][:2]
