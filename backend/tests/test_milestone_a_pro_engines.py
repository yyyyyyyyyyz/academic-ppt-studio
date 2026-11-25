"""Milestone A Verification Tests: ChemDraw .cdxml, PyMOL/3D .sdf, Nature/Origin Real-Data Plots, 3D Mechanism Pathway & API Switch."""

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
from rdkit import Chem

import app.main as main_mod
from app.agents.doc_parser import ParsedTable, extract_chart_data_from_table
from app.config import Settings
from app.figure_factory.chem_grounding import export_mol_to_cdxml, extract_compounds_from_text, resolve_compound_smiles
from app.figure_factory.chemdraw_engine import render_molecule
from app.figure_factory.cylview3d_engine import render_cylview3d
from app.figure_factory.origin_engine import export_plot_data_csv, render_origin_plot
from app.figure_factory.vector_mech import render_vector_mechanism
from app.schemas.deck_spec import ArchetypeId, EngineType, FigureAsset, FigureBoxIn, FigureSpec


def test_drug_grounding_and_native_cdxml_styles(tmp_path: Path) -> None:
    smi_cn = resolve_compound_smiles("奥希替尼")
    smi_en = resolve_compound_smiles("Osimertinib")
    assert smi_cn is not None and smi_cn == smi_en
    assert Chem.MolFromSmiles(smi_cn) is not None

    pairs = extract_compounds_from_text("本课题以青蒿素和伊马替尼作为对照分子研究。")
    assert len(pairs) == 2

    cdxml_p = export_mol_to_cdxml(smi_cn, tmp_path / "osimertinib.cdxml", color_hex="#9E2F1E")
    xml_txt = cdxml_p.read_text(encoding="utf-8")
    assert "<CDXML" in xml_txt and 'BondLength="14.40"' in xml_txt and "<fragment" in xml_txt and "<b " in xml_txt

    for style in ("jacs_terracotta", "reactive_spot"):
        res = render_molecule(
            smiles="青蒿素",
            output_png=tmp_path / f"{style}.png",
            output_svg=tmp_path / f"{style}.svg",
            chem_style=style,
        )
        assert res.png_path.is_file()
        assert res.cdxml_path is not None and res.cdxml_path.is_file()
        assert res.svg_path is not None and res.svg_path.is_file()


def test_cylview_3d_sdf_and_pathway_mechanism(tmp_path: Path) -> None:
    res_3d = render_cylview3d(
        smiles="Osimertinib",
        output_png=tmp_path / "osi_3d.png",
        palette_id="nature_crimson",
        target_width_px=480,
        dpi=200,
    )
    assert res_3d.png_path.is_file()
    assert res_3d.sdf_path is not None and res_3d.sdf_path.is_file()
    assert "V2000" in res_3d.sdf_path.read_text(encoding="utf-8")

    mech_png = render_vector_mechanism(
        mech_mode="molecular_3d_pathway",
        output_png=tmp_path / "pathway_3d.png",
        palette_id="lancet",
        mech_data={
            "title_top": "Covalent vs. Allosteric Route",
            "blocked_label": "C797S Blocked",
            "sub_box_label": "Non-Covalent Allosteric Pocket Locking",
            "nodes": [
                {"smiles": "CC(=O)OO", "label": "PAA Oxidant"},
                {"smiles": "Gefitinib", "label": "Hinge Anchor"},
                {"smiles": "Osimertinib", "label": "YJ-402 Lead"},
            ],
            "step_labels": ["Met793 H-Bond", "Back-Pocket Lock"],
        },
        dpi=200,
    )
    assert mech_png.is_file()
    with Image.open(mech_png) as im:
        assert im.width >= 1000 and im.height >= 600


def test_nature_origin_presets_and_word_table_to_chart(tmp_path: Path) -> None:
    tbl = ParsedTable(
        headers=["化合物", "C797S IC50 (nM)", "WT IC50 (nM)"],
        rows=[
            ["Osimertinib", "580", "184"],
            ["Brigatinib", "67", "210"],
            ["YJ-402", "1.8", "261"],
        ],
    )
    pdata = extract_chart_data_from_table(tbl, heading="激酶活性对比")
    assert pdata is not None
    assert pdata["categories"] == ["Osimertinib", "Brigatinib", "YJ-402"]
    assert len(pdata["series"]) == 2

    csv_p = export_plot_data_csv(pdata, tmp_path / "activity.csv")
    assert csv_p is not None and "YJ-402" in csv_p.read_text(encoding="utf-8-sig")

    for preset in ("nature_grouped_bar", "nature_step_drop_zoom", "nature_horizontal_ranked"):
        out = render_origin_plot(
            preset=preset,
            output_png=tmp_path / f"{preset}.png",
            palette_id="nature",
            plot_data=pdata if preset == "nature_grouped_bar" else {},
            dpi=200,
        )
        assert out.is_file()


