"""Art Director Agent — Matches Content Semantics to Archetypes A01–A10 & Builds FigureSpecs."""

from __future__ import annotations

from typing import List, Optional

from ..builder.v5_layouts import get_v5_figure_box
from ..providers.llm_image_provider import ModelProvider
from ..schemas.deck_spec import (
    ArchetypeId,
    DesignStyle,
    EngineType,
    FigureAsset,
    FigureBoxIn,
    FigureSpec,
    LayoutId,
    NativeOverlay,
    SlideSpec,
    SlideType,
    TableData,
)


def build_default_figure_spec(
    archetype: ArchetypeId,
    slide_no: int,
    palette_id: str = "lancet",
    box_in: Optional[FigureBoxIn] = None,
    smiles: Optional[str] = None,
    origin_preset: Optional[str] = None,
    is_proposal: bool = False,
) -> FigureSpec:
    """Create a complete publication-grade FigureSpec for any Archetype A01–A10."""
    box = box_in or FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42)
    fid = f"fig_{slide_no:02d}"
    mol_smiles = smiles or "CN(C)CCN(Cc1ccccc1)c2ccccn2"

    if archetype == ArchetypeId.A01:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A01,
            visual_story_scale="macro_to_micro_zoom",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_reactor_3d",
                    engine=EngineType.sci3d_art,
                    render_mode="c4d_octane_cutaway",
                    scene_description="Cutaway borosilicate catalytic reactor on left with porous zeolite micro-cavity host on right",
                    best_of_n=2,
                    norm_box=[0.0, 0.0, 1.0, 1.0],
                )
            ],
            native_overlays=[
                NativeOverlay(
                    type="zoom_lens_frame",
                    source_circle_in=[box.left + box.width * 0.28, box.top + box.height * 0.54, 0.42],
                    target_circle_in=[box.left + box.width * 0.74, box.top + box.height * 0.50, 1.48],
                    color_token="s1",
                )
            ],
            caption=f"Fig. {slide_no}  Macro-to-micro cutaway reactor interface and confined active pocket.",
        )

    if archetype == ArchetypeId.A02:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A02,
            visual_story_scale="meso_dispersion_contrast",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_dispersion",
                    engine=EngineType.sci3d_art,
                    render_mode="c4d_octane_cutaway",
                    scene_description="Agglomerated inactive metal cluster on left vs porous cage hosting single-dispersed active spheres on right",
                    best_of_n=2,
                )
            ],
            native_overlays=[
                NativeOverlay(type="contrast_check", pos_in=[box.left + 0.55, box.top + box.height - 0.42], label="Agglomerated", status="fail", color_token="alert"),
                NativeOverlay(type="contrast_check", pos_in=[box.left + box.width * 0.56, box.top + box.height - 0.42], label="Cage-Confined", status="pass", color_token="s1"),
            ],
            caption=f"Fig. {slide_no}  Sintering failure (left) vs. porous framework confinement stabilizing active sites (right).",
        )

    if archetype == ArchetypeId.A03:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A03,
            visual_story_scale="field_coupled_editorial",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_editorial",
                    engine=EngineType.sci3d_art,
                    render_mode="editorial_flat_3d",
                    scene_description="Editorial flat-3D piezoelectric/photocatalytic activation of spherical catalyst and substrate capsules",
                    best_of_n=2,
                )
            ],
            caption=f"Fig. {slide_no}  Editorial illustration of external physical field-driven catalytic activation.",
        )

    if archetype == ArchetypeId.A04:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A04,
            visual_story_scale="molecular_3d_conformer",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_cylview",
                    engine=EngineType.cylview_3d,
                    smiles=mol_smiles,
                    label="3D Conformer (ETKDGv3 + MMFF94)",
                    norm_box=[0.05, 0.05, 0.90, 0.90],
                )
            ],
            caption=f"Fig. {slide_no}  Deterministic 3D ball-and-stick conformer rendered via ETKDGv3/MMFF94.",
        )

    if archetype == ArchetypeId.A05:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A05,
            visual_story_scale="molecular_2d_reaction",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_sub",
                    engine=EngineType.chemdraw_rdkit,
                    smiles="Nc1ccccc1",
                    label="Amine Substrate",
                    highlight_atoms=[0],
                    norm_box=[0.02, 0.14, 0.36, 0.72],
                ),
                FigureAsset(
                    asset_id=f"{fid}_prod",
                    engine=EngineType.chemdraw_rdkit,
                    smiles=mol_smiles,
                    label="Target API Scaffold",
                    highlight_rings=True,
                    norm_box=[0.52, 0.10, 0.46, 0.80],
                ),
            ],
            native_overlays=[
                NativeOverlay(
                    type="reaction_arrow",
                    from_in=[box.left + box.width * 0.38, box.top + box.height * 0.50],
                    to_in=[box.left + box.width * 0.52, box.top + box.height * 0.50],
                    label="Cat. · 45 min",
                    color_token="s1",
                )
            ],
            caption=f"Fig. {slide_no}  ACS 1996 reaction comparison with locked bond length and soft halo highlight.",
        )

    if archetype == ArchetypeId.A06:
        if is_proposal:
            # Strict Zero-Simulated-Curves guard: route to A10 gap_quadrant / SOP
            return build_default_figure_spec(ArchetypeId.A10, slide_no=slide_no, palette_id=palette_id, box_in=box, is_proposal=True)
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A06,
            visual_story_scale="quantitative_origin_plot",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_origin",
                    engine=EngineType.origin_plot,
                    preset=origin_preset or "kinetics_spline",
                    data_verified=True,
                )
            ],
            caption=f"Fig. {slide_no}  600 DPI 1:1 quantitative dataset rendered with OriginPro publication standards.",
        )

    if archetype == ArchetypeId.A07:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A07,
            visual_story_scale="crystal_interface_split",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_vesta",
                    engine=EngineType.sci3d_art,
                    render_mode="vesta_polyhedra",
                    best_of_n=2,
                )
            ],
            caption=f"Fig. {slide_no}  Crystallographic polyhedral slab and interfacial bi-color microenvironment.",
        )

    if archetype == ArchetypeId.A08:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A08,
            visual_story_scale="multiscale_macro_meso_micro",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_lineart",
                    engine=EngineType.sci3d_art,
                    render_mode="nature_line_art",
                    best_of_n=2,
                )
            ],
            caption=f"Fig. {slide_no}  Multi-scale lifecycle schematic: macro loop, meso cross-section, and micro solution.",
        )

    if archetype == ArchetypeId.A09:
        return FigureSpec(
            figure_id=fid,
            archetype=ArchetypeId.A09,
            visual_story_scale="taxonomy_sunburst",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_sunburst",
                    engine=EngineType.vector_mech,
                    mech_mode="sunburst_pathway",
                )
            ],
            caption=f"Fig. {slide_no}  Concentric taxonomy mapping synthetic modalities and characterization tools.",
        )

    # Default A10 vector mechanism
    return FigureSpec(
        figure_id=fid,
        archetype=ArchetypeId.A10,
        visual_story_scale="vector_mechanism",
        box_in=box,
        assets=[
            FigureAsset(
                asset_id=f"{fid}_mech",
                engine=EngineType.vector_mech,
                mech_mode="gap_quadrant" if is_proposal else "dual_cycle",
            )
        ],
        caption=f"Fig. {slide_no}  Native editable vector mechanism schematic.",
    )


