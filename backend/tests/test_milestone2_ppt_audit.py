"""Milestone 2 Verification Tests: Native python-pptx Compiler, XML Dual Font, Baseline Sub/Sup, Audit & Word Sync."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from docx import Document
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from app.builder.ppt_core import compile_deck_to_pptx
from app.builder.word_sync import sync_word_into_pptx
from app.figure_factory.factory import ScientificFigureFactory
from app.qa.audit_pptx import audit_pptx
from app.qa.slide_renderer import render_deck_previews, render_slide_preview_png
from app.schemas.deck_spec import (
    ArchetypeId,
    DeckMeta,
    DeckSpec,
    EngineType,
    FigureAsset,
    FigureBoxIn,
    FigureSpec,
    InsightItem,
    KpiItem,
    LayoutId,
    NativeOverlay,
    SlideSpec,
    SlideType,
    TableData,
)


def _sample_deck() -> DeckSpec:
    return DeckSpec(
        meta=DeckMeta(
            deck_id="test_m2",
            deck_title="无溶剂球磨介导非贵金属催化 C–N 偶联机制研究",
            deck_subtitle="基于孔道限域调控与高通量表征的绿色合成新策略",
            author="张三",
            affiliation="药物化学研究所",
            target_slide_count=4,
            palette_id="lancet",
        ),
        slides=[
            SlideSpec(
                slide_no=1,
                slide_type=SlideType.cover,
                layout_id=LayoutId.cover,
                eyebrow="THESIS DEFENSE · MEDICINAL CHEMISTRY",
                title="封面",
                figure_spec=FigureSpec(
                    figure_id="fig_cover",
                    archetype=ArchetypeId.A01,
                    box_in=FigureBoxIn(left=7.35, top=1.45, width=5.40, height=4.55),
                    assets=[FigureAsset(asset_id="cover_3d", engine=EngineType.sci3d_art, render_mode="c4d_octane_cutaway")],
                    caption="",
                ),
            ),
            SlideSpec(
                slide_no=2,
                slide_type=SlideType.content,
                layout_id=LayoutId.frameless_63_37,
                eyebrow="SECTION 01 · INTERFACIAL MECHANISM",
                title="机械剪切与孔道限域协同降低 C–N 偶联活化能垒",
                takeaway="ZSM-5 孔道限域捕获 H2O 副产物并稳定 Ni2+ 活性中心，实现 45 分钟高效偶联。",
                figure_spec=FigureSpec(
                    figure_id="fig_02",
                    archetype=ArchetypeId.A01,
                    box_in=FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42),
                    assets=[
                        FigureAsset(asset_id="reactor", engine=EngineType.sci3d_art, render_mode="c4d_octane_cutaway", norm_box=[0.0, 0.0, 0.68, 1.0]),
                        FigureAsset(asset_id="mol", engine=EngineType.chemdraw_rdkit, smiles="c1ccc(CNc2ccccc2)cc1", highlight_atoms=[7], norm_box=[0.66, 0.15, 0.34, 0.70]),
                    ],
                    native_overlays=[
                        NativeOverlay(type="zoom_lens_frame", source_circle_in=[2.3, 3.8, 0.42], target_circle_in=[5.2, 3.8, 1.42], color_token="s1"),
                    ],
                    caption="Fig. 1  Cutaway ball-mill reactor and confined active pocket driving H2O sequestration.",
                ),
                kpis=[
                    KpiItem(value="91.2%", label="分离收率", color_token="s1"),
                    KpiItem(value="-91.7%", label="溶剂减废", color_token="alert"),
                ],
                insights=[
                    InsightItem(index="01", heading="无溶剂剪切传质", body="局部高能碰撞打破固体晶格扩散限制。", highlight="打破固体晶格"),
                    InsightItem(index="02", heading="副产 H2O 原位锁定", body="微孔限域消除逆向水解并提升选择性。", highlight="消除逆向水解"),
                ],
                speaker_notes="Detailed experimental stoichiometry and GC-MS calibration notes.",
            ),
            SlideSpec(
                slide_no=3,
                slide_type=SlideType.content,
                layout_id=LayoutId.frameless_63_37,
                eyebrow="SECTION 02 · QUANTITATIVE KINETICS",
                title="表观动力学与三线表数据定量互证催化优势",
                takeaway="本工作速率常数提升 2.4 倍且 48 h 稳定性保持 98.1%，显著优于传统均相体系。",
                figure_spec=FigureSpec(
                    figure_id="fig_03",
                    archetype=ArchetypeId.A06,
                    box_in=FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42),
                    assets=[FigureAsset(asset_id="kin_plot", engine=EngineType.origin_plot, preset="paired_gain_bar", data_verified=True)],
                    caption="Fig. 2  Substrate scope comparison across aryl halides with direct percentage gains.",
                ),
                table_data=TableData(
                    headers=["Entry", "Catalyst", "Yield (%)", "PMI"],
                    rows=[
                        ["1", "Ni@ZSM-5", "91.2", "4.8"],
                        ["2", "Conv. Ref", "62.4", "58.2"],
                    ],
                ),
                insights=[
                    InsightItem(index="01", heading="过程绿色度跃升", body="过程质量强度 PMI 由 58.2 降至 4.8。", highlight="由 58.2 降至 4.8"),
                ],
            ),
            SlideSpec(
                slide_no=4,
                slide_type=SlideType.closing,
                layout_id=LayoutId.closing,
                title="敬请各位专家批评指正",
                takeaway="张三 · 药物化学研究所",
            ),
        ],
    )


def test_compile_audit_and_word_sync(tmp_path: Path) -> None:
    deck = _sample_deck()
    factory = ScientificFigureFactory()
    for sl in deck.slides:
        if sl.figure_spec:
            factory.render_figure_spec(sl.figure_spec, tmp_path / "figs" / f"s{sl.slide_no}", palette_id=deck.meta.palette_id)

    pptx_p = compile_deck_to_pptx(deck, tmp_path / "demo.pptx")
    assert pptx_p.exists()

    # Check native XML baseline on H2O and Ni2+ (slide 2 takeaway)
    prs = Presentation(str(pptx_p))
    slide2 = prs.slides[1]
    baselines = []
    for shp in slide2.shapes:
        if shp.has_text_frame and getattr(shp, "name", "") == "L3_takeaway":
            for r in shp.text_frame.paragraphs[0].runs:
                rPr = r._r.find(qn("a:rPr"))
                if rPr is not None and "baseline" in rPr.attrib:
                    baselines.append((r.text, rPr.attrib["baseline"]))
    assert any(txt == "2" and b == "-25000" for txt, b in baselines)
    assert any(txt == "2+" and b == "30000" for txt, b in baselines)

    # Check native editable GroupShape molecule (slide 2) & native Excel-backed Chart (slide 3)
    assert any(shp.shape_type == MSO_SHAPE_TYPE.GROUP and shp.name.startswith("L1_") for shp in slide2.shapes)
    slide3 = prs.slides[2]
    assert any(getattr(shp, "has_chart", False) for shp in slide3.shapes)

    report = audit_pptx(pptx_p, deck_spec=deck)
    assert report.passed is True, f"Audit failed: {report.violations}"
    assert report.filled_body_boxes == 0
    assert report.unicode_sub_sup_count == 0
    assert report.missing_xml_font_runs == 0
    assert report.min_body_pt_observed >= 18.0
    assert report.min_any_pt_observed >= 14.0

    # Render full + layer-separated previews
    previews = render_deck_previews(deck, tmp_path / "previews", pptx_path=pptx_p)
    assert len(previews) == 4 and all(p.exists() for p in previews)
    l1_only = render_slide_preview_png(deck.slides[1], deck, tmp_path / "s2_l1.png", layers=("L1",))
    assert l1_only.exists()

    # Word sync test preserving XML fonts
    docx_p = tmp_path / "update.docx"
    doc = Document()
    doc.add_heading("机械剪切与孔道限域协同降低 C–N 偶联活化能垒", level=1)
    doc.add_paragraph("更新结论：ZSM-5 限域微孔可高效锁定 H2O 并加速反应，在 35 分钟内实现 93% 收率与完整催化剂循环复用。")
    doc.save(str(docx_p))

    synced_pptx = tmp_path / "synced.pptx"
    sync_res = sync_word_into_pptx(docx_p, pptx_p, synced_pptx)
    assert 2 in sync_res["updated_slides"]
    synced_report = audit_pptx(synced_pptx, deck_spec=deck)
    assert synced_report.passed is True
