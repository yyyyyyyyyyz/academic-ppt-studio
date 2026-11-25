---
name: academic-ppt-design
description: >
  Design and compile 100% natively editable, zero-fill frameless or modular academic PowerPoint decks
  and publication-grade scientific figures (4-style ChemDraw/RDKit, CYLview3D, OriginPro 600 DPI,
  C4D/Editorial 3D with true Alpha matting, and vector mechanisms). Includes 5 theme-adaptive cover
  templates, reference PPTX TOC/Part-divider architecture, 5 matched closing templates, and a
  zero-LLM deterministic Word (.docx) to PPT pipeline. Trigger when building or revising thesis
  defense, midterm, group-meeting, or literature-review slides, generating scientific figures
  (A01–A10), or syncing Word manuscripts into editable .pptx decks.
---

# Academic PPT Design (`academic-ppt-design` v5.0)

Build 100% natively editable `.pptx` presentations paired with **one dedicated publication-grade scientific figure (or original manuscript figure) per content slide**, supporting both LLM-assisted deep planning and **zero-LLM deterministic Word-to-PPT compilation**.

## Core Architecture (3-Layer Physical Separation)

Every content slide strictly separates visual layers so every molecule, arrow, line, table, and word remains editable in PowerPoint:
- **Layer 1 (Transparent Visual Assets & Extracted Word Figures)**: 4-style fixed-bond-length 2D molecules (`ChemDrawEngine`: `nature_burgundy`, `ring_shaded`, `cylview_3d`, `minimal_mono`), deterministic 3D ball-and-stick conformers (`CYLview3DEngine`), 1:1 physical 600 DPI quantitative charts (`OriginPlotEngine`), strictly zero-text true-alpha studio 3D/editorial renders (`Sci3DArtEngine`), and auto-extracted `.docx` embedded figures (`uploaded_image`).
- **Layer 2 (Native Vector Skeleton)**: Editable PowerPoint connectors, exact external-bitangent zoom-lens frames, reaction arrows, `3 pt` left insight accent bars, `0.75 pt` hairline dividers, and user-reference cover/TOC/part-divider/closing geometry (`v5_covers.py`).
- **Layer 3 (Native Editable Text & Tables)**: Dual-XML-font textboxes (`Arial` + `微软雅黑` on Windows, `Noto Sans CJK SC` on Linux), native `baseline` sub/superscripts, and zero-fill / zebra-striped academic tables parsed directly from Word `.docx` tables or structured metrics.

## Structural & Chemical Visual Systems

1. **5 Theme-Adaptive Cover & Closing Templates** (from reference screenshots, 100% recolored by `ScientificPalette`):
   - `hero_band_bottom_bar` (Classic Full-Bleed Top Hero + White 3-Col Bottom Bar)
   - `top_bottom_bands_framed` (Symmetrical Dark Top/Bottom Bands + Framed White Center)
   - `floating_rounded_hero_card` (White Border + Rounded Dark Floating Card + Bottom Metadata Strip)
   - `left_aligned_rounded_panel` (Rounded Left-Aligned Typographic Hero + Dual-Col Affiliation Footer)
   - `chevron_v_cut_banner` (Chevron V-Cut Geometric Banner + White Pill Metadata + Centered Footer Seal)
   - Every cover template has a dedicated **matched Closing slide** (`v5_covers.py`).
2. **Reference TOC & Part Divider** (from `演示文稿2.pptx`):
   - **TOC**: White canvas, rounded-top `"CONTENTS"` tab header + dark pill sub-badge, vertical dashed spine with solid circular badges `01`–`06` and English subtitle sub-rows.
   - **Part Divider**: Horizontal dual-tone split strip (`PART 0X` dark pill + large Chinese/English section title + topic chips).
3. **4 Classical Chemical Drawing Styles** (`chemdraw_engine.py` & `cylview3d_engine.py`):
   - `nature_burgundy` (Deep crimson ACS/Nature archival hand-drawn accent)
   - `ring_shaded` (Translucent pharmacophore ring fill highlights)
   - `cylview_3d` (ETKDGv3 + MMFF94 Phong Z-buffer outline 3D conformer)
   - `minimal_mono` (Monochrome ACS 1996 + subtle SMARTS halo)

## Workflow (With or Without External LLM)

1. **Structured Document Ingestion (`doc_parser.py`)**:
   - Use `parse_document_file(path, image_output_dir=...)` for `.docx`/`.pdf`/`.md`/`.txt`.
   - For `.docx`, preserve section headings, clean paragraphs, real Word tables (`ParsedTable`), embedded Word pictures (`word_fig_XX.png`), per-section `SMILES`, and quantitative KPIs (`IC50`, `t1/2`, `F%`, `TGI`, selectivity, yields) with **zero fabricated defaults**.
2. **Confirm Deck Scope, Palette & Cover Template**:
   - Accept any slide count ($N \in [3, 40]$), `DesignStyle` (`defense_modular`, `consulting_editorial`, `zero_fill_frameless`), `palette_id` from the 15 palettes ([`references/03-color-palettes.md`](references/03-color-palettes.md)), and `cover_template`.
3. **Narrative Mapping (`planner_agent.py` + [`references/01-layout-specs.md`](references/01-layout-specs.md))**:
   - If an external LLM is enabled (`hosted` redeem code or BYOK key), synthesize concise JSON slide outlines + speaker notes.
   - In **Zero-LLM Local Mode**, deterministically extract takeaways, real numeric KPIs, real sentence insights, Word tables (`data_dashboard_table`), embedded Word images, and per-section RDKit SMILES without inventing placeholder metrics or boilerplate phrases.
4. **Render, Compile & Audit Native `.pptx`**:
   - Compile `DeckSpec` via [`scripts/build_deck.py`](scripts/build_deck.py) and verify via [`scripts/audit_deck.py`](scripts/audit_deck.py) (`passed == True`, `filled_body_boxes == 0`, zero overlaps).

## CLI Scripts

- Build the 4-slide Nature Archival Crimson specimen deck: `python skill/scripts/build_nature_editorial_showcase.py`
- Generate 10-archetype showcase + 15-palette reference card: `python skill/scripts/generate_archetype_gallery.py`
- Compile a `DeckSpec JSON` to `.pptx` + previews + audit: `python skill/scripts/build_deck.py --spec deck.json --out out.pptx`
- Audit an existing `.pptx`: `python skill/scripts/audit_deck.py --pptx out.pptx`
