"""Milestone 1 Verification Tests: 15 Palettes, 5 Figure Engines, Alpha Matting & Critic QA."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["FIGURE_PROVIDER_MODE"] = "local"
os.environ["LLM_PROVIDER_MODE"] = "local"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from PIL import Image, ImageDraw
import numpy as np

from app.figure_factory.alpha_matting import compute_alpha_edge_cleanliness, matte_white_background
from app.figure_factory.chemdraw_engine import render_molecule
from app.figure_factory.cylview3d_engine import render_cylview3d
from app.figure_factory.factory import ScientificFigureFactory
from app.figure_factory.icon_library import ICON_NAMES, render_icon
from app.figure_factory.origin_engine import PRESET_DISPATCH, render_origin_plot
from app.figure_factory.palettes import PALETTES, generate_palette_reference_card, get_palette
from app.figure_factory.vector_mech import compute_external_bitangents, render_vector_mechanism
from app.schemas.deck_spec import ArchetypeId, EngineType, FigureAsset, FigureBoxIn, FigureSpec


def test_15_palettes_verbatim(tmp_path: Path) -> None:
    assert len(PALETTES) == 15
    assert get_palette("lancet").s1 == "#00468B"
    assert get_palette("sci_angew_blue_orange").series[0] == "#3A80DA"
    assert get_palette("sci_sunburst_pastel").series[0] == "#EDF4FC"
    card = generate_palette_reference_card(tmp_path / "palettes.jpg")
    assert card.exists() and card.stat().st_size > 20_000


def test_chemdraw_fixed_bond_length_invariance(tmp_path: Path) -> None:
    # Small molecule (aniline) vs large drug (tripelennamine) must share identical physical scale per bond!
    small = render_molecule(
        smiles="Nc1ccccc1",
        output_png=tmp_path / "aniline.png",
        output_svg=tmp_path / "aniline.svg",
        palette_id="lancet",
        fixed_bond_length_px=28,
        highlight_atoms=[0],
    )
    large = render_molecule(
        smiles="CN(C)CCN(Cc1ccccc1)c2ccccn2",
        output_png=tmp_path / "tripelennamine.png",
        output_svg=tmp_path / "tripelennamine.svg",
        palette_id="lancet",
        fixed_bond_length_px=28,
        highlight_rings=True,
    )
    assert small.png_path.exists() and small.svg_path and small.svg_path.exists()
    assert large.png_path.exists()
    # Large molecule must physically span substantially larger width/height than small aniline
    assert large.physical_width_in > small.physical_width_in * 1.4
    # Transparent alpha check
    arr = np.array(Image.open(small.png_path).convert("RGBA"))
    assert float(np.mean(arr[:, :, 3] < 10)) > 0.25


def test_cylview3d_zero_hallucination_alpha(tmp_path: Path) -> None:
    res = render_cylview3d(
        smiles="c1ccnc(c1)c2ccccn2",
        output_png=tmp_path / "bipy_3d.png",
        palette_id="lancet",
    )
    assert res.png_path.exists()
    assert res.atom_count == 20  # bipyridine C10H8N2 -> 20 atoms with explicit H
    img = Image.open(res.png_path).convert("RGBA")
    assert round(img.info.get("dpi", (0, 0))[0]) == 600
    assert compute_alpha_edge_cleanliness(res.png_path) >= 8.5


def test_origin_all_8_presets_1to1_600dpi(tmp_path: Path) -> None:
    w_in, h_in = 7.75, 4.42
    for preset in PRESET_DISPATCH.keys():
        out = render_origin_plot(
            preset=preset,
            output_png=tmp_path / f"{preset}.png",
            palette_id="sci_high_entropy_echem" if preset == "electrochem_suite" else "lancet",
            box_width_in=w_in,
            box_height_in=h_in,
            dpi=600,
        )
        assert out.exists()
        img = Image.open(out)
        assert abs(img.width - int(round(w_in * 600))) <= 4
        assert abs(img.height - int(round(h_in * 600))) <= 4


def test_alpha_matting_removes_white_bg_keeps_interior_highlight(tmp_path: Path) -> None:
    raw = Image.new("RGB", (300, 300), (255, 255, 255))
    d = ImageDraw.Draw(raw)
    d.ellipse([60, 60, 240, 240], fill=(0, 70, 139), outline=(20, 30, 43), width=4)
    # Interior pure white specular dot inside blue sphere
    d.ellipse([105, 95, 130, 120], fill=(255, 255, 255))
    raw_p = tmp_path / "raw.png"
    raw.save(raw_p)
    matted = matte_white_background(raw_p, output_path=tmp_path / "matted.png")
    arr = np.array(matted)
    # Corners must be transparent
    assert arr[0, 0, 3] == 0
    # Interior specular dot must stay opaque!
    cy, cx = matted.height // 2 - 42, matted.width // 2 - 32
    assert arr[cy, cx, 3] > 240


def test_bitangents_and_vector_mech(tmp_path: Path) -> None:
    tangents = compute_external_bitangents((2.2, 3.8, 0.4), (5.6, 3.8, 1.5))
    assert len(tangents) == 2
    p1_a, p2_a = tangents[0]
    p1_b, p2_b = tangents[1]
    assert abs(p1_a[1] - p1_b[1]) > 0.5 and abs(p2_a[1] - p2_b[1]) > 2.0

    for icon in ICON_NAMES[:4]:
        p = render_icon(icon, tmp_path / f"{icon}.png", palette_id="lancet")
        assert p.exists()

    for mode in ("sunburst_pathway", "dual_cycle", "roadmap_4stage", "gap_quadrant", "delta_g_concept"):
        out = render_vector_mechanism(mode, tmp_path / f"{mode}.png", palette_id="sci_sunburst_pastel")
        assert out.exists()


def test_factory_qa_and_proposal_zero_simulated_curves(tmp_path: Path) -> None:
    factory = ScientificFigureFactory()

    # 1. Sci3D A01 Best-of-2 + QA >= 8.5
    spec_a01 = FigureSpec(
        figure_id="fig_test_a01",
        archetype=ArchetypeId.A01,
        box_in=FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42),
        assets=[
            FigureAsset(
                asset_id="reactor_3d",
                engine=EngineType.sci3d_art,
                render_mode="c4d_octane_cutaway",
                best_of_n=2,
            )
        ],
    )
    res_a01 = factory.render_figure_spec(spec_a01, tmp_path / "a01", palette_id="lancet", is_proposal=False)
    assert res_a01.qa_passed is True
    assert res_a01.overall_qa_score >= 8.5
    assert res_a01.assets[0].qa_result.ocr_text_count == 0

    # 2. Proposal rigor guard converts unverified Origin plot automatically
    spec_prop = FigureSpec(
        figure_id="fig_test_prop",
        archetype=ArchetypeId.A06,
        assets=[
            FigureAsset(
                asset_id="unverified_curve",
                engine=EngineType.origin_plot,
                preset="kinetics_spline",
                data_verified=False,
            )
        ],
    )
    res_prop = factory.render_figure_spec(spec_prop, tmp_path / "prop", palette_id="lancet", is_proposal=True)
    assert res_prop.assets[0].engine == EngineType.vector_mech
    assert res_prop.qa_passed is True
