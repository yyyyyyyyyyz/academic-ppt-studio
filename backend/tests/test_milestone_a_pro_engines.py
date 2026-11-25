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
