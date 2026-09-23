# Design direction

Monokl should look and read like a careful research instrument for Jcode: dark, focused, warm at the edges, and precise enough to trust.

## Visual principles

1. **Discipline first.** Layouts should make hierarchy obvious before adding decoration.
2. **Pixel-crafted, not retro for its own sake.** Pixel art is useful when it explains staged research, evidence trails, or a journey through a vault.
3. **Warm signal on a dark field.** Use color to guide attention, not to create generic neon futurism.
4. **No fake dashboards.** Avoid charts, metrics, badges, or benchmark visuals unless the repository has evidence for them.
5. **Meaningful images.** An image should explain the method, product identity, or research journey.

## Palette

Existing base:

- Ink: `#0E1116`

Recommended accent family for pixel-art and landing visuals:

- Peach: `#FFB28A`
- Coral: `#FF7A8A`
- Magenta: `#E653A9`
- Violet: `#8E5CFF`
- Deep purple: `#3A236F`
- Soft paper: `#F4E7D3`
- Muted grid: `#273044`

Use the accents as sparse lights against the dark base. Peach and soft paper carry readable highlights. Magenta and violet should mark motion, handoff, critique, and synthesis.

## Composition

Good Monokl compositions:

- show a path from question to corpus to contradiction to report;
- make stage transitions legible;
- use small artifacts like notes, pins, citations, ledgers, and threads;
- leave enough negative space for calm reading;
- use sharp pixel edges or blocky geometry with intentional alignment.

Avoid:

- glossy glassmorphism;
- generic SaaS gradients;
- robot mascots making unsupported automation claims;
- cyberpunk clutter;
- stock images of researchers;
- fake analytics panels.

## Typography and hierarchy

- Prefer concise headings with direct nouns and verbs.
- Use tables for method structure when they reduce cognitive load.
- Keep paragraphs short.
- Put installation commands in copyable fenced blocks.
- Make the first screen answer: what it is, who it is for, and how to start.

## Illustration guidance

The research journey image should communicate this sequence:

1. A question enters the system.
2. Sources and evidence are gathered into a persistent vault.
3. Contradictions and loci are mapped.
4. Investigators and critics work in separate lanes.
5. Patches and citation checks refine the report.
6. A final readable artifact exits with provenance.

Alt text should describe the communication value of the image, not merely the file style. Example:

> Pixel-art research journey showing Monokl moving from question decomposition through evidence gathering, contradiction mapping, investigation, critique, citation audit, and final report polish.

## Prose style

Write like a careful maintainer, not a growth marketer.

Use:

- concrete nouns;
- active verbs;
- explicit boundaries;
- upstream attribution;
- safety constraints;
- short lists.

Do not use:

- unsupported superlatives;
- artificial urgency;
- vague transformation language;
- exaggerated autonomy;
- claims that imply web sources, models, or generated reports are trusted by default.

## Accessibility checklist

Before shipping a page or image:

- Does the first screen explain the product without relying on the image?
- Does each image have meaningful alt text?
- Are commands split into readable lines?
- Are external claims linked to a source or removed?
- Does color support hierarchy without being the only signal?
