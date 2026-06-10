# 门禁 rubric · assets（渲染产物 RenderedAssets）

assets 阶段**以规则校验为主**（已由 `videogeo validate assets` 跑过 check_assets）。
gate-reviewer 在规则通过后只做轻量复核，通常直接放行：

- **片段齐全**（blocker）：每个分镜都有 clip_url（规则已判，这里复核）。
- **首帧存在**（minor）：image_url 是否齐全（v1 走参考图，缺失只记 minor）。
- **旁白覆盖**（minor）：有 narration 的分镜是否拿到 narration_audio_url。
- **时长合理**（minor）：各片段 duration_sec 是否落在 5/10/15 档位附近。

绝大多数情况 passed=true。只有出现 blocker（缺片段）才回退重跑对应分镜的渲染步骤。
