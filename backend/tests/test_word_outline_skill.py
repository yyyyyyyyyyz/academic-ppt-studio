"""Tests for Skill-driven Word -> PPT Outline framework (`word_to_outline_skill.md`, `OutlineAgent`, `/api/outline/from-file`)."""

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
from fastapi.testclient import TestClient

import app.main as main_mod
from app.agents.outline_agent import load_word_outline_skill
from app.config import Settings


def _make_sample_docx(path: Path) -> None:
    doc = Document()
    doc.add_paragraph("新型非共价 EGFR C797S 变构抑制剂设计")
    doc.add_heading("1. 研究背景与耐药痛点", level=1)
    doc.add_paragraph("Osimertinib 长期给药诱发 C797S 耐药突变，亟需开发新型非共价变构抑制剂。")
    doc.add_heading("2. 先导优化与构效关系", level=1)
    doc.add_paragraph(
        "基于嘧啶胺核心（SMILES: COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4）优化，"
        "化合物 YJ-402 对 C797S IC50 = 1.8 nM，选择性 145 倍。"
    )
    tbl = doc.add_table(rows=2, cols=3)
    tbl.rows[0].cells[0].text = "化合物"
    tbl.rows[0].cells[1].text = "C797S IC50"
    tbl.rows[0].cells[2].text = "口服 F"
    tbl.rows[1].cells[0].text = "YJ-402"
    tbl.rows[1].cells[1].text = "1.8 nM"
    tbl.rows[1].cells[2].text = "64.5%"
    doc.add_heading("3. 3D 结合构象与总结", level=1)
    doc.add_paragraph("3D 分子对接显示与 Met793 形成稳定氢键。")
    doc.save(str(path))


def test_word_outline_skill_endpoint_and_prompt_loading(tmp_path: Path, monkeypatch) -> None:
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

    skill_txt = load_word_outline_skill()
    assert "visual_mode" in skill_txt and "acs1996" in skill_txt and "ball_stick" in skill_txt

    resp = client.get("/api/skills/word-outline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "word-to-ppt-outline"
    assert "word-to-ppt-outline" in data["content"]


def test_outline_from_docx_local_and_llm_mock(tmp_path: Path, monkeypatch) -> None:
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

    docx_p = tmp_path / "sample.docx"
    _make_sample_docx(docx_p)

    # 1. Deterministic local outline extraction
    with docx_p.open("rb") as f:
        r_local = client.post(
            "/api/outline/from-file",
            data={"target_slide_count": "6", "scenario": "defense", "is_proposal": "false"},
            files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert r_local.status_code == 200, r_local.text
    d_loc = r_local.json()
    assert d_loc["engine_used"] == "local"
    assert d_loc["content_slide_count"] == 3
    assert d_loc["table_count"] == 1
    assert len(d_loc["detected_compounds"]) >= 1
    assert "## 1." in d_loc["outline_markdown"]

    # 2. Skill-driven LLM path (mock ModelProvider)
    captured_prompts: list[str] = []

    def fake_backend(self) -> str:
        return "openai"

    def fake_gen_json(self, system_prompt: str, user_prompt: str, timeout: float = 45.0):
        captured_prompts.append(system_prompt)
        return {
            "title": "第四代 EGFR 变构抑制剂研发汇报",
            "summary": "围绕耐药痛点完成 YJ-402 结构设计与构效验证。",
            "slides": [
                {
                    "section_name": "背景与痛点",
                    "title": "Osimertinib 诱发 C797S 耐药",
                    "takeaway": "亟需非共价变构抑制剂克服 C797S 突变。",
                    "bullets": ["C797S 突变阻断共价结合", "明确变构口袋靶向策略"],
                    "kpis": [{"value": "1.8 nM", "label": "C797S IC50"}],
                    "compound_name": "Osimertinib",
                    "smiles": "",
                    "visual_mode": "2d",
                    "visual_style": "acs1996",
                    "layout_id": "pain_points_left_arrows",
                },
                {
                    "section_name": "结合构象",
                    "title": "Met793 氢键锁定 3D 构象",
                    "takeaway": "吲哚骨架与 Met793 形成稳定双齿氢键。",
                    "bullets": ["3D 构象契合非共价疏水口袋", "口服生物利用度达 64.5%"],
                    "kpis": [{"value": "64.5%", "label": "口服 F"}],
                    "compound_name": "Gefitinib",
                    "smiles": "",
                    "visual_mode": "3d",
                    "visual_style": "pymol_neon_green",
                    "layout_id": "mechanism_3col_flow",
                },
            ],
        }

    from app.providers.llm_image_provider import ModelProvider

    monkeypatch.setattr(ModelProvider, "active_text_backend", fake_backend)
    monkeypatch.setattr(ModelProvider, "generate_json", fake_gen_json)

    with docx_p.open("rb") as f:
        r_llm = client.post(
            "/api/outline/from-file",
            data={"target_slide_count": "5", "scenario": "defense", "is_proposal": "false"},
            files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert r_llm.status_code == 200, r_llm.text
    d_llm = r_llm.json()
    assert d_llm["engine_used"] == "openai"
    assert len(captured_prompts) == 1 and "word-to-ppt-outline/" in captured_prompts[0]
    assert d_llm["slides"][0]["smiles"] != ""
    assert d_llm["slides"][1]["visual_mode"] == "3d"
    assert "Osimertinib 诱发 C797S 耐药" in d_llm["outline_markdown"]


def test_full_5_stage_deck_with_dividers_and_native_editable_pptx(tmp_path: Path, monkeypatch) -> None:
    from PIL import Image
    from io import BytesIO

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

    plan_resp = client.post(
        "/api/plan",
        json={
            "source_text": (
                "# 非共价 EGFR 变构抑制剂设计与构效关系\n"
                "## 1. 背景痛点\nOsimertinib 产生 C797S 耐药突变。\n"
                "## 2. 骨架优化\n引入吗啉尾链提升选择性 145 倍。SMILES: COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4\n"
                "## 3. 3D 结合模式\nMet793 双齿氢键稳定结合。\n"
                "## 4. 定量评价\nYJ-402 IC50 = 1.8 nM，口服生物利用度 F = 64.5%。\n"
                "## 5. 总结展望\n推进 hERG 安全筛查。"
            ),
            "target_slide_count": 10,
            "palette_id": "lancet",
            "scenario": "defense",
            "is_proposal": False,
            "include_dividers": True,
        },
    )
    assert plan_resp.status_code == 200, plan_resp.text
    pdata = plan_resp.json()
    deck = pdata["deck_spec"]
    slide_types = [s["slide_type"] for s in deck["slides"]]
    for required_t in ("cover", "toc", "part_divider", "content", "closing"):
        assert required_t in slide_types, f"Missing {required_t} in {slide_types}"

    # Verify Full HD 1920x1080 preview resolution
    p_bytes = client.get(pdata["artifact_urls"]["slide_01"]).content
    with Image.open(BytesIO(p_bytes)) as im:
        assert im.size == (1920, 1080)

    # Verify 100% natively editable PPTX export passes visual/structural audit across all upgraded layouts
    build_resp = client.post("/api/build/pptx", json={"deck_spec": deck, "run_qa_loop": True})
    assert build_resp.status_code == 200
    audit = build_resp.json()["audit_report"]
    assert audit["passed"] is True, f"Audit failed: {audit}"
    assert audit["filled_body_boxes"] == 0
