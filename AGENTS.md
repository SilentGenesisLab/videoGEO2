# videoGEO2 - 多 Agent 视频生成编排框架

这是 videoGEO2 仓库的 Codex 入口文档。它定义 Leader 编排流程、当前可用 Agent、
Skill 触发方式，以及 Codex 架构维护约定。

## 当前结构

| 区域 | 路径 | 用途 |
|---|---|---|
| Codex 入口文档 | `AGENTS.md` | Codex 编排流程的主说明。 |
| Codex Agents | `.codex/agents/*.toml` | Codex 可调用的 Agent 定义。 |
| Codex Skill | `.agents/skills/videogeo-run/SKILL.md` | Codex 侧视频生成流水线触发入口。 |
| 门禁 Rubric | `videogeo/gates/rubrics/*.md` | 各阶段语义质量审核标准。 |
| 契约 Schema | `videogeo/schemas/` | Agent 产物与 Python 执行器之间的硬契约。 |

## 架构：Codex 当大脑，Python 当薄执行器

- **大脑 / 控制平面 = Codex Leader**。本文件就是编排剧本；创意与审核角色在
  `.codex/agents/` 下。
- **薄执行器 = `videogeo` Python 包**。它只做确定性工作：编译创意 JSON 为
  `plan.json`、渲染素材、校验契约、合成成片。
- **媒体重活**，包括图像生成、视频生成、TTS、音乐、ffmpeg 合成，全部委托
  chorify-ai-service `/v1/*`。
- v1 默认 `VIDEOGEO_USE_MOCKS=true`，无需密钥/网络也可以端到端跑通。

## Agents

| Agent | 输入 -> 输出 | 职责 |
|---|---|---|
| `director` | `requirement.json` -> `brief.json` | 创意概念、叙事 beats、氛围、视觉方向。 |
| `script-orchestrator` | `brief.json` + `requirement.json` -> `script.json` | 可执行分镜序列，包含图像/视频 prompt、旁白、屏幕文字、转场。 |
| `editor` | `assets.json` + `script.json` -> `final.json` | 成片时间线与混音方案；不编造 `video_url`。 |
| `gate-reviewer` | stage + artifact + rubric -> `gate-*.json` | 唯一通用语义门禁，只按传入 rubric 审核。 |

Agent 约定：

- Agent 只读写 Leader 明确指定的路径。
- Agent 输出必须是符合 schema 的纯 JSON。
- 门禁不过时，Leader 将 `fix_instructions` 原样回灌给上游 Agent，并要求重写完整产物。
- 修改 schema 时，必须同步更新 `.codex/agents/*.toml`、validator 与 rubrics。

## Skill

`videogeo-run` 是端到端视频生成触发 Skill。当用户要求生成视频、短视频、广告片、产品片，
或明确说“跑 videoGEO / 走视频生成流程”时使用。

Codex 侧 Skill 路径：

```text
.agents/skills/videogeo-run/SKILL.md
```

Skill 保持轻量：负责启动与收尾，具体编排流程以本 `AGENTS.md` 为准。

## 产物落盘

每次运行写入 `runs/<run_id>/`。

```text
runs/<run_id>/
  requirement.json       Leader 归一化后的 Requirement
  brief.json             director 产出的 CreativeBrief
  script.json            script-orchestrator 产出的 VideoScript
  plan.json              可执行/可展示 Plan，由执行器原地回填状态
  assets.json            render 阶段产出的 RenderedAssets
  final.json             FinalVideo 时间线与最终 video_url
  gate-<stage>-<n>.json  各门禁尝试的 GateVerdict
```

`run_id` 格式：`YYYYMMDD-HHMMSS-<短随机>`。

## 固定编排流程

创意阶段统一闭环：

```text
生成 -> 规则校验 -> 语义门禁 -> 不过则带 fix_instructions 重跑
```

回环上限：`VIDEOGEO_MAX_RETRIES_PER_STAGE`，默认 `2`。

所有命令在仓库根目录执行。PowerShell mock 环境：

```powershell
$env:VIDEOGEO_USE_MOCKS="true"
$env:PYTHONIOENCODING="utf-8"
```

### 0. 归一化需求

Leader 将用户需求写成 `runs/<id>/requirement.json`。

缺省值：

- `platform`: `通用`
- `duration_sec`: `15`
- `aspect_ratio`: `9:16`
- `language`: `zh`
- 参考图链接写入 `reference_image_urls`

### 1. 导演 -> brief

1. 派 `director`：读 `requirement.json`，写 `brief.json`。
2. 规则校验：

   ```powershell
   python -m videogeo validate brief runs/<id>/brief.json --target <duration>
   ```

3. 派 `gate-reviewer`，rubric 为 `videogeo/gates/rubrics/brief.md`，输出
   `gate-brief-0.json`。
4. validate 或 gate 不过时，把问题和整改指令回灌给 `director`，直到超过阶段上限。

### 2. 脚本编排 -> script

1. 派 `script-orchestrator`：读 `brief.json` 和 `requirement.json`，写 `script.json`。
2. 执行 `validate script`。
3. 派 `gate-reviewer`，rubric 为 `videogeo/gates/rubrics/script.md`。
4. 不过则带整改指令重跑。

### 3. 编译 -> plan

确定性阶段，无语义门禁：

```powershell
python -m videogeo compile runs/<id>/script.json --run <id> `
  --ref "<逗号拼接的 requirement.reference_image_urls>" --target <duration> `
  --out runs/<id>/plan.json
```

命令打印出的 outline 是给用户看的执行计划。

### 4. 渲染 -> assets

```powershell
python -m videogeo render runs/<id>/plan.json --assets runs/<id>/assets.json
```

执行器运行 image/video/TTS/music 步骤，并原地更新 `plan.json`。重跑时会跳过已完成步骤。

然后执行 `validate assets`，并派 `gate-reviewer` 使用
`videogeo/gates/rubrics/assets.md` 审核。素材缺失或无效时重跑 `render`。

### 5. 剪辑 -> final

1. 派 `editor`：读 `assets.json` 和 `script.json`，写 `final.json`。
2. 执行 `validate final`。
3. 派 `gate-reviewer`，rubric 为 `videogeo/gates/rubrics/final.md`。
4. 不过则带整改指令重跑。

### 6. 合成 -> 成片

```powershell
python -m videogeo assemble runs/<id>/plan.json --final runs/<id>/final.json
```

执行器把 editor 的 timeline 并入 concat 步骤，并把最终 `video_url` 写回 `final.json`。

### 7. 汇总

向用户报告：

- 成片 URL。
- 各阶段是否一次通过，以及重跑次数。
- 最终 `plan.json` 状态摘要。
- `runs/<id>/` 下的产物清单。

若任一阶段超过重试上限，停在该阶段，并把 gate 的 `fix_instructions` 交给用户决策。

## 维护规则

- `AGENTS.md` 是唯一 Leader 编排入口。
- `.agents/skills/videogeo-run/SKILL.md` 指向 `AGENTS.md`。
- Codex Agent 定义集中在 `.codex/agents/*.toml`。
- 契约变更必须同步 schema、validator、agents、rubrics。
