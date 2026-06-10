# videoGEO2 Spec: Quality Gates, HyperFrames Subtitles, 4-Round Iteration

Status: draft for implementation
Owner: Codex Leader
Last updated: 2026-06-11

## 1. Problem

Current videoGEO2 can generate a real TVC through:

```text
requirement -> brief -> script -> plan -> render -> assets -> final -> assemble
```

But the production core is still too shallow in five places:

1. Subtitles are only a boolean in `final.json`; there is no deterministic subtitle
   composition stage.
2. Gates mostly check file existence and simple schema rules. They do not score
   professional script quality, storyboard quality, generated frame quality,
   video continuity, caption readability, ad effectiveness, or audio-visual sync.
3. Video generation is one-pass. It does not force systematic multi-round
   regeneration, comparison, and improvement.
4. Lessons from good/bad clips are not persisted and re-read by later runs.
5. Longer videos such as 45s require stronger global narrative continuity than
   the current 25s two-segment path.

This spec upgrades videoGEO2 from "can run" to "can iterate and learn".

## 2. Research Grounding

The new gate system should combine advertising, caption, technical, and
subjective-quality standards:

- Google/YouTube's ABCD video ad framework gives ad-quality dimensions:
  Attention, Branding, Connection, Direction.
- ITU-T P.910 defines subjective video quality assessment for multimedia
  applications; videoGEO should use structured subjective review instead of
  only file checks.
- Netflix VMAF is a perceptual video quality metric; when a reference exists,
  videoGEO can add objective quality comparison in addition to LLM review.
- W3C captions guidance frames captions as synchronized speech plus meaningful
  non-speech audio for accessibility.
- Netflix/UCOP caption guidance motivates hard checks around cue duration,
  line count, line length, timing against audio, and avoiding important visual
  occlusion.
- HyperFrames is an HTML/CSS/JS video composition system. Its docs describe
  deterministic MP4 rendering and caption patching/transcription support, which
  makes it a good post-assembly subtitle and overlay layer.

Sources:

- https://support.google.com/google-ads/answer/14783551
- https://www.itu.int/rec/t-rec-p.910
- https://github.com/Netflix/vmaf
- https://www.w3.org/WAI/media/av/captions/
- https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements
- https://www.ucop.edu/electronic-accessibility/standards-and-best-practices/ecourse-accessibility-checklist/captioning-best-practices.html
- https://github.com/heygen-com/hyperframes
- https://hyperframes.mintlify.app/packages/cli

## 3. Target Pipeline

New required chain:

```text
Leader requirement.json
  -> lesson retrieval
  -> director brief.json
  -> professional brief gate
  -> script-orchestrator script.json
  -> professional script gate
  -> storyboard generation storyboards.json
  -> storyboard visual gate
  -> compile plan.json
  -> render round 0 assets.json
  -> video/audio/frame gate
  -> iteration rounds 1..3
       review -> decide -> regenerate selected segments -> compare -> lessons
  -> editor final.json
  -> final timeline gate
  -> assemble clean_video
  -> subtitle planner captions.json
  -> HyperFrames compose captioned_video
  -> caption/final delivery gate
  -> self_audit.json
  -> lesson consolidation
```

The clean assembled video remains useful. The delivered video should usually be
the HyperFrames captioned output when `subtitle_policy.enabled=true`.

## 4. New Artifacts

Each run writes:

```text
runs/<run_id>/
  requirement.json
  retrieved_lessons.json
  brief.json
  script.json
  storyboards.json
  plan.json
  assets.json
  final.json
  captions.json
  hyperframes/
    composition.html
    composition.json
    render.log
  audit.json
  lessons_delta.json
  iterations/
    round_0/
      assets.json
      gate-video-0.json
      issues.json
    round_1/
      decision.json
      regenerated_plan.json
      assets.json
      comparison.json
      gate-video-1.json
    round_2/
    round_3/
  gate-<stage>-<round>.json
```

Global learning store:

```text
lessons/
  lesson_index.json
  lessons.jsonl
  video_quality.md
  storyboard.md
  seedance.md
  subtitles.md
  product_tvc.md
```

`lessons/` is source-controlled after sanitization. It must not contain secrets,
private URLs with credentials, or raw user infrastructure values.

