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
   `lessons -> director -> gate -> script-orchestrator -> gate -> storyboard -> gate -> compile -> concurrent render -> gate -> iterate -> editor -> gate -> assemble -> captions -> HyperFrames -> delivery gate -> audit -> lessons`.
4. For 25s product/TVC jobs, verify `script.json` contains:
   - `global_narrative`
   - storyboard `shots`
   - exactly two render `segments`
   - narration and BGM directions baked into Seedance prompts by default
5. For 45s product/TVC jobs, verify `script.json` contains:
   - 12-18 storyboard `shots`
   - 3-4 render `segments`, each `<=15s`
   - `entry_state`, `exit_state`, and `continuity_anchor` on every segment
6. If subtitles are requested or useful, generate clean video first, then use
   `python -m videogeo captions` and `python -m videogeo hyperframes`; never ask
   the generative video model to burn subtitles.
7. Run `python -m videogeo iterate runs/<id> --rounds 4` after first assets.
8. End every real run with `python -m videogeo audit runs/<id>`.
9. Show the user the compiled `plan.json` outline before long real rendering.
10. Report final video URL, captioned video status, run directory, gate retries,
    iteration summary, audit risks, and failed steps if any.

PowerShell defaults:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:VIDEOGEO_USE_MOCKS="true"
$env:VIDEOGEO_AUDIO_MODE="seedance_native"
```

For real media, set `VIDEOGEO_USE_MOCKS=false` and confirm `.env` is configured.
