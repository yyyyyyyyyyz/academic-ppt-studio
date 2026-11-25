"""Verification for 5 Xiaohongshu defense layouts, custom HEX palettes, unified palette names & Skill sync."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_mod
from app.agents.art_director_agent import ArtDirectorAgent
from app.agents.outline_agent import load_word_outline_skill
from app.builder.ppt_core import compile_deck_to_pptx
from app.config import Settings
from app.figure_factory.factory import ScientificFigureFactory
from app.figure_factory.palettes import PALETTES, build_custom_palette, get_palette
from app.qa.audit_pptx import audit_pptx
from app.qa.slide_renderer import render_slide_preview_png
from app.schemas.deck_spec import (
    DeckMeta,
    DeckSpec,
    DesignStyle,
    InsightItem,
    KpiItem,
    LayoutId,
    SlideSpec,
    SlideType,
    V5_LAYOUT_IDS,
)


def test_unified_palette_names_and_custom_hex() -> None:
    assert len(PALETTES) == 15
    for pid, pal in PALETTES.items():
        assert " · " in pal.name, f"Palette {pid} missing unified separator in name: {pal.name}"

    custom = build_custom_palette("#1B6B52")
    assert custom.id == "custom_1B6B52"
    assert custom.s1 == "#1B6B52"
    assert len(custom.series) == 6
    assert get_palette("custom_1B6B52").s1 == "#1B6B52"
    assert get_palette("#7C3AED").id == "custom_7C3AED"


def test_custom_palette_apply_endpoint(tmp_path: Path, monkeypatch) -> None:
    test_settings = Settings(
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
    )
    monkeypatch.setattr(main_mod, "settings", test_settings)
    client = TestClient(main_mod.app)
    plan_res = client.post(
        "/api/plan",
        json={
            "source_text": "# Test\n## 1. 背景\nCC(=O)Oc1ccccc1C(=O)O 显示显著抑炎活性。",
            "target_slide_count": 4,
            "palette_id": "lancet",
            "design_style": "defense_modular",
        },
    )
    assert plan_res.status_code == 200
    deck_spec = plan_res.json()["deck_spec"]

    apply_res = client.post(
        "/api/palettes/apply",
        json={"deck_spec": deck_spec, "palette_id": "custom_1B6B52", "rerender_figures": True},
    )
    assert apply_res.status_code == 200
    body = apply_res.json()
    assert body["deck_spec"]["meta"]["palette_id"] == "custom_1B6B52"
    assert "slide_01" in body["artifact_urls"]


def test_five_new_xiaohongshu_layouts_compile_render_and_audit(tmp_path: Path) -> None:
    new_layouts = [
        LayoutId.timeline_chevron_flow,
        LayoutId.quadrant_2x2_matrix,
        LayoutId.hub_spoke_radial,
        LayoutId.dual_compare_cards,
        LayoutId.tri_column_showcase,
    ]
    director = ArtDirectorAgent()
    factory = ScientificFigureFactory()

    slides = [
        SlideSpec(
            slide_no=1,
            slide_type=SlideType.cover,
            layout_id=LayoutId.cover,
            title="答辩信息图排版综合测试",
            takeaway="验证五种小红书答辩排版引擎。",
        )
    ]
    for idx, lid in enumerate(new_layouts):
        sl = SlideSpec(
            slide_no=idx + 2,
            slide_type=SlideType.content,
            layout_id=lid,
            section_name=f"板块 {idx + 1}",
            title=f"核心版式验证 · {lid.value}",
            takeaway="通过可编辑原生矢量排版呈现结构化科研逻辑与定量指标。",
            kpis=[
                KpiItem(value="1.8 nM", label="IC50 活性", color_token="s1"),
                KpiItem(value="42.5%", label="口服生物利用度", color_token="s2"),
            ],
            insights=[
                InsightItem(index="01", heading="科学痛点突破", body="克服共价结合引起的耐药突变失效。", highlight="耐药突破"),
                InsightItem(index="02", heading="先导骨架优化", body="引入极性杂环改善水溶性与暴露量。", highlight="PK 优化"),
                InsightItem(index="03", heading="三维结合验证", body="分子对接揭示铰链区双齿氢键锚定。", highlight="双齿氢键"),
                InsightItem(index="04", heading="临床前转化", body="动物模型验证显著抑瘤且毒性极低。", highlight="高效低毒"),
            ],
        )
        sl = director.direct_slide(
            sl,
            palette_id="custom_1B6B52",
            detected_smiles=["COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4"],
            content_index=idx,
            design_style=DesignStyle.defense_modular,
            visual_plan={"layout_id": lid.value},
        )
        assert sl.layout_id == lid
        factory.render_figure_spec(
            sl.figure_spec,
            output_dir=tmp_path / f"fig_{idx + 2}",
            palette_id="custom_1B6B52",
        )
        slides.append(sl)

    deck = DeckSpec(
        meta=DeckMeta(
            deck_id="test_xhs_v5",
            deck_title="小红书答辩版式自动化验证",
            palette_id="custom_1B6B52",
            design_style=DesignStyle.defense_modular,
            target_slide_count=len(slides),
        ),
        slides=slides,
    )

    pptx_out = compile_deck_to_pptx(deck, tmp_path / "xhs_layouts.pptx")
    assert pptx_out.exists()

    report = audit_pptx(pptx_out, deck)
    assert report.passed, f"Audit failed: {[v.model_dump() for v in report.violations]}"
    assert report.overlap_count == 0
    assert report.out_of_bounds_count == 0
    assert report.min_any_pt_observed >= 13.5
    assert report.min_body_pt_observed >= 18.0

    for sl in slides[1:]:
        png_p = render_slide_preview_png(sl, deck, tmp_path / f"slide_{sl.slide_no:02d}.png")
        img = Image.open(png_p)
        assert img.size == (1920, 1080)


def test_word_outline_skill_lists_all_v5_layouts() -> None:
    skill_text = load_word_outline_skill()
    assert len(V5_LAYOUT_IDS) == 13
    for lid in V5_LAYOUT_IDS:
        assert lid.value in skill_text, f"Layout {lid.value} missing from word_to_outline_skill.md"
    for role_tok in ("s1", "s2", "s3", "alert"):
        assert role_tok in skill_text, f"Multi-color role {role_tok} missing from word_to_outline_skill.md"


def test_palette_slide_roles_multicolor_and_legible() -> None:
    for pid in list(PALETTES.keys()) + ["custom_1B6B52"]:
        pal = get_palette(pid)
        roles = pal.slide_roles()
        assert len(roles["accents"]) == 4
        assert len(roles["tints"]) == 4
        assert len(roles["borders"]) == 4
        assert len({c.upper() for c in roles["accents"]}) == 4, f"Duplicate accents in {pid}: {roles['accents']}"
        assert roles["alert"].startswith("#")
        for acc in roles["accents"]:
            r, g, b = (int(acc[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            assert luma <= 0.59, f"Accent {acc} in {pid} too bright for white badge text (luma={luma:.3f})"


def test_cylview3d_pbr_quality_and_pptx_picture_embed(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from app.figure_factory.alpha_matting import compute_alpha_edge_cleanliness
    from app.figure_factory.cylview3d_engine import render_cylview3d
    from app.schemas.deck_spec import ArchetypeId, EngineType, FigureAsset, FigureSpec

    fig_dir = tmp_path / "figs_3d"
    fig_dir.mkdir(parents=True, exist_ok=True)
    res3d = render_cylview3d("Osimertinib", fig_dir / "osimertinib_3d.png", palette_id="lancet", style_3d="ball_stick")
    assert res3d.atom_count > 50  # Explicit hydrogens enabled for small/medium drug molecules
    assert compute_alpha_edge_cleanliness(res3d.png_path) >= 8.5

    factory = ScientificFigureFactory()
    fig_spec = factory.render_figure_spec(
        FigureSpec(
            figure_id="fig_3d_pbr",
            archetype=ArchetypeId.A04,
            assets=[
                FigureAsset(
                    asset_id="osimertinib_3d",
                    engine=EngineType.cylview_3d,
                    smiles="Osimertinib",
                    style_3d="ball_stick",
                    label="3D Conformer (Osimertinib)",
                )
            ],
        ),
        output_dir=fig_dir / "factory",
        palette_id="lancet",
    )
    sl = SlideSpec(
        slide_no=1,
        slide_type=SlideType.content,
        layout_id=LayoutId.dual_compare_cards,
        section_name="结构对比",
        title="三维 PBR 嵌入验证",
        takeaway="自动将高清 3D PBR 渲染图嵌入 PPTX 幻灯片。",
        kpis=[KpiItem(value="1.4 nM", label="IC50", color_token="s1")],
        insights=[
            InsightItem(index="01", heading="立体构象", body="芳香双键与球棍高光清晰。", highlight="PBR"),
            InsightItem(index="02", heading="多色协同", body="s1/s2/s3/alert 分色呈现。", highlight="多色"),
        ],
        figure_spec=fig_spec,
    )
    deck = DeckSpec(
        meta=DeckMeta(deck_id="test_3d_embed", deck_title="3D PBR Test", palette_id="lancet", target_slide_count=3),
        slides=[sl],
    )
    pptx_path = compile_deck_to_pptx(deck, tmp_path / "embed_3d.pptx")
    prs = Presentation(str(pptx_path))
    pics = [shp for shp in prs.slides[0].shapes if shp.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) >= 1, "Expected 3D PBR PNG to be embedded as Picture in PPTX"
    report = audit_pptx(pptx_path, deck)
    assert report.passed, f"Audit failed: {[v.model_dump() for v in report.violations]}"
