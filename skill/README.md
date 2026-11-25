# `academic-ppt-design` Agent Skill (v4.0)

Independent, modular Agent Skill for creating **100% natively editable, zero-fill frameless academic PowerPoint decks** paired with **publication-grade scientific figures**.

## Structure

- [`SKILL.md`](SKILL.md): Core workflow, 3-layer separation architecture, and completion gates.
- [`references/01-layout-specs.md`](references/01-layout-specs.md): 16:9 canvas coordinates, zero-fill frameless rules, dynamic slide scaling, XML dual fonts, and native `baseline` sub/superscript rules.
- [`references/02-scientific-drawing.md`](references/02-scientific-drawing.md): 10 publication archetypes (`A01`–`A10`), 5 deterministic/AI figure engines, Best-of-N + Alpha matting, and proposal rigor rules.
- [`references/03-color-palettes.md`](references/03-color-palettes.md): 15 exact HEX scientific palettes, `s1`–`s6` semantic tokens, and 3D material prompt mappings.
- [`references/04-content-to-layout.md`](references/04-content-to-layout.md): Content-to-archetype mapping matrix, speaker-notes offloading, and run-level Word sync protocol.
- [`scripts/`](scripts/): Executable Python CLI scripts for archetype gallery generation, `.pptx` building, and automated auditing.
- [`assets/journal_color_palettes.jpg`](assets/journal_color_palettes.jpg): Rendered reference sheet of all 15 palettes.