## 5. Subtitle and HyperFrames Spec

### 5.1 Schema

Add `videogeo/schemas/captions.py`:

```json
{
  "enabled": true,
  "language": "zh",
  "style": {
    "font_family": "Source Han Sans / Noto Sans CJK",
    "font_weight": 600,
    "position": "bottom_safe",
    "max_lines": 2,
    "max_chars_per_line_zh": 14,
    "max_chars_per_line_en": 34,
    "background": "soft_shadow_or_translucent_plate",
    "avoid_product_occlusion": true
  },
  "cues": [
    {
      "start_sec": 0.4,
      "end_sec": 2.6,
      "text": "水油轻盈流动",
      "emphasis": ["轻盈"],
      "source": "script.segment[0].narration"
    }
  ]
}
```

### 5.2 Subtitle Planning Rules

- Generate subtitles after `final.json`, before HyperFrames composition.
- Cues come from approved narration, not ad-libbed transcript, unless the video
  has unplanned generated speech. If using Seedance native audio, optionally run
  ASR to align actual speech timing.
- Chinese TVC captions should be short, brand-grade, and usually 6-14 Chinese
  characters per cue.
- No cue should cover the product hero label, face focal point, or key texture.
- Default cue duration: 1.2-4.0s. Hard fail below 0.8s; warn above 6.0s.
- Use a safe-zone layout per aspect ratio:
  - 9:16: bottom 14-22% area, leave product packshot safe zone if product is
    bottom-centered.
  - 16:9: lower third, avoid platform UI overlays.
- Render subtitles with HyperFrames, not the generative video model. The video
  prompts should still say `no subtitle, no watermark, no text overlay`.

### 5.3 HyperFrames Execution

New command:

```powershell
python -m videogeo captions runs/<id>/final.json `
  --script runs/<id>/script.json `
  --out runs/<id>/captions.json

python -m videogeo hyperframes runs/<id>/final.json `
  --captions runs/<id>/captions.json `
  --out runs/<id>/final_captioned.json
```

The HyperFrames adapter should:

- Create `runs/<id>/hyperframes/composition.html`.
- Use the clean assembled video as full-bleed background.
- Add timed caption DOM nodes from `captions.json`.
- Render MP4.
- Upload the captioned MP4 to OSS.
- Write `final_captioned.json.video_url`.

If HyperFrames CLI is missing, fail with a clear actionable error and keep the
clean no-subtitle MP4 as fallback.

## 6. Professional Gate System

All semantic gates output a scorecard:

```json
{
  "passed": false,
  "score": 0.78,
  "threshold": 0.86,
  "dimensions": [
    {
      "name": "brand_recognition",
      "weight": 0.12,
      "score": 0.65,
      "severity": "major",
      "evidence": "product label unreadable in final packshot",
      "fix": "regenerate segment 1 with product hero lock-off and label clarity"
    }
  ],
  "regenerate_targets": ["segment:1"],
  "fix_instructions": "..."
}
```

Hard rule:

- blocker dimension below threshold: fail
- weighted total below stage threshold: fail
- two major issues in the same segment: fail that segment

### 6.1 Brief Gate Dimensions

Threshold: 0.86

| Dimension | Weight | Checks |
|---|---:|---|
| Single-minded concept | 0.12 | One memorable idea, not a feature list |
| Product truth | 0.14 | Claims match product material; no medical exaggeration |
| Audience and market fit | 0.10 | Tone and message fit target buyer/platform |
| Narrative arc | 0.14 | Clear beginning/build/proof/landing |
| Visual ownability | 0.14 | Distinct material, light, motif, brand world |
| Feasibility | 0.12 | Can be rendered with available providers/assets |
| Reference adaptation | 0.10 | Learns rhythm without copying irrelevant content |
| Risk control | 0.14 | Avoids unsafe claims, deforming shots, impossible actions |

### 6.2 Script Gate Dimensions

Threshold: 0.88

