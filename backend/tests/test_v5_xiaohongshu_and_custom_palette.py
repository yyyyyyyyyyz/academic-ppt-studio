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
