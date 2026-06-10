# 门禁 rubric · script（脚本编排产物 VideoScript）

逐条判定。任一 blocker 不过则 passed=false。

- **分镜顺序**（blocker）：index 是否从 0 连续递增、顺序即时间线、无重复。
- **prompt 可执行**（blocker）：每个分镜的 image_prompt / video_prompt 是否具体到能直接喂生成模型
  （有主体、动作、镜头、风格），不能是空话或占位。
- **总时长贴合**（major）：所有分镜 duration_sec 之和是否贴近目标总时长，**偏差 > 20% 判 major**。
  另注意单镜时长最终会被吸附到 5/10/15s 档位，过短/过长要提示。
- **旁白与画面匹配**（major）：narration 是否与该镜画面一致，整体是否覆盖核心卖点。
- **承接 brief**（minor）：氛围、视觉风格是否延续 CreativeBrief，没有跑偏。
- **不违反硬约束**（blocker）：是否触碰 requirement.constraints。

fix_instructions：指明哪个 shots[i] 的哪个字段怎么改。