| Dimension | Weight | Checks |
|---|---:|---|
| Global continuity | 0.14 | All segments serve one film, not isolated clips |
| Shot concreteness | 0.12 | Subject, scene, composition, light, motion, material |
| Segment renderability | 0.12 | Each segment <= provider max duration, no overloaded prompts |
| Audio-visual sync | 0.10 | Narration fits image beats and time |
| ABCD ad quality | 0.14 | Attention, Branding, Connection, Direction |
| Product visibility | 0.10 | Product appears early and returns at landing |
| Rhythm and pacing | 0.10 | Hook/build/proof/landing cadence |
| Constraint compliance | 0.10 | no generated subtitles, no watermark, no forbidden claims |
| Iteration hooks | 0.08 | Segment ids and shot ids allow targeted regeneration |
| Longer-video coherence | 0.10 | For >30s, act structure and continuity anchors exist |

### 6.3 Storyboard Gate Dimensions

Threshold: 0.84

| Dimension | Weight | Checks |
|---|---:|---|
| Narrative coverage | 0.12 | Every major beat appears |
| Shot variety | 0.12 | Product/person/texture/proof/packshot alternation |
| Product fidelity | 0.14 | Bottle/box shape, color, label, category not drifted |
| Composition quality | 0.10 | Premium framing, no awkward crop |
| Lighting and material | 0.10 | Matches brief; liquid/skin/glass believable |
| Character consistency | 0.10 | Same person when required |
| Text cleanliness | 0.10 | No random text, watermark, malformed labels |
| Render usefulness | 0.10 | Gives enough information for video prompt |
| Reference fit | 0.06 | Learns pacing from reference without copying wrong product |
| Risk flags | 0.06 | No deformed hands/faces/problem-skin exploitation |

### 6.4 Rendered Video Gate Dimensions

Threshold: 0.86

| Dimension | Weight | Checks |
|---|---:|---|
| Technical validity | 0.08 | Duration, fps, resolution, audio stream, no black frames |
| Product recognizability | 0.14 | Product category and hero shots readable |
| Motion realism | 0.10 | No liquid/hand/camera physics failures |
| Frame aesthetics | 0.10 | Premium color, contrast, lighting, no muddy image |
| Continuity | 0.12 | Segment handoff, character consistency, prop consistency |
| Prompt adherence | 0.10 | Actual video matches intended shot beats |
| Audio quality | 0.08 | No silence unless intended, no clipping, voice/BGM balance |
| Audio-visual sync | 0.08 | Voice moments align with shown content |
| Ad effectiveness | 0.08 | Attention/brand/connection/direction visible in output |
| Safety/compliance | 0.06 | No forbidden claims shown/spoken |
| Caption readiness | 0.06 | Safe zones available for post subtitles |

Automated probes:

- ffprobe: duration, streams, resolution, fps
- black/freeze frame detection via ffmpeg
- audio loudness and silence detection
- optional frame sampling to vision model for product/quality review
- optional VMAF only when a same-content reference exists

### 6.5 Caption Gate Dimensions

Threshold: 0.90

| Dimension | Weight | Checks |
|---|---:|---|
| Timing readability | 0.18 | cue duration, natural phrase breaks, no flash captions |
| Line length | 0.12 | <= configured chars per line |
| Line count | 0.10 | max 2 lines unless justified |
| Audio alignment | 0.14 | subtitle timing matches narration or ASR |
| Visual occlusion | 0.14 | no product/face/key texture coverage |
| Contrast | 0.10 | readable over bright/dark regions |
| Brand tone | 0.08 | captions feel premium, not noisy |
| Language correctness | 0.08 | no typos, mojibake, awkward translation |
| Platform safe area | 0.06 | avoids UI overlays for target platform |

### 6.6 Final Delivery Gate Dimensions

Threshold: 0.88

| Dimension | Weight | Checks |
|---|---:|---|
| Story continuity | 0.12 | Beginning-to-end makes sense |
| Brand memory | 0.12 | Brand/product seen early and at end |
| Emotional finish | 0.08 | Ending feels intentional |
| Technical delivery | 0.12 | duration/aspect/audio/container valid |
| Caption integration | 0.12 | readable and polished if enabled |
| Cut rhythm | 0.10 | no jarring join unless intended |
| Commercial usefulness | 0.12 | could be used as a product ad |
| Defect scan | 0.14 | no obvious AI artifacts, text garbage, warped hands |
| Evidence completeness | 0.08 | all artifacts, scores, logs present |

## 7. Four-Round Iteration

Every real production run must support up to four render/review rounds:

