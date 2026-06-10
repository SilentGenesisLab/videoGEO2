# videoGEO2

多 Agent 视频生成编排框架。**Codex 当大脑，Python 当薄执行器。**

一句话需求 → 导演（创意/叙事/氛围/画质）→ 脚本编排（可执行分镜）→ 编译成可执行计划
`plan.json` → 渲染 → 剪辑（时间线）→ 合成成片。每一阶段都过审核门禁（规则预校验 +
语义评审），不过则带反馈自动回环重跑。

## 设计

- **大脑 = Codex Leader**：编排流程写死在 [`AGENTS.md`](AGENTS.md)；导演/脚本编排/剪辑/门禁是
  `.codex/agents/` 下的 subagents（门禁是唯一一个 Agent，按 rubric 适配各阶段）。
- **Skill 入口 = `.agents/skills/videogeo-run/`**：当用户要求生成视频、短视频、广告片或运行
  videoGEO 流水线时触发，按 `AGENTS.md` 创建 run、驱动阶段闭环、汇总结果。
- **薄执行器 = `videogeo` 包**：只做确定性工作，把脚本编译成 `plan.json`，按计划调
  chorify-ai-service 渲染/合成。无创意决策。
- **媒体能力**：图/视频/TTS/音乐/ffmpeg 合成委托 chorify-ai-service `/v1/*`。
  v1 默认 `VIDEOGEO_USE_MOCKS=true` 全程 mock。

## 用法

最自然的方式：在 Codex 里直接说「帮我生成一支 XXX 短视频」，触发 `videogeo-run` skill，
它按 `AGENTS.md` 跑完整条流水线。

薄执行器也可单独用（mock）：

```bash
export VIDEOGEO_USE_MOCKS=true PYTHONIOENCODING=utf-8
python -m videogeo compile  runs/<id>/script.json --run <id> --ref "<参考图url>" --target 15 --out runs/<id>/plan.json
python -m videogeo render    runs/<id>/plan.json --assets runs/<id>/assets.json
python -m videogeo assemble  runs/<id>/plan.json --final  runs/<id>/final.json
python -m videogeo validate  script runs/<id>/script.json --target 15
python -m videogeo outline   runs/<id>/plan.json
```

## 目录

```text
AGENTS.md                     写死的 Codex Leader 编排流程
.codex/agents/                director / script-orchestrator / editor / gate-reviewer
.agents/skills/videogeo-run/  触发入口
videogeo/
  schemas/                    产物契约（Requirement -> Brief -> Script -> Plan -> Assets -> Final + GateVerdict）
  capabilities/               媒体能力（base 协议 + mock + ai_service 真实 HTTP adapter）
  compile.py                  VideoScript -> plan.json
  executor.py                 跑 plan、原地回填状态、断点续
  gates/                      rules.py 规则预校验 + rubrics/ 给门禁 subagent 的评审标准
  __main__.py                 CLI: compile/render/assemble/validate/outline
runs/<run_id>/                每次运行的产物（不提交）
```

## 接真实媒体

设 `VIDEOGEO_USE_MOCKS=false`，并把 `VIDEOGEO_AI_SERVICE_BASE_URL` 指向正在运行的
chorify-ai-service。真实模式通过 `videogeo/capabilities/ai_service.py` 映射到
`/v1/video/batch`、`/v1/video/job/{id}`、`/v1/tts/*`、`/v1/long-video/concat`
等端点；视频异步 job 的轮询封在 adapter 内部。编排流程不变。

真实服务器、OSS、飞书、GitHub 等密钥只放本地 `.env` 或服务器环境变量，禁止提交。
