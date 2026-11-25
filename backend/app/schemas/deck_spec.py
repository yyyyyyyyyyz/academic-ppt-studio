"""DeckSpec JSON Schema (v4.0) and API/Audit Pydantic models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    defense = "defense"
    midterm = "midterm"
    group_meeting = "group_meeting"
    literature_review = "literature_review"


class SlideType(str, Enum):
    cover = "cover"
    toc = "toc"
    part_divider = "part_divider"
    content = "content"
    closing = "closing"


class DesignStyle(str, Enum):
    defense_modular = "defense_modular"
    consulting_editorial = "consulting_editorial"
    zero_fill_frameless = "zero_fill_frameless"


class CoverTemplateId(str, Enum):
    hero_band_bottom_bar = "hero_band_bottom_bar"
    top_bottom_bands_framed = "top_bottom_bands_framed"
    floating_rounded_hero_card = "floating_rounded_hero_card"
    left_aligned_rounded_panel = "left_aligned_rounded_panel"
    chevron_v_cut_banner = "chevron_v_cut_banner"


class LayoutId(str, Enum):
    cover = "cover"
    toc = "toc"
    part_divider = "part_divider"
    frameless_63_37 = "frameless_63_37"
    split_50_50 = "split_50_50"
    flow_30_46_20 = "flow_30_46_20"
    dual_wing_28_38_28 = "dual_wing_28_38_28"
    full_roadmap = "full_roadmap"
    three_line_table = "three_line_table"
    lit_overview_dual_card = "lit_overview_dual_card"
    mechanism_3col_flow = "mechanism_3col_flow"
    data_dashboard_table = "data_dashboard_table"
    bg_top_summary_3box = "bg_top_summary_3box"
    pain_points_left_arrows = "pain_points_left_arrows"
    fig_left_3step_chain = "fig_left_3step_chain"
    vs_center_wing = "vs_center_wing"
    roadmap_layered_matrix = "roadmap_layered_matrix"
    timeline_chevron_flow = "timeline_chevron_flow"
    quadrant_2x2_matrix = "quadrant_2x2_matrix"
    hub_spoke_radial = "hub_spoke_radial"
    dual_compare_cards = "dual_compare_cards"
    tri_column_showcase = "tri_column_showcase"
    closing = "closing"


V5_LAYOUT_IDS = frozenset({
    LayoutId.lit_overview_dual_card,
    LayoutId.mechanism_3col_flow,
    LayoutId.data_dashboard_table,
    LayoutId.bg_top_summary_3box,
    LayoutId.pain_points_left_arrows,
    LayoutId.fig_left_3step_chain,
    LayoutId.vs_center_wing,
    LayoutId.roadmap_layered_matrix,
    LayoutId.timeline_chevron_flow,
    LayoutId.quadrant_2x2_matrix,
    LayoutId.hub_spoke_radial,
    LayoutId.dual_compare_cards,
    LayoutId.tri_column_showcase,
})


class ArchetypeId(str, Enum):
    A01 = "A01_cutaway_reactor_zoom"
    A02 = "A02_dispersion_contrast"
    A03 = "A03_editorial_vector"
    A04 = "A04_cylview_3d"
    A05 = "A05_chemdraw_halo"
    A06 = "A06_origin_suite"
    A07 = "A07_vesta_split"
    A08 = "A08_multiscale_line"
    A09 = "A09_sunburst_pathway"
    A10 = "A10_vector_cycle"


class EngineType(str, Enum):
    chemdraw_rdkit = "chemdraw_rdkit"
    cylview_3d = "cylview_3d"
    origin_plot = "origin_plot"
    sci3d_art = "sci3d_art"
    vector_mech = "vector_mech"
    uploaded_image = "uploaded_image"


class FigureQualityGate(BaseModel):
    rdkit_fixed_bond_length_px: int = 28
    origin_dpi: int = 600
    origin_physical_1to1: bool = True
    sci3d_true_alpha_matting: bool = True
    sci3d_ocr_zero_text: bool = True
    vlm_aesthetic_min_score: float = 8.5
    best_of_n_candidates: int = 2


class LockedStandards(BaseModel):
    canvas_in: List[float] = Field(default_factory=lambda: [13.333, 7.5])
    background: str = "#FFFFFF"
    zero_fill_frameless: bool = True
    every_content_slide_requires_figure: bool = True
    fonts: Dict[str, str] = Field(default_factory=lambda: {"ea": "微软雅黑", "latin": "Arial"})
    min_pt: Dict[str, float] = Field(default_factory=lambda: {"body": 18.0, "chart_caption": 14.0})
    body_line_spacing: float = 1.5
    native_xml_sub_superscript: bool = True
    zero_simulated_curves_for_proposal: bool = True
    figure_quality_gate: FigureQualityGate = Field(default_factory=FigureQualityGate)


class DeckMeta(BaseModel):
    deck_id: str = "deck_default"
    deck_title: str = "Academic Research Presentation"
    deck_subtitle: str = "Scientific Mechanisms, Characterization & Quantitative Insights"
    author: str = "Researcher"
    affiliation: str = "Department of Medicinal Chemistry"
    advisor: str = ""
    date_str: str = ""
    scenario: ScenarioType = ScenarioType.defense
    target_slide_count: int = Field(default=10, ge=3, le=45)
    palette_id: str = "lancet"
    is_proposal: bool = False
    design_style: DesignStyle = DesignStyle.zero_fill_frameless
    cover_template: Optional[CoverTemplateId] = None


class FigureBoxIn(BaseModel):
    left: float = 0.46
    top: float = 1.68
    width: float = 7.75
    height: float = 4.42


class AssetCandidate(BaseModel):
    candidate_id: str
    png_path: str
    raw_png_path: Optional[str] = None
    ocr_text_count: int = 0
    vlm_aesthetic_score: float = 9.0
    passed: bool = True
    prompt_used: Optional[str] = None
    critique_notes: List[str] = Field(default_factory=list)


class AssetQAResult(BaseModel):
    ocr_text_count: int = 0
    vlm_aesthetic_score: float = 9.0
    scientific_accuracy_ok: bool = True
    alpha_cleanliness_score: float = 9.2
    palette_harmony_score: float = 9.1
    passed: bool = True
    diagnostics: List[str] = Field(default_factory=list)
    rounds_run: int = 1


class FigureAsset(BaseModel):
    asset_id: str
    engine: EngineType
    label: Optional[str] = None
    sublabel: Optional[str] = None

    # Placement inside figure box (normalized 0..1 or explicit box_in)
    norm_box: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    physical_width_in: Optional[float] = None
    physical_height_in: Optional[float] = None

    # ChemDraw / CYLview3D fields
    smiles: Optional[str] = None
    fixed_bond_length_px: int = 28
    highlight_atoms: List[int] = Field(default_factory=list)
    highlight_bonds: List[int] = Field(default_factory=list)
    highlight_rings: bool = False
    highlight_halo_token: str = "s6"
    highlight_groups: List[Dict[str, Any]] = Field(default_factory=list)
    show_nonpolar_h: Optional[bool] = None
    heteroatom_theme_sync: bool = True
    drug_burgundy: bool = False
    chem_style: str = "acs1996"
    style_3d: str = "ball_stick"
    rotation_deg: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    outline_stroke: str = "#4A4A4A"

    # OriginPlotEngine fields
    preset: Optional[str] = None
    plot_data: Dict[str, Any] = Field(default_factory=dict)
    data_verified: bool = True

    # Sci3DArtEngine fields
    render_mode: str = "c4d_octane_cutaway"
    scene_description: Optional[str] = None
    prompt_compiled: Optional[str] = None
    refinement_note: Optional[str] = None
    alpha_matting: bool = True
    best_of_n: int = 2

    # VectorMechanismEngine fields
    mech_mode: Optional[str] = None
    mech_data: Dict[str, Any] = Field(default_factory=dict)

    # Output artifacts & QA
    candidates: List[AssetCandidate] = Field(default_factory=list)
    selected_candidate_idx: int = 0
    qa_result: AssetQAResult = Field(default_factory=AssetQAResult)
    png_path: Optional[str] = None
    svg_path: Optional[str] = None
    cdxml_path: Optional[str] = None
    sdf_path: Optional[str] = None
    csv_path: Optional[str] = None


class NativeOverlay(BaseModel):
    type: Literal[
        "zoom_lens_frame",
        "arrow",
        "dashed_connector",
        "reaction_arrow",
        "badge_label",
        "plus_sign",
        "contrast_check",
        "divider",
        "pocket_subsite",
    ]
    source_circle_in: Optional[List[float]] = None  # [cx, cy, r]
    target_circle_in: Optional[List[float]] = None  # [cx, cy, r]
    from_in: Optional[List[float]] = Field(default=None, alias="from")
    to_in: Optional[List[float]] = Field(default=None, alias="to")
    pos_in: Optional[List[float]] = None
    style: str = "solid_curved"
    label: Optional[str] = None
    sublabel: Optional[str] = None
    color_token: str = "s1"
    status: Optional[Literal["pass", "fail"]] = None

    model_config = {"populate_by_name": True}


class FigureSpec(BaseModel):
    figure_id: str
    required: bool = True
    archetype: ArchetypeId = ArchetypeId.A01
    visual_story_scale: str = "macro_to_micro_zoom"
    palette_sync: bool = True
    box_in: FigureBoxIn = Field(default_factory=FigureBoxIn)
    assets: List[FigureAsset] = Field(default_factory=list)
    native_overlays: List[NativeOverlay] = Field(default_factory=list)
    caption: str = "Fig. 1  Publication-grade scientific schematic generated with unified palette."
    overall_qa_score: float = 9.0
    qa_passed: bool = True


class KpiItem(BaseModel):
    value: str
    label: str
    color_token: str = "s1"


class InsightItem(BaseModel):
    index: str = "01"
    heading: str
    body: str
    highlight: Optional[str] = None


class TableData(BaseModel):
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = None


class SlideSpec(BaseModel):
    slide_no: int = Field(ge=1)
    slide_type: SlideType = SlideType.content
    layout_id: LayoutId = LayoutId.frameless_63_37
    section_name: str = "研究背景与科学问题"
    eyebrow: str = "SECTION 01 · SCIENTIFIC INSIGHT"
    title: str
    takeaway: str = ""
    figure_spec: Optional[FigureSpec] = None
    kpis: List[KpiItem] = Field(default_factory=list)
    insights: List[InsightItem] = Field(default_factory=list)
    table_data: Optional[TableData] = None
    toc_items: List[str] = Field(default_factory=list)
    footer_left: str = "Academic PPT Design Studio · 2026"
    speaker_notes: str = ""

    # v5.0 Defense Modular & Consulting Layout Fields (optional, backward-compatible)
    nav_sections: List[str] = Field(default_factory=list)
    active_nav_idx: int = 0
    takeaway_badge: Optional[str] = None
    takeaway_highlight: Optional[str] = None
    chevron_steps: List[str] = Field(default_factory=list)
    left_cards: List[Dict[str, str]] = Field(default_factory=list)
    right_chain: List[Dict[str, str]] = Field(default_factory=list)
    profile_card: Optional[Dict[str, Any]] = None
    callout_badges: List[Dict[str, Any]] = Field(default_factory=list)
    strategy_cards: List[Dict[str, str]] = Field(default_factory=list)
    bottom_banner: Optional[Dict[str, Any]] = None
    pain_points: List[str] = Field(default_factory=list)
    figure_chips: List[str] = Field(default_factory=list)
    figure_bottom_note: Optional[str] = None
    header_variant: Literal["nav_tabs", "solid_bar", "editorial"] = "nav_tabs"


class DeckSpec(BaseModel):
    schema_version: str = Field(default="academic-ppt-design/deck-spec/v4.0", alias="schema")
    meta: DeckMeta = Field(default_factory=DeckMeta)
    locked_standards: LockedStandards = Field(default_factory=LockedStandards)
    slides: List[SlideSpec] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---- FastAPI Request / Response Models ----

class PlanRequest(BaseModel):
    source_text: str = ""
    deck_title: Optional[str] = None
    author: str = "Researcher"
    affiliation: str = "School of Pharmaceutical Sciences"
    advisor: str = ""
    date_str: str = ""
    scenario: ScenarioType = ScenarioType.defense
    target_slide_count: int = Field(default=10, ge=3, le=40)
    palette_id: str = "lancet"
    is_proposal: bool = False
    design_style: DesignStyle = DesignStyle.defense_modular
    cover_template: CoverTemplateId = CoverTemplateId.hero_band_bottom_bar
    include_dividers: Optional[bool] = None


class GenerateFigureRequest(BaseModel):
    deck_id: Optional[str] = None
    slide_no: int = 1
    palette_id: str = "lancet"
    scenario: ScenarioType = ScenarioType.defense
    is_proposal: bool = False
    figure_spec: FigureSpec
    best_of_n: int = Field(default=2, ge=1, le=4)


class SelectOrRefineFigureRequest(BaseModel):
    deck_id: Optional[str] = None
    slide_no: int = 1
    palette_id: str = "lancet"
    figure_spec: FigureSpec
    asset_id: Optional[str] = None
    selected_candidate_idx: Optional[int] = None
    refinement_instruction: Optional[str] = None
    archetype_override: Optional[ArchetypeId] = None
    smiles_override: Optional[str] = None
    fixed_bond_length_px: Optional[int] = None
    highlight_atoms: Optional[List[int]] = None
    origin_preset: Optional[str] = None
    render_mode: Optional[str] = None
    mech_mode_override: Optional[str] = None
    chem_style_override: Optional[str] = None
    style_3d_override: Optional[str] = None
    rotation_deg_override: Optional[List[float]] = None
    show_nonpolar_h_override: Optional[bool] = None


class PaletteApplyRequest(BaseModel):
    deck_spec: DeckSpec
    palette_id: str
    rerender_figures: bool = True


class BuildPptxRequest(BaseModel):
    deck_spec: DeckSpec
    run_qa_loop: bool = True


class AuditViolation(BaseModel):
    slide_no: int
    rule: str
    severity: Literal["error", "warning"] = "error"
    message: str


class AuditReport(BaseModel):
    passed: bool
    pptx_path: Optional[str] = None
    total_slides: int = 0
    content_slides: int = 0
    filled_body_boxes: int = 0
    min_body_pt_observed: float = 18.0
    min_any_pt_observed: float = 14.0
    unicode_sub_sup_count: int = 0
    missing_xml_font_runs: int = 0
    slides_missing_figure: List[int] = Field(default_factory=list)
    slides_below_qa_score: List[int] = Field(default_factory=list)
    full_slide_baked_images: List[int] = Field(default_factory=list)
    overlap_count: int = 0
    out_of_bounds_count: int = 0
    violations: List[AuditViolation] = Field(default_factory=list)
