---
name: academic-ppt-design
description: >
  Design and compile 100% natively editable, zero-fill frameless academic PowerPoint decks
  and publication-grade scientific figures (ChemDraw/RDKit, CYLview3D, OriginPro 600 DPI,
  C4D/Editorial 3D with true Alpha matting, and vector mechanisms). Trigger when building
  or revising thesis defense, midterm, group-meeting, or literature-review slides, generating
  scientific figures (A01–A10), or syncing Word manuscripts into editable .pptx decks.
---

# Academic PPT Design (`academic-ppt-design` v4.0)

Build 100% natively editable `.pptx` presentations paired with **one dedicated publication-grade scientific figure per content slide**.

## Core Architecture (3-Layer Physical Separation)

Every content slide strictly separates visual layers so every molecule, arrow, line, and word remains editable in PowerPoint:
- **Layer 1 (Transparent Visual Assets)**: Fixed-bond-length 2D molecules (`ChemDrawEngine`), deterministic 3D ball-and-stick conformers (`CYLview3DEngine`), 1:1 physical 600 DPI quantitative charts (`OriginPlotEngine`), and strictly zero-text, true-alpha studio 3D/editorial renders (`Sci3DArtEngine`).
- **Layer 2 (Native Vector Skeleton)**: Editable PowerPoint connectors, exact external-bitangent zoom-lens frames, reaction arrows, `3 pt` left insight accent bars, and `0.75 pt` hairline dividers.
- **Layer 3 (Native Editable Text & Tables)**: Dual-XML-font textboxes (`Arial` + `微软雅黑`), native `baseline` sub/superscripts, and zero-fill academic three-line tables.

## Workflow

1. **Confirm Deck Scope & Palette**:
   - Accept any user-requested slide count ($N \in [3, 30+]$) and scenario (`defense`, `midterm`, `group_meeting`, `literature_review`).
   - Load [`references/03-color-palettes.md`](references/03-color-palettes.md) and lock one palette from the 15-palette system (default: `lancet`). Every PPT element and all 5 figure engines derive colors from this palette's `s1`–`s6` tokens.
   - **Completion criterion**: `DeckMeta` holds `target_slide_count`, `scenario`, and `palette_id`.

2. **Plan Structure & Narrative Mapping**:
   - Load [`references/01-layout-specs.md`](references/01-layout-specs.md) and [`references/04-content-to-layout.md`](references/04-content-to-layout.md).
   - Scale structural slides automatically (`<=10`: skip TOC/PART; `11–18`: cover + TOC + closing; `>=19`: cover + TOC + PART dividers + closing).
   - Keep slide body copy concise ($\le 3$ insights, $40\text{--}70$ chars total) and offload full methods/details into `speaker_notes`.
   - **Completion criterion**: Every content slide has a concise single-sentence `takeaway` and `figure_spec`.

3. **Design & Render Publication-Grade Figures (Highest Priority)**:
   - Load [`references/02-scientific-drawing.md`](references/02-scientific-drawing.md) and assign an archetype (`A01`–`A10`) per content slide.
   - Enforce proposal rigor: on `defense`/proposal decks, route unmeasured data claims to experimental SOP / probe matrices / characterization frameworks instead of simulated curves.
   - Run Best-of-$N$ ($N \ge 2$) for `Sci3DArtEngine`, apply true-alpha edge decontamination, and verify with `FigureCriticAgent` (`detected_text_count == 0` for `sci3d_art`, `vlm_aesthetic_score >= 8.5`).
   - **Completion criterion**: Every content slide holds `qa_passed == True` and `overall_qa_score >= 8.5`.

4. **Compile & Audit Native `.pptx`**:
   - Compile `DeckSpec v4.0` via [`scripts/build_deck.py`](scripts/build_deck.py).
   - Audit via [`scripts/audit_deck.py`](scripts/audit_deck.py) and verify **0 violations** (`filled_body_boxes == 0`, `min_body_pt >= 18`, `min_any_pt >= 14`, explicit XML fonts, `unicode_sub_sup_count == 0`, zero overlaps, every content slide has a figure).
   - **Completion criterion**: `audit_deck.py` exits `0` with `passed == True`, and visual preview PNGs show clean typography and crisp figures.

## CLI Scripts

- Generate 10-archetype showcase + 15-palette reference card: `python skill/scripts/generate_archetype_gallery.py`
- Compile a `DeckSpec JSON` to `.pptx` + previews + audit: `python skill/scripts/build_deck.py --spec deck.json --out out.pptx`
- Audit an existing `.pptx`: `python skill/scripts/audit_deck.py --pptx out.pptx`