def test_api_2d_3d_switch_and_source_export_urls(tmp_path: Path, monkeypatch) -> None:
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

    init_spec = FigureSpec(
        figure_id="fig_03",
        archetype=ArchetypeId.A05,
        box_in=FigureBoxIn(left=0.5, top=1.7, width=7.5, height=4.4),
        assets=[
            FigureAsset(
                asset_id="mol_main",
                engine=EngineType.chemdraw_rdkit,
                smiles="COc1ccccc1",
            )
        ],
    )

    # 1. Refine with Chinese drug name "青蒿素" & JACS style -> returns .cdxml + .svg URLs
    r_2d = client.post(
        "/api/figures/select-or-refine",
        json={
            "deck_id": "deck_test_2d3d",
            "slide_no": 3,
            "palette_id": "nature",
            "figure_spec": init_spec.model_dump(),
            "asset_id": "mol_main",
            "smiles_override": "青蒿素",
            "chem_style_override": "jacs_terracotta",
        },
    )
    assert r_2d.status_code == 200
    d2 = r_2d.json()
    asset_2d = d2["figure_spec"]["assets"][0]
    assert asset_2d["chem_style"] == "jacs_terracotta"
    assert asset_2d["smiles"] == resolve_compound_smiles("青蒿素")
    urls_2d = d2["asset_urls"]["mol_main"]
    assert urls_2d["cdxml_url"] and client.get(urls_2d["cdxml_url"]).status_code == 200
    assert urls_2d["svg_url"] and client.get(urls_2d["svg_url"]).status_code == 200

    # 2. One-click switch to A04 3D -> preserves Artemisinin SMILES and returns .sdf URL
    r_3d = client.post(
        "/api/figures/select-or-refine",
        json={
            "deck_id": "deck_test_2d3d",
            "slide_no": 3,
            "palette_id": "nature",
            "figure_spec": d2["figure_spec"],
            "archetype_override": "A04_cylview_3d",
        },
    )
    assert r_3d.status_code == 200
    d3 = r_3d.json()
    asset_3d = d3["figure_spec"]["assets"][0]
    assert asset_3d["engine"] == "cylview_3d"
    assert asset_3d["smiles"] == resolve_compound_smiles("青蒿素")
    urls_3d = d3["asset_urls"][asset_3d["asset_id"]]
    assert urls_3d["sdf_url"] and client.get(urls_3d["sdf_url"]).status_code == 200


def test_a05_uses_user_molecule_not_hardcoded_aniline() -> None:
    from app.agents.art_director_agent import build_default_figure_spec

    aspirin = "CC(=O)Oc1ccccc1C(=O)O"
    fspec = build_default_figure_spec(ArchetypeId.A05, slide_no=2, smiles=aspirin)
    assert len(fspec.assets) == 1
    assert fspec.assets[0].engine == EngineType.chemdraw_rdkit
    assert fspec.assets[0].smiles == aspirin
    assert fspec.native_overlays == []


