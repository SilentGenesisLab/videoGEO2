# videoGEO2 - Codex-native video generation framework

This file is the Codex Leader playbook. Codex does the creative orchestration;
Python stays a thin deterministic executor.

## Core Rule

For product/TVC jobs, do not let one agent improvise the whole video directly.
The required chain is:

```text
Leader requirement.json
  -> director brief.json
  -> gate
  -> script-orchestrator script.json
       global_narrative
       storyboard shots
       two render segments for 25s TVC
  -> gate
  -> compile plan.json
  -> concurrent Seedance render assets.json
  -> gate
  -> editor final.json
  -> gate
  -> assemble final video
```

## Architecture

- Control plane: Codex Leader and `.codex/agents/*.toml`.
- Skill entry: `.agents/skills/videogeo-run/SKILL.md`.
- Contracts: `videogeo/schemas/`.
- Deterministic executor: `python -m videogeo compile|render|assemble|validate|outline`.
- Media provider: chorify-ai-service via `VIDEOGEO_USE_MOCKS=false`.

## Agents

| Agent | Input -> Output | Responsibility |
|---|---|---|
| `director` | `requirement.json` -> `brief.json` | Concept, narrative beats, mood, visual quality, product constraints. |
| `script-orchestrator` | `requirement.json` + `brief.json` -> `script.json` | Whole-film global script, storyboard micro-shots, render segments, prompts, VO, text. |
| `editor` | `assets.json` + `script.json` -> `final.json` | Timeline, segment order, transitions, subtitle policy, audio mix plan. |
| `gate-reviewer` | stage + artifact + rubric -> `gate-*.json` | Only semantic gate; judge by the supplied rubric. |

All agents must read/write JSON with UTF-8. If Chinese text appears as mojibake,
re-read as UTF-8 before judging content.

## script.json Contract

`script.json` is no longer just a list of executable shots. It has three layers:

1. `global_narrative`: the whole-film story spine, funnel, voiceover spine, and visual spine.
2. `shots`: storyboard micro-shots, usually 8-11 for a 25s luxury/product TVC. These are references for rhythm and prompt detail.
3. `segments`: actual render units. For a 25s TVC, use exactly two segments. Each segment covers multiple storyboard shots and must be `<=15s`.

For a 25s TVC, prefer a practical split of `10s + 15s` when the downstream
video provider only exposes 5/10/15 buckets. If the provider accepts arbitrary
durations up to 15s, `12s + 13s` is acceptable. In both cases, keep the two
segments as one continuous global story, not two separate ads.

Storyboards are references. Do not feed a storyboard grid as the Seedance seed
unless a later provider-specific decision explicitly sets `feed_storyboard_seed=true`.
The default is product/reference image as seed and Chinese video prompts for stability.

## Audio Policy

Default audio mode is `VIDEOGEO_AUDIO_MODE=seedance_native`.

In this mode, TTS/BGM are not separate pre-render steps. The segment narration
and music direction are baked into each Seedance prompt, matching the 0609-r1
reference format:

```text
voiceover: "..."
background music / sound design: ...
```

Therefore a normal 25s TVC plan should show two video steps (`seg0.vid`,
`seg1.vid`) and no `tts` or `music` steps. Use `VIDEOGEO_AUDIO_MODE=external`
only for the older fallback path where separate TTS/BGM assets are generated and
mixed after video render.

## Run Directory

Each run writes to `runs/<run_id>/`:

```text
requirement.json
brief.json
script.json
plan.json
assets.json
final.json
gate-<stage>-<n>.json
```

`run_id` format: `YYYYMMDD-HHMMSS-<short-random>`.

## Fixed Flow

Set environment in PowerShell:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:VIDEOGEO_USE_MOCKS="true"
```

Use `VIDEOGEO_USE_MOCKS=false` only when real media generation is intended and
the chorify-ai-service environment is ready.

### 0. Normalize Requirement

Leader writes `runs/<id>/requirement.json`. Fill reasonable defaults:

- `platform`: `generic`
- `duration_sec`: `15`, unless user requested another duration
- `aspect_ratio`: `9:16`
- `language`: `zh`
- `reference_image_urls`: product/reference images

### 1. Director -> Brief

Run `director`, then:

```powershell
python -m videogeo validate brief runs/<id>/brief.json --target <duration> --out runs/<id>/gate-brief-rules-0.json
```

Then run `gate-reviewer` with `videogeo/gates/rubrics/brief.md`.
If rules or gate fail, feed issues back to `director` and rewrite the complete file.

### 2. Script-Orchestrator -> Script

Run `script-orchestrator`. It must produce:

- one `global_narrative`
- storyboard `shots`
- actual render `segments`
- executable `bgm_direction`

For 25s TVC: exactly two render segments, covering all storyboard shots.

Then:

```powershell
python -m videogeo validate script runs/<id>/script.json --target <duration> --out runs/<id>/gate-script-rules-0.json
```

Then run `gate-reviewer` with `videogeo/gates/rubrics/script.md`.

### 3. Compile -> Plan

```powershell
python -m videogeo compile runs/<id>/script.json --run <id> `
  --ref "<comma-separated requirement.reference_image_urls>" --target <duration> `
  --out runs/<id>/plan.json
```

Compile uses `segments` first. If `segments` exist, video steps are `seg0.vid`,
`seg1.vid`, etc. `shots` remain storyboard references.

### 4. Concurrent Render -> Assets

```powershell
python -m videogeo render runs/<id>/plan.json --assets runs/<id>/assets.json
```

Render runs ready steps concurrently. In default `seedance_native` audio mode,
VO/BGM are already inside the video prompts, so there are no separate TTS/BGM
steps to wait for. Tuning:

- `VIDEOGEO_RENDER_CONCURRENCY=4`
- `VIDEOGEO_VIDEO_CONCURRENCY=2`
- `VIDEOGEO_AUDIO_MODE=seedance_native`

Then validate and gate `assets.json`.

### 5. Editor -> Final

Run `editor` to write `final.json`. Timeline references rendered segment indices,
not storyboard micro-shot indices. Then:

```powershell
python -m videogeo validate final runs/<id>/final.json --target <duration> --out runs/<id>/gate-final-rules-0.json
```

Then run `gate-reviewer` with `videogeo/gates/rubrics/final.md`.

### 6. Assemble

```powershell
python -m videogeo assemble runs/<id>/plan.json --final runs/<id>/final.json
```

The executor writes final `video_url` back into `final.json`.

## Maintenance Rules

- No legacy agent entrypoints in this repo.
- Do not commit secrets. Keep real infrastructure values in local `.env` or server environment variables.
- When changing schemas, update validators, rubrics, agent TOMLs, README, and skill instructions in the same commit.
