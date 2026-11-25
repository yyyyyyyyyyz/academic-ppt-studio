"""Art Director Agent — Matches Content Semantics to Archetypes A01–A10 & Builds FigureSpecs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..builder.v5_layouts import get_v5_figure_box
from ..figure_factory.chem_grounding import resolve_compound_smiles
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
    V5_LAYOUT_IDS,
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
            visual_story_scale="molecular_2d_structure",
            box_in=box,
            assets=[
                FigureAsset(
                    asset_id=f"{fid}_mol",
                    engine=EngineType.chemdraw_rdkit,
                    smiles=mol_smiles,
                    label="Target Molecule (ChemDraw 2D)",
                    chem_style="acs1996",
                    highlight_rings=True,
                    norm_box=[0.04, 0.06, 0.92, 0.88],
                )
            ],
            native_overlays=[],
            caption=f"Fig. {slide_no}  Publication-grade 2D chemical structure rendered in ChemDraw ACS 1996 style.",
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
                mech_mode="gap_quadrant" if is_proposal else "molecular_3d_pathway",
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

        if any(k in txt for k in ("3d", "立体", "构象", "对接", "口袋", "球棍", "建模", "cylview")):
            return (ArchetypeId.A04, None, None)
        if any(k in txt for k in ("2d", "chemdraw", "合成", "先导", "抑制剂", "骨架", "结构", "底物")):
            return (ArchetypeId.A05, None, None) if content_index % 2 == 0 else (ArchetypeId.A04, None, None)

        return (ArchetypeId.A05, None, None) if content_index % 2 == 0 else (ArchetypeId.A04, None, None)

    def _choose_v5_layout(self, slide: SlideSpec, is_proposal: bool, content_index: int) -> LayoutId:
        if slide.table_data is not None:
            return LayoutId.data_dashboard_table
        txt = f"{slide.section_name} {slide.title} {slide.takeaway}".lower()
        if any(k in txt for k in ("时间", "进度", "流程", "步骤", "阶段", "timeline")):
            return LayoutId.timeline_chevron_flow
        if any(k in txt for k in ("四象限", "象限", "矩阵", "创新", "风险", "策略", "多维")):
            return LayoutId.quadrant_2x2_matrix
        if any(k in txt for k in ("思路", "体系", "框架", "总体", "核心构筑", "拓扑")):
            return LayoutId.hub_spoke_radial
        if any(k in txt for k in ("国内外", "传统", "优缺点", "比较", "差异", "pk")):
            return LayoutId.dual_compare_cards
        if any(k in txt for k in ("三大", "意义", "亮点", "成果", "柱状", "模块")):
            return LayoutId.tri_column_showcase
        if any(k in txt for k in ("文献", "综述", "演进", "构效", "sar")):
            return LayoutId.lit_overview_dual_card
        if any(k in txt for k in ("背景", "立题", "绪论")):
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
            LayoutId.dual_compare_cards,
            LayoutId.hub_spoke_radial,
            LayoutId.timeline_chevron_flow,
            LayoutId.quadrant_2x2_matrix,
            LayoutId.tri_column_showcase,
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
                derived_metrics = [(k.label, k.value) for k in slide.kpis[:3]]
                if not derived_metrics:
                    derived_metrics = [
                        (ins.heading[:12], (ins.highlight or ins.body[:14]))
                        for ins in slide.insights[:2]
                    ]
                slide.profile_card = {
                    "journal_badge": "KEY STUDY · 文献档案",
                    "paper_title": slide.title,
                    "authors": slide.footer_left,
                    "metrics": derived_metrics or [("研究主题", slide.section_name[:12])],
                    "focus_text": slide.takeaway,
                }
        elif slide.layout_id == LayoutId.mechanism_3col_flow:
            if not slide.chevron_steps:
                slide.chevron_steps = [
                    f"{i + 1:02d} {ins.heading[:8]}" for i, ins in enumerate(slide.insights[:4])
                ] or ["01 核心问题", "02 关键发现", "03 机理阐明"]
            if not slide.left_cards:
                slide.left_cards = [{"heading": ins.heading, "body": ins.body} for ins in slide.insights[:3]]
            if not slide.right_chain:
                tail_ins = slide.insights[-1] if slide.insights else None
                slide.right_chain = [{"title": k.value, "body": k.label} for k in slide.kpis[:2]] + [
                    {
                        "title": tail_ins.heading[:10] if tail_ins else "关键结论",
                        "body": (tail_ins.body if tail_ins else slide.takeaway)[:30],
                    }
                ]
            if not slide.bottom_banner:
                left_lbl = slide.insights[0].heading[:10] if slide.insights else slide.section_name[:10]
                right_lbl = (
                    f"{slide.kpis[0].label} {slide.kpis[0].value}"[:16]
                    if slide.kpis
                    else (slide.insights[-1].highlight or "定量与机制互证")[:16]
                )
                slide.bottom_banner = {
                    "mode": "triple_pill",
                    "left": left_lbl,
                    "center": slide.title[:18],
                    "right": right_lbl,
                }
        elif slide.layout_id == LayoutId.data_dashboard_table:
            if not slide.table_data:
                summary_rows = [[k.label[:14], k.value[:16]] for k in slide.kpis[:3]]
                for ins in slide.insights[:3]:
                    if len(summary_rows) >= 4:
                        break
                    summary_rows.append([ins.heading[:14], (ins.highlight or ins.body[:20])])
                slide.table_data = TableData(
                    headers=["关键维度", "核心数据 / 发现"],
                    rows=summary_rows or [[slide.section_name[:14], slide.takeaway[:24]]],
                )
            if not slide.strategy_cards:
                slide.strategy_cards = [
                    {"badge": "要点解析", "badge_color": "s2" if idx == 0 else "s3", "title": ins.heading, "body": ins.body}
                    for idx, ins in enumerate(slide.insights[:2])
                ]
        elif slide.layout_id in (LayoutId.bg_top_summary_3box, LayoutId.fig_left_3step_chain, LayoutId.tri_column_showcase):
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "solid_bar", "badge": "突破", "text": slide.takeaway}
        elif slide.layout_id == LayoutId.timeline_chevron_flow:
            if not slide.chevron_steps:
                slide.chevron_steps = [
                    f"{i + 1:02d} {ins.heading[:10]}" for i, ins in enumerate(slide.insights[:4])
                ] or ["01 问题提出", "02 分子设计", "03 机理验证", "04 定量突破"]
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "solid_bar", "badge": "阶段", "text": slide.takeaway}
        elif slide.layout_id == LayoutId.dual_compare_cards:
            if not slide.left_cards:
                slide.left_cards = [{"heading": ins.heading, "body": ins.body} for ins in slide.insights[:3]]
            if not slide.right_chain:
                slide.right_chain = [{"title": k.value, "body": k.label} for k in slide.kpis[:2]]
            if not slide.bottom_banner:
                slide.bottom_banner = {"mode": "bar", "badge": "优势对照", "text": slide.takeaway}
        elif slide.layout_id == LayoutId.quadrant_2x2_matrix:
            if not slide.left_cards:
                slide.left_cards = [{"heading": ins.heading, "body": ins.body} for ins in slide.insights[:4]]
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
        section_smiles: Optional[List[str]] = None,
        section_images: Optional[List[str]] = None,
        visual_plan: Optional[Dict[str, Any]] = None,
        table_chart_data: Optional[Dict[str, Any]] = None,
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

        vp = visual_plan or {}
        arch, preset, mech_mode = self._choose_archetype_and_preset(slide, is_proposal=is_proposal, content_index=content_index)

        vp_smiles = str(vp.get("smiles") or vp.get("compound_name") or "").strip()
        smiles: Optional[str] = None
        if vp_smiles:
            smiles = resolve_compound_smiles(vp_smiles) or (section_smiles[0] if section_smiles else None)
        elif section_smiles:
            smiles = section_smiles[0]
        elif detected_smiles:
            smiles = detected_smiles[content_index % len(detected_smiles)]

        vp_mode = str(vp.get("mode") or "").strip().lower()
        chem_style = str(vp.get("chem_style") or "").strip().lower()
        custom_plot_data: Optional[Dict[str, Any]] = None
        custom_mech_data: Optional[Dict[str, Any]] = None
        custom_scene_desc: Optional[str] = None

        if vp_mode == "chemdraw_2d":
            arch = ArchetypeId.A05
        elif vp_mode == "pymol_3d":
            arch = ArchetypeId.A04
        elif vp_mode == "mechanism_3d_pathway":
            arch = ArchetypeId.A10
            mech_mode = "molecular_3d_pathway"
            if isinstance(vp.get("pathway_spec"), dict):
                custom_mech_data = dict(vp["pathway_spec"])
        elif vp_mode == "origin_real_data" and not is_proposal:
            arch = ArchetypeId.A06
            preset = str(vp.get("origin_preset") or "nature_grouped_bar")
            if isinstance(vp.get("chart_data"), dict) and (vp["chart_data"].get("categories") or vp["chart_data"].get("labels")):
                custom_plot_data = dict(vp["chart_data"])
        elif vp_mode == "blender_3d_ai":
            arch = ArchetypeId.A01
            if vp.get("scene_description"):
                custom_scene_desc = str(vp["scene_description"])
        elif table_chart_data and not is_proposal and arch not in (ArchetypeId.A04, ArchetypeId.A05):
            arch = ArchetypeId.A06
            preset = "nature_grouped_bar"
            custom_plot_data = dict(table_chart_data)

        if not custom_plot_data and table_chart_data and arch == ArchetypeId.A06 and not is_proposal:
            preset = "nature_grouped_bar"
            custom_plot_data = dict(table_chart_data)

        if design_style != DesignStyle.zero_fill_frameless:
            llm_layout_raw = str(vp.get("layout_id") or "").strip()
            chosen_layout: Optional[LayoutId] = None
            for lid in V5_LAYOUT_IDS:
                if lid.value == llm_layout_raw:
                    chosen_layout = lid
                    break
            if slide.table_data is not None:
                chosen_layout = LayoutId.data_dashboard_table
            slide.layout_id = chosen_layout or self._choose_v5_layout(slide, is_proposal=is_proposal, content_index=content_index)
            if design_style == DesignStyle.consulting_editorial:
                slide.header_variant = "editorial"
            elif slide.layout_id in (LayoutId.pain_points_left_arrows, LayoutId.roadmap_layered_matrix, LayoutId.dual_compare_cards):
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

        valid_word_imgs = [p for p in (section_images or []) if p and Path(p).is_file()]
        if valid_word_imgs:
            slide.figure_spec = FigureSpec(
                figure_id=f"fig_{slide.slide_no:02d}",
                archetype=arch,
                visual_story_scale="word_embedded_figure",
                box_in=box,
                assets=[
                    FigureAsset(
                        asset_id=f"fig_{slide.slide_no:02d}_word_img",
                        engine=EngineType.uploaded_image,
                        png_path=valid_word_imgs[0],
                        label=slide.section_name[:22],
                    )
                ],
                caption=f"Fig. {slide.slide_no}  {slide.section_name}（提取自原始文稿插图）",
            )
            return slide

        fig_spec = build_default_figure_spec(
            archetype=arch,
            slide_no=slide.slide_no,
            palette_id=palette_id,
            box_in=box,
            smiles=smiles,
            origin_preset=preset,
            is_proposal=is_proposal,
        )
        if fig_spec.assets:
            primary = fig_spec.assets[0]
            if mech_mode:
                primary.mech_mode = mech_mode
            if custom_mech_data:
                primary.mech_data = custom_mech_data
            if custom_plot_data and primary.engine == EngineType.origin_plot:
                primary.plot_data = custom_plot_data
            if custom_scene_desc and primary.engine == EngineType.sci3d_art:
                primary.scene_description = custom_scene_desc
            if chem_style:
                for ast in fig_spec.assets:
                    if ast.engine == EngineType.chemdraw_rdkit:
                        ast.chem_style = chem_style
                        ast.drug_burgundy = chem_style == "nature_burgundy"
            else:
                _styles_2d = ["acs1996", "shaded_scaffold", "nature_burgundy", "jacs_terracotta"]
                _styles_3d = ["ball_stick", "stick_clean", "pymol_neon_green", "metallic_studio"]
                for ast in fig_spec.assets:
                    if ast.engine == EngineType.chemdraw_rdkit:
                        chosen_2d = _styles_2d[content_index % len(_styles_2d)]
                        ast.chem_style = chosen_2d
                        ast.drug_burgundy = chosen_2d == "nature_burgundy"
                    elif ast.engine == EngineType.cylview_3d:
                        ast.style_3d = _styles_3d[content_index % len(_styles_3d)]
        slide.figure_spec = fig_spec
        return slide
