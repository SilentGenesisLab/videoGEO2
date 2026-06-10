---
name: videogeo-run
description: Run the videoGEO2 Codex video pipeline. Use when the user asks to generate a video, short ad, product TVC, storyboard-driven video, or says to run videoGEO.
---

# videoGEO2 Pipeline Skill

This skill only starts and closes the workflow. The authoritative orchestration
rules are in the repository root `AGENTS.md`.

## Required Behavior

1. Create `runs/<run_id>/`.
2. Write `requirement.json`.
3. Follow `AGENTS.md` exactly:
   `director -> gate -> script-orchestrator -> gate -> compile -> concurrent render -> gate -> editor -> gate -> assemble`.
4. For 25s product/TVC jobs, verify `script.json` contains:
   - `global_narrative`
   - storyboard `shots`
   - exactly two render `segments`
   - TTS and BGM directions that compile into independent plan steps
5. Show the user the compiled `plan.json` outline before long real rendering.
6. Report final video URL, run directory, gate retries, and failed steps if any.

PowerShell defaults:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:VIDEOGEO_USE_MOCKS="true"
```

For real media, set `VIDEOGEO_USE_MOCKS=false` and confirm `.env` is configured.
