"""Persistent lesson store."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from videogeo.schemas.lessons import Lesson, RetrievedLessons


LESSONS_DIR = Path("lessons")
LESSONS_JSONL = LESSONS_DIR / "lessons.jsonl"


def append_lesson(lesson: Lesson, *, path: Path = LESSONS_JSONL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(lesson.model_dump_json() + "\n")


def load_lessons(*, path: Path = LESSONS_JSONL) -> list[Lesson]:
    if not path.exists():
        return []
    lessons: list[Lesson] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        lessons.append(Lesson.model_validate_json(line))
    return lessons


def retrieve_lessons(query: dict[str, Any], *, limit: int = 12, path: Path = LESSONS_JSONL) -> RetrievedLessons:
    lessons = load_lessons(path=path)
    q_terms = _terms(json.dumps(query, ensure_ascii=False))
    scored: list[tuple[int, Lesson]] = []
    for lesson in lessons:
        blob = " ".join([lesson.domain, lesson.provider, lesson.stage, lesson.symptom, lesson.fix_pattern, " ".join(lesson.tags)])
        terms = _terms(blob)
        score = len(q_terms & terms)
        if query.get("stage") and lesson.stage == query.get("stage"):
            score += 3
        if query.get("provider") and lesson.provider == query.get("provider"):
            score += 2
        scored.append((score, lesson))
    ranked = [lesson for score, lesson in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0]
    return RetrievedLessons(query=query, lessons=ranked[:limit])


def consolidate_lessons(run_dir: Path, *, path: Path = LESSONS_JSONL) -> list[Lesson]:
    """Convert run issues into simple lessons.

    This first version looks for `lessons_delta.json`; if absent, it writes no
    new global lessons rather than inventing data.
    """
    delta = run_dir / "lessons_delta.json"
    if not delta.exists():
        return []
    raw = json.loads(delta.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("lessons", [])
    out: list[Lesson] = []
    for item in items:
        lesson = Lesson.model_validate(item)
        append_lesson(lesson, path=path)
        out.append(lesson)
    return out


def _terms(text: str) -> set[str]:
    import re

    return {t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]+", text or "") if len(t) > 1}