```text
round_0: first full render
round_1: fix blockers and worst major issues
round_2: improve aesthetics, continuity, product fidelity
round_3: final polish, subtitles, delivery-risk cleanup
```

### 7.1 Round Decision Contract

`iterations/round_<n>/decision.json`:

```json
{
  "round": 1,
  "previous_score": 0.74,
  "target_score": 0.86,
  "actions": [
    {
      "type": "regenerate_segment",
      "segment_index": 1,
      "reason": "final product packshot label unreadable",
      "prompt_patch": "hold camera steady, centered product hero, clear label"
    }
  ],
  "keep": ["segment:0"],
  "reject": ["segment:1"],
  "budget_note": "regenerate one 15s segment only"
}
```

### 7.2 Regeneration Policy

- Do not regenerate everything by default.
- Regenerate the smallest failing unit:
  - storyboard only if prompt visual plan is wrong
  - segment only if rendered motion/quality failed
  - caption only if subtitle gate failed
  - final composition only if HyperFrames overlay failed
- Keep good segments and record why they were accepted.
- If the same issue repeats twice, escalate to prompt strategy change instead of
  another blind retry.

### 7.3 Compare Candidates

Each round compares old vs new:

```json
{
  "segment_index": 1,
  "old_url": "...",
  "new_url": "...",
  "score_delta": 0.11,
  "winner": "new",
  "why": [
    "product label clearer",
    "fewer hand artifacts",
    "ending holds for 1.2s"
  ],
  "regressions": [
    "skin tone slightly colder"
  ]
}
```

If a new candidate is worse, keep the old one and write a negative lesson.

## 8. Lesson Data Loop

Lessons are first-class production data.

### 8.1 Lesson Schema

Append to `lessons/lessons.jsonl`:

```json
{
  "id": "lesson_20260611_meixu_seedance_product_hero_001",
  "date": "2026-06-11",
  "domain": "product_tvc",
  "provider": "seedance",
  "stage": "rendered_video",
  "polarity": "positive",
  "symptom": "final product hero stayed readable for >1s",
  "cause": "prompt requested centered lock-off packshot and no camera whip",
  "fix_pattern": "For luxury product ending, ask for stable centered product hero, gentle spotlight, last second hold.",
  "anti_pattern": "Do not end with fast camera motion or abstract ingredient shot.",
  "evidence": {
    "run_id": "20260611-0520-meixu-oil-r2",
    "segment_index": 1,
    "score_delta": 0.11
  },
  "tags": ["packshot", "luxury_skincare", "seedance", "ending"]
}
```

### 8.2 Lesson Retrieval

Before `director` runs, Leader writes `retrieved_lessons.json`:

- Match by product category, provider, aspect ratio, duration, language, stage.
- Prefer recent lessons with repeated evidence.
- Include both positive and negative lessons.
- Limit to 10-20 high-signal lessons to avoid prompt bloat.

Agents must explicitly use lessons:

- `director`: uses lessons for concept risks and reference adaptation.
- `script-orchestrator`: uses lessons for prompt patterns and anti-patterns.
- `gate-reviewer`: checks if repeated known failures reappear.
- `editor`: uses subtitle and transition lessons.

### 8.3 Lesson Consolidation

After delivery:

1. Collect all gate issues and round comparisons.
2. Convert repeated issues into stable lessons.
3. Reject noisy one-off observations unless they caused a blocker.
4. Update topic markdown files with distilled guidance.
5. Keep raw per-run evidence in `runs/<id>/lessons_delta.json`.

## 9. Longer Video: 45s Support

45s is not just "three 15s clips". It needs a global act structure.

Default split:

```text
Act 1 Hook + product world: 0-10s
Act 2 Texture + ingredient/proof: 10-25s
Act 3 Use + transformation/result: 25-35s
Act 4 Brand landing + CTA: 35-45s
```

Provider segment plan:

- preferred: `10s + 15s + 10s + 10s`
- fallback: `15s + 15s + 15s`
- if using extension/V2V continuity: pass last-frame references only when the
  provider path is proven stable for the product.

45s script requirements:

