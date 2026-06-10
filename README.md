# videoGEO2

Codex-native multi-agent video generation framework.

Codex is the brain. Python is the thin executor. The pipeline turns a user
video request into structured artifacts, gates every semantic stage, compiles a
deterministic `plan.json`, renders Seedance segments concurrently, and assembles
the final video.

## Current TVC Kernel

The main product/TVC flow is:

```text
requirement -> brief -> global script -> storyboard shots -> render segments
  -> plan -> concurrent render -> assets -> final timeline -> assemble
```

For a 25s TVC, `script.json` should contain storyboard micro-shots but only two
actual render segments. TTS and BGM are not independent plan steps by default:
they are baked into each Seedance prompt as native `voiceover:` and
`background music / sound design:` instructions.
Set `VIDEOGEO_AUDIO_MODE=external` only when separate TTS/BGM post-production is
desired.

## Usage

In Codex, ask for a video and use the `videogeo-run` skill. The authoritative
orchestration rules live in [`AGENTS.md`](AGENTS.md).

Executor commands can also be run directly:

```bash
export VIDEOGEO_USE_MOCKS=true
export PYTHONIOENCODING=utf-8
export VIDEOGEO_AUDIO_MODE=seedance_native

python -m videogeo validate script runs/<id>/script.json --target 25
python -m videogeo compile runs/<id>/script.json --run <id> --ref "<image-url>" --target 25 --out runs/<id>/plan.json
python -m videogeo render runs/<id>/plan.json --assets runs/<id>/assets.json
python -m videogeo assemble runs/<id>/plan.json --final runs/<id>/final.json
```

PowerShell:

```powershell
$env:VIDEOGEO_USE_MOCKS="true"
$env:PYTHONIOENCODING="utf-8"
$env:VIDEOGEO_AUDIO_MODE="seedance_native"
```

## Repository Layout

```text
AGENTS.md                     Codex Leader orchestration contract
.codex/agents/                director / script-orchestrator / editor / gate-reviewer
.agents/skills/videogeo-run/  Codex skill entry
videogeo/
  schemas/                    Requirement -> Brief -> Script -> Plan -> Assets -> Final + GateVerdict
  capabilities/               mock + chorify-ai-service adapter
  compile.py                  VideoScript -> plan.json
  executor.py                 concurrent render, resumable plan status
  gates/                      deterministic rules + semantic rubrics
  __main__.py                 CLI
runs/<run_id>/                generated artifacts, ignored by git
docs/                         sanitized infrastructure notes
```

## Real Media Mode

Set `VIDEOGEO_USE_MOCKS=false` and configure chorify-ai-service in `.env`.
Real secrets must stay out of git. Use `.env.example` and
`docs/development-infrastructure.md` as safe templates.
