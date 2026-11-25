export type ScenarioType = "defense" | "midterm" | "group_meeting" | "literature_review";
export type DesignStyle = "defense_modular" | "consulting_editorial" | "zero_fill_frameless";
export type CoverTemplateId =
  | "hero_band_bottom_bar"
  | "top_bottom_bands_framed"
  | "floating_rounded_hero_card"
  | "left_aligned_rounded_panel"
  | "chevron_v_cut_banner";

export const COVER_TEMPLATE_OPTIONS: Array<{ id: CoverTemplateId; name: string; desc: string }> = [
  { id: "hero_band_bottom_bar", name: "01 · 经典横幅底栏", desc: "主色满幅+底部三标" },
  { id: "top_bottom_bands_framed", name: "02 · 双带纯白夹心", desc: "上下色带+居中胶囊" },
  { id: "floating_rounded_hero_card", name: "03 · 悬浮圆角浮卡", desc: "大圆角卡片+底栏图标" },
  { id: "left_aligned_rounded_panel", name: "04 · 左对齐大圆角板", desc: "左侧排印+双栏脚标" },
  { id: "chevron_v_cut_banner", name: "05 · 顶部 V 型切角", desc: "V形几何顶栏+三胶囊" },
];
export type SlideType = "cover" | "toc" | "part_divider" | "content" | "closing";
export type LayoutId =
  | "cover"
  | "toc"
  | "part_divider"
  | "frameless_63_37"
  | "split_50_50"
  | "flow_30_46_20"
  | "dual_wing_28_38_28"
  | "full_roadmap"
  | "three_line_table"
  | "lit_overview_dual_card"
  | "mechanism_3col_flow"
  | "data_dashboard_table"
  | "bg_top_summary_3box"
  | "pain_points_left_arrows"
  | "fig_left_3step_chain"
  | "vs_center_wing"
  | "roadmap_layered_matrix"
  | "timeline_chevron_flow"
  | "quadrant_2x2_matrix"
  | "hub_spoke_radial"
  | "dual_compare_cards"
  | "tri_column_showcase"
  | "closing";

export type ArchetypeId =
  | "A01_cutaway_reactor_zoom"
  | "A02_dispersion_contrast"
  | "A03_editorial_vector"
  | "A04_cylview_3d"
  | "A05_chemdraw_halo"
  | "A06_origin_suite"
  | "A07_vesta_split"
  | "A08_multiscale_line"
  | "A09_sunburst_pathway"
  | "A10_vector_cycle";

export type EngineType =
  | "chemdraw_rdkit"
  | "cylview_3d"
  | "origin_plot"
  | "sci3d_art"
  | "vector_mech"
  | "uploaded_image";

export interface PaletteTokens {
  s1: string;
  s2: string;
  s3: string;
  s4: string;
  s5: string;
  s6: string;
  ink: string;
  muted: string;
  line: string;
  alert: string;
}

export interface PaletteInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  series: string[];
  tokens: PaletteTokens;
  material_prompt_terms: string;
}

export interface ArchetypeInfo {
  id: ArchetypeId;
  name: string;
  engines: EngineType[];
}

export interface AssetCandidate {
  candidate_id: string;
  png_path: string;
  raw_png_path?: string | null;
  ocr_text_count: number;
  vlm_aesthetic_score: number;
  passed: boolean;
  prompt_used?: string | null;
  critique_notes: string[];
}

export interface AssetQAResult {
  ocr_text_count: number;
  vlm_aesthetic_score: number;
  scientific_accuracy_ok: boolean;
  alpha_cleanliness_score: number;
  palette_harmony_score: number;
  passed: boolean;
  diagnostics: string[];
  rounds_run: number;
}

export interface FigureAsset {
  asset_id: string;
  engine: EngineType;
  label?: string | null;
  sublabel?: string | null;
  norm_box: number[];
  physical_width_in?: number | null;
  physical_height_in?: number | null;
  smiles?: string | null;
  fixed_bond_length_px: number;
  highlight_atoms: number[];
  highlight_bonds: number[];
  highlight_rings: boolean;
  highlight_halo_token: string;
  heteroatom_theme_sync: boolean;
  drug_burgundy: boolean;
  chem_style?: string;
  style_3d?: string;
  show_nonpolar_h?: boolean | null;
  rotation_deg: number[];
  outline_stroke: string;
  preset?: string | null;
  plot_data: Record<string, unknown>;
  data_verified: boolean;
  render_mode: string;
  scene_description?: string | null;
  prompt_compiled?: string | null;
  refinement_note?: string | null;
  alpha_matting: boolean;
  best_of_n: number;
  mech_mode?: string | null;
  mech_data: Record<string, unknown>;
  candidates: AssetCandidate[];
  selected_candidate_idx: number;
  qa_result: AssetQAResult;
  png_path?: string | null;
  svg_path?: string | null;
  cdxml_path?: string | null;
  sdf_path?: string | null;
  csv_path?: string | null;
}

export interface NativeOverlay {
  type:
    | "zoom_lens_frame"
    | "arrow"
    | "dashed_connector"
    | "reaction_arrow"
    | "badge_label"
    | "plus_sign"
    | "contrast_check"
    | "divider";
  source_circle_in?: number[] | null;
  target_circle_in?: number[] | null;
  from?: number[] | null;
  to?: number[] | null;
  pos_in?: number[] | null;
  style: string;
  label?: string | null;
  color_token: string;
  status?: "pass" | "fail" | null;
}

