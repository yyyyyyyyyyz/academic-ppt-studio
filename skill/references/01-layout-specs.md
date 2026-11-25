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
- Every run binds `<a:latin typeface="Arial"/>`, `<a:ea typeface="微软雅黑"/>`, `<a:cs typeface="Arial"/>`.
- Subscripts and superscripts use plain ASCII + XML `rPr.set("baseline", "-25000")` or `"30000"`, eliminating raw Unicode `₀–₉` / `⁰–⁹` tofu (`□`) issues.
- Zero full-slide baked images (`> 85%` slide area) and every content slide carries a verified Layer 1 figure (`QA >= 8.5`).
