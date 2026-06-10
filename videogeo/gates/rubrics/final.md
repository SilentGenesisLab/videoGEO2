# 门禁 rubric · final（剪辑产物 FinalVideo）

逐条判定。任一 blocker 不过则 passed=false。

- **时间线连续**（blocker）：timeline 是否无重叠、无空洞，顺序与分镜叙事一致。
- **不引用幽灵素材**（blocker）：timeline 里的 shot_index 是否都在已渲染的分镜内。
- **总时长贴合**（major）：duration_sec 是否等于时间线末尾 end，且贴近目标时长（偏差 > 20% 判 major）。
- **混音/字幕合理**（minor）：若是 Seedance native audio，audio_mix 是否说明保留 clip 内置旁白/BGM；若是 external audio，audio_mix 对旁白与 BGM 的电平关系是否说得通；has_subtitles 取舍是否合理。

注意：video_url 在剪辑 subagent 给出 timeline 后由执行器 concat 填充，评审 timeline 本身即可，
不要因 video_url 暂空而判不过（assemble 阶段才会有 url）。

fix_instructions：指明时间线哪一段重叠/空洞、怎么调。
