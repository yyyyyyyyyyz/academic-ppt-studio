"""Engine 2: CYLview3DEngine — Zero-Hallucination Deterministic 3D Ball-and-Stick Renderer.

Computes exact 3D molecular geometry via RDKit ETKDGv3 + MMFF94, aligns principal axes via SVD,
and renders studio Phong-shaded spheres + two-tone half-cylinder bonds with CYLview-style
#4A4A4A silhouette outlines and true Alpha transparency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image
from rdkit import Chem
from rdkit.Chem import AllChem

from .chem_grounding import resolve_compound_smiles
from .palettes import ScientificPalette, get_palette, hex_to_rgb


@dataclass
class CYLviewRenderResult:
    png_path: Path
    smiles: str
    pixel_width: int
    pixel_height: int
    atom_count: int
    bond_count: int
    method: str = "ETKDGv3+MMFF94+AnalyticalZBuffer"
    sdf_path: Optional[Path] = None


_ATOM_RADII_A: Dict[int, float] = {
    1: 0.24,
    6: 0.36,
    7: 0.37,
    8: 0.37,
    9: 0.35,
    15: 0.43,
    16: 0.43,
    17: 0.42,
    35: 0.45,
    53: 0.48,
    26: 0.48,
    28: 0.47,
    29: 0.47,
    46: 0.49,
    78: 0.50,
}


def _visible_atom_mask(mol: Chem.Mol, show_nonpolar_h: Optional[bool] = None) -> np.ndarray:
    """Return boolean mask of visible atoms: keep all H for small ligands (<=18 heavy), polar H only for large drugs."""
    heavy = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() != 1)
    keep_nonpolar = (heavy <= 18) if show_nonpolar_h is None else bool(show_nonpolar_h)
    n = mol.GetNumAtoms()
    if keep_nonpolar:
        return np.ones(n, dtype=bool)
    mask = np.zeros(n, dtype=bool)
    for i, a in enumerate(mol.GetAtoms()):
        if a.GetAtomicNum() != 1:
            mask[i] = True
        else:
            if any(nb.GetAtomicNum() in (7, 8, 16) for nb in a.GetNeighbors()):
                mask[i] = True
    return mask


def _atom_color(atomic_num: int, palette: ScientificPalette, style_3d: str = "ball_stick") -> np.ndarray:
    style = (style_3d or "ball_stick").lower()
    if style == "pymol_neon_green":
        carbon_col = (58, 224, 72)
        nitrogen_col = (68, 108, 255)
        oxygen_col = (252, 68, 68)
        hydrogen_col = (248, 250, 252)
    elif style == "stick_clean":
        carbon_col = (82, 146, 166)
        nitrogen_col = hex_to_rgb(palette.s1)
        oxygen_col = (212, 36, 48)
        hydrogen_col = (244, 246, 250)
    elif style == "spacefill_cpk":
        carbon_col = (92, 96, 104)
        nitrogen_col = (48, 92, 212)
        oxygen_col = (220, 40, 46)
        hydrogen_col = (245, 245, 245)
    elif style == "metallic_studio":
        carbon_col = (164, 172, 184)
        nitrogen_col = hex_to_rgb(palette.s1)
        oxygen_col = hex_to_rgb(palette.alert)
        hydrogen_col = (240, 244, 248)
    else:
        carbon_col = (104, 116, 130)
        nitrogen_col = hex_to_rgb(palette.s1)
        oxygen_col = (212, 36, 48)
        hydrogen_col = (246, 248, 252)

    base = {
        1: hydrogen_col,
        6: carbon_col,
        7: nitrogen_col,
        8: oxygen_col,
        9: (22, 174, 152),
        15: (224, 130, 44),
        16: (226, 186, 52),
        17: (46, 168, 92),
        35: (146, 48, 36),
        53: (116, 46, 142),
    }
    if atomic_num in base:
        return np.array(base[atomic_num], dtype=np.float32)
    return np.array(nitrogen_col, dtype=np.float32)


def _embed_and_align(smiles: str, rotation_deg: Sequence[float] = (0.0, 0.0, 0.0)) -> Tuple[Chem.Mol, np.ndarray]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES for CYLview3D: {smiles!r}")
    mol = Chem.AddHs(mol)

    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    status = AllChem.EmbedMolecule(mol, params)
    if status != 0:
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)

    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol, maxIters=300)
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=300)
    except Exception:
        pass

    conf = mol.GetConformer()
    coords = np.array(
        [[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z] for i in range(mol.GetNumAtoms())],
        dtype=np.float32,
    )
    coords -= coords.mean(axis=0, keepdims=True)

    # Align principal plane (largest 2 singular vectors -> X, Y)
    if len(coords) >= 3:
        _, _, vt = np.linalg.svd(coords, full_matrices=False)
        coords = coords @ vt.T
        # Slight tilt so 3D depth of bonds/H atoms reads clearly
        tilt_x = np.deg2rad(16.0 + float(rotation_deg[0] if len(rotation_deg) > 0 else 0.0))
        tilt_y = np.deg2rad(-14.0 + float(rotation_deg[1] if len(rotation_deg) > 1 else 0.0))
        tilt_z = np.deg2rad(float(rotation_deg[2] if len(rotation_deg) > 2 else 0.0))
    else:
        tilt_x, tilt_y, tilt_z = 0.25, -0.20, 0.0

    rx = np.array([[1, 0, 0], [0, np.cos(tilt_x), -np.sin(tilt_x)], [0, np.sin(tilt_x), np.cos(tilt_x)]], dtype=np.float32)
    ry = np.array([[np.cos(tilt_y), 0, np.sin(tilt_y)], [0, 1, 0], [-np.sin(tilt_y), 0, np.cos(tilt_y)]], dtype=np.float32)
    rz = np.array([[np.cos(tilt_z), -np.sin(tilt_z), 0], [np.sin(tilt_z), np.cos(tilt_z), 0], [0, 0, 1]], dtype=np.float32)
    coords = coords @ rx.T @ ry.T @ rz.T

    # Flip Y for image coordinates (top-down)
    coords[:, 1] = -coords[:, 1]
    return mol, coords


def _shade_surface(
    nx: np.ndarray,
    ny: np.ndarray,
    nz: np.ndarray,
    base_rgb: np.ndarray,
    outline_rgb: np.ndarray,
    rim_width: float = 0.25,
    depth_t: Optional[np.ndarray] = None,
    spec_power: float = 56.0,
    spec_weight: float = 0.64,
) -> np.ndarray:
    """Apply CYLview/PyMOL studio lighting + glossy Phong specular + subtle depth cueing + contour rim."""
    k = np.array([-0.50, -0.58, 0.64], dtype=np.float32)
    k /= np.linalg.norm(k)
    f = np.array([0.62, 0.36, 0.69], dtype=np.float32)
    f /= np.linalg.norm(f)
    h_vec = k + np.array([0.0, 0.0, 1.0], dtype=np.float32)
    h_vec /= np.linalg.norm(h_vec)

    diff_k = np.maximum(0.0, nx * k[0] + ny * k[1] + nz * k[2])
    diff_f = np.maximum(0.0, nx * f[0] + ny * f[1] + nz * f[2])
    spec = np.maximum(0.0, nx * h_vec[0] + ny * h_vec[1] + nz * h_vec[2]) ** spec_power

    ambient = 0.26 + 0.14 * np.maximum(0.0, nz)
    shade = ambient + 0.66 * diff_k + 0.22 * diff_f
    rgb = base_rgb[None, :] * shade[:, None] + np.array([255.0, 255.0, 255.0], dtype=np.float32)[None, :] * (spec_weight * spec[:, None])

    if depth_t is not None:
        fog = (1.0 - np.clip(depth_t, 0.0, 1.0)) * 0.14
        rgb = rgb * (1.0 - fog[:, None]) + 255.0 * fog[:, None]

    rim_factor = np.clip((rim_width - nz) / max(rim_width * 0.55, 1e-3), 0.0, 1.0)
    rgb = rgb * (1.0 - rim_factor[:, None]) + outline_rgb[None, :] * rim_factor[:, None]
    return np.clip(rgb, 0.0, 255.0)


def project_3d_substructure_anchor(
    smiles: str,
    smarts: str,
    box_in: Tuple[float, float, float, float],
    norm_box: Sequence[float] = (0.0, 0.0, 1.0, 1.0),
    rotation_deg: Sequence[float] = (0.0, 0.0, 0.0),
    show_nonpolar_h: Optional[bool] = None,
) -> Tuple[float, float]:
    """Deterministically project a SMARTS pharmacophore match to exact slide (x_in, y_in) coordinates."""
    mol, coords = _embed_and_align(smiles, rotation_deg=rotation_deg)
    vis = _visible_atom_mask(mol, show_nonpolar_h)
    radii_a = np.array([_ATOM_RADII_A.get(a.GetAtomicNum(), 0.36) for a in mol.GetAtoms()], dtype=np.float32)

    vis_coords = coords[vis]
    vis_radii = radii_a[vis]
    min_xy = (vis_coords[:, :2] - vis_radii[:, None]).min(axis=0)
    max_xy = (vis_coords[:, :2] + vis_radii[:, None]).max(axis=0)
    span_xy = np.maximum(max_xy - min_xy, 1.8)

    nb = norm_box if len(norm_box) == 4 else (0.0, 0.0, 1.0, 1.0)
    sub_l = box_in[0] + float(nb[0]) * box_in[2]
    sub_t = box_in[1] + float(nb[1]) * box_in[3]
    sub_w = float(nb[2]) * box_in[2]
    sub_h = float(nb[3]) * box_in[3]

    avail_w = max(0.6, sub_w - 0.16)
    avail_h = max(0.6, sub_h - 0.16)
    scale = min(avail_w / float(span_xy[0]), avail_h / float(span_xy[1]))
    mid_xy = 0.5 * (min_xy + max_xy)
    cx_box = sub_l + 0.5 * sub_w
    cy_box = sub_t + 0.5 * sub_h

    pat = Chem.MolFromSmarts(smarts)
    match = mol.GetSubstructMatch(pat) if pat is not None else ()
    if not match:
        return (round(cx_box, 3), round(cy_box, 3))
    mean_xy = coords[list(match), :2].mean(axis=0)
    px = cx_box + (float(mean_xy[0]) - float(mid_xy[0])) * scale
    py = cy_box + (float(mean_xy[1]) - float(mid_xy[1])) * scale
    return (round(px, 3), round(py, 3))


def _try_render_pymol_raytrace(
    sdf_path: Path,
    out_png: Path,
    width: int = 960,
    height: int = 720,
    dpi: int = 300,
    style_3d: str = "ball_stick",
) -> bool:
    """Invoke headless PyMOL ray tracing when `pymol` CLI is installed in Linux container."""
    pymol_bin = shutil.which("pymol")
    if not pymol_bin:
        return False
    pml_path = out_png.with_suffix(".pml")
    style = (style_3d or "ball_stick").lower()
    if style == "stick_clean":
        rep_cmds = ["show sticks, lig", "set stick_radius, 0.22", "util.cbac lig"]
    elif style == "spacefill_cpk":
        rep_cmds = ["show spheres, lig", "set sphere_scale, 0.92", "util.cbaw lig"]
    elif style == "pymol_neon_green":
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.17", "set sphere_scale, 0.29", "util.cbag lig"]
    elif style == "metallic_studio":
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.16", "set sphere_scale, 0.28", "set spec_reflect, 1.0", "set spec_power, 200", "util.cbaw lig"]
    else:
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.16", "set sphere_scale, 0.27", "util.cbaw lig"]

    script = "\n".join([
        f"load {sdf_path.resolve()}, lig",
        "bg_color white",
        "set ray_opaque_background, 0",
        "hide everything",
        *rep_cmds,
        "set valence, 1",
        "set antialias, 2",
        "set ambient, 0.35",
        "set spec_reflect, 0.85",
        "orient lig",
        "zoom lig, 1.4",
        f"ray {width}, {height}",
        f"png {out_png.resolve()}, dpi={dpi}",
        "quit",
    ])
    try:
        pml_path.write_text(script, encoding="utf-8")
        subprocess.run(
            [pymol_bin, "-cq", str(pml_path)],
            timeout=25,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return out_png.is_file() and out_png.stat().st_size > 4096
    except Exception:
        return False
    finally:
        pml_path.unlink(missing_ok=True)


def render_cylview3d(
    smiles: str,
    output_png: Path | str,
    palette_id: str = "lancet",
    outline_stroke: str = "#3D4652",
    rotation_deg: Sequence[float] = (0.0, 0.0, 0.0),
    target_width_px: int = 860,
    dpi: int = 600,
    show_nonpolar_h: Optional[bool] = None,
    style_3d: str = "ball_stick",
) -> CYLviewRenderResult:
    """Render deterministic ETKDGv3+MMFF94 3D conformer PNG, export .sdf, using PyMOL ray-trace if installed."""
    palette = get_palette(palette_id)
    style = (style_3d or "ball_stick").lower()
    style_cfg = {
        "ball_stick": {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True, "rim_w": 0.24, "spec_power": 56.0, "spec_weight": 0.64},
        "stick_clean": {"sphere_mult": 0.40, "bond_mult": 1.35, "draw_bonds": True, "rim_w": 0.16, "spec_power": 48.0, "spec_weight": 0.58},
        "spacefill_cpk": {"sphere_mult": 2.25, "bond_mult": 0.0, "draw_bonds": False, "rim_w": 0.20, "spec_power": 42.0, "spec_weight": 0.55},
        "pymol_neon_green": {"sphere_mult": 1.04, "bond_mult": 1.05, "draw_bonds": True, "rim_w": 0.20, "spec_power": 70.0, "spec_weight": 0.72},
        "metallic_studio": {"sphere_mult": 1.02, "bond_mult": 1.02, "draw_bonds": True, "rim_w": 0.26, "spec_power": 96.0, "spec_weight": 0.88},
    }.get(style, {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True, "rim_w": 0.24, "spec_power": 56.0, "spec_weight": 0.64})

    resolved_smiles = resolve_compound_smiles(smiles) or smiles
    mol, coords = _embed_and_align(resolved_smiles, rotation_deg=rotation_deg)
    vis = _visible_atom_mask(mol, show_nonpolar_h)
    vis_bonds = sum(1 for b in mol.GetBonds() if vis[b.GetBeginAtomIdx()] and vis[b.GetEndAtomIdx()])

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sdf_p = out_p.with_suffix(".sdf")
    writer = Chem.SDWriter(str(sdf_p))
    writer.write(mol)
    writer.close()

    if _try_render_pymol_raytrace(sdf_p, out_p, width=max(720, target_width_px), height=max(540, int(target_width_px * 0.75)), dpi=min(dpi, 300), style_3d=style):
        with Image.open(out_p) as py_img:
            pw, ph = py_img.size
        return CYLviewRenderResult(
            png_path=out_p,
            smiles=resolved_smiles,
            pixel_width=pw,
            pixel_height=ph,
            atom_count=int(vis.sum()),
            bond_count=vis_bonds,
            method=f"PyMOL+RayTrace({style})",
            sdf_path=sdf_p,
        )

    eff_outline = "#1E262E" if style == "pymol_neon_green" else outline_stroke
    outline_rgb = np.array(hex_to_rgb(eff_outline), dtype=np.float32)

    supersample = 2
    ss_w = target_width_px * supersample
    radii = np.array([_ATOM_RADII_A.get(a.GetAtomicNum(), 0.36) for a in mol.GetAtoms()], dtype=np.float32) * float(style_cfg["sphere_mult"])
    colors = np.array([_atom_color(a.GetAtomicNum(), palette, style_3d=style) for a in mol.GetAtoms()], dtype=np.float32)

    vis_coords = coords[vis]
    vis_radii = radii[vis]
    min_xy = (vis_coords[:, :2] - vis_radii[:, None]).min(axis=0)
    max_xy = (vis_coords[:, :2] + vis_radii[:, None]).max(axis=0)
    span_xy = np.maximum(max_xy - min_xy, 1.8)
    pad_px = 44 * supersample
    scale = (ss_w - 2 * pad_px) / float(span_xy[0])
    est_h = int(span_xy[1] * scale) + 2 * pad_px
    max_ss_h = int(ss_w * 0.92)
    if est_h > max_ss_h:
        scale = (max_ss_h - 2 * pad_px) / float(span_xy[1])
        ss_w = int(span_xy[0] * scale) + 2 * pad_px
        ss_h = max_ss_h
    else:
        ss_h = max(int(360 * supersample), est_h)

    center_a = 0.5 * (min_xy + max_xy)
    pts = np.empty_like(coords)
    pts[:, 0] = (coords[:, 0] - center_a[0]) * scale + ss_w * 0.5
    pts[:, 1] = (coords[:, 1] - center_a[1]) * scale + ss_h * 0.5
    pts[:, 2] = coords[:, 2] * scale
    radii_px = radii * scale

    vis_z = pts[vis, 2]
    z_min = float(vis_z.min()) if len(vis_z) else -1.0
    z_span = max(float(vis_z.max() - z_min), 1e-4) if len(vis_z) else 1.0

    color_buf = np.zeros((ss_h, ss_w, 3), dtype=np.float32)
    alpha_buf = np.zeros((ss_h, ss_w), dtype=np.float32)
    z_buf = np.full((ss_h, ss_w), -1e9, dtype=np.float32)

    # 1. Rasterize half-cylinder bonds with analytic ray-cylinder intersection (visible atoms only)
    bond_r = float(0.128 * float(style_cfg["bond_mult"]) * scale)
    vis_bonds = 0
    for bond in (mol.GetBonds() if style_cfg["draw_bonds"] else []):
        i1 = bond.GetBeginAtomIdx()
        i2 = bond.GetEndAtomIdx()
        if not (vis[i1] and vis[i2]):
            continue
        vis_bonds += 1
        p1 = pts[i1]
        p2 = pts[i2]
        mid = 0.5 * (p1 + p2)
        order = bond.GetBondTypeAsDouble()
        eff_r = bond_r * (1.12 if order >= 1.8 else 1.0)

        for seg_start, seg_end, seg_col in (
            (p1, mid, colors[i1]),
            (mid, p2, colors[i2]),
        ):
            v = seg_end - seg_start
            L = float(np.linalg.norm(v))
            if L < 1e-3:
                continue
            d = v / L

            x0 = max(0, int(np.floor(min(seg_start[0], seg_end[0]) - eff_r - 2)))
            x1 = min(ss_w, int(np.ceil(max(seg_start[0], seg_end[0]) + eff_r + 2)))
            y0 = max(0, int(np.floor(min(seg_start[1], seg_end[1]) - eff_r - 2)))
            y1 = min(ss_h, int(np.ceil(max(seg_start[1], seg_end[1]) + eff_r + 2)))
            if x1 <= x0 or y1 <= y0:
                continue

            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            ox = xx - seg_start[0]
            oy = yy - seg_start[1]
            dx, dy, dz = float(d[0]), float(d[1]), float(d[2])
            denom_xy = max(1e-5, 1.0 - dz * dz)

            if denom_xy < 1e-4:
                dist2 = ox * ox + oy * oy
                hit = dist2 <= eff_r * eff_r
                if not np.any(hit):
                    continue
                z_hit = np.maximum(seg_start[2], seg_end[2])
                nx_h = ox[hit] / max(eff_r, 1e-4)
                ny_h = oy[hit] / max(eff_r, 1e-4)
                nz_h = np.sqrt(np.maximum(0.0, 1.0 - nx_h * nx_h - ny_h * ny_h))
                z_vals = np.full(nx_h.shape, z_hit, dtype=np.float32)
            else:
                dot_xy = ox * dx + oy * dy
                A = 1.0 - dz * dz
                B = -2.0 * dz * dot_xy
                C = (ox * ox + oy * oy) - (dot_xy * dot_xy) - eff_r * eff_r
                disc = B * B - 4.0 * A * C
                valid = disc >= 0.0
                if not np.any(valid):
                    continue
                sqrt_d = np.sqrt(np.maximum(0.0, disc))
                z_rel = (-B + sqrt_d) / (2.0 * A)
                t_along = dot_xy + z_rel * dz
                hit = valid & (t_along >= -0.5) & (t_along <= L + 0.5)
                if not np.any(hit):
                    continue
                z_vals = seg_start[2] + z_rel[hit]
                t_h = t_along[hit]
                nx_h = (ox[hit] - t_h * dx) / eff_r
                ny_h = (oy[hit] - t_h * dy) / eff_r
                nz_h = (z_rel[hit] - t_h * dz) / eff_r

            sub_z = z_buf[y0:y1, x0:x1]
            vis_hit = z_vals > sub_z[hit]
            if not np.any(vis_hit):
                continue

            dt = (z_vals[vis_hit] - z_min) / z_span
            shaded = _shade_surface(
                nx_h[vis_hit], ny_h[vis_hit], nz_h[vis_hit],
                base_rgb=seg_col, outline_rgb=outline_rgb, rim_width=float(style_cfg["rim_w"]) * 0.9, depth_t=dt,
                spec_power=float(style_cfg["spec_power"]), spec_weight=float(style_cfg["spec_weight"]),
            )
            hy, hx = np.where(hit)
            vy = hy[vis_hit] + y0
            vx = hx[vis_hit] + x0
            z_buf[vy, vx] = z_vals[vis_hit]
            color_buf[vy, vx] = shaded
            alpha_buf[vy, vx] = 255.0

    # 2. Rasterize atomic spheres (visible atoms only)
    for idx in range(mol.GetNumAtoms()):
        if not vis[idx]:
            continue
        cx, cy, cz = float(pts[idx, 0]), float(pts[idx, 1]), float(pts[idx, 2])
        r = float(radii_px[idx])
        col = colors[idx]
        x0 = max(0, int(np.floor(cx - r - 2)))
        x1 = min(ss_w, int(np.ceil(cx + r + 2)))
        y0 = max(0, int(np.floor(cy - r - 2)))
        y1 = min(ss_h, int(np.ceil(cy + r + 2)))
        if x1 <= x0 or y1 <= y0:
            continue

        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx = (xx - cx) / r
        dy = (yy - cy) / r
        r2 = dx * dx + dy * dy
        hit = r2 <= 1.0
        if not np.any(hit):
            continue

        nz = np.sqrt(np.maximum(0.0, 1.0 - r2[hit]))
        z_vals = cz + r * nz
        sub_z = z_buf[y0:y1, x0:x1]
        vis_hit = z_vals > sub_z[hit]
        if not np.any(vis_hit):
            continue

        dt = (z_vals[vis_hit] - z_min) / z_span
        shaded = _shade_surface(
            dx[hit][vis_hit], dy[hit][vis_hit], nz[vis_hit],
            base_rgb=col, outline_rgb=outline_rgb, rim_width=float(style_cfg["rim_w"]), depth_t=dt,
            spec_power=float(style_cfg["spec_power"]), spec_weight=float(style_cfg["spec_weight"]),
        )
        hy, hx = np.where(hit)
        vy = hy[vis_hit] + y0
        vx = hx[vis_hit] + x0
        z_buf[vy, vx] = z_vals[vis_hit]
        color_buf[vy, vx] = shaded
        alpha_buf[vy, vx] = 255.0

    # 3. Whisper-soft contact shadow ellipse underneath molecule (keeps corners 100% transparent)
    rgba_ss = np.dstack([color_buf, alpha_buf]).astype(np.uint8)
    vis_pts_x = pts[vis, 0]
    vis_pts_y = pts[vis, 1]
    if len(vis_pts_x) > 0:
        sh_cx = float(0.5 * (vis_pts_x.min() + vis_pts_x.max()))
        sh_cy = float(vis_pts_y.max() + radii_px[vis].max() * 0.45)
        sh_rx = max(24.0, float(0.38 * (vis_pts_x.max() - vis_pts_x.min())))
        sh_ry = max(8.0, float(10.0 * supersample))
        sy0 = max(0, int(sh_cy - sh_ry - 4))
        sy1 = min(ss_h, int(sh_cy + sh_ry + 4))
        sx0 = max(0, int(sh_cx - sh_rx - 4))
        sx1 = min(ss_w, int(sh_cx + sh_rx + 4))
        if sy1 > sy0 and sx1 > sx0:
            syy, sxx = np.mgrid[sy0:sy1, sx0:sx1].astype(np.float32)
            ell = ((sxx - sh_cx) / sh_rx) ** 2 + ((syy - sh_cy) / sh_ry) ** 2
            sh_a = np.clip((1.0 - ell) * 26.0, 0.0, 26.0).astype(np.float32)
            bg_mask = rgba_ss[sy0:sy1, sx0:sx1, 3] == 0
            rgba_ss[sy0:sy1, sx0:sx1, 0][bg_mask] = 15
            rgba_ss[sy0:sy1, sx0:sx1, 1][bg_mask] = 23
            rgba_ss[sy0:sy1, sx0:sx1, 2][bg_mask] = 42
            rgba_ss[sy0:sy1, sx0:sx1, 3][bg_mask] = sh_a[bg_mask].astype(np.uint8)

    img_ss = Image.fromarray(rgba_ss, mode="RGBA")
    img_out = img_ss.resize((ss_w // supersample, ss_h // supersample), resample=Image.Resampling.LANCZOS)

    arr = np.array(img_out)
    ys, xs = np.where(arr[:, :, 3] > 6)
    if len(ys) > 0 and len(xs) > 0:
        pad = 12
        y0 = max(0, int(ys.min()) - pad)
        y1 = min(img_out.height, int(ys.max()) + 1 + pad)
        x0 = max(0, int(xs.min()) - pad)
        x1 = min(img_out.width, int(xs.max()) + 1 + pad)
        img_out = img_out.crop((x0, y0, x1, y1))

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    img_out.save(str(out_p), format="PNG", dpi=(dpi, dpi))

    return CYLviewRenderResult(
        png_path=out_p,
        smiles=resolved_smiles,
        pixel_width=img_out.width,
        pixel_height=img_out.height,
        atom_count=int(vis.sum()),
        bond_count=vis_bonds,
        sdf_path=sdf_p,
    )
