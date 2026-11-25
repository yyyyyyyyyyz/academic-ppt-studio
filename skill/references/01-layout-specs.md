# 01 · Layout Specs, v5.0 Modular Defense Grammar & XML Typography

## Supported Visual Systems (`DesignStyle`)
1. **`defense_modular` (v5.0 Default for Planner & Web Studio)**: Synthesized from 22 top university thesis-defense & National Key R&D templates (Zhejiang Univ, Fudan, SYSU, SHU, CSU). Features top horizontal section navigation tabs (or solid dark section bar), colored takeaway pill + soft summary ribbon, dashed scientific figure containment frames, interlocking chevron process bars, zebra-striped deep-header tables, vertical progression chains, and executive bottom summary banners.
2. **`consulting_editorial`**: McKinsey / J.P. Morgan style clean Action Title + thin accent bar + KPI dashboard tiles + crisp data comparison.
3. **`zero_fill_frameless` (v4.0 Strict Minimalist)**: Pure `#FFFFFF` canvas with zero filled body textboxes, `63:37` asymmetric split, `>= 18 pt` body text, and `3 pt` left accent bars.

## 8 v5.0 Modular Layouts (`V5_LAYOUT_IDS`)
| LayoutId | Visual Architecture | Ideal Scientific Content |
| :--- | :--- | :--- |
| `lit_overview_dual_card` | Left dashed dual-molecule/figure frame + 2 bottom insight cards; right deep-blue journal dossier card + focus card | Literature overview, SAR evolution, lead-to-candidate optimization |
| `mechanism_3col_flow` | 4-step Chevron pipeline; left 3 pharmacophore cards; center dashed 3D figure + callout leader badges; right 3-node down-arrow chain; bottom 3-pill value bar | 3D conformers, catalytic cycles, binding mechanisms |
| `data_dashboard_table` | Left KPI tile strip + 600 DPI Origin chart; right deep-header zebra comparison table + 2 badge strategy cards | PK/efficacy comparisons, electrochemistry, DFT/ML metrics |
| `bg_top_summary_3box` | Top soft-blue summary bullet card + 3 dashed boxes linked by thick right arrows + solid deep-blue bottom banner | Research background, clinical/industrial demand |
| `pain_points_left_arrows` | Left 3–4 pain-point strips with circular right arrows pointing to right dashed figure panel + chip tags + crimson synthesis | Bottlenecks, state-of-the-art gaps |
| `fig_left_3step_chain` | Left bordered figure panel with pill header; right 3 vertical `[dark square tag \| content]` blocks linked by down arrows | Multi-scale validation, characterization proofs |
| `vs_center_wing` | Left 2–3 cards + center dashed figure hub + right symmetrical cards + bottom pale-rose quote bar | Domestic vs. international comparison, control vs. innovation |
| `roadmap_layered_matrix` | Left 3 layered row tags + embedded technical roadmap; right vertical closed-loop implementation tower | Overall roadmap, National Key R&D task breakdown |

## Native XML Typography Hard Rules
- Every run binds `<a:latin typeface="Arial"/>`, `<a:ea typeface="微软雅黑"/>`, `<a:cs typeface="Arial"/>` (with `Noto Sans CJK SC` fallback on Linux containers).
- Subscripts and superscripts use plain ASCII + XML `rPr.set("baseline", "-25000")` or `"30000"`, eliminating raw Unicode `₀–₉` / `⁰–⁹` tofu (`□`) issues.
- Zero full-slide baked images (`> 85%` slide area) and every content slide carries a verified Layer 1 figure (`QA >= 8.5`).

## 5 Theme-Adaptive Cover & Closing Templates (`CoverTemplateId`)
| Template ID | Cover Visual Geometry (Palette-Adaptive) | Matched Closing Geometry |
| :--- | :--- | :--- |
| `hero_band_bottom_bar` | Full-bleed dark-tinted hero top (`~68%`) + centered emblem & hairline divider + white 3-column circular-badge metadata bar | Centered dark hero thank-you card + white bottom speaker/affiliation pill bar |
| `top_bottom_bands_framed` | Deep theme top & bottom bands framing a crisp white central title band + faint watermark seal + pill badges | Framed white thank-you card between deep theme bands + Q&A contact pills |
| `floating_rounded_hero_card` | Crisp white outer frame + large rounded dark hero card + top-left pill scenario tag + clean bottom 2-col metadata | Rounded floating thank-you hero card + bottom institutional signature strip |
| `left_aligned_rounded_panel` | Asymmetric left-aligned typographic hero rounded card + right watermark seal + clean bottom dual-column affiliation row | Left-aligned rounded closing statement + right emblem + bottom lab metadata |
| `chevron_v_cut_banner` | Geometric deep-theme V-cut top banner + pure white horizontal pill metadata + centered bottom white institution footer | Inverted chevron accent banner + centered thank-you typography + Q&A badges |

## Reference TOC & Part Divider (`演示文稿2.pptx`)
- **TOC (`toc`)**: Pure white canvas + rounded-top `CONTENTS` ribbon tab (`s1`) + dark pill subtitle + vertical dashed progression spine connecting solid circular index badges `01`–`06`, bold Chinese titles, and bilingual subtitle tags.
- **Part Divider (`part_divider`)**: Symmetrical horizontal split bar (`s1` deep pill `PART 0X` + large bilingual heading + 3 rounded sub-topic chips).

## Zero-LLM Structured Word (`.docx`) Mapping Rules
1. **Paragraphs & Headings**: `Heading 1/2/3` or numbered (`1. `, `一、`, `## `) headings split slides cleanly while preserving full prose in `speaker_notes`.
2. **Real Tables (`w:tbl`)**: Automatically parsed into `TableData` and routed to `data_dashboard_table`.
3. **Embedded Word Images (`a:blip`)**: Extracted into `word_images/word_fig_XX.png` and mounted directly as Layer-1 `uploaded_image` assets on their originating slide.
4. **Per-Section `SMILES:` & Metrics**: Bound slide-by-slide without cross-slide repetition; numeric KPIs (`IC50`, `t1/2`, `F`, `TGI`, yields) populate real KPI cards with zero fabricated fallback numbers.
