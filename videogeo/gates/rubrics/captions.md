# Caption Gate Rubric

Judge `captions.json` and the HyperFrames composition.

Required dimensions:

- Timing readability: cue duration should normally be 1.2-4.0s.
- Line length: Chinese TVC captions should stay concise; English captions should
  not overflow lower thirds.
- Line count: maximum two lines unless explicitly justified.
- Audio alignment: cue timing follows narration or ASR.
- Visual occlusion: captions do not cover product hero, faces, hands, or texture.
- Contrast: captions remain readable across bright and dark frames.
- Brand tone: wording feels premium, not noisy or explanatory.
- Language correctness: no typo, mojibake, mistranslation, or malformed text.
- Platform safe area: avoids common mobile UI overlays.

Render subtitles with HyperFrames or another deterministic post layer. Do not ask
the video generation model to create subtitles directly.
