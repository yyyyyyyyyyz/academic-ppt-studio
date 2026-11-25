"""Tests for Zero-LLM Structured Word (.docx) -> PPT Conversion (Real Paragraphs, Tables, Images & Per-Section SMILES)."""

from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from docx import Document
from docx.shared import Inches
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app.main as main_mod
from app.config import Settings


_BANNED_PLACEHOLDERS = (
    "微观限域微环境",
    "同色标下精准对齐",
    "无中途开罐",
    "62.4%",
    "底物活化",
    "限域预组织",
)


def _create_sample_word_docx(docx_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("新型第四代EGFR变构抑制剂设计与成药性研究")

    doc.add_heading("1. 研究背景与耐药痛点", level=1)
    doc.add_paragraph(
        "第三代共价抑制剂在连续给药后诱发 C797S 三重耐药突变，对照药物 Osimertinib（"
        "SMILES：COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34 ）对突变体活性下降超过 100 倍。"
    )
    doc.add_paragraph("因此亟需开发高选择性非共价变构抑制剂，避免野生型脱靶毒性。")

    doc.add_heading("2. 骨架跃迁与先导化合物优化", level=1)
    doc.add_paragraph(
        "基于苯胺基喹唑啉核心（SMILES：COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4 ）引入吗啉极性侧链，"
        "先导分子 YJ-402 满足 cLogP = 3.1 与 TPSA = 86 Å²，完整通过 Lipinski 五规则。"
    )

    doc.add_heading("3. 关键催化合成路线", level=1)
    doc.add_paragraph(
        "采用 Pd 催化交叉偶联路线制备核心中间体（SMILES：Cc1nc(Nc2ncc(s2)C(=O)Nc3c(C)cccc3Cl)cc(n1)N4CCN(CCO)CC4 ），"
        "优化后单步分离收率达 93.5%，金属残留低于 4 ppm。"
    )

    doc.add_heading("4. 分子对接与结合模式图解", level=1)
    doc.add_paragraph("诱导契合分子对接表明先导分子与 Met793 形成双齿氢键，结合自由能 ΔG_bind = -11.4 kcal/mol。")
    # Embed a genuine PNG plot directly inside Section 4 of Word
    img_buf = BytesIO()
    im = Image.new("RGBA", (420, 300), (255, 255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle([30, 30, 390, 270], outline=(153, 27, 27, 255), width=6)
    draw.ellipse([120, 80, 300, 220], fill=(0, 70, 139, 180))
    im.save(img_buf, format="PNG")
    img_buf.seek(0)
    doc.add_picture(img_buf, width=Inches(3.2))

    doc.add_heading("5. 体外酶学与体内药代动力学评价", level=1)
    doc.add_paragraph(
        "YJ-402 对 C797S 突变体 IC50 = 1.8 nM，野生型 WT-EGFR IC50 = 261 nM，选择性高达 145 倍；"
        "小鼠口服生物利用度 F = 64.5%，半衰期 t1/2 = 6.8 h，抑瘤率 TGI = 88.4%。"
    )
    tbl = doc.add_table(rows=3, cols=4)
    headers = ["化合物", "C797S IC50", "WT-EGFR IC50", "口服 F / TGI"]
    rows = [
        ["Osimertinib", "580 nM", "184 nM", "临床对照"],
        ["YJ-402", "1.8 nM", "261 nM", "64.5% / 88.4%"],
    ]
    for c_idx, h in enumerate(headers):
        tbl.rows[0].cells[c_idx].text = h
    for r_idx, r_vals in enumerate(rows, start=1):
        for c_idx, v in enumerate(r_vals):
            tbl.rows[r_idx].cells[c_idx].text = v

    doc.add_heading("6. 总结与后续开发计划", level=1)
    doc.add_paragraph("下一步推进 hERG 心脏安全性筛查与复合物单晶解析。")

    docx_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(docx_path))


def test_zero_llm_docx_upload_extracts_real_prose_tables_images_and_smiles(tmp_path: Path, monkeypatch) -> None:
    test_settings = Settings(
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
        llm_provider_mode="local",
        figure_provider_mode="local",
    )
    monkeypatch.setattr(main_mod, "settings", test_settings)
    client = TestClient(main_mod.app)

    docx_path = tmp_path / "egfr_study.docx"
    _create_sample_word_docx(docx_path)

    with docx_path.open("rb") as f:
        resp = client.post(
            "/api/plan/upload",
            headers={"X-LLM-Provider": "local"},
            data={
                "target_slide_count": "9",
                "palette_id": "nature_crimson",
                "scenario": "defense",
                "is_proposal": "false",
                "design_style": "defense_modular",
            },
            files={"file": ("egfr_study.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    deck = data["deck_spec"]
    slides = deck["slides"]
    assert len(slides) == 9
    assert deck["meta"]["deck_title"] == "新型第四代EGFR变构抑制剂设计与成药性研究"

    content_slides = [sl for sl in slides if sl["slide_type"] == "content"]
    assert len(content_slides) == 6

    # 1. Verify ZERO hardcoded placeholder boilerplate leaked into any content slide
    full_blob = str(content_slides)
    for banned in _BANNED_PLACEHOLDERS:
        assert banned not in full_blob, f"Hardcoded placeholder '{banned}' leaked into zero-LLM slide output"

    # 2. Verify real Word table (YJ-402 / Osimertinib) is preserved on Section 5
    sec5_slide = next(sl for sl in content_slides if "体外酶学" in sl["title"])
    assert sec5_slide["layout_id"] == "data_dashboard_table"
    assert sec5_slide["table_data"] is not None
    table_text = str(sec5_slide["table_data"])
    assert "YJ-402" in table_text and "1.8 nM" in table_text
    assert any("1.8 nM" in k["value"] or "64.5%" in k["value"] or "88.4%" in k["value"] for k in sec5_slide["kpis"])

    # 3. Verify embedded Word image inside Section 4 was extracted and bound cleanly
    sec4_slide = next(sl for sl in content_slides if "分子对接" in sl["title"])
    sec4_asset = sec4_slide["figure_spec"]["assets"][0]
    assert sec4_asset["engine"] == "uploaded_image"
    assert "word_images" in sec4_asset["png_path"]
    asset_url = data["asset_urls"][sec4_asset["asset_id"]]["png_url"]
    assert client.get(asset_url).status_code == 200

    # 4. Verify multiple distinct SMILES extracted across sections (not all locked to SMILES[0])
    rendered_smiles = {
        a.get("smiles")
        for sl in content_slides
        if sl.get("figure_spec")
        for a in sl["figure_spec"].get("assets", [])
        if a.get("smiles") and a.get("asset_id") != f"fig_{sl['slide_no']:02d}_sub"
    }
    assert len(rendered_smiles) >= 2, f"Expected multiple distinct SMILES across slides, got: {rendered_smiles}"

    # 5. Build native editable .pptx & verify audit passes 100%
    build_resp = client.post("/api/build/pptx", json={"deck_spec": deck, "run_qa_loop": True})
    assert build_resp.status_code == 200
    audit = build_resp.json()["audit_report"]
    assert audit["passed"] is True, f"Audit failed: {audit}"
