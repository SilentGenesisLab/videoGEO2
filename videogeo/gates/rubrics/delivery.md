# Final Delivery Gate Rubric

Judge the delivered clean/captioned video after assembly.

Required dimensions:

- Story continuity: the film reads as one coherent piece.
- Brand memory: product/brand appears early and lands at the end.
- Emotional finish: ending feels intentional and usable.
- Technical delivery: container, duration, aspect ratio, audio, and URL are valid.
- Caption integration: if enabled, captions are readable and do not occlude.
- Cut rhythm: no accidental black gaps, repeats, or jarring joins.
- Commercial usefulness: a marketer could plausibly use it as a product ad.
- Defect scan: no obvious AI artifacts, random text, warped hands, or bad faces.
- Evidence completeness: artifacts, gates, iteration logs, and audit are present.

Use `python -m videogeo score delivery final.json --captions captions.json`.
