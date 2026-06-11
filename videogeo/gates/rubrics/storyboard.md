# Storyboard Gate Rubric

Judge `storyboards.json` and the generated storyboard images as production
references, not decorative contact sheets.

Required dimensions:

- Narrative coverage: every major brief beat appears.
- Shot variety: product, person, texture, proof, and packshot alternate.
- Product fidelity: bottle/box/category remain faithful to the product image.
- Composition quality: premium framing, no awkward crops.
- Lighting and material: matches the brief and looks render-useful.
- Character consistency: same person when the same character appears.
- Text cleanliness: no random text, watermark, malformed subtitles, or UI junk.
- Render usefulness: each storyboard cell gives enough information for prompt
  repair or video generation.
- Reference fit: learns pacing from reference, without copying the wrong product.
- Risk flags: no deformed hands/faces, unsafe claims, or problem-skin exploitation.

Use `python -m videogeo score storyboard <storyboards.json>` for the first
deterministic scorecard, then add visual evidence if a multimodal reviewer is
available.
