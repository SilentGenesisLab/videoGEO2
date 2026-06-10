# 门禁 rubric · brief（导演产物 CreativeBrief）

逐条判定，每条给 ok=true/false 与 note。任一 blocker 不过则 passed=false。

- **创意清晰有记忆点**（major）：concept 是否一句话讲清、有钩子，且服务于需求 goal。
- **叙事完整有逻辑**（major）：narrative 是否首尾自洽、能支撑成片。
- **节奏 beats 合理**（blocker）：beats 是否有起伏（钩子→展开→落点之类）；
  各拍 est_duration_sec 之和是否贴近目标时长，**偏差 > 30% 判 blocker**。
- **视觉规格可执行**（major）：visual 的 style/camera/quality 是否具体到下游能照着拆分镜。
- **不违反硬约束**（blocker）：是否触碰 requirement.constraints 里的任一硬性约束。

fix_instructions：若不过，给导演 subagent 可直接照做的整改指令（指明改哪拍、改什么）。
