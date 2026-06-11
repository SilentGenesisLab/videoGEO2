# videoGEO2 - Codex-native video generation framework

This file is the Codex Leader playbook. Codex does the creative orchestration;
Python stays a thin deterministic executor.

## Core Rule

For product/TVC jobs, do not let one agent improvise the whole video directly.
The required chain is:

```text
Leader requirement.json
  -> lesson retrieval
  -> director brief.json
  -> gate
  -> script-orchestrator script.json
       global_narrative
       storyboard shots
       two render segments for 25s TVC
  -> gate
  -> storyboard generation storyboards.json
  -> storyboard gate
  -> compile plan.json
  -> EXTEND-chain Seedance render assets.json
  -> multimodal visual-review gate
  -> four-round executable iteration loop
  -> editor final.json
  -> gate
  -> assemble final video
  -> captions.json
  -> HyperFrames captioned video
  -> delivery gate
  -> self-audit
  -> lesson consolidation
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

## Lessons

Before creative work, retrieve lessons:

```powershell
python -m videogeo lessons retrieve --query '{"domain":"product_tvc","provider":"seedance","stage":"script"}' `
  --out runs/<id>/retrieved_lessons.json
```

`director`, `script-orchestrator`, `editor`, and `gate-reviewer` must read
`retrieved_lessons.json` when present. After delivery, write
`runs/<id>/lessons_delta.json` for new good/bad findings and consolidate:

```powershell
python -m videogeo lessons consolidate --run-dir runs/<id>
```

## script.json Contract

`script.json` is no longer just a list of executable shots. It has three layers:

1. `global_narrative`: the whole-film story spine, funnel, voiceover spine, and visual spine.
2. `shots`: storyboard micro-shots, usually 8-11 for a 25s luxury/product TVC. These are references for rhythm and prompt detail.
3. `segments`: actual render units. For a 25s TVC, use exactly two segments. Each segment covers multiple storyboard shots and must be `<=15s`.

For a 25s TVC, prefer a practical split of `10s + 15s` when the downstream
video provider only exposes 5/10/15 buckets. If the provider accepts arbitrary
durations up to 15s, `12s + 13s` is acceptable. In both cases, keep the two
segments as one continuous global story, not two separate ads.

For a 45s TVC, prefer `10s + 15s + 10s + 10s` or `15s + 15s + 15s`.
Every render segment must include `entry_state`, `exit_state`, and
`continuity_anchor`; otherwise the script gate treats it as insufficiently
continuous.

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

Subtitles are post-production overlays. Video prompts should continue to forbid
generated subtitles. If subtitles are needed, create `captions.json` and render a
captioned delivery through HyperFrames:

```powershell
python -m videogeo captions runs/<id>/final.json --script runs/<id>/script.json --out runs/<id>/captions.json
python -m videogeo hyperframes runs/<id>/final.json --captions runs/<id>/captions.json --out runs/<id>/final_captioned.json
```

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
  captions.json
  final_captioned.json
  audit.json
  iterations/
  hyperframes/
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

Also write a professional scorecard:

```powershell
python -m videogeo score script runs/<id>/script.json --target <duration> --out runs/<id>/gate-script-score-0.json
```

### 3. Compile -> Plan

```powershell
python -m videogeo compile runs/<id>/script.json --run <id> `
  --ref "<comma-separated requirement.reference_image_urls>" --target <duration> `
  --out runs/<id>/plan.json
```

Compile uses `segments` first. If `segments` exist, video steps are `seg0.vid`,
`seg1.vid`, etc. `shots` remain storyboard references.

### 4. EXTEND-Chain Render -> Assets

```powershell
python -m videogeo render runs/<id>/plan.json --assets runs/<id>/assets.json
```

For multi-segment product/TVC jobs, the default is `VIDEOGEO_USE_EXTEND=true`:

- `seg0.vid` is generated from the product/reference image.
- `seg1+` use EXTEND. Before each EXTEND, the executor inserts
  `segN.extend_seed`, which takes the previous clip, trims it to a tail-aligned
  `14.8s` seed, applies face blur, and passes that processed video as
  `video_urls=[seed]`.
- This intentionally serializes video segments where continuity matters, so BGM
  and visual state can link across segments. Image/reference steps may still run
  independently.

In default `seedance_native` audio mode, VO/BGM are already inside the video
prompts, so there are no separate TTS/BGM steps to wait for. Tuning:

- `VIDEOGEO_RENDER_CONCURRENCY=4`
- `VIDEOGEO_VIDEO_CONCURRENCY=2`
- `VIDEOGEO_AUDIO_MODE=seedance_native`
- `VIDEOGEO_USE_EXTEND=true`
- `VIDEOGEO_EXTEND_SEED_MAX_DURATION_SEC=14.8`
- `VIDEOGEO_BLUR_FACES_BEFORE_EXTEND=true`

Then validate and gate `assets.json`.

Run multimodal video review, professional scoring, and the executable
four-round iteration loop:

```powershell
python -m videogeo visual-review runs/<id> --out runs/<id>/visual_review.json
python -m videogeo score assets runs/<id>/assets.json --visual-review runs/<id>/visual_review.json --out runs/<id>/gate-video-score-0.json
python -m videogeo iterate runs/<id> --execute --visual-review --rounds 4 --target-score 0.86
```

The iteration loop must preserve accepted segments and regenerate only failing
targets. In EXTEND mode, regenerating one segment also regenerates downstream
segments, because their seed depends on the previous accepted clip. A candidate
only replaces the current assets if its score improves or it turns a failed gate
into a passed gate.

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

### 7. Captions and HyperFrames

If subtitles are enabled for the run:

```powershell
python -m videogeo captions runs/<id>/final.json --script runs/<id>/script.json --out runs/<id>/captions.json
python -m videogeo validate captions runs/<id>/captions.json --out runs/<id>/gate-captions-rules-0.json
python -m videogeo score captions runs/<id>/captions.json --out runs/<id>/gate-captions-score-0.json
python -m videogeo hyperframes runs/<id>/final.json --captions runs/<id>/captions.json --out runs/<id>/final_captioned.json
```

Then run delivery scoring:

```powershell
python -m videogeo score delivery runs/<id>/final.json --captions runs/<id>/captions.json --out runs/<id>/gate-delivery-score-0.json
```

### 8. Self-Audit

Always write:

```powershell
python -m videogeo audit runs/<id> --out runs/<id>/audit.json
```

## Maintenance Rules

- No legacy agent entrypoints in this repo.
- Do not commit secrets. Keep real infrastructure values in local `.env` or server environment variables.
- When changing schemas, update validators, rubrics, agent TOMLs, README, and skill instructions in the same commit.
- Generated media stays under ignored `runs/`; reusable sanitized lessons under
  `lessons/` may be committed.
