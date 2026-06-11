"""HyperFrames subtitle composition adapter."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from videogeo.capabilities.base import CapabilityClient
from videogeo.schemas.captions import CaptionPlan
from videogeo.schemas.edit import FinalVideo


def build_hyperframes_project(
    *,
    final: FinalVideo,
    captions: CaptionPlan,
    run_dir: Path,
) -> Path:
    """Write a minimal HyperFrames composition project."""
    project_dir = run_dir / "hyperframes"
    assets_dir = project_dir / "assets"
    project_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    composition = {
        "source_video_url": final.video_url,
        "duration_sec": final.duration_sec,
        "captions": [cue.model_dump() for cue in captions.cues],
        "style": captions.style.model_dump(),
    }
    (project_dir / "composition.json").write_text(json.dumps(composition, ensure_ascii=False, indent=2), encoding="utf-8")
    (project_dir / "meta.json").write_text(
        json.dumps({"name": f"videogeo-{run_dir.name}", "entry": "index.html"}, indent=2),
        encoding="utf-8",
    )
    (project_dir / "index.html").write_text(_html(final, captions), encoding="utf-8")
    return project_dir


def render_hyperframes(
    *,
    final: FinalVideo,
    captions: CaptionPlan,
    run_dir: Path,
    cap: CapabilityClient | None = None,
    dry_run: bool = False,
) -> dict[str, str]:
    """Render captioned MP4 through HyperFrames if available.

    The function always writes the composition. If HyperFrames is unavailable or
    dry_run is true, it returns a composition-ready result and keeps the clean
    video URL as fallback.
    """
    project_dir = build_hyperframes_project(final=final, captions=captions, run_dir=run_dir)
    out_mp4 = project_dir / "captioned.mp4"
    log_path = project_dir / "render.log"
    npx = shutil.which("npx")
    if dry_run:
        log_path.write_text("dry_run=true; HyperFrames render skipped.\n", encoding="utf-8")
        return {"status": "composition_ready", "video_url": final.video_url, "project_dir": str(project_dir)}
    if not npx:
        log_path.write_text("npx not found; install Node.js/npm and run npx hyperframes render.\n", encoding="utf-8")
        return {"status": "hyperframes_unavailable", "video_url": final.video_url, "project_dir": str(project_dir)}

    cmd = [npx, "hyperframes", "render", "--output", str(out_mp4)]
    proc = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    log_path.write_text(
        "COMMAND: " + " ".join(cmd) + "\n\nSTDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
        encoding="utf-8",
    )
    if proc.returncode != 0 or not out_mp4.exists():
        return {"status": "render_failed", "video_url": final.video_url, "project_dir": str(project_dir)}
    if cap is None:
        return {"status": "rendered_local", "video_url": str(out_mp4), "project_dir": str(project_dir)}

    # Upload through the existing capability interface.
    import asyncio

    data = out_mp4.read_bytes()
    url = asyncio.run(cap.upload(data=data, name=f"{run_dir.name}_captioned.mp4"))
    return {"status": "uploaded", "video_url": url, "project_dir": str(project_dir)}


def _html(final: FinalVideo, captions: CaptionPlan) -> str:
    cues_json = json.dumps([cue.model_dump() for cue in captions.cues], ensure_ascii=False)
    video_url = final.video_url
    duration = max(0.1, final.duration_sec)
    return f"""<!doctype html>
<html lang="{captions.language}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape(final.title)}</title>
  <style>
    html, body {{ margin: 0; width: 100%; height: 100%; background: #000; overflow: hidden; }}
    #root {{ position: relative; width: 720px; height: 1280px; background: #000; font-family: {captions.style.font_family}; }}
    video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
    .caption {{
      position: absolute;
      left: 7%;
      right: 7%;
      bottom: 10%;
      color: white;
      font-size: 42px;
      line-height: 1.24;
      font-weight: {captions.style.font_weight};
      text-align: center;
      letter-spacing: 0;
      text-shadow: 0 3px 14px rgba(0,0,0,.72), 0 1px 2px rgba(0,0,0,.8);
      padding: 12px 18px;
      opacity: 0;
      white-space: pre-line;
      transition: opacity .18s linear;
    }}
    .caption.plate {{ background: rgba(0,0,0,.32); border-radius: 8px; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="videogeo-captioned" data-width="720" data-height="1280" data-duration="{duration}">
    <video id="video" src="{_escape(video_url)}" data-start="0" data-duration="{duration}" playsinline></video>
    <div id="caption" class="caption {'plate' if captions.style.background == 'translucent_plate' else ''}"></div>
  </div>
  <script>
    const cues = {cues_json};
    const video = document.getElementById('video');
    const caption = document.getElementById('caption');
    function tick() {{
      const t = video.currentTime || 0;
      const cue = cues.find(c => t >= c.start_sec && t <= c.end_sec);
      if (cue) {{
        caption.textContent = cue.text;
        caption.style.opacity = 1;
      }} else {{
        caption.style.opacity = 0;
      }}
      requestAnimationFrame(tick);
    }}
    tick();
  </script>
</body>
</html>
"""


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
