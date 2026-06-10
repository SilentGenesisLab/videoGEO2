---
name: videogeo-run
description: 触发 videoGEO 视频生成流水线。当用户要"生成一支视频/短视频/广告片"、给出视频创意需求、或说"跑 videogeo / 走视频生成流程"时使用。从一句话需求一路编排到成片：导演→脚本编排→编译 plan.json→渲染→剪辑→合成，每阶段过审核门禁。
---

# videoGEO 视频生成流水线

把用户的视频需求跑成成片。**编排细节以仓库根 `AGENTS.md` 为准**（写死的流程），本 skill 只负责
启动与收尾。

## 启动步骤

1. **建 run**：生成 `run_id`（`YYYYMMDD-HHMMSS-<短随机>`），建 `runs/<run_id>/`。
   设环境（PowerShell）：`$env:VIDEOGEO_USE_MOCKS="true"; $env:PYTHONIOENCODING="utf-8"`。
   v1 默认全程 mock，不需要任何密钥。

2. **归一化需求**：把用户这句话（及任何参考图链接、平台、时长、卖点、硬约束）抽成 Requirement，
   写 `runs/<run_id>/requirement.json`。信息不足时用合理默认，并在最后向用户说明默认了什么。

3. **按 AGENTS.md 跑闭环流程**：导演→门禁 → 脚本编排→门禁 → `compile`（产出 **plan.json**，
   把计划清单显示给用户）→ `render`→门禁 → 剪辑→门禁 → `assemble`。
   每个创意阶段不过门禁就带 fix_instructions 回灌对应 subagent 重跑（上限见
   `VIDEOGEO_MAX_RETRIES_PER_STAGE`）。

4. **收尾**：展示成片 url、`plan.json` 最终清单（各步 ✅/❌）、各阶段重跑次数、`runs/<run_id>/`
   产物清单。若某阶段被门禁卡死超限，停在该步并把门禁意见交给用户。

## 关键点
- 执行器命令都在仓库根跑（`python -m videogeo compile|render|assemble|validate|outline ...`）。
- plan.json 既是计划也是状态：中断后重跑 `render`/`assemble` 会自动跳过已完成步骤。
- 要出真实成片（非 mock）：设 `VIDEOGEO_USE_MOCKS=false`，并确认
  `VIDEOGEO_AI_SERVICE_BASE_URL` 指向正在运行的 chorify-ai-service。
