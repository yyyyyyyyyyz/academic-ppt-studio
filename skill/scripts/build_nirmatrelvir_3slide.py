"""Build a 4-slide v5.0 medicinal chemistry literature deck (TOC + 3 content slides, Owen et al., Science 2021)."""

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
    TableData,
)


PF00835231_SMILES = "COc1cccc2[nH]c(C(=O)N[C@@H](CC(C)C)C(=O)N[C@@H](C[C@@H]3CCNC3=O)C(=O)CO)cc12"
NIRMATRELVIR_SMILES = "CC1(C)[C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N"


def build_spec() -> DeckSpec:
    nav_tabs = [
        "01 弹头与构效演进|SAR & Warhead Evolution",
        "02 三维构象与机理|3D Conformation & Binding",
        "03 药代与临床转化|Oral PK & Translation",
    ]
    citation = "Owen et al., Science 2021, 374, 1586–1593"
    box1 = FigureBoxIn(left=0.52, top=1.86, width=8.18, height=2.92)
    box2 = FigureBoxIn(left=4.05, top=1.98, width=5.24, height=3.84)
    box3 = FigureBoxIn(left=0.54, top=2.86, width=7.30, height=3.18)

    box2_tuple = (box2.left, box2.top, box2.width, box2.height)
    nb2 = (0.06, 0.14, 0.88, 0.64)
    p2_xy = project_3d_substructure_anchor(NIRMATRELVIR_SMILES, "C1(C)(C)C2C1CN(C2)", box2_tuple, nb2, show_nonpolar_h=False)
    p1_xy = project_3d_substructure_anchor(NIRMATRELVIR_SMILES, "O=C1CCCN1", box2_tuple, nb2, show_nonpolar_h=False)
    cf3_xy = project_3d_substructure_anchor(NIRMATRELVIR_SMILES, "C(=O)C(F)(F)F", box2_tuple, nb2, show_nonpolar_h=False)
    cn_xy = project_3d_substructure_anchor(NIRMATRELVIR_SMILES, "C#N", box2_tuple, nb2, show_nonpolar_h=False)

    slides = [
        SlideSpec(
            slide_no=1,
            slide_type=SlideType.toc,
            layout_id=LayoutId.toc,
            eyebrow="CONTENTS",
            title="目录",
            takeaway="围绕构效演进、三维构象机制与口服临床转化三部分展开汇报。",
            toc_items=nav_tabs,
            footer_left=citation,
            speaker_notes="Literature review outline: Science 2021 Nirmatrelvir discovery in 3 core sections.",
        ),
        SlideSpec(
            slide_no=2,
            slide_type=SlideType.content,
            layout_id=LayoutId.lit_overview_dual_card,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=0,
            section_name="01 弹头与构效演进",
            eyebrow="SCIENCE 2021 · SAR EVOLUTION",
            title="理性构效优化：弹头替换与氢键精简",
            takeaway="以氰基 (-CN) 取代羟甲基酮并将 HBD 由 5 降至 3，兼顾纳摩尔活性与口服。",
            takeaway_highlight="纳摩尔活性与口服",
            figure_bottom_note="药物化学结构演进：PF-00835231 (IV) → Nirmatrelvir (口服)",
            figure_spec=FigureSpec(
                figure_id="fig_01",
                archetype=ArchetypeId.A05,
                visual_story_scale="molecular_2d_reaction",
                box_in=box1,
                assets=[
                    FigureAsset(
                        asset_id="pf00835231_2d",
                        engine=EngineType.chemdraw_rdkit,
                        smiles=PF00835231_SMILES,
                        label="PF-00835231 (IV, HBD = 5)",
                        sublabel="静脉先导 · IV",
                        fixed_bond_length_px=20,
                        highlight_atoms=[28, 29, 30, 31],
                        highlight_halo_token="alert",
                        highlight_groups=[{"atoms": [28, 29, 30, 31], "color_token": "alert"}],
                        norm_box=[0.01, 0.06, 0.40, 0.78],
                    ),
                    FigureAsset(
                        asset_id="nirmatrelvir_2d",
                        engine=EngineType.chemdraw_rdkit,
                        smiles=NIRMATRELVIR_SMILES,
                        label="Nirmatrelvir (口服, HBD = 3)",
                        sublabel="临床口服 · PO",
                        fixed_bond_length_px=20,
                        highlight_atoms=[33, 34],
                        highlight_halo_token="s1",
                        highlight_groups=[
                            {"atoms": [33, 34], "color_token": "s1"},
                            {"atoms": [1, 0, 2, 3, 4, 5, 6, 7], "color_token": "s2"},
                        ],
                        norm_box=[0.59, 0.06, 0.40, 0.78],
                    ),
                ],
                native_overlays=[
                    NativeOverlay(
                        type="reaction_arrow",
                        from_in=[box1.left + box1.width * 0.43, box1.top + box1.height * 0.44],
                        to_in=[box1.left + box1.width * 0.57, box1.top + box1.height * 0.44],
                        label="-CH2OH→-CN|HBD 5→3",
                        color_token="s1",
                    )
                ],
                caption="Fig. 1  Lead-to-candidate structural evolution.",
            ),
            kpis=[
                KpiItem(value="3.11 nM", label="Mpro 抑制常数 Ki", color_token="s1"),
                KpiItem(value="74.5 nM", label="Vero E6 EC50", color_token="s2"),
            ],
            insights=[
                InsightItem(
                    index="01",
                    heading="氰基可逆共价弹头",
                    body="以 -CN 取代羟甲基酮，消除差向异构化。",
                    highlight="消除差向异构化",
                ),
                InsightItem(
                    index="02",
                    heading="降氢键供体 (5→3)",
                    body="去除吲哚 NH 并引入三氟乙酰增强透膜。",
                    highlight="增强透膜",
                ),
            ],
            profile_card={
                "journal_badge": "SCIENCE 2021 · 文献档案",
                "paper_title": "An oral SARS-CoV-2 Mpro inhibitor clinical candidate",
                "authors": "Owen et al. · Science 374, 1586–1593",
                "metrics": [
                    ("靶点蛋白", "SARS-CoV-2 Mpro"),
                    ("酶学 Ki", "3.11 nM"),
                    ("细胞 EC50", "74.5 nM"),
                    ("分子式/MW", "C23H32F3N5O4 · 499.5"),
                ],
                "focus_text": "重构 P1 弹头与 P2/P3 氢键系统，将静脉先导转化为高活性口服候选药。",
            },
            bottom_banner={
                "mode": "bar",
                "badge": "关键突破",
                "text": "精细调控弹头反应性与极性表面积，首次在纳摩尔抗病毒活性下打通口服路径。",
            },
            footer_left=citation,
            speaker_notes=(
                "Owen et al. (Science 2021, 374, 1586-1593) optimized intravenous SARS-CoV-1 lead PF-00835231 (HBD=5) "
                "into oral Nirmatrelvir (PF-07321332, HBD=3, Ki=3.11 nM, Vero E6 EC50=74.5 nM)."
            ),
        ),
        SlideSpec(
            slide_no=3,
            slide_type=SlideType.content,
            layout_id=LayoutId.mechanism_3col_flow,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=1,
            section_name="02 三维构象与机理",
            eyebrow="SCIENCE 2021 · 3D CONFORMATION & MECHANISM",
            title="三维刚性构象预组织与 Cys145 可逆结合",
            takeaway="双环 [3.1.0] 脯氨酸锁定构象，引导氰基弹头与催化中心 Cys145 可逆加成。",
            takeaway_highlight="Cys145 可逆加成",
            left_cards=[
                {"heading": "P1 γ-内酰胺", "body": "与 His163/Glu166 形成双氢键锚定 S1。"},
                {"heading": "P2 双环脯氨酸", "body": "替代亮氨酸并消去酰胺 NH，降低熵损。"},
                {"heading": "P3 三氟乙酰基", "body": "增强 S4 疏水结合并阻断体内快速水解。"},
            ],
            figure_spec=FigureSpec(
                figure_id="fig_02",
                archetype=ArchetypeId.A04,
                visual_story_scale="molecular_3d_conformer",
                box_in=box2,
                assets=[
                    FigureAsset(
                        asset_id="nirmatrelvir_3d",
                        engine=EngineType.cylview_3d,
                        smiles=NIRMATRELVIR_SMILES,
                        label="Nirmatrelvir 3D (ETKDGv3)",
                        show_nonpolar_h=False,
                        norm_box=list(nb2),
                    )
                ],
                native_overlays=[
                    NativeOverlay(type="pocket_subsite", source_circle_in=[p1_xy[0], p1_xy[1], 0.50], color_token="s3"),
                    NativeOverlay(type="pocket_subsite", source_circle_in=[p2_xy[0], p2_xy[1], 0.48], color_token="s3"),
                    NativeOverlay(type="pocket_subsite", source_circle_in=[cf3_xy[0], cf3_xy[1], 0.48], color_token="s2"),
                    NativeOverlay(
                        type="pocket_subsite",
                        from_in=[round(cn_xy[0] + 0.58, 3), round(cn_xy[1] + 0.08, 3)],
                        to_in=[cn_xy[0], cn_xy[1]],
                        sublabel="Cys145–SH",
                        color_token="alert",
                    ),
                ],
                caption="Fig. 2  Deterministic 3D conformer of Nirmatrelvir.",
            ),
            callout_badges=[
                {"text": "P2 双环脯氨酸 (S2)", "x_in": 4.06, "y_in": 1.76, "w_in": 1.98, "target_x_in": p2_xy[0], "target_y_in": p2_xy[1], "color_token": "s1"},
                {"text": "P1 γ-内酰胺 (S1)", "x_in": 7.46, "y_in": 1.76, "w_in": 1.82, "target_x_in": p1_xy[0], "target_y_in": p1_xy[1], "color_token": "s1"},
                {"text": "P3 三氟乙酰 (S4)", "x_in": 4.06, "y_in": 5.36, "w_in": 1.82, "target_x_in": cf3_xy[0], "target_y_in": cf3_xy[1], "color_token": "s2"},
                {"text": "Cys145 氰基弹头", "x_in": 7.36, "y_in": 5.36, "w_in": 1.92, "target_x_in": cn_xy[0], "target_y_in": cn_xy[1], "color_token": "alert"},
            ],
            right_chain=[
                {"title": "MW = 499.5 Da", "body": "类药分子量与 PSA 均衡"},
                {"title": "HBD = 3 · 刚性高", "body": "构象锁定，有利跨膜渗透"},
                {"title": "可逆硫代亚胺酯", "body": "解离可控，显著降低脱靶"},
            ],
            bottom_banner={
                "mode": "triple_pill",
                "left": "刚性双环 · 低结合熵损",
                "center": "三维空间契合 + 可逆共价驱动",
                "right": "可逆 -CN · 高靶点选择性",
            },
            footer_left=citation,
            speaker_notes=(
                "CYLview3DEngine renders exact ETKDGv3 + MMFF94 3D geometry of Nirmatrelvir with clean heavy + polar-H styling."
            ),
        ),
        SlideSpec(
            slide_no=4,
            slide_type=SlideType.content,
            layout_id=LayoutId.data_dashboard_table,
            header_variant="nav_tabs",
            nav_sections=nav_tabs,
            active_nav_idx=2,
            section_name="03 药代与临床转化",
            eyebrow="SCIENCE 2021 · PRECLINICAL PK & PAXLOVID",
            title="临床前口服药代跃升与利托那韦增效",
            takeaway="Nirmatrelvir 大鼠口服 F 提升 35 倍，联用利托那韦抑制 CYP3A4 清除。",
            takeaway_highlight="提升 35 倍",
            kpis=[
                KpiItem(value="34–50%", label="大鼠口服生物利用度", color_token="s1"),
                KpiItem(value="35×", label="较先导暴露提升", color_token="s2"),
                KpiItem(value="5.1 h", label="大鼠半衰期 t1/2", color_token="s1"),
            ],
            figure_spec=FigureSpec(
                figure_id="fig_03",
                archetype=ArchetypeId.A06,
                visual_story_scale="quantitative_origin_plot",
                box_in=box3,
                assets=[
                    FigureAsset(
                        asset_id="pk_bar_plot",
                        engine=EngineType.origin_plot,
                        preset="paired_gain_bar",
                        data_verified=True,
                        plot_data={
                            "categories": ["Rat F (%)", "Rat Fa×Fg", "Cyno Fa×Fg", "Cyno F (%)"],
                            "control": [1.4, 8.0, 2.0, 0.8],
                            "this_work": [50.0, 95.0, 20.0, 8.5],
                            "control_label": "PF-00835231 (IV Lead)",
                            "work_label": "PF-07321332 (Nirmatrelvir)",
                            "deltas": ["↑35×", "↑12×", "↑10×", "↑10×"],
                            "ylabel": "Oral PK Metric (%)",
                        },
                    )
                ],
                caption="Fig. 3  Preclinical oral PK metrics.",
            ),
            table_data=TableData(
                headers=["对比参数", "PF-00835231", "Nirmatrelvir"],
                rows=[
                    ["给药方式", "静脉 (IV)", "口服 (PO)"],
                    ["Mpro Ki", "0.27 nM", "3.11 nM"],
                    ["HBD 供体数", "5", "3"],
                    ["Rat F (%)", "1.4%", "34–50%"],
                    ["Cyno F (%)", "< 1.0%", "8.5%"],
                ],
            ),
            strategy_cards=[
                {
                    "badge": "代谢瓶颈",
                    "badge_color": "#D97706",
                    "title": "CYP3A4 首过消除限制暴露",
                    "body": "食蟹猴口服 F 为 8.5%，肝微粒体氧化为主。",
                },
                {
                    "badge": "临床增效",
                    "badge_color": "#00468B",
                    "title": "Paxlovid 联合利托那韦",
                    "body": "Ritonavir 阻断 CYP3A4 代谢，维持稳态浓度。",
                },
            ],
            bottom_banner={
                "mode": "bar",
                "badge": "转化总结",
                "text": "降 HBD + 氰基弹头 + CYP3A4 增效，构筑抗病毒口服新药研发典范。",
            },
            footer_left=citation,
            speaker_notes=(
                "Oral bioavailability jumped 35-fold in rats (34-50%, Fa*Fg=65-95%) and reached 8.5% in cynomolgus monkeys. "
                "Co-dosing with ritonavir blocks CYP3A4 first-pass metabolism in Paxlovid."
            ),
        ),
    ]

    return DeckSpec(
        meta=DeckMeta(
            deck_id="science2021_nirmatrelvir",
            deck_title="Oral SARS-CoV-2 Mpro Inhibitor Nirmatrelvir (Science 2021)",
            deck_subtitle="Owen et al., Science 374, 1586–1593 (2021)",
            author="药物化学文献精读",
            affiliation="Academic PPT Studio",
            scenario=ScenarioType.literature_review,
            target_slide_count=4,
            palette_id="lancet",
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
