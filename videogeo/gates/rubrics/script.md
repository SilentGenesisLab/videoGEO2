# Script Gate Rubric

Judge `script.json` as a TVC production contract. Any blocker means
`passed=false`.

- **Global script exists** (blocker): `global_narrative` must contain a clear
  whole-film story, visual spine, narration spine, and funnel. A list of shots
  without a global idea fails.
- **Storyboard is concrete** (blocker): `shots[*].image_prompt` and
  `shots[*].video_prompt` must be specific enough for image/video generation:
  subject, composition, light, material, camera, motion, and constraints.
- **Two-segment 25s TVC** (blocker for 25s jobs): a 25s TVC must have exactly
  two `segments`, each `<=15s`, covering all storyboard shots.
- **Segments are renderable** (blocker): each segment must have a complete
  I2V prompt, duration, narration/text strategy, and storyboard coverage.
- **Storyboard reference policy** (major): storyboard references should guide
  prompts, but `feed_storyboard_seed` should remain false unless justified.
- **Narration/visual sync** (major): narration must match the segment visuals
  and fit the segment duration.
- **Native Seedance audio** (major): unless the run explicitly uses external
  audio mode, segment narration and BGM direction must be suitable for prompt
  embedding as `voiceover: "..."` and `background music / sound design: ...`.
- **TVC rhythm** (major): the whole film should use a two-part rhythm:
  hook/build -> proof/landing, with product/person/detail alternation where
  appropriate.
- **Brief alignment** (major): visual tone, selling points, constraints, and
  target market must continue the director brief.
- **Safety and product constraints** (blocker): no forbidden claims, no
  problem-skin closeups as the main appeal, no incoherent before/after gimmick.

`fix_instructions` must name the exact fields to rewrite, such as
`global_narrative.arc`, `shots[3].video_prompt`, or `segments[1].shot_indices`.