export interface FigureSpec {
  figure_id: string;
  required: boolean;
  archetype: ArchetypeId;
  visual_story_scale: string;
  palette_sync: boolean;
  box_in: { left: number; top: number; width: number; height: number };
  assets: FigureAsset[];
  native_overlays: NativeOverlay[];
  caption: string;
  overall_qa_score: number;
  qa_passed: boolean;
}

export interface KpiItem {
  value: string;
  label: string;
  color_token: string;
}

export interface InsightItem {
  index: string;
  heading: string;
  body: string;
  highlight?: string | null;
}

export interface SlideSpec {
  slide_no: number;
  slide_type: SlideType;
  layout_id: LayoutId;
  section_name: string;
  eyebrow: string;
  title: string;
  takeaway: string;
  figure_spec?: FigureSpec | null;
  kpis: KpiItem[];
  insights: InsightItem[];
  toc_items: string[];
  footer_left: string;
  speaker_notes: string;
  header_variant?: "nav_tabs" | "solid_bar" | "editorial";
  takeaway_badge?: string | null;
  bottom_banner?: Record<string, unknown> | null;
}

export interface DeckMeta {
  deck_id: string;
  deck_title: string;
  deck_subtitle: string;
  author: string;
  affiliation: string;
  advisor?: string;
  date_str?: string;
  scenario: ScenarioType;
  target_slide_count: number;
  palette_id: string;
  is_proposal: boolean;
  design_style?: DesignStyle;
  cover_template?: CoverTemplateId;
}

export interface LockedStandards {
  fonts?: { ea: string; latin: string };
  min_pt?: { body: number; chart_caption: number };
}

export interface DeckSpec {
  schema: string;
  meta: DeckMeta;
  locked_standards?: LockedStandards;
  slides: SlideSpec[];
}

export interface AuditViolation {
  slide_no: number;
  rule: string;
  severity: "error" | "warning";
  message: string;
}

export interface AuditReport {
  passed: boolean;
  pptx_path?: string | null;
  total_slides: number;
  content_slides: number;
  filled_body_boxes: number;
  min_body_pt_observed: number;
  min_any_pt_observed: number;
  unicode_sub_sup_count: number;
  missing_xml_font_runs: number;
  slides_missing_figure: number[];
  slides_below_qa_score: number[];
  full_slide_baked_images: number[];
  overlap_count: number;
  out_of_bounds_count: number;
  violations: AuditViolation[];
}

export interface AssetUrlBundle {
  png_url?: string | null;
  svg_url?: string | null;
  cdxml_url?: string | null;
  sdf_url?: string | null;
  csv_url?: string | null;
  candidates?: Array<{
    candidate_id: string;
    png_url?: string | null;
    ocr_text_count: number;
    vlm_aesthetic_score: number;
    passed: boolean;
  }>;
}

function normalizeHex6(raw: string, fallback = "00468B"): string {
  const clean = (raw || "").trim().replace(/^#/, "");
  return /^[0-9A-Fa-f]{6}$/.test(clean) ? clean.toUpperCase() : fallback;
}

function mixWithWhite(hexStr: string, factor: number): string {
  const h = normalizeHex6(hexStr);
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const nr = Math.round(r + (255 - r) * factor);
  const ng = Math.round(g + (255 - g) * factor);
  const nb = Math.round(b + (255 - b) * factor);
  return `#${nr.toString(16).padStart(2, "0").toUpperCase()}${ng.toString(16).padStart(2, "0").toUpperCase()}${nb.toString(16).padStart(2, "0").toUpperCase()}`;
}

export function buildCustomHexRamp(hex: string): string[] {
  const h = normalizeHex6(hex);
  const base = `#${h}`;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0;
  const s1 = luma > 0.72
    ? `#${Math.round(r * 0.75).toString(16).padStart(2, "0")}${Math.round(g * 0.75).toString(16).padStart(2, "0")}${Math.round(b * 0.75).toString(16).padStart(2, "0")}`.toUpperCase()
    : base;
  return [
    s1,
    mixWithWhite(s1, 0.18),
    mixWithWhite(s1, 0.38),
    mixWithWhite(s1, 0.60),
    mixWithWhite(s1, 0.80),
    mixWithWhite(s1, 0.92),
  ];
}

export function resolvePaletteAccent(paletteId: string, palettes: PaletteInfo[]): string {
  if (paletteId?.toLowerCase().startsWith("custom_")) {
    const part = paletteId.slice(7).split("_")[0] || "";
    if (/^[0-9A-Fa-f]{6}$/.test(part)) {
      return buildCustomHexRamp(part)[0];
    }
  }
  const found = palettes.find((p) => p.id === paletteId);
  return found?.tokens?.s1 || "#00468B";
}

export function resolvePaletteTint(paletteId: string, palettes: PaletteInfo[]): string {
  if (paletteId?.toLowerCase().startsWith("custom_")) {
    const part = paletteId.slice(7).split("_")[0] || "";
    if (/^[0-9A-Fa-f]{6}$/.test(part)) {
      return buildCustomHexRamp(part)[3];
    }
  }
  const found = palettes.find((p) => p.id === paletteId);
  return found?.tokens?.s4 || "#72A6D5";
}

export function formatPaletteLabel(paletteId: string, palettes: PaletteInfo[]): string {
  if (paletteId?.toLowerCase().startsWith("custom_")) {
    const part = paletteId.slice(7).split("_")[0] || "";
    if (/^[0-9A-Fa-f]{6}$/.test(part)) {
      return `#${part.toUpperCase()}`;
    }
  }
  const found = palettes.find((p) => p.id === paletteId);
  return found ? found.name : paletteId;
}