- `global_narrative.arc` must describe all four acts.
- `shots` should contain 12-18 storyboard micro-shots.
- `segments` should contain 3-4 render segments, each `<=15s`.
- Each segment must have:
  - `entry_state`
  - `exit_state`
  - `continuity_anchor` such as product position, character, light motif, or
    last-frame visual target.
- The script gate fails if the 45s story reads like independent ads.

45s final gate adds:

- act-level continuity
- cumulative message clarity
- fatigue check: no repetitive product orbit shots
- audio arc: music/narration should build and release, not restart every segment

## 10. Self-Audit

Every run ends with `audit.json`.

```json
{
  "run_id": "...",
  "delivered_video_url": "...",
  "artifact_presence": {
    "requirement": true,
    "brief": true,
    "script": true,
    "storyboards": true,
    "plan": true,
    "assets": true,
    "final": true,
    "captions": true,
    "audit": true
  },
  "gate_summary": [
    {"stage": "script", "round": 0, "passed": true, "score": 0.91}
  ],
  "iteration_summary": {
    "rounds_attempted": 4,
    "segments_regenerated": [1, 2],
    "best_score": 0.89
  },
  "technical_checks": {
    "duration_sec": 45.1,
    "aspect_ratio": "9:16",
    "has_audio": true,
    "has_captions": true,
    "black_frame_check": "pass",
    "silence_check": "pass"
  },
  "known_risks": [
    "VMAF skipped because no frame-aligned reference exists"
  ],
  "secrets_check": "no secrets written to tracked files",
  "git_check": "no generated files staged"
}
```

Self-audit must be honest. If a gate was manual or skipped, the audit says so.
If only a clean no-subtitle fallback was delivered, the audit says so.

## 11. Implementation Plan

### Phase 1: Contracts

- Add schemas:
  - `QualityScorecard`
  - `CaptionPlan`
  - `IterationDecision`
  - `Lesson`
  - `SelfAudit`
- Add `storyboard` as a first-class gate stage.
- Add `caption` and `delivery` gate stages.

### Phase 2: Rubrics and Rules

- Rewrite `videogeo/gates/rubrics/*.md` with the dimensions in this spec.
- Add deterministic checks:
  - duration/fps/resolution/audio stream
  - black frame/freeze frame/silence
  - caption cue duration/line count/line length
  - segment count and max duration for 25s/45s

### Phase 3: HyperFrames Adapter

- Add `videogeo/capabilities/hyperframes.py`.
- Add `python -m videogeo captions`.
- Add `python -m videogeo hyperframes`.
- Add template composition under `videogeo/templates/hyperframes/`.

### Phase 4: Iteration Engine

- Add `python -m videogeo iterate`.
- Persist `iterations/round_<n>/`.
- Support targeted segment regeneration and candidate comparison.
- Ensure plan status writes after each completed step, not only after the whole
  render batch returns.

### Phase 5: Lesson Store

- Add `lessons/` directory.
- Add `python -m videogeo lessons retrieve|append|consolidate`.
- Update `AGENTS.md` and agent TOMLs so every generation run reads lessons.

### Phase 6: 45s Real Run

- Create a 45s smoke requirement using mocks.
- Then run one real 45s product TVC:
  - 3-4 segments
  - storyboard first
  - four iteration rounds
  - HyperFrames subtitles
  - self-audit

## 12. Acceptance Criteria

The upgrade is complete when:

- A 25s run can deliver both clean and captioned MP4s.
- `captions.json` and HyperFrames composition are reproducible from `final.json`.
- Script/storyboard/video/caption/final gates produce weighted scorecards.
- Four iteration rounds can run without losing good previous segments.
- Good and bad outcomes are written into `lessons/` and retrieved on the next run.
- A 45s mock run validates fully.
- At least one real 45s run completes with `audit.json`.
- Generated media and secrets remain untracked by git.

## 13. Open Decisions

1. HyperFrames installation path: local npm package, global CLI, or vendored tool?
2. Caption timing source: script-estimated timing, Seedance native ASR, or
   HyperFrames auto-transcribe?
3. Vision reviewer: use one multimodal model for all visual gates, or split
   product-fidelity and aesthetics reviewers?
4. Cost policy: must every run spend four rounds, or can gate score >=0.92 end
   early after round 1?
5. 45s generation strategy: pure I2V independent segments, last-frame continuity,
   or provider-specific extend chain?

