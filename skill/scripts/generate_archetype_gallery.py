"""Generate standard showcase figures for all 10 Archetypes (A01–A10), all 8 Origin presets,
and the 15-Palette Reference Card into D:\academic-ppt-design\artifacts\archetype_gallery.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FIGURE_PROVIDER_MODE", "local")
os.environ.setdefault("LLM_PROVIDER_MODE", "local")

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.figure_factory.factory import ScientificFigureFactory
from app.figure_factory.origin_engine import PRESET_DISPATCH, render_origin_plot
from app.figure_factory.palettes import generate_palette_reference_card
from app.schemas.deck_spec import ArchetypeId, EngineType, FigureAsset, FigureBoxIn, FigureSpec


def generate_gallery(output_root: Path | None = None) -> Path:
    settings = get_settings()
    out = output_root or settings.gallery_root
    out.mkdir(parents=True, exist_ok=True)

    # 1. 15-Palette Reference Card in skill/assets/journal_color_palettes.jpg
    generate_palette_reference_card(settings.skill_root / "assets" / "journal_color_palettes.jpg")

    factory = ScientificFigureFactory(settings=settings)
    specs = [
        ("A01_cutaway_reactor_zoom", "lancet", FigureSpec(
            figure_id="A01_demo", archetype=ArchetypeId.A01,
            assets=[FigureAsset(asset_id="a01_reactor", engine=EngineType.sci3d_art, render_mode="c4d_octane_cutaway", best_of_n=2)],
            caption="Fig. A01  3D cutaway borosilicate reactor + porous micro-cavity host.",
        )),
        ("A02_dispersion_contrast", "sci_angew_blue_orange", FigureSpec(
            figure_id="A02_demo", archetype=ArchetypeId.A02,
            assets=[FigureAsset(asset_id="a02_disp", engine=EngineType.sci3d_art, render_mode="c4d_octane_cutaway", best_of_n=2)],
            caption="Fig. A02  Agglomerated sintering failure vs. confined single-dispersed cage.",
        )),
        ("A03_editorial_vector", "cell", FigureSpec(
            figure_id="A03_demo", archetype=ArchetypeId.A03,
            assets=[FigureAsset(asset_id="a03_edit", engine=EngineType.sci3d_art, render_mode="editorial_flat_3d", best_of_n=2)],
            caption="Fig. A03  Editorial flat-3D piezocatalytic coupling illustration.",
        )),
        ("A04_cylview_3d", "lancet", FigureSpec(
            figure_id="A04_demo", archetype=ArchetypeId.A04,
            assets=[FigureAsset(asset_id="a04_mol3d", engine=EngineType.cylview_3d, smiles="c1ccc(cc1)C(=O)Nc2ccccn2")],
            caption="Fig. A04  Deterministic CYLview-style 3D ball-and-stick conformer.",
        )),
        ("A05_chemdraw_halo", "lancet", FigureSpec(
            figure_id="A05_demo", archetype=ArchetypeId.A05,
            assets=[FigureAsset(asset_id="a05_mol2d", engine=EngineType.chemdraw_rdkit, smiles="CN(C)CCN(Cc1ccccc1)c2ccccn2", fixed_bond_length_px=28, highlight_atoms=[6, 7], highlight_rings=True)],
            caption="Fig. A05  ACS 1996 fixed-bond-length drug scaffold with soft pastel highlight halo.",
        )),
        ("A06_origin_suite", "sci_high_entropy_echem", FigureSpec(
            figure_id="A06_demo", archetype=ArchetypeId.A06,
            box_in=FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42),
            assets=[FigureAsset(asset_id="a06_echem", engine=EngineType.origin_plot, preset="electrochem_suite", data_verified=True)],
            caption="Fig. A06  600 DPI 1:1 physical OriginPro electrochemical 4-panel suite.",
        )),
        ("A07_vesta_split", "sci_angew_blue_orange", FigureSpec(
            figure_id="A07_demo", archetype=ArchetypeId.A07,
            assets=[FigureAsset(asset_id="a07_vesta", engine=EngineType.sci3d_art, render_mode="vesta_polyhedra", best_of_n=2)],
            caption="Fig. A07  VESTA octahedral slab interface with bi-color split microenvironment.",
        )),
        ("A08_multiscale_line", "nature", FigureSpec(
            figure_id="A08_demo", archetype=ArchetypeId.A08,
            assets=[FigureAsset(asset_id="a08_line", engine=EngineType.sci3d_art, render_mode="nature_line_art", best_of_n=2)],
            caption="Fig. A08  Nature Reviews thin-line multi-scale macro/meso/micro schematic.",
        )),
        ("A09_sunburst_pathway", "sci_sunburst_pastel", FigureSpec(
            figure_id="A09_demo", archetype=ArchetypeId.A09,
            assets=[FigureAsset(asset_id="a09_sun", engine=EngineType.vector_mech, mech_mode="sunburst_pathway")],
            caption="Fig. A09  Concentric sunburst literature & strategy taxonomy.",
        )),
        ("A10_vector_cycle", "lancet", FigureSpec(
            figure_id="A10_demo", archetype=ArchetypeId.A10,
            assets=[FigureAsset(asset_id="a10_cycle", engine=EngineType.vector_mech, mech_mode="dual_cycle")],
            caption="Fig. A10  Coupled dual catalytic cycle schematic.",
        )),
    ]

    summary = []
    for folder, pal_id, fspec in specs:
        res = factory.render_figure_spec(fspec, out / folder, palette_id=pal_id, best_of_n=2)
        summary.append((folder, res.overall_qa_score, res.qa_passed, res.assets[0].png_path))

    # Also render all 8 Origin presets for verification
    origin_dir = out / "origin_8_presets"
    for preset in PRESET_DISPATCH.keys():
        pal = "sci_nanoconfined_xps" if preset == "xps_deconv" else ("sci_high_entropy_echem" if preset == "electrochem_suite" else "lancet")
        render_origin_plot(preset=preset, output_png=origin_dir / f"{preset}.png", palette_id=pal, box_width_in=7.75, box_height_in=4.42, dpi=600)

    for folder, score, passed, png_p in summary:
        print(f"[Gallery] {folder}: score={score}, passed={passed}, file={png_p}")
    return out


if __name__ == "__main__":
    generate_gallery()
