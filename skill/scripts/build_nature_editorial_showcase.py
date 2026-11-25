"""Build a 4-slide Nature Archival Crimson showcase deck with 4 distinct chemical structure styles & Pd coupling cycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

API_BASE = "http://127.0.0.1:8000"
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.figure_factory.cylview3d_engine import project_3d_substructure_anchor
from app.schemas.deck_spec import (
    ArchetypeId,
    DeckMeta,
    DeckSpec,
    DesignStyle,
    EngineType,
    FigureAsset,
    FigureBoxIn,
    FigureSpec,
    InsightItem,
    KpiItem,
    LayoutId,
    NativeOverlay,
    ScenarioType,
    SlideSpec,
    SlideType,
)


PEN_G_SMILES = "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O"
ARTEMISININ_SMILES = "C[C@@H]1CC[C@H]2[C@@H](C)C(=O)O[C@@H]3O[C@@]4(C)CC[C@@H]1[C@@]23OO4"
IMATINIB_SMILES = "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc4nccc(n4)c5cccnc5"


def build_spec() -> DeckSpec:
    nav_tabs = [
        "01 多风格二维结构式|Multi-Style 2D Art",
        "02 三维构象与过氧桥|3D CYLview & Peroxide",
        "03 催化机理与极简线稿|Pd Cycle & Minimal Mono",
    ]
    citation = "Nature Editorial Specimen · Classic Medicinal Chemistry & Catalysis"
    box1 = FigureBoxIn(left=0.52, top=1.86, width=8.18, height=2.92)
    box2 = FigureBoxIn(left=4.05, top=1.98, width=5.24, height=3.84)
    box4 = FigureBoxIn(left=0.56, top=2.06, width=7.44, height=3.84)

    box2_tuple = (box2.left, box2.top, box2.width, box2.height)
    nb2 = (0.06, 0.14, 0.88, 0.64)
    peroxide_xy = project_3d_substructure_anchor(ARTEMISININ_SMILES, "OO", box2_tuple, nb2, show_nonpolar_h=False)
    lactone_xy = project_3d_substructure_anchor(ARTEMISININ_SMILES, "C(=O)OC", box2_tuple, nb2, show_nonpolar_h=False)
    ring_ab_xy = (5.81, 3.60)
    c9_me_xy = (6.62, 2.73)

    slides = [
        SlideSpec(
            slide_no=1,
            slide_type=SlideType.toc,
            layout_id=LayoutId.toc,
            eyebrow="CONTENTS",
            title="目录",
            takeaway="展示 Nature 编辑部红金配色下四种分子绘风、3D 球棍与 Pd(0)/Pd(II) 催化循环机理。",
            toc_items=nav_tabs,
            footer_left=citation,
            speaker_notes="Nature Archival Crimson showcase: 4 chemical styles + Pd(0)/Pd(II) catalytic mechanism.",
        ),
        SlideSpec(
            slide_no=2,
            slide_type=SlideType.content,
            layout_id=LayoutId.lit_overview_dual_card,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=0,
            section_name="01 多风格二维结构式",
            eyebrow="NATURE EDITORIAL · MULTI-STYLE 2D STRUCTURES",
            title="经典药物分子多风格矢量演绎：青霉素 G 与青蒿素",
            takeaway="同一画布支持绛红药化风与药效团环填充风，键线与手性楔形键均原生可编辑。",
            takeaway_highlight="绛红药化风与药效团环填充风",
            figure_bottom_note="双风格矢量对照：Penicillin G vs. (+)-Artemisinin",
            figure_spec=FigureSpec(
                figure_id="fig_01_2d_styles",
                archetype=ArchetypeId.A05,
                visual_story_scale="molecular_2d_reaction",
                box_in=box1,
                assets=[
                    FigureAsset(
                        asset_id="peng_burgundy",
                        engine=EngineType.chemdraw_rdkit,
                        smiles=PEN_G_SMILES,
                        label="Penicillin G (β-内酰胺经典母核)",
                        sublabel="风格一 · 绛红手绘",
                        chem_style="nature_burgundy",
                        drug_burgundy=True,
                        fixed_bond_length_px=21,
                        highlight_atoms=[17, 16, 5, 4, 18],
                        highlight_halo_token="s1",
                        highlight_groups=[{"atoms": [17, 16, 5, 4, 18], "color_token": "s1"}],
                        norm_box=[0.01, 0.06, 0.40, 0.78],
                    ),
                    FigureAsset(
                        asset_id="artemisinin_shaded",
                        engine=EngineType.chemdraw_rdkit,
                        smiles=ARTEMISININ_SMILES,
                        label="(+)-Artemisinin (过氧三氧杂环)",
                        sublabel="风格二 · 环内铺色",
                        chem_style="shaded_scaffold",
                        fixed_bond_length_px=21,
                        highlight_atoms=[18, 19],
                        highlight_halo_token="s1",
                        highlight_groups=[
                            {"atoms": [18, 19], "color_token": "s1"},
                            {"atoms": [7, 8, 9], "color_token": "alert"},
                        ],
                        norm_box=[0.59, 0.06, 0.40, 0.78],
                    ),
                ],
                native_overlays=[
                    NativeOverlay(
                        type="reaction_arrow",
                        from_in=[box1.left + box1.width * 0.43, box1.top + box1.height * 0.44],
                        to_in=[box1.left + box1.width * 0.57, box1.top + box1.height * 0.44],
                        label="多风格渲染|原生矢量",
                        color_token="s1",
                    )
                ],
                caption="Fig. 1  Contrasting 2D chemical rendering styles on Penicillin G and Artemisinin.",
            ),
            kpis=[
                KpiItem(value="334.4 Da", label="青霉素 G MW", color_token="s1"),
                KpiItem(value="282.3 Da", label="青蒿素 MW", color_token="alert"),
            ],
            insights=[
                InsightItem(
                    index="01",
                    heading="绛红高对比药化骨架",
                    body="#7F1D1D 深绛红骨架配牛津蓝杂原子，呈现 Nature 期刊印刷质感。",
                    highlight="Nature 期刊印刷质感",
                ),
                InsightItem(
                    index="02",
                    heading="多边形环内柔和铺色",
                    body="精准识别三氧杂环与内酯环顶点，内置淡彩铺底而不遮挡手性楔形键。",
                    highlight="精准识别",
                ),
            ],
            profile_card={
                "journal_badge": "NATURE EDITORIAL · 档案",
                "paper_title": "Four Distinct Editable Chemical & Mechanism Styles",
                "authors": "Penicillin G · Artemisinin · Imatinib",
                "metrics": [
                    ("风格 I", "绛红药化手绘风"),
                    ("风格 II", "药效团环内填充风"),
                    ("风格 III", "PyMOL 3D 球棍风"),
                    ("风格 IV", "极简单色突出线稿"),
                ],
                "focus_text": "全套骨架、楔形键与杂原子均编译为 GroupShape，可在 PPT 逐键编辑。",
            },
            bottom_banner={
                "mode": "bar",
                "badge": "风格对照",
                "text": "通过 chem_style 参数一键切换四类顶刊分子视觉范式，兼顾化学严谨度与杂志质感。",
            },
            footer_left=citation,
            speaker_notes="Slide 2 contrasts nature_burgundy (Penicillin G) with shaded_scaffold (Artemisinin).",
        ),
        SlideSpec(
            slide_no=3,
            slide_type=SlideType.content,
            layout_id=LayoutId.mechanism_3col_flow,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=1,
            section_name="02 三维构象与过氧桥",
            eyebrow="NATURE EDITORIAL · 3D CYLVIEW CONFORMATION",
            title="风格三：(+)-青蒿素三维球棍构象与过氧桥机制",
            takeaway="隐藏非极性 C–H 突出五环笼状手性拓扑，精准标定 Fe2+ 诱导过氧桥裂解中心。",
            takeaway_highlight="Fe2+ 诱导过氧桥裂解",
            left_cards=[
                {"heading": "1,2,4-三氧杂环活性芯", "body": "内过氧桥 (–O–O–) 在亚铁血红素催化下均裂，生成高活性自由基。"},
                {"heading": "刚性倍半萜笼状骨架", "body": "稠合五环锁死立体构象，保护过氧桥免受非特异性水相分解。"},
                {"heading": "δ-内酯水溶性微调基", "body": "为临床半合成改造（蒿甲醚/青蒿琥酯）提供关键 C10 修饰位点。"},
            ],
            figure_spec=FigureSpec(
                figure_id="fig_02_art_3d",
                archetype=ArchetypeId.A04,
                visual_story_scale="molecular_3d_conformer",
                box_in=box2,
                assets=[
                    FigureAsset(
                        asset_id="artemisinin_3d",
                        engine=EngineType.cylview_3d,
                        smiles=ARTEMISININ_SMILES,
                        label="(+)-Artemisinin 3D (ETKDGv3)",
                        show_nonpolar_h=False,
                        norm_box=list(nb2),
                    )
                ],
                native_overlays=[
                    NativeOverlay(type="pocket_subsite", source_circle_in=[peroxide_xy[0], peroxide_xy[1], 0.46], color_token="s1"),
                    NativeOverlay(type="pocket_subsite", source_circle_in=[lactone_xy[0], lactone_xy[1], 0.44], color_token="alert"),
                    NativeOverlay(
                        type="pocket_subsite",
                        from_in=[4.92, 4.18],
                        to_in=[peroxide_xy[0], peroxide_xy[1]],
                        sublabel="Fe2+ 激活裂解",
                        color_token="s1",
                    ),
                ],
                caption="Fig. 2  Deterministic ETKDGv3 3D conformer of (+)-Artemisinin.",
            ),
            callout_badges=[
                {"text": "倍半萜刚性环 (A/B)", "x_in": 4.06, "y_in": 1.76, "w_in": 1.96, "target_x_in": ring_ab_xy[0], "target_y_in": ring_ab_xy[1], "color_token": "alert"},
                {"text": "C9 立体甲基中心", "x_in": 7.38, "y_in": 1.76, "w_in": 1.90, "target_x_in": c9_me_xy[0], "target_y_in": c9_me_xy[1], "color_token": "alert"},
                {"text": "核心过氧桥 (–O–O–)", "x_in": 4.06, "y_in": 5.36, "w_in": 1.98, "target_x_in": peroxide_xy[0], "target_y_in": peroxide_xy[1], "color_token": "s1"},
                {"text": "δ-内酯羰基 (C=O)", "x_in": 7.38, "y_in": 5.36, "w_in": 1.90, "target_x_in": lactone_xy[0], "target_y_in": lactone_xy[1], "color_token": "alert"},
            ],
            right_chain=[
                {"title": "C15H22O5 · 282.3 Da", "body": "高脂溶性倍半萜内酯"},
                {"title": "7 个连续手性中心", "body": "ETKDGv3 精确几何还原"},
                {"title": "碳中心自由基烷化", "body": "不可逆共价失活疟原虫蛋白"},
            ],
            bottom_banner={
                "mode": "triple_pill",
                "left": "ETKDGv3 + MMFF94 精确构象",
                "center": "铁激活内过氧桥自由基级联机制",
                "right": "深度雾化 + 柔和接地阴影",
            },
            footer_left=citation,
            speaker_notes="Slide 3 showcases 3D CYLview heavy+polar-H rendering of (+)-Artemisinin with SMARTS anchors.",
        ),
        SlideSpec(
            slide_no=4,
            slide_type=SlideType.content,
            layout_id=LayoutId.fig_left_3step_chain,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=2,
            section_name="03 催化机理与极简线稿",
            eyebrow="NATURE EDITORIAL · CATALYTIC CYCLE & MINIMAL LINE ART",
            title="Pd(0)/Pd(II) 偶联机理图与风格四极简线稿伊马替尼",
            takeaway="Pd(0)/Pd(II) 催化循环实现 C–N 高效构筑，极简黑线红高亮风精准锁定成键位点。",
            takeaway_highlight="极简黑线红高亮风",
            figure_spec=FigureSpec(
                figure_id="fig_03_pd_mech",
                archetype=ArchetypeId.A10,
                visual_story_scale="catalytic_mechanism_dual",
                box_in=box4,
                assets=[
                    FigureAsset(
                        asset_id="pd_cycle_mech",
                        engine=EngineType.vector_mech,
                        mech_mode="pd_coupling_cycle",
                        label="Pd(0)/Pd(II) Buchwald–Hartwig 催化循环",
                        norm_box=[0.00, 0.00, 0.63, 0.88],
                    ),
                    FigureAsset(
                        asset_id="imatinib_mono",
                        engine=EngineType.chemdraw_rdkit,
                        smiles=IMATINIB_SMILES,
                        label="Imatinib · 极简单色高亮风",
                        chem_style="minimal_mono",
                        fixed_bond_length_px=20,
                        highlight_atoms=[23, 24, 25, 26, 27, 28, 29, 30],
                        highlight_halo_token="s1",
                        highlight_groups=[{"atoms": [23, 24, 25, 26, 27, 28, 29, 30], "color_token": "s1"}],
                        norm_box=[0.65, 0.04, 0.34, 0.84],
                    ),
                ],
                caption="Fig. 3  Pd(0)/Pd(II) catalytic coupling cycle paired with minimal monochrome Imatinib.",
            ),
            right_chain=[
                {"title": "01 氧化加成", "body": "Ar–X 对低价 Pd(0)L₂ 氧化加成生成关键 Ar–Pd(II)–X 中间体。"},
                {"title": "02 胺配位脱质子", "body": "杂环胺 R–NH₂ 与强碱协同脱质子，完成转金属并脱除 Base·HX。"},
                {"title": "03 还原消除", "body": "大位阻膦配体促进 C–N 还原消除，构筑二芳胺核并再生 Pd(0)。"},
            ],
            bottom_banner={
                "mode": "bar",
                "badge": "机理闭环",
                "text": "极简单色线稿 + 红色成键位点高亮配合循环机理图，是 Nature Chemistry / Nat. Synth. 常用制图范式。",
            },
            footer_left=citation,
            speaker_notes="Slide 4 pairs Pd(0)/Pd(II) Buchwald-Hartwig catalytic mechanism with minimal_mono Imatinib.",
        ),
    ]

    return DeckSpec(
        meta=DeckMeta(
            deck_id="nature_editorial_showcase",
            deck_title="Classic Medicinal Chemistry Structures & Catalytic Mechanisms",
            deck_subtitle="Nature Editorial Palette · 4 Distinct Structure Styles & Pd(0)/Pd(II) Cycle",
            author="计算药化课题组",
            affiliation="Nature Editorial Desk",
            scenario=ScenarioType.literature_review,
            target_slide_count=4,
            palette_id="nejm",
            is_proposal=False,
            design_style=DesignStyle.defense_modular,
        ),
        slides=slides,
    )


def main() -> int:
    deck = build_spec()
    payload = {"deck_spec": deck.model_dump(by_alias=True), "run_qa_loop": True}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{API_BASE}/api/build/pptx", json=payload)
        resp.raise_for_status()
        data = resp.json()

    print(json.dumps({
        "pptx_url": data["pptx_url"],
        "preview_urls": data["preview_urls"],
        "audit_passed": data["audit_report"]["passed"],
        "audit_report": data["audit_report"],
    }, ensure_ascii=False, indent=2))
    return 0 if data["audit_report"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
