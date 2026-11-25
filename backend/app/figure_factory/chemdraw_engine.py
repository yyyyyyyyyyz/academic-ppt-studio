"""Engine 1: ChemDrawEngine — RDKit ACS 1996 Precision Molecular Engine.

Guarantees:
- Global fixed physical bond length (`fixedBondLength`) across all molecules on a slide
- Auto dynamic canvas sizing + tight alpha crop (never stretches small benzene rings!)
- Heteroatom coloring synchronized to the active 15-palette system
- Soft pastel Highlight Halo (`alpha` Gaussian glow) underneath active bonds/atoms
- True transparent RGBA PNG + vector SVG output
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D

from .palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb, hex_to_rgb_norm


@dataclass
class ChemDrawRenderResult:
    png_path: Path
    svg_path: Optional[Path]
    smiles: str
    pixel_width: int
    pixel_height: int
    physical_width_in: float
    physical_height_in: float
    bond_length_px_1x: float
    atom_count: int


def _apply_acs1996_options(
    drawer: Any,
    palette: ScientificPalette,
    fixed_bond_len_px: float,
    supersample: int,
    heteroatom_theme_sync: bool,
    drug_burgundy: bool,
    chem_style: str = "acs1996",
) -> None:
    style = (chem_style or ("nature_burgundy" if drug_burgundy else "acs1996")).strip().lower()
    if style == "acs1996" and drug_burgundy:
        style = "nature_burgundy"

    opts = drawer.drawOptions()
    opts.fixedBondLength = float(fixed_bond_len_px * supersample)
    if style == "nature_burgundy":
        opts.bondLineWidth = float(2.75 * supersample)
    elif style == "minimal_mono":
        opts.bondLineWidth = float(1.80 * supersample)
    elif style == "shaded_scaffold":
        opts.bondLineWidth = float(2.35 * supersample)
    else:
        opts.bondLineWidth = float(2.4 * supersample)
    opts.multipleBondOffset = 0.17
    opts.minFontSize = int(18 * supersample)
    opts.maxFontSize = int(22 * supersample)
    opts.clearBackground = False
    opts.setBackgroundColour((1.0, 1.0, 1.0, 0.0))
    opts.padding = 0.05
    opts.additionalAtomLabelPadding = 0.08

    if style == "nature_burgundy":
        c_rgb = hex_to_rgb_norm("#7F1D1D")
        n_rgb = hex_to_rgb_norm("#1F4E78")
        alert_rgb = hex_to_rgb_norm("#B5121B")
        s_rgb = hex_to_rgb_norm("#9A6B16")
    elif style == "minimal_mono":
        c_rgb = hex_to_rgb_norm("#1E1E1E")
        n_rgb = c_rgb
        alert_rgb = c_rgb
        s_rgb = c_rgb
    else:
        c_rgb = hex_to_rgb_norm("#141E2B")
        if heteroatom_theme_sync:
            n_rgb = hex_to_rgb_norm(palette.s1)
            alert_rgb = hex_to_rgb_norm(palette.alert)
            s_rgb = hex_to_rgb_norm(palette.s2)
        else:
            n_rgb = hex_to_rgb_norm("#00468B")
            alert_rgb = hex_to_rgb_norm("#AD002A")
            s_rgb = hex_to_rgb_norm("#B07300")

    atom_palette = {
        0: c_rgb,
        1: c_rgb,
        6: c_rgb,
        7: n_rgb,
        8: alert_rgb,
        9: alert_rgb,
        15: s_rgb,
        16: s_rgb,
        17: alert_rgb,
        35: alert_rgb,
        53: alert_rgb,
        26: n_rgb,
        28: n_rgb,
        29: n_rgb,
        46: n_rgb,
        78: n_rgb,
    }
    opts.updateAtomPalette(atom_palette)
    opts.setSymbolColour(c_rgb)


def _prepare_molecule(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES string: {smiles!r}")
    mol = rdMolDraw2D.PrepareMolForDrawing(mol, kekulize=True, wedgeBonds=True)
    if mol.GetNumConformers() == 0:
        AllChem.Compute2DCoords(mol)
    return mol


def _estimate_canvas_size(mol: Chem.Mol, fixed_bond_len_px: float, supersample: int) -> Tuple[int, int]:
    conf = mol.GetConformer()
    xs = [conf.GetAtomPosition(i).x for i in range(mol.GetNumAtoms())]
    ys = [conf.GetAtomPosition(i).y for i in range(mol.GetNumAtoms())]
    if not xs:
        return (int(420 * supersample), int(320 * supersample))

    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    # Typical RDKit 2D bond length is ~1.5 coordinate units
    px_per_unit = (fixed_bond_len_px * supersample) / 1.5
    margin = int(140 * supersample)
    w = max(int(360 * supersample), int(span_x * px_per_unit) + 2 * margin)
    h = max(int(300 * supersample), int(span_y * px_per_unit) + 2 * margin)
    return (w, h)


def _resolve_halo_centers(
    mol: Chem.Mol,
    drawer: rdMolDraw2D.MolDraw2DCairo,
    highlight_atoms: Sequence[int],
    highlight_bonds: Sequence[int],
    highlight_rings: bool,
) -> List[Tuple[float, float]]:
    centers: List[Tuple[float, float]] = []
    num_atoms = mol.GetNumAtoms()
    num_bonds = mol.GetNumBonds()

    atom_indices = [idx for idx in highlight_atoms if 0 <= idx < num_atoms]
    if not atom_indices and highlight_rings:
        ring_info = mol.GetRingInfo()
        atom_rings = ring_info.AtomRings()
        if atom_rings:
            atom_indices = list(atom_rings[0])
        elif num_atoms > 0:
            # Highlight heteroatoms if no ring exists
            atom_indices = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() not in (1, 6)]
            if not atom_indices:
                atom_indices = [0]

    for idx in atom_indices:
        pt = drawer.GetDrawCoords(idx)
        centers.append((float(pt.x), float(pt.y)))

    for b_idx in highlight_bonds:
        if 0 <= b_idx < num_bonds:
            bond = mol.GetBondWithIdx(b_idx)
            p1 = drawer.GetDrawCoords(bond.GetBeginAtomIdx())
            p2 = drawer.GetDrawCoords(bond.GetEndAtomIdx())
            centers.append((0.5 * (p1.x + p2.x), 0.5 * (p1.y + p2.y)))

    return centers


def _render_halo_layer(
    width: int,
    height: int,
    groups: List[Tuple[List[Tuple[float, float]], str, str]],
    bond_px: float,
    supersample: int = 2,
    mol: Optional[Chem.Mol] = None,
    drawer: Optional[Any] = None,
    group_atom_sets: Optional[List[Tuple[set[int], str, str]]] = None,
    chem_style: str = "acs1996",
) -> Image.Image:
    """Render subtle pastel SAR halos, dashed pharmacophore rings, or shaded scaffold polygons."""
    if not groups:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))

    halo_arr = np.zeros((height, width, 4), dtype=np.uint8)
    if chem_style not in ("minimal_mono", "shaded_scaffold"):
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        sigma = float(bond_px * 0.62)
        for centers, halo_hex, _ in groups:
            if not centers:
                continue
            density = np.zeros((height, width), dtype=np.float32)
            for cx, cy in centers:
                dist2 = (xx - cx) ** 2 + (yy - cy) ** 2
                density = np.maximum(density, np.exp(-dist2 / (2.0 * sigma * sigma)))

            r, g, b = hex_to_rgb(halo_hex)
            alpha_g = np.clip(density * 68.0, 0.0, 76.0).astype(np.uint8)
            mask = alpha_g > halo_arr[:, :, 3]
            halo_arr[mask, 0] = r
            halo_arr[mask, 1] = g
            halo_arr[mask, 2] = b
            halo_arr[mask, 3] = alpha_g[mask]

    halo_img = Image.fromarray(halo_arr, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=1.2))
    ring_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ring_overlay)

    # Shaded scaffold mode: translucent pastel wash strictly inside highlighted ring polygons
    if chem_style == "shaded_scaffold" and mol is not None and drawer is not None and group_atom_sets:
        atom_rings = mol.GetRingInfo().AtomRings()
        for ring in atom_rings:
            r_set = set(ring)
            matched_ring_hex: Optional[str] = None
            for aset, _, r_hex in group_atom_sets:
                if r_set & aset:
                    matched_ring_hex = r_hex
                    break
            if matched_ring_hex:
                poly = [(float(drawer.GetDrawCoords(a).x), float(drawer.GetDrawCoords(a).y)) for a in ring]
                if len(poly) >= 3:
                    pr, pg, pb = hex_to_rgb(matched_ring_hex)
                    draw.polygon(poly, fill=(pr, pg, pb, 48))

    ring_w = max(2, int(round(1.3 * supersample)))
    for centers, _, ring_hex in groups:
        if len(centers) < 2:
            continue
        xs_c = [p[0] for p in centers]
        ys_c = [p[1] for p in centers]
        pad = bond_px * 0.78
        x0 = max(2.0, min(xs_c) - pad)
        y0 = max(2.0, min(ys_c) - pad)
        x1 = min(width - 2.0, max(xs_c) + pad)
        y1 = min(height - 2.0, max(ys_c) + pad)
        cx_e, cy_e = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        rx_e, ry_e = max(8.0, 0.5 * (x1 - x0)), max(8.0, 0.5 * (y1 - y0))
        rr, rg, rb = hex_to_rgb(ring_hex)
        for deg in range(0, 360, 16):
            a0 = math.radians(deg)
            a1 = math.radians(deg + 9)
            pts_arc = [
                (cx_e + rx_e * math.cos(a0 + (a1 - a0) * t), cy_e + ry_e * math.sin(a0 + (a1 - a0) * t))
                for t in (0.0, 0.5, 1.0)
            ]
            draw.line(pts_arc, fill=(rr, rg, rb, 195), width=ring_w)

    return Image.alpha_composite(halo_img, ring_overlay)


def render_molecule(
    smiles: str,
    output_png: Path | str,
    output_svg: Optional[Path | str] = None,
    palette_id: str = "lancet",
    fixed_bond_length_px: int = 28,
    highlight_atoms: Optional[Sequence[int]] = None,
    highlight_bonds: Optional[Sequence[int]] = None,
    highlight_rings: bool = False,
    highlight_halo_token: str = "s6",
    highlight_groups: Optional[Sequence[Dict[str, Any]]] = None,
    heteroatom_theme_sync: bool = True,
    drug_burgundy: bool = False,
    chem_style: str = "acs1996",
    supersample: int = 2,
    dpi: int = 600,
) -> ChemDrawRenderResult:
    """Render a single molecule with ACS 1996 or editorial style variants and locked bond length."""
    palette = get_palette(palette_id)
    style = (chem_style or ("nature_burgundy" if drug_burgundy else "acs1996")).strip().lower()
    if style == "acs1996" and drug_burgundy:
        style = "nature_burgundy"
    mol = _prepare_molecule(smiles)
    canvas_w, canvas_h = _estimate_canvas_size(mol, fixed_bond_length_px, supersample)

    drawer = rdMolDraw2D.MolDraw2DCairo(canvas_w, canvas_h)
    _apply_acs1996_options(
        drawer=drawer,
        palette=palette,
        fixed_bond_len_px=float(fixed_bond_length_px),
        supersample=supersample,
        heteroatom_theme_sync=heteroatom_theme_sync,
        drug_burgundy=drug_burgundy,
        chem_style=style,
    )

    hl_atoms_rd: List[int] = []
    hl_bonds_rd: List[int] = []
    hl_acol_rd: Dict[int, Tuple[float, float, float]] = {}
    hl_bcol_rd: Dict[int, Tuple[float, float, float]] = {}
    if style == "minimal_mono":
        accent_norm = hex_to_rgb_norm(palette.s1)
        accent_atoms = set()
        if highlight_groups:
            for g in highlight_groups:
                accent_atoms.update(int(i) for i in (g.get("atoms") or []) if 0 <= i < mol.GetNumAtoms())
        elif highlight_atoms:
            accent_atoms.update(int(i) for i in highlight_atoms if 0 <= i < mol.GetNumAtoms())
        for idx in sorted(accent_atoms):
            hl_atoms_rd.append(idx)
            hl_acol_rd[idx] = (*accent_norm, 0.22)
        for b in mol.GetBonds():
            if b.GetBeginAtomIdx() in accent_atoms and b.GetEndAtomIdx() in accent_atoms:
                hl_bonds_rd.append(b.GetIdx())
                hl_bcol_rd[b.GetIdx()] = (*accent_norm, 0.30)

    if hl_atoms_rd:
        drawer.DrawMolecule(
            mol,
            highlightAtoms=hl_atoms_rd,
            highlightBonds=hl_bonds_rd,
            highlightAtomColors=hl_acol_rd,
            highlightBondColors=hl_bcol_rd,
        )
    else:
        drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    from io import BytesIO

    png_bytes = drawer.GetDrawingText()
    mol_img = Image.open(BytesIO(png_bytes)).convert("RGBA")

    def _halo_colors(tok: str) -> Tuple[str, str]:
        base_hex = palette.token(tok)
        h_hex = blend_with_white(palette.s4, 0.35) if tok == "s6" else blend_with_white(base_hex, 0.30)
        r_hex = palette.s1 if tok == "s6" else base_hex
        return h_hex, r_hex

    groups_spec: List[Tuple[List[Tuple[float, float]], str, str]] = []
    group_atom_sets: List[Tuple[set[int], str, str]] = []
    if highlight_groups:
        num_atoms = mol.GetNumAtoms()
        for grp in highlight_groups:
            idxs = [idx for idx in (grp.get("atoms") or []) if 0 <= idx < num_atoms]
            if not idxs:
                continue
            ctok = str(grp.get("color_token", highlight_halo_token or "s6"))
            h_hex, r_hex = _halo_colors(ctok)
            pts_g = [(float(drawer.GetDrawCoords(idx).x), float(drawer.GetDrawCoords(idx).y)) for idx in idxs]
            groups_spec.append((pts_g, h_hex, r_hex))
            group_atom_sets.append((set(idxs), h_hex, r_hex))
    else:
        centers = _resolve_halo_centers(
            mol=mol,
            drawer=drawer,
            highlight_atoms=highlight_atoms or [],
            highlight_bonds=highlight_bonds or [],
            highlight_rings=highlight_rings,
        )
        if centers:
            h_hex, r_hex = _halo_colors(highlight_halo_token)
            groups_spec.append((centers, h_hex, r_hex))
            if highlight_atoms:
                group_atom_sets.append((set(int(i) for i in highlight_atoms), h_hex, r_hex))

    halo_img = _render_halo_layer(
        width=mol_img.width,
        height=mol_img.height,
        groups=groups_spec,
        bond_px=float(fixed_bond_length_px * supersample),
        supersample=supersample,
        mol=mol,
        drawer=drawer,
        group_atom_sets=group_atom_sets,
        chem_style=style,
    )

    combined = Image.alpha_composite(halo_img, mol_img)

    # Tight-crop transparent bounds with consistent padding
    arr = np.array(combined)
    ys, xs = np.where(arr[:, :, 3] > 6)
    pad = int(14 * supersample)
    if len(ys) > 0 and len(xs) > 0:
        y0 = max(0, int(ys.min()) - pad)
        y1 = min(combined.height, int(ys.max()) + 1 + pad)
        x0 = max(0, int(xs.min()) - pad)
        x1 = min(combined.width, int(xs.max()) + 1 + pad)
        combined = combined.crop((x0, y0, x1, y1))

    out_png = Path(output_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    combined.save(str(out_png), format="PNG", dpi=(dpi, dpi))

    svg_written: Optional[Path] = None
    if output_svg is not None:
        svg_drawer = rdMolDraw2D.MolDraw2DSVG(canvas_w, canvas_h)
        _apply_acs1996_options(
            drawer=svg_drawer,
            palette=palette,
            fixed_bond_len_px=float(fixed_bond_length_px),
            supersample=supersample,
            heteroatom_theme_sync=heteroatom_theme_sync,
            drug_burgundy=drug_burgundy,
            chem_style=style,
        )
        svg_drawer.DrawMolecule(mol)
        svg_drawer.FinishDrawing()
        svg_written = Path(output_svg)
        svg_written.parent.mkdir(parents=True, exist_ok=True)
        svg_written.write_text(svg_drawer.GetDrawingText(), encoding="utf-8")

    # Lock physical inch conversion solely by fixed_bond_length_px (0.28 in per standard bond)
    px_per_in = float(fixed_bond_length_px * supersample) / 0.28
    phys_w = round(combined.width / px_per_in, 3)
    phys_h = round(combined.height / px_per_in, 3)

    return ChemDrawRenderResult(
        png_path=out_png,
        svg_path=svg_written,
        smiles=smiles,
        pixel_width=combined.width,
        pixel_height=combined.height,
        physical_width_in=phys_w,
        physical_height_in=phys_h,
        bond_length_px_1x=float(fixed_bond_length_px),
        atom_count=mol.GetNumAtoms(),
    )