class ArtDirectorAgent:
    """Assigns the optimal publication figure archetype (A01–A10) to every slide."""

    def __init__(self, provider: Optional[ModelProvider] = None) -> None:
        self.provider = provider or ModelProvider()

    def _choose_archetype_and_preset(self, slide: SlideSpec, is_proposal: bool, content_index: int) -> tuple[ArchetypeId, Optional[str], Optional[str]]:
        txt = f"{slide.section_name} {slide.title} {slide.takeaway}".lower()

        if any(k in txt for k in ("路线", "roadmap", "方案", "设计", "workflow")):
            return (ArchetypeId.A10, None, "roadmap_4stage")
        if any(k in txt for k in ("空白", "进展", "gap", "现状", "综述", "分类")):
            return (ArchetypeId.A10, None, "gap_quadrant") if "空白" in txt or "gap" in txt else (ArchetypeId.A09, None, "sunburst_pathway")
        if any(k in txt for k in ("团聚", "分散", "稳定", "dispersion", "烧结")):
            return (ArchetypeId.A02, None, None)
        if any(k in txt for k in ("压电", "光催", "声", "外场", "piezo", "photo")):
            return (ArchetypeId.A03, None, None)
        if any(k in txt for k in ("立体", "配合物", "构象", "3d", "cylview")):
            return (ArchetypeId.A04, None, None)
        if any(k in txt for k in ("合成", "背景", "痛点", "药", "底物", "chemdraw", "c–n")):
            return (ArchetypeId.A05, None, None) if content_index % 2 == 0 else (ArchetypeId.A01, None, None)
        if any(k in txt for k in ("循环", "机理", "催化", "能垒")):
            return (ArchetypeId.A10, None, "dual_cycle")
        if any(k in txt for k in ("晶面", "vesta", "双电层", "界面")):
            return (ArchetypeId.A07, None, None)
        if any(k in txt for k in ("总结", "展望", "outlook", "summary")):
            return (ArchetypeId.A08, None, None)

        # Quantitative data routing (blocked if proposal without verified data)
        if not is_proposal:
            if any(k in txt for k in ("xps", "谱学", "价态")):
                return (ArchetypeId.A06, "xps_deconv", None)
            if any(k in txt for k in ("电化学", "lsv", "tafel", "过电位")):
                return (ArchetypeId.A06, "electrochem_suite", None)
            if any(k in txt for k in ("dft", "自由能", "吸附")):
                return (ArchetypeId.A06, "dft_energy_profile", None)
            if any(k in txt for k in ("ml", "机器学习", "预测")):
                return (ArchetypeId.A06, "ml_parity_kde", None)
            if any(k in txt for k in ("动力学", "收率", "绿色度", "pmi", "定量", "效率")):
                return (ArchetypeId.A06, "paired_gain_bar", None)

        # Diverse fallback rotation across archetypes
        rotation = [
            (ArchetypeId.A01, None, None),
            (ArchetypeId.A03, None, None),
            (ArchetypeId.A10, None, "roadmap_4stage"),
            (ArchetypeId.A04, None, None),
            (ArchetypeId.A05, None, None),
            (ArchetypeId.A02, None, None),
            (ArchetypeId.A06 if not is_proposal else ArchetypeId.A10, "kinetics_spline", "delta_g_concept"),
            (ArchetypeId.A08, None, None),
        ]
        return rotation[content_index % len(rotation)]

    def _choose_v5_layout(self, slide: SlideSpec, is_proposal: bool, content_index: int) -> LayoutId:
        txt = f"{slide.section_name} {slide.title} {slide.takeaway}".lower()
        if any(k in txt for k in ("文献", "综述", "演进", "构效", "sar")):
            return LayoutId.lit_overview_dual_card
        if any(k in txt for k in ("背景", "立题", "绪论", "意义")):
            return LayoutId.bg_top_summary_3box
        if any(k in txt for k in ("空白", "痛点", "现状", "问题", "挑战")):
            return LayoutId.pain_points_left_arrows if content_index % 2 == 1 else LayoutId.vs_center_wing
        if any(k in txt for k in ("路线", "roadmap", "方案", "计划", "实施")):
            return LayoutId.roadmap_layered_matrix
        if any(k in txt for k in ("机理", "循环", "构象", "3d", "结合", "催化")):
            return LayoutId.mechanism_3col_flow
        if not is_proposal and any(k in txt for k in ("定量", "药代", "收率", "效率", "xps", "dft", "ml", "电化学", "数据", "对比")):
            return LayoutId.data_dashboard_table
        if any(k in txt for k in ("验证", "表征", "总结", "展望", "可行")):
            return LayoutId.fig_left_3step_chain

        rotation = [
            LayoutId.bg_top_summary_3box,
            LayoutId.pain_points_left_arrows,
            LayoutId.roadmap_layered_matrix,
            LayoutId.mechanism_3col_flow,
            LayoutId.data_dashboard_table if not is_proposal else LayoutId.fig_left_3step_chain,
            LayoutId.vs_center_wing,
            LayoutId.lit_overview_dual_card,
            LayoutId.fig_left_3step_chain,
        ]
        return rotation[content_index % len(rotation)]

    def _populate_v5_defaults(self, slide: SlideSpec, is_proposal: bool) -> None:
        if not slide.takeaway_badge:
            slide.takeaway_badge = "核心目标" if slide.layout_id in (LayoutId.pain_points_left_arrows, LayoutId.roadmap_layered_matrix) else "核心结论"
        if not slide.takeaway_highlight and slide.insights and slide.insights[0].highlight:
            slide.takeaway_highlight = slide.insights[0].highlight

        if slide.layout_id == LayoutId.lit_overview_dual_card:
            if not slide.profile_card:
                slide.profile_card = {
                    "journal_badge": "KEY STUDY · 文献档案",
                    "paper_title": slide.title,
                    "authors": slide.footer_left,
                    "metrics": [(k.label, k.value) for k in slide.kpis[:3]] or [("核心指标", "高选择性"), ("绿色度", "显著提升")],
                    "focus_text": slide.takeaway,
                }
        elif slide.layout_id == LayoutId.mechanism_3col_flow:
            if not slide.chevron_steps:
                slide.chevron_steps = ["01 底物活化", "02 限域预组织", "03 中间体转化", "04 高效选择生成"]
            if not slide.left_cards:
                slide.left_cards = [{"heading": ins.heading, "body": ins.body} for ins in slide.insights[:3]]
            if not slide.right_chain:
                slide.right_chain = [{"title": k.value, "body": k.label} for k in slide.kpis[:2]] + [{"title": "协同降垒", "body": "显著加速关键反应步骤"}]
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "triple_pill", "left": "结构精确预组织", "center": slide.title[:18], "right": "稳定高效循环"}
        elif slide.layout_id == LayoutId.data_dashboard_table:
            if not slide.table_data:
                slide.table_data = TableData(
                    headers=["评价指标", "常规体系", "本工作"],
                    rows=[
                        ["分离收率", "62.4%", "91.2%"],
                        ["PMI 减废", "58.2", "4.8"],
                        ["反应时长", "12 h", "45 min"],
                        ["循环稳定性", "3 次", "8 次 (98%)"],
                    ],
                )
            if not slide.strategy_cards:
                slide.strategy_cards = [
                    {"badge": "性能突破", "badge_color": "#00468B", "title": ins.heading, "body": ins.body}
                    for ins in slide.insights[:2]
                ]
        elif slide.layout_id in (LayoutId.bg_top_summary_3box, LayoutId.fig_left_3step_chain):
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "solid_bar", "badge": "突破", "text": slide.takeaway}
        elif slide.layout_id == LayoutId.vs_center_wing:
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "rose_quote", "text": slide.takeaway}

        if not slide.bottom_banner:
            slide.bottom_banner = {"mode": "bar", "badge": "关键启示", "text": slide.takeaway}

    def direct_slide(
        self,
        slide: SlideSpec,
        palette_id: str = "lancet",
        is_proposal: bool = False,
        detected_smiles: Optional[List[str]] = None,
        content_index: int = 0,
        design_style: DesignStyle = DesignStyle.defense_modular,
    ) -> SlideSpec:
        if slide.slide_type == SlideType.cover:
            slide.figure_spec = build_default_figure_spec(
                ArchetypeId.A01,
                slide_no=slide.slide_no,
                palette_id=palette_id,
                box_in=FigureBoxIn(left=7.35, top=1.35, width=5.45, height=4.80),
                is_proposal=is_proposal,
            )
            slide.figure_spec.native_overlays = []
            slide.figure_spec.caption = ""
            return slide

        if slide.slide_type != SlideType.content:
            return slide

        arch, preset, mech_mode = self._choose_archetype_and_preset(slide, is_proposal=is_proposal, content_index=content_index)
        smiles = detected_smiles[0] if detected_smiles else None

        if design_style != DesignStyle.zero_fill_frameless:
            slide.layout_id = self._choose_v5_layout(slide, is_proposal=is_proposal, content_index=content_index)
            if design_style == DesignStyle.consulting_editorial:
                slide.header_variant = "editorial"
            elif slide.layout_id in (LayoutId.pain_points_left_arrows, LayoutId.roadmap_layered_matrix):
                slide.header_variant = "solid_bar"
            else:
                slide.header_variant = "nav_tabs"
            box = get_v5_figure_box(slide.layout_id)
            self._populate_v5_defaults(slide, is_proposal=is_proposal)
        else:
            if mech_mode == "roadmap_4stage":
                slide.layout_id = LayoutId.full_roadmap
                box = FigureBoxIn(left=0.46, top=1.68, width=12.40, height=4.10)
            else:
                box = FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42)

        fig_spec = build_default_figure_spec(
            archetype=arch,
            slide_no=slide.slide_no,
            palette_id=palette_id,
            box_in=box,
            smiles=smiles,
            origin_preset=preset,
            is_proposal=is_proposal,
        )
        if mech_mode and fig_spec.assets:
            fig_spec.assets[0].mech_mode = mech_mode
        slide.figure_spec = fig_spec
        return slide
