"""门禁 —— 两层结构。

- rules.py：确定性规则预校验（时长贴合、index 连续、素材齐全…），便宜、可在 CLI 跑，
  尤其 assets 阶段几乎纯规则。
- rubrics/*.md：给 gate-reviewer subagent（Codex 大脑里那个唯一的门禁 Agent）的评审标准，
  每阶段一份。subagent 读 rubric + 产物 → 输出 GateVerdict（见 schemas/gate.py）。

CC 主线程的编排：先跑 rules 预校验拦掉硬伤，再喊 gate-reviewer 做语义评审；
任一不过则带 fix_instructions 回灌上游 subagent 重跑（≤ max_retries_per_stage）。
"""
from videogeo.gates.rules import (
    check_assets,
    check_brief,
    check_final,
    check_script,
)

__all__ = ["check_brief", "check_script", "check_assets", "check_final"]