def test_select_or_refine_mech_mode_override(tmp_path: Path, monkeypatch) -> None:
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

    init_spec = FigureSpec(
        figure_id="fig_04",
        archetype=ArchetypeId.A05,
        box_in=FigureBoxIn(left=0.5, top=1.7, width=7.5, height=4.4),
        assets=[FigureAsset(asset_id="mol_main", engine=EngineType.chemdraw_rdkit, smiles="COc1ccccc1")],
    )
    resp = client.post(
        "/api/figures/select-or-refine",
        json={
            "deck_id": "deck_test_mech",
            "slide_no": 4,
            "palette_id": "lancet",
            "figure_spec": init_spec.model_dump(),
            "archetype_override": "A10_vector_cycle",
            "mech_mode_override": "molecular_3d_pathway",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    ast = body["figure_spec"]["assets"][0]
    assert ast["engine"] == "vector_mech"
    assert ast["mech_mode"] == "molecular_3d_pathway"
    png_url = body["asset_urls"][ast["asset_id"]]["png_url"]
    assert png_url and client.get(png_url).status_code == 200


def test_palette_apply_recolors_slide_pixels_and_cache_busts(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
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
            "source_text": "# Test\n## 1. 背景\nOsimertinib 抑制 EGFR。\n## 2. 活性\nIC50 = 1.8 nM。\n## 3. 总结\n完成先导化合物优化。",
            "deck_title": "Palette Switch Verification",
            "author": "Tester",
            "affiliation": "Lab",
            "scenario": "defense",
            "target_slide_count": 5,
            "palette_id": "lancet",
            "is_proposal": False,
        },
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    deck_spec = plan_data["deck_spec"]

    lancet_cover_bytes = client.get(plan_data["artifact_urls"]["slide_01"]).content
    lancet_content_bytes = client.get(plan_data["artifact_urls"]["slide_03"]).content

    pal_resp = client.post(
        "/api/palettes/apply",
        json={"deck_spec": deck_spec, "palette_id": "nature", "rerender_figures": True},
    )
    assert pal_resp.status_code == 200
    pal_data = pal_resp.json()
    assert "?v=nature_" in pal_data["artifact_urls"]["slide_01"]
    assert "?v=nature_" in pal_data["artifact_urls"]["slide_03"]

    nature_cover_bytes = client.get(pal_data["artifact_urls"]["slide_01"]).content
    nature_content_bytes = client.get(pal_data["artifact_urls"]["slide_03"]).content

    im_l1 = np.asarray(Image.open(BytesIO(lancet_cover_bytes)).convert("RGB"), dtype=np.int16)
    im_n1 = np.asarray(Image.open(BytesIO(nature_cover_bytes)).convert("RGB"), dtype=np.int16)
    im_l3 = np.asarray(Image.open(BytesIO(lancet_content_bytes)).convert("RGB"), dtype=np.int16)
    im_n3 = np.asarray(Image.open(BytesIO(nature_content_bytes)).convert("RGB"), dtype=np.int16)

    assert float(np.mean(np.abs(im_l1 - im_n1))) > 5.0
    assert float(np.mean(np.abs(im_l3 - im_n3))) > 1.0


def test_all_5_3d_molecular_styles_and_api_override(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
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

    styles_3d = ["ball_stick", "stick_clean", "spacefill_cpk", "pymol_neon_green", "metallic_studio"]
    for st in styles_3d:
        res = render_cylview3d(
            smiles="青蒿素",
            output_png=tmp_path / f"artemisinin_{st}.png",
            palette_id="lancet",
            target_width_px=360,
            dpi=150,
            style_3d=st,
        )
        assert res.png_path.is_file()
        assert res.sdf_path is not None and res.sdf_path.is_file()

    init_spec = FigureSpec(
        figure_id="fig_05",
        archetype=ArchetypeId.A04,
        box_in=FigureBoxIn(left=0.5, top=1.7, width=7.5, height=4.4),
        assets=[FigureAsset(asset_id="mol_3d", engine=EngineType.cylview_3d, smiles="Osimertinib", style_3d="ball_stick")],
    )
    r_base = client.post(
        "/api/figures/select-or-refine",
        json={
            "deck_id": "deck_test_3d_styles",
            "slide_no": 5,
            "palette_id": "lancet",
            "figure_spec": init_spec.model_dump(),
            "asset_id": "mol_3d",
            "style_3d_override": "ball_stick",
        },
    )
    assert r_base.status_code == 200
    base_png = client.get(r_base.json()["asset_urls"]["mol_3d"]["png_url"]).content

    r_neon = client.post(
        "/api/figures/select-or-refine",
        json={
            "deck_id": "deck_test_3d_styles",
            "slide_no": 5,
            "palette_id": "lancet",
            "figure_spec": r_base.json()["figure_spec"],
            "asset_id": "mol_3d",
            "style_3d_override": "pymol_neon_green",
            "rotation_deg_override": [35.0, 0.0, 0.0],
        },
    )
    assert r_neon.status_code == 200
    ast_neon = r_neon.json()["figure_spec"]["assets"][0]
    assert ast_neon["style_3d"] == "pymol_neon_green"
    assert ast_neon["rotation_deg"] == [35.0, 0.0, 0.0]
    neon_png = client.get(r_neon.json()["asset_urls"]["mol_3d"]["png_url"]).content

    arr_b = np.asarray(Image.open(BytesIO(base_png)).convert("RGB").resize((120, 90)), dtype=np.int16)
    arr_n = np.asarray(Image.open(BytesIO(neon_png)).convert("RGB").resize((120, 90)), dtype=np.int16)
    assert float(np.mean(np.abs(arr_b - arr_n))) > 3.0
