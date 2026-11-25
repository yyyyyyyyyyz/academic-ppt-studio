# 04 · Content-to-Layout Mapping, Notes Offloading & Word Sync

## Content-to-Layout & Archetype Routing Table
| Scientific Module | Recommended v5.0 Layout | Preferred Archetype(s) | Notes Offloading Rule |
| :--- | :--- | :--- | :--- |
| Cover | `cover` | `A01` / `A02` | Single concise subtitle only |
| Literature Overview / SAR | `lit_overview_dual_card` | `A05` (ChemDraw fixed-bond comparison) | Journal dossier metrics on right; citations to notes |
| Background / Rationale | `bg_top_summary_3box` | `A01` (reactor) or `A05` | Top 3 summary bullets + 3-box visual chain |
| State of Art / Pain Points | `pain_points_left_arrows` / `vs_center_wing` | `A03` / `A10` (`gap_quadrant`) | Concise pain strips left; synthesis note below figure |
| Overall Roadmap | `roadmap_layered_matrix` | `A10` (`roadmap_4stage`) | Layered objective/route/validation rows + closed-loop tower |
| Mechanism / 3D Binding | `mechanism_3col_flow` | `A04` (`CYLview3D`) / `A10` (`dual_cycle`) | 4-step Chevron bar + callout badges on 3D molecule |
| Quantitative / PK / Spectra | `data_dashboard_table` | `A06` (`OriginPlotEngine`) / `A07` | 3 KPI tiles + 600 DPI chart + zebra comparison table |
| Experimental Validation / Summary | `fig_left_3step_chain` | `A08` (multi-scale) / `A09` (`sunburst_pathway`) | 3 vertical step cards linked by down arrows |

## Word-to-PPTX Synchronization
- Never assign `shape.text = new_text` directly (that wipes out XML dual-font and color formatting).
- Replace text at `paragraph.runs[0].text` level while clearing surplus runs and spilling long overflow text into `slide.notes_slide`.
