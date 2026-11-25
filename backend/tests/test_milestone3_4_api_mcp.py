"""Milestone 3 & 4 Verification Tests: FastAPI Endpoints, Multi-Agent Planner, QA & MCP Tools."""

from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from PIL import Image
from docx import Document

import app.main as main_mod
from app import mcp_server
from app.config import Settings


def test_fastapi_full_workflow_and_mcp(tmp_path: Path, monkeypatch) -> None:
    # Redirect artifacts to pytest tmp_path so sandbox stays 100% isolated
    test_settings = Settings(
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
    )
    monkeypatch.setattr(main_mod, "settings", test_settings)

    client = TestClient(main_mod.app)

    # 1. Health, palettes (15), archetypes (10)
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/palettes").json()["palettes"]) == 15
    assert len(client.get("/api/archetypes").json()["archetypes"]) == 10

    # 2. Plan a 6-slide deck (free slide count + Art Director assignment)
    plan_resp = client.post("/api/plan", json={
        "source_text": "# 无溶剂机械化学催化 C-N 偶联\n## 1. 背景痛点\n传统反应需要大量有毒溶剂。\n## 2. 技术路线\n无溶剂球磨协同分子筛限域催化。\n## 3. 动力学定量\n产物收率 91.2%，SMILES: CN(C)CCN(Cc1ccccc1)c2ccccn2",
        "target_slide_count": 6,
        "palette_id": "lancet",
        "scenario": "defense",
        "is_proposal": False,
    })
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    deck_spec = plan_data["deck_spec"]
    deck_id = deck_spec["meta"]["deck_id"]
    assert len(deck_spec["slides"]) == 6

    # Verify TOC on slide 2, first content slide on slide 3 with a figure_spec, and preview serves cleanly
    assert deck_spec["slides"][1]["slide_type"] == "toc"
    content_sl = deck_spec["slides"][2]
    c_no = content_sl["slide_no"]
    assert content_sl["figure_spec"] is not None
    preview_url = plan_data["artifact_urls"][f"slide_{c_no:02d}"]
    assert client.get(preview_url).status_code == 200

    # 3. Single-slide FigureWorkbench: switch archetype to A05 ChemDraw & refine
    refine_resp = client.post("/api/figures/select-or-refine", json={
        "deck_id": deck_id,
        "slide_no": c_no,
        "palette_id": "lancet",
        "figure_spec": content_sl["figure_spec"],
        "archetype_override": "A05_chemdraw_halo",
        "smiles_override": "c1ccc(CNc2ccccc2)cc1",
        "fixed_bond_length_px": 30,
    })
    assert refine_resp.status_code == 200
    refined_fspec = refine_resp.json()["figure_spec"]
    assert refined_fspec["archetype"] == "A05_chemdraw_halo"
    assert refined_fspec["qa_passed"] is True
    content_sl["figure_spec"] = refined_fspec

    # 4. Upload a custom high-res figure replacement
    buf = BytesIO()
    Image.new("RGBA", (400, 300), (0, 70, 139, 255)).save(buf, format="PNG")
    buf.seek(0)
    up_resp = client.post(
        "/api/figures/upload",
        data={"deck_id": deck_id, "slide_no": str(c_no), "asset_id": "custom_upload"},
        files={"file": ("custom.png", buf, "image/png")},
    )
    assert up_resp.status_code == 200
    assert client.get(up_resp.json()["png_url"]).status_code == 200

    # 5. Hot-switch global palette across all slides + backend re-render
    pal_resp = client.post("/api/palettes/apply", json={
        "deck_spec": deck_spec,
        "palette_id": "sci_angew_blue_orange",
        "rerender_figures": True,
    })
    assert pal_resp.status_code == 200
    updated_deck = pal_resp.json()["deck_spec"]
    assert updated_deck["meta"]["palette_id"] == "sci_angew_blue_orange"

    # 6. Build native editable .pptx + run audit_pptx
    build_resp = client.post("/api/build/pptx", json={"deck_spec": updated_deck, "run_qa_loop": True})
    assert build_resp.status_code == 200
    build_data = build_resp.json()
    assert build_data["audit_report"]["passed"] is True, f"Audit violations: {build_data['audit_report']}"
    assert build_data["audit_report"]["filled_body_boxes"] == 0
    assert client.get(build_data["pptx_url"]).status_code == 200

    # 7. Word sync endpoint
    docx_buf = BytesIO()
    doc = Document()
    doc.add_heading(updated_deck["slides"][2]["title"], level=1)
    doc.add_paragraph("同步更新的精炼核心结论：固相限域催化将反应温度降低至室温。")
    doc.save(docx_buf)
    docx_buf.seek(0)
    sync_resp = client.post(
        "/api/sync/word",
        data={"deck_id": deck_id},
        files={"docx_file": ("updated.docx", docx_buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert sync_resp.status_code == 200
    assert client.get(sync_resp.json()["synced_pptx_url"]).status_code == 200

    # 8. Verify MCP tools work cleanly
    import asyncio
    tools = asyncio.run(mcp_server.mcp.list_tools())
    tool_names = {t.name for t in tools}
    assert {
        "list_palettes_and_archetypes",
        "plan_academic_deck",
        "generate_scientific_figure",
        "build_and_audit_pptx",
        "audit_existing_pptx",
        "sync_word_to_pptx",
    }.issubset(tool_names)
    pal_arch_json = json.loads(mcp_server.list_palettes_and_archetypes())
    assert len(pal_arch_json["palettes"]) == 15
    assert len(pal_arch_json["archetypes"]) == 10
    mcp_plan = json.loads(mcp_server.plan_academic_deck("测试开题报告研究方案与拟开展实验", target_slide_count=12, is_proposal=True))
    assert len(mcp_plan["slides"]) == 12
    # Medium deck (11..18) automatically includes cover + toc + closing
    assert mcp_plan["slides"][1]["slide_type"] == "toc"

    # 9. Verify v5.0 defense_modular planner assigns diverse modular layouts & passes audit_pptx
    from app.agents.planner_agent import PlannerAgent
    from app.agents.qa_agent import SlideVisualQAAgent
    from app.figure_factory.factory import ScientificFigureFactory
    from app.schemas.deck_spec import DesignStyle, SlideType, V5_LAYOUT_IDS

    v5_deck = PlannerAgent().plan_deck(
        source_text="# 新型纳米限域催化体系研究\n## 1. 研究背景\n传统均相工艺废弃物多。\n## 2. 研究痛点\n催化剂易团聚。\n## 3. 技术路线\n四阶段闭环设计。\n## 4. 催化机理\n双环耦合降能垒。\n## 5. 定量数据\n收率 91.2%。\n## 6. 表征验证\n原位谱学互证。",
        target_slide_count=8,
        palette_id="lancet",
        design_style=DesignStyle.defense_modular,
        deck_id="test_v5_planner",
    )
    v5_content_layouts = [s.layout_id for s in v5_deck.slides if s.slide_type == SlideType.content]
    assert len(set(v5_content_layouts)) >= 4
    assert all(lid in V5_LAYOUT_IDS for lid in v5_content_layouts)
    qa_agent = SlideVisualQAAgent(factory=ScientificFigureFactory(settings=test_settings))
    _, v5_report, v5_previews = qa_agent.build_and_verify(v5_deck, tmp_path / "v5_out")
    assert v5_report.passed is True, f"v5 audit failed: {v5_report.violations}"
    assert v5_report.min_any_pt_observed >= 13.0
    assert len(v5_previews) == 8


def test_byok_headers_and_llm_test_endpoint(monkeypatch) -> None:
    from app.providers.llm_image_provider import ModelProvider, settings_from_request_headers

    base = Settings()
    # Default/local stays isolated and does not mutate base
    req_openai = settings_from_request_headers(
        base,
        {
            "X-LLM-Provider": "openai",
            "X-LLM-Api-Key": "sk-secret-123",
            "X-LLM-Base-Url": "https://api.deepseek.com/v1/",
            "X-LLM-Model": "deepseek-chat",
        },
    )
    assert req_openai.llm_provider_mode == "openai"
    assert req_openai.openai_api_key == "sk-secret-123"
    assert req_openai.openai_base_url == "https://api.deepseek.com/v1"
    assert req_openai.openai_text_model == "deepseek-chat"
    assert req_openai.figure_provider_mode == "local"
    assert base.openai_api_key == ""

    client = TestClient(main_mod.app)
    # 1. Local test succeeds cleanly
    local_res = client.post("/api/llm/test", headers={"X-LLM-Provider": "local"})
    assert local_res.status_code == 200
    assert local_res.json()["ok"] is True
    assert local_res.json()["backend"] == "local"

    # 2. Mock OpenAI-compatible BYOK ping & ensure secret scrubbing on errors
    class _FakeResp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class _OkHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            assert url == "https://api.deepseek.com/v1/chat/completions"
            assert headers["Authorization"] == "Bearer sk-secret-123"
            assert json["model"] == "deepseek-chat"
            return _FakeResp({"choices": [{"message": {"content": '{"pong": true}'}}]})

    import app.providers.llm_image_provider as prov_mod

    monkeypatch.setattr(prov_mod.httpx, "Client", _OkHttpClient)
    ok_res = client.post(
        "/api/llm/test",
        headers={
            "X-LLM-Provider": "openai",
            "X-LLM-Api-Key": "sk-secret-123",
            "X-LLM-Base-Url": "https://api.deepseek.com/v1",
            "X-LLM-Model": "deepseek-chat",
        },
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["ok"] is True
    assert ok_res.json()["backend"] == "openai"
    assert ok_res.json()["model"] == "deepseek-chat"

    class _ErrHttpClient(_OkHttpClient):
        def post(self, url, headers=None, json=None):
            raise RuntimeError("Upstream rejected key sk-secret-123")

    monkeypatch.setattr(prov_mod.httpx, "Client", _ErrHttpClient)
    err_res = client.post(
        "/api/llm/test",
        headers={
            "X-LLM-Provider": "openai",
            "X-LLM-Api-Key": "sk-secret-123",
            "X-LLM-Base-Url": "https://api.deepseek.com/v1",
            "X-LLM-Model": "deepseek-chat",
        },
    )
    assert err_res.status_code == 200
    body = err_res.json()
    assert body["ok"] is False
    assert "sk-secret-123" not in body["message"]
    assert "***" in body["message"]
    assert ModelProvider(base).active_text_backend() == "local"


def test_single_port_spa_static_serving(tmp_path: Path, monkeypatch) -> None:
    dist_dir = tmp_path / "frontend" / "dist"
    (dist_dir / "assets").mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>Academic Studio</body></html>", encoding="utf-8")
    (dist_dir / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")

    test_settings = Settings(
        repo_root=tmp_path,
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
    )
    monkeypatch.setattr(main_mod, "settings", test_settings)

    client = TestClient(main_mod.app)
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "Academic Studio" in root_resp.text

    asset_resp = client.get("/assets/app.js")
    assert asset_resp.status_code == 200
    assert "console.log('ok')" in asset_resp.text

    missing_api = client.get("/api/does-not-exist")
    assert missing_api.status_code == 404


def test_all_5_cover_templates_multi_palette_audit(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from app.builder.ppt_core import compile_deck_to_pptx
    from app.qa.audit_pptx import audit_pptx
    from app.qa.slide_renderer import render_slide_preview_png
    from app.schemas.deck_spec import CoverTemplateId, DeckMeta, DeckSpec, DesignStyle, SlideSpec, SlideType

    pairs = [
        (CoverTemplateId.hero_band_bottom_bar, "nejm"),
        (CoverTemplateId.top_bottom_bands_framed, "lancet"),
        (CoverTemplateId.floating_rounded_hero_card, "nature"),
        (CoverTemplateId.left_aligned_rounded_panel, "science"),
        (CoverTemplateId.chevron_v_cut_banner, "immunology"),
    ]
    for tpl_id, pal_id in pairs:
        cover = SlideSpec(
            slide_no=1,
            slide_type=SlideType.cover,
            title="基于分子对接与绿色催化的新型先导化合物研究",
            takeaway="Target molecule-mediated selective activation & catalytic C–N synthesis",
        )
        deck = DeckSpec(
            meta=DeckMeta(
                deck_id=f"cov_{tpl_id.value}",
                deck_title="基于分子对接与绿色催化的新型先导化合物研究",
                deck_subtitle="Target molecule-mediated selective activation & catalytic C–N synthesis",
                author="李明",
                affiliation="药学院计算药化研究所",
                advisor="张教授",
                date_str="2026 年 11 月",
                palette_id=pal_id,
                design_style=DesignStyle.defense_modular,
                cover_template=tpl_id,
                target_slide_count=3,
            ),
            slides=[cover],
        )
        out_pptx = tmp_path / f"{tpl_id.value}_{pal_id}.pptx"
        compile_deck_to_pptx(deck, out_pptx)
        prs = Presentation(str(out_pptx))
        pics = [s for s in prs.slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        assert pics == [], f"{tpl_id.value} should be 100% native vector shapes"

        report = audit_pptx(out_pptx, deck_spec=deck)
        assert report.passed is True, f"{tpl_id.value} ({pal_id}) violations: {report.violations}"
        assert report.overlap_count == 0
        assert report.out_of_bounds_count == 0

        png_out = tmp_path / f"{tpl_id.value}_{pal_id}.png"
        render_slide_preview_png(cover, deck, png_out)
        assert png_out.exists() and png_out.stat().st_size > 15_000


def test_toc_part_divider_and_5_closing_templates_audit(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from app.builder.ppt_core import compile_deck_to_pptx
    from app.qa.audit_pptx import audit_pptx
    from app.qa.slide_renderer import render_slide_preview_png
    from app.schemas.deck_spec import CoverTemplateId, DeckMeta, DeckSpec, DesignStyle, LayoutId, SlideSpec, SlideType

    pairs = [
        (CoverTemplateId.hero_band_bottom_bar, "nejm"),
        (CoverTemplateId.top_bottom_bands_framed, "lancet"),
        (CoverTemplateId.floating_rounded_hero_card, "nature"),
        (CoverTemplateId.left_aligned_rounded_panel, "science"),
        (CoverTemplateId.chevron_v_cut_banner, "immunology"),
    ]
    for tpl_id, pal_id in pairs:
        toc_sl = SlideSpec(
            slide_no=1,
            slide_type=SlideType.toc,
            layout_id=LayoutId.toc,
            title="目录",
            toc_items=[
                "选题背景与意义|Background & Significance",
                "研究内容与目的|Research Scope & Aims",
                "研究方法与思路|Synthetic Strategy & Methods",
                "重难点与创新点|Key Challenges & Innovations",
                "论文进度与安排|Milestones & Schedule",
                "预期结果与分析|Expected Outcomes",
            ],
        )
        div_sl = SlideSpec(
            slide_no=2,
            slide_type=SlideType.part_divider,
            layout_id=LayoutId.part_divider,
            eyebrow="PART 05",
            title="论文进度与安排",
            takeaway="Research Plan, Milestones, and Literature Support",
            figure_chips=["三阶段任务", "进度与里程碑", "预期成果与文献"],
        )
        cls_sl = SlideSpec(
            slide_no=3,
            slide_type=SlideType.closing,
            layout_id=LayoutId.closing,
            title="感谢聆听  敬请各位专家批评指正",
            takeaway="THANK YOU FOR YOUR ATTENTION · Q & A",
        )
        deck = DeckSpec(
            meta=DeckMeta(
                deck_id=f"struct_{tpl_id.value}",
                deck_title="基于分子对接与绿色催化的新型先导化合物研究",
                deck_subtitle="Target molecule-mediated selective activation & catalytic C–N synthesis",
                author="李明",
                affiliation="药学院计算药化研究所",
                advisor="张教授",
                date_str="2026 年 11 月",
                palette_id=pal_id,
                design_style=DesignStyle.defense_modular,
                cover_template=tpl_id,
                target_slide_count=3,
            ),
            slides=[toc_sl, div_sl, cls_sl],
        )
        out_pptx = tmp_path / f"struct_{tpl_id.value}_{pal_id}.pptx"
        compile_deck_to_pptx(deck, out_pptx)
        prs = Presentation(str(out_pptx))
        for sl in prs.slides:
            assert [s for s in sl.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE] == []

        report = audit_pptx(out_pptx, deck_spec=deck)
        assert report.passed is True, f"Struct ({tpl_id.value}, {pal_id}) violations: {report.violations}"
        assert report.overlap_count == 0
        assert report.out_of_bounds_count == 0

        for idx, sl in enumerate((toc_sl, div_sl, cls_sl), 1):
            png_out = tmp_path / f"struct_{tpl_id.value}_{idx}.png"
            render_slide_preview_png(sl, deck, png_out)
            assert png_out.exists() and png_out.stat().st_size > 12_000


def test_cross_platform_fonts_cleanup_and_bootstrap(tmp_path: Path, monkeypatch) -> None:
    import time
    from app.qa.font_resolver import resolve_pil_font
    from app.main import cleanup_old_decks

    # 1. Cross-platform PIL font resolution works cleanly for CJK & Latin
    f_cjk = resolve_pil_font(20, is_cjk=True, bold=True)
    f_lat = resolve_pil_font(20, is_cjk=False, bold=False)
    assert f_cjk is not None and f_lat is not None

    # 2. Expired deck cleanup removes old temporary decks while preserving showcase & fresh decks
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    old_deck = decks_dir / "deck_expired_123"
    fresh_deck = decks_dir / "deck_fresh_456"
    showcase_deck = decks_dir / "nature_editorial_showcase"
    for d in (old_deck, fresh_deck, showcase_deck):
        d.mkdir(parents=True, exist_ok=True)
        (d / "dummy.txt").write_text("ok", encoding="utf-8")

    old_ts = time.time() - 48 * 3600
    os.utime(old_deck, (old_ts, old_ts))
    os.utime(showcase_deck, (old_ts, old_ts))

    removed = cleanup_old_decks(decks_dir, ttl_hours=24.0)
    assert removed == 1
    assert not old_deck.exists()
    assert fresh_deck.exists()
    assert showcase_deck.exists()

    # 3. Upload size guard returns HTTP 413 cleanly
    monkeypatch.setattr(main_mod, "MAX_UPLOAD_BYTES", 64)
    test_settings = Settings(
        artifacts_root=tmp_path / "artifacts",
        decks_root=tmp_path / "artifacts" / "decks",
        gallery_root=tmp_path / "artifacts" / "archetype_gallery",
        demo_deck_root=tmp_path / "artifacts" / "demo_deck",
    )
    monkeypatch.setattr(main_mod, "settings", test_settings)
    client = TestClient(main_mod.app)
    big_res = client.post(
        "/api/figures/upload",
        data={"deck_id": "deck_limit", "slide_no": "1", "asset_id": "big"},
        files={"file": ("big.png", BytesIO(b"x" * 256), "image/png")},
    )
    assert big_res.status_code == 413

    # 4. In-process showcase bootstrap generates all 4 preview PNGs & PPTX cleanly
    import docker_entrypoint

    boot_root = tmp_path / "boot_artifacts"
    built = docker_entrypoint.ensure_showcase_artifacts(boot_root)
    assert built is True
    assert (boot_root / "decks" / "nature_editorial_showcase" / "nature_editorial_showcase.pptx").is_file()
    for i in range(1, 5):
        assert (boot_root / "decks" / "nature_editorial_showcase" / "previews" / f"slide_{i:02d}.png").is_file()
    assert docker_entrypoint.ensure_showcase_artifacts(boot_root) is False
