"""Engine 2: CYLview3DEngine — Studio PBR 3D Molecular Renderer.

Computes exact 3D molecular geometry via RDKit ETKDGv3 + MMFF94, aligns principal axes via SVD,
and renders PyMOL/Blender-grade studio 3-point PBR spheres + multi-order half-blended valence
cylinders (single / double / aromatic / triple) with analytical 3D Ambient Occlusion, perspective
projection, soft Gaussian ground contact shadow, and true Alpha transparency.
Uses headless PyMOL ray tracing automatically when available in Linux containers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageFilter
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
    method: str = "ETKDGv3+MMFF94+StudioPBR"
    sdf_path: Optional[Path] = None


_ATOM_RADII_A: Dict[int, float] = {
    1: 0.20,
    6: 0.32,
    7: 0.33,
    8: 0.32,
    9: 0.30,
    15: 0.40,
    16: 0.40,
    17: 0.38,
    35: 0.42,
    53: 0.45,
    26: 0.44,
    28: 0.43,
    29: 0.43,
    46: 0.45,
    78: 0.46,
}


def _visible_atom_mask(
    mol: Chem.Mol,
    show_nonpolar_h: Optional[bool] = None,
    style_3d: str = "ball_stick",
) -> np.ndarray:
    """Return mask of visible atoms. Keeps all H for ball/stick & CPK (<=38 heavy atoms); clean sticks hide nonpolar H."""
    heavy = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() != 1)
    style = (style_3d or "ball_stick").lower()
    if show_nonpolar_h is None:
        keep_nonpolar = (heavy <= 14) if style == "stick_clean" else (heavy <= 38)
    else:
        keep_nonpolar = bool(show_nonpolar_h)

    n = mol.GetNumAtoms()
    if keep_nonpolar:
        return np.ones(n, dtype=bool)
    mask = np.zeros(n, dtype=bool)
    for i, a in enumerate(mol.GetAtoms()):
        if a.GetAtomicNum() != 1:
            mask[i] = True
        elif any(nb.GetAtomicNum() in (7, 8, 16) for nb in a.GetNeighbors()):
            mask[i] = True
    return mask


def _atom_color(atomic_num: int, palette: ScientificPalette, style_3d: str = "ball_stick") -> np.ndarray:
    style = (style_3d or "ball_stick").lower()
    roles = palette.slide_roles()
    c1_rgb = hex_to_rgb(roles["c1"])
    c2_rgb = hex_to_rgb(roles["c2"])
    alert_rgb = hex_to_rgb(roles["alert"])

    if style == "pymol_neon_green":
        carbon_col = (52, 212, 86)
        nitrogen_col = (56, 108, 250)
        oxygen_col = (242, 62, 62)
        hydrogen_col = (232, 238, 245)
    elif style == "stick_clean":
        carbon_col = (68, 138, 164)
        nitrogen_col = c1_rgb
        oxygen_col = (218, 48, 56)
        hydrogen_col = (232, 236, 242)
    elif style == "spacefill_cpk":
        carbon_col = (76, 82, 92)
        nitrogen_col = (44, 92, 214)
        oxygen_col = (218, 42, 48)
        hydrogen_col = (234, 236, 240)
    elif style == "metallic_studio":
        carbon_col = (158, 168, 182)
        nitrogen_col = c1_rgb
        oxygen_col = alert_rgb
        hydrogen_col = (228, 234, 242)
    else:
        # Studio dark-slate carbon harmonizing with theme accent for heteroatoms
        carbon_col = (84, 94, 108)
        nitrogen_col = c1_rgb if _rgb_brightness(c1_rgb) < 210 else (44, 94, 196)
        oxygen_col = (216, 44, 52)
        hydrogen_col = (232, 237, 244)

    base = {
        1: hydrogen_col,
        6: carbon_col,
        7: nitrogen_col,
        8: oxygen_col,
        9: c2_rgb if style == "metallic_studio" else (24, 178, 152),
        15: (232, 134, 38),
        16: (224, 182, 42),
        17: (42, 168, 88),
        35: (148, 50, 38),
        53: (118, 46, 148),
    }
    if atomic_num in base:
        return np.array(base[atomic_num], dtype=np.float32)
    return np.array(c2_rgb, dtype=np.float32)


def _rgb_brightness(rgb: Tuple[int, int, int]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


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

    if len(coords) >= 3:
        _, _, vt = np.linalg.svd(coords, full_matrices=False)
        coords = coords @ vt.T
        tilt_x = np.deg2rad(16.0 + float(rotation_deg[0] if len(rotation_deg) > 0 else 0.0))
        tilt_y = np.deg2rad(-14.0 + float(rotation_deg[1] if len(rotation_deg) > 1 else 0.0))
        tilt_z = np.deg2rad(float(rotation_deg[2] if len(rotation_deg) > 2 else 0.0))
    else:
        tilt_x, tilt_y, tilt_z = 0.25, -0.20, 0.0

    rx = np.array([[1, 0, 0], [0, np.cos(tilt_x), -np.sin(tilt_x)], [0, np.sin(tilt_x), np.cos(tilt_x)]], dtype=np.float32)
    ry = np.array([[np.cos(tilt_y), 0, np.sin(tilt_y)], [0, 1, 0], [-np.sin(tilt_y), 0, np.cos(tilt_y)]], dtype=np.float32)
    rz = np.array([[np.cos(tilt_z), -np.sin(tilt_z), 0], [np.sin(tilt_z), np.cos(tilt_z), 0], [0, 0, 1]], dtype=np.float32)
    coords = coords @ rx.T @ ry.T @ rz.T
    coords[:, 1] = -coords[:, 1]
    return mol, coords


def _apply_perspective(coords: np.ndarray, span_max: float) -> Tuple[np.ndarray, np.ndarray]:
    """Apply subtle telephoto 3D perspective foreshortening along Z."""
    cam_dist = max(18.0, float(span_max) * 3.6)
    persp = cam_dist / np.maximum(cam_dist - coords[:, 2], 4.0)
    proj = coords.copy()
    proj[:, 0] *= persp
    proj[:, 1] *= persp
    return proj, persp


def _bond_offsets_3d(
    mol: Chem.Mol,
    coords: np.ndarray,
    bond: Chem.Bond,
) -> List[Tuple[np.ndarray, float]]:
    """Return 3D valence cylinder offsets (in Angstroms) and radius multipliers for single/double/aromatic/triple."""
    order = bond.GetBondTypeAsDouble()
    is_arom = bond.GetIsAromatic() or (1.30 <= order <= 1.75)
    if order < 1.30 and not is_arom:
        return [(np.zeros(3, dtype=np.float32), 1.0)]

    i1, i2 = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
    p1, p2 = coords[i1], coords[i2]
    bvec = p2 - p1
    blen = float(np.linalg.norm(bvec))
    if blen < 1e-4:
        return [(np.zeros(3, dtype=np.float32), 1.0)]
    u = bvec / blen

    # Determine ring centroid or neighbor vector for true in-plane double-bond orientation
    ref_dir: Optional[np.ndarray] = None
    ring_info = mol.GetRingInfo()
    for ring in ring_info.AtomRings():
        if i1 in ring and i2 in ring:
            rc = coords[list(ring)].mean(axis=0)
            mid = 0.5 * (p1 + p2)
            cand = rc - mid
            cand -= np.dot(cand, u) * u
            if np.linalg.norm(cand) > 1e-3:
                ref_dir = cand / np.linalg.norm(cand)
            break

    if ref_dir is None:
        for atom_idx, p_anchor in ((i1, p1), (i2, p2)):
            for nb in mol.GetAtomWithIdx(atom_idx).GetNeighbors():
                nb_idx = nb.GetIdx()
                if nb_idx not in (i1, i2) and nb.GetAtomicNum() != 1:
                    cand = coords[nb_idx] - p_anchor
                    cand -= np.dot(cand, u) * u
                    if np.linalg.norm(cand) > 1e-3:
                        ref_dir = cand / np.linalg.norm(cand)
                        break
            if ref_dir is not None:
                break

    if ref_dir is None:
        perp = np.cross(u, np.array([0.0, 0.0, 1.0], dtype=np.float32))
        if np.linalg.norm(perp) < 1e-3:
            perp = np.cross(u, np.array([0.0, 1.0, 0.0], dtype=np.float32))
        ref_dir = perp / max(float(np.linalg.norm(perp)), 1e-4)

    if order >= 2.5:
        return [
            (-0.088 * ref_dir, 0.52),
            (np.zeros(3, dtype=np.float32), 0.54),
            (0.088 * ref_dir, 0.52),
        ]
    if is_arom:
        return [
            (-0.056 * ref_dir, 0.70),
            (0.058 * ref_dir, 0.54),
        ]
    return [
        (-0.064 * ref_dir, 0.66),
        (0.064 * ref_dir, 0.66),
    ]


def _compute_pixel_ao(
    world_pts: np.ndarray,
    normals: np.ndarray,
    occ_coords: np.ndarray,
    occ_radii: np.ndarray,
    strength: float = 0.72,
) -> np.ndarray:
    """Fast vectorized analytical 3D sphere ambient occlusion for crevices and atom-bond junctions."""
    if len(occ_coords) == 0 or len(world_pts) == 0:
        return np.ones(len(world_pts), dtype=np.float32)

    diff = occ_coords[None, :, :] - world_pts[:, None, :]  # (K, M, 3)
    d2 = np.sum(diff * diff, axis=2)  # (K, M)
    r2 = (occ_radii * occ_radii)[None, :]
    eff_d2 = np.maximum(d2, r2 * 1.02 + 1e-4)
    inv_d = np.sqrt(1.0 / np.maximum(d2, 1e-5))
    dot_n = np.maximum(0.0, np.sum(normals[:, None, :] * diff, axis=2) * inv_d)
    # Falloff vanishes gently beyond ~3.2 Angstroms
    range_w = np.clip(1.0 - d2 / 11.5, 0.0, 1.0)
    occ = dot_n * (r2 / eff_d2) * range_w
    return np.clip(1.0 - strength * np.sum(occ, axis=1), 0.42, 1.0).astype(np.float32)


def _shade_surface_pbr(
    nx: np.ndarray,
    ny: np.ndarray,
    nz: np.ndarray,
    base_rgb: np.ndarray,
    ao: Optional[np.ndarray] = None,
    spec_power: float = 92.0,
    spec_weight: float = 0.74,
    metallic: float = 0.0,
) -> np.ndarray:
    """3-point softbox studio PBR shading with analytical AO, dual specular lobe, and clean Fresnel rim."""
    k = np.array([-0.44, -0.56, 0.70], dtype=np.float32)
    k /= np.linalg.norm(k)
    f = np.array([0.64, 0.22, 0.73], dtype=np.float32)
    f /= np.linalg.norm(f)
    b_l = np.array([0.0, 0.85, 0.52], dtype=np.float32)
    b_l /= np.linalg.norm(b_l)

    h_vec = k + np.array([0.0, 0.0, 1.0], dtype=np.float32)
    h_vec /= np.linalg.norm(h_vec)

    diff_k = np.maximum(0.0, nx * k[0] + ny * k[1] + nz * k[2])
    diff_f = np.maximum(0.0, nx * f[0] + ny * f[1] + nz * f[2])
    diff_b = np.maximum(0.0, nx * b_l[0] + ny * b_l[1] + nz * b_l[2])

    ndoth = np.maximum(0.0, nx * h_vec[0] + ny * h_vec[1] + nz * h_vec[2])
    spec_pin = ndoth ** spec_power
    spec_sheen = ndoth ** 14.0

    ao_term = ao if ao is not None else np.ones_like(nz)
    diff_scale = (0.34 + 0.62 * diff_k + 0.20 * diff_f + 0.10 * diff_b) * ao_term
    fresnel = np.power(np.clip(1.0 - nz, 0.0, 1.0), 3.2)

    base_mat = base_rgb if base_rgb.ndim == 2 else base_rgb[None, :]
    lit = base_mat * diff_scale[:, None]

    # Metallic tints specular slightly toward base pigment; dielectric keeps pure softbox white
    spec_tint = (
        base_mat * (0.45 * metallic) + np.array([255.0, 255.0, 255.0], dtype=np.float32)[None, :] * (1.0 - 0.45 * metallic)
    )
    spec_total = spec_weight * spec_pin[:, None] + 0.14 * spec_sheen[:, None]
    lit = lit + spec_tint * spec_total

    # Crisp sky Fresnel rim light (plus ultra-gentle edge definition so pale H spheres pop cleanly on white)
    sky_rim = np.array([232.0, 241.0, 252.0], dtype=np.float32)[None, :]
    edge_def = 1.0 - 0.10 * np.power(np.clip(1.0 - nz, 0.0, 1.0), 6.0)
    lit = (lit + sky_rim * (0.20 * fresnel[:, None]) * ao_term[:, None]) * edge_def[:, None]
    return np.clip(lit, 0.0, 255.0)


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
    radii_a = np.array([_ATOM_RADII_A.get(a.GetAtomicNum(), 0.32) for a in mol.GetAtoms()], dtype=np.float32)

    vis_raw = coords[vis]
    raw_span = float(np.max(vis_raw.max(axis=0) - vis_raw.min(axis=0))) if len(vis_raw) else 4.0
    coords_p, persp = _apply_perspective(coords, raw_span)
    radii_p = radii_a * persp

    vis_coords = coords_p[vis]
    vis_radii = radii_p[vis]
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
    mean_xy = coords_p[list(match), :2].mean(axis=0)
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
    rotation_deg: Sequence[float] = (0.0, 0.0, 0.0),
    show_nonpolar_h: Optional[bool] = None,
) -> bool:
    """Invoke headless PyMOL studio ray tracing when `pymol` CLI is installed in Linux container."""
    pymol_bin = shutil.which("pymol")
    if not pymol_bin:
        return False
    pml_path = out_png.with_suffix(".pml")
    style = (style_3d or "ball_stick").lower()
    if style == "stick_clean":
        rep_cmds = ["show sticks, lig", "set stick_radius, 0.19", "util.cbac lig"]
    elif style == "spacefill_cpk":
        rep_cmds = ["show spheres, lig", "set sphere_scale, 0.90", "util.cbaw lig"]
    elif style == "pymol_neon_green":
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.14", "set sphere_scale, 0.25", "util.cbag lig"]
    elif style == "metallic_studio":
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.14", "set sphere_scale, 0.24", "set spec_reflect, 1.0", "set spec_power, 220", "util.cbaw lig"]
    else:
        rep_cmds = ["show sticks, lig", "show spheres, lig", "set stick_radius, 0.14", "set sphere_scale, 0.24", "util.cbaw lig"]

    rx = float(rotation_deg[0] if len(rotation_deg) > 0 else 0.0) + 14.0
    ry = float(rotation_deg[1] if len(rotation_deg) > 1 else 0.0) - 12.0
    rz = float(rotation_deg[2] if len(rotation_deg) > 2 else 0.0)

    h_cmds = ["remove (hydro and not (neighbor elem N+O+S))"] if show_nonpolar_h is False else []

    script = "\n".join([
        f"load {sdf_path.resolve()}, lig",
        *h_cmds,
        "bg_color white",
        "set ray_opaque_background, 0",
        "hide everything",
        *rep_cmds,
        "set valence, 1",
        "set valence_mode, 1",
        "set stick_ball, on",
        "set stick_ball_ratio, 1.85",
        "set sphere_quality, 4",
        "set stick_quality, 24",
        "set antialias, 2",
        "set ray_shadows, 1",
        "set light_count, 3",
        "set ambient, 0.24",
        "set direct, 0.50",
        "set reflect, 0.45",
        "set spec_reflect, 0.85",
        "set shininess, 55",
        "set depth_cue, 0",
        "orient lig",
        f"turn x, {rx:.1f}",
        f"turn y, {ry:.1f}",
        f"turn z, {rz:.1f}",
        "zoom lig, 1.2",
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
        if not (out_png.is_file() and out_png.stat().st_size > 4096):
            return False
        with Image.open(out_png) as raw_im:
            im_rgba = raw_im.convert("RGBA")
            arr = np.array(im_rgba)
            ys, xs = np.where(arr[:, :, 3] > 6)
            if len(ys) > 0 and len(xs) > 0:
                pad = 12
                im_crop = im_rgba.crop((
                    max(0, int(xs.min()) - pad),
                    max(0, int(ys.min()) - pad),
                    min(im_rgba.width, int(xs.max()) + 1 + pad),
                    min(im_rgba.height, int(ys.max()) + 1 + pad),
                ))
                im_crop.save(str(out_png), format="PNG", dpi=(dpi, dpi))
        return True
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
    """Render publication-grade studio 3D conformer PNG, export .sdf, using PyMOL ray-trace if installed."""
    palette = get_palette(palette_id)
    style = (style_3d or "ball_stick").lower()
    style_cfg = {
        "ball_stick": {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True, "spec_power": 92.0, "spec_weight": 0.72, "metallic": 0.0, "ao_str": 0.72},
        "stick_clean": {"sphere_mult": 0.44, "bond_mult": 1.28, "draw_bonds": True, "spec_power": 78.0, "spec_weight": 0.65, "metallic": 0.0, "ao_str": 0.62},
        "spacefill_cpk": {"sphere_mult": 2.65, "bond_mult": 0.0, "draw_bonds": False, "spec_power": 64.0, "spec_weight": 0.58, "metallic": 0.0, "ao_str": 0.85},
        "pymol_neon_green": {"sphere_mult": 1.04, "bond_mult": 1.04, "draw_bonds": True, "spec_power": 108.0, "spec_weight": 0.78, "metallic": 0.08, "ao_str": 0.74},
        "metallic_studio": {"sphere_mult": 1.02, "bond_mult": 1.02, "draw_bonds": True, "spec_power": 135.0, "spec_weight": 0.94, "metallic": 0.85, "ao_str": 0.76},
    }.get(style, {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True, "spec_power": 92.0, "spec_weight": 0.72, "metallic": 0.0, "ao_str": 0.72})

    resolved_smiles = resolve_compound_smiles(smiles) or smiles
    mol, coords_world = _embed_and_align(resolved_smiles, rotation_deg=rotation_deg)
    vis = _visible_atom_mask(mol, show_nonpolar_h, style_3d=style)
    vis_bonds = sum(1 for b in mol.GetBonds() if vis[b.GetBeginAtomIdx()] and vis[b.GetEndAtomIdx()])

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sdf_p = out_p.with_suffix(".sdf")
    writer = Chem.SDWriter(str(sdf_p))
    writer.write(mol)
    writer.close()

    if _try_render_pymol_raytrace(
        sdf_p, out_p,
        width=max(760, target_width_px),
        height=max(560, int(target_width_px * 0.75)),
        dpi=min(dpi, 300),
        style_3d=style,
        rotation_deg=rotation_deg,
        show_nonpolar_h=show_nonpolar_h,
    ):
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

    supersample = 3 if target_width_px <= 640 else 2
    ss_w = target_width_px * supersample
    radii_a = np.array([_ATOM_RADII_A.get(a.GetAtomicNum(), 0.32) for a in mol.GetAtoms()], dtype=np.float32) * float(style_cfg["sphere_mult"])
    colors = np.array([_atom_color(a.GetAtomicNum(), palette, style_3d=style) for a in mol.GetAtoms()], dtype=np.float32)

    vis_raw = coords_world[vis]
    raw_span = float(np.max(vis_raw.max(axis=0) - vis_raw.min(axis=0))) if len(vis_raw) else 4.0
    coords_p, persp = _apply_perspective(coords_world, raw_span)
    radii_p = radii_a * persp

    vis_coords = coords_p[vis]
    vis_radii = radii_p[vis]
    min_xy = (vis_coords[:, :2] - vis_radii[:, None]).min(axis=0)
    max_xy = (vis_coords[:, :2] + vis_radii[:, None]).max(axis=0)
    span_xy = np.maximum(max_xy - min_xy, 1.8)
    pad_px = 42 * supersample
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
    pts = np.empty_like(coords_p)
    pts[:, 0] = (coords_p[:, 0] - center_a[0]) * scale + ss_w * 0.5
    pts[:, 1] = (coords_p[:, 1] - center_a[1]) * scale + ss_h * 0.5
    pts[:, 2] = coords_p[:, 2] * scale
    radii_px = radii_p * scale

    color_buf = np.zeros((ss_h, ss_w, 3), dtype=np.float32)
    alpha_buf = np.zeros((ss_h, ss_w), dtype=np.float32)
    z_buf = np.full((ss_h, ss_w), -1e9, dtype=np.float32)

    vis_indices = np.where(vis)[0]
    vis_world_xyz = coords_world[vis]
    vis_world_r = radii_a[vis]

    # 1. Rasterize valence-aware blended cylinders (single / double / aromatic / triple)
    base_bond_a = 0.106 * float(style_cfg["bond_mult"])
    for bond in (mol.GetBonds() if style_cfg["draw_bonds"] else []):
        i1 = bond.GetBeginAtomIdx()
        i2 = bond.GetEndAtomIdx()
        if not (vis[i1] and vis[i2]):
            continue

        offsets = _bond_offsets_3d(mol, coords_world, bond)
        w_p1_base = coords_world[i1]
        w_p2_base = coords_world[i2]
        span_max_v = max(raw_span, 1.0)
        cam_dist = max(18.0, span_max_v * 3.6)

        for off_vec, r_mult in offsets:
            wp1 = w_p1_base + off_vec
            wp2 = w_p2_base + off_vec
            pe1 = cam_dist / max(cam_dist - float(wp1[2]), 4.0)
            pe2 = cam_dist / max(cam_dist - float(wp2[2]), 4.0)
            p1 = np.array([(wp1[0] * pe1 - center_a[0]) * scale + ss_w * 0.5, (wp1[1] * pe1 - center_a[1]) * scale + ss_h * 0.5, wp1[2] * scale], dtype=np.float32)
            p2 = np.array([(wp2[0] * pe2 - center_a[0]) * scale + ss_w * 0.5, (wp2[1] * pe2 - center_a[1]) * scale + ss_h * 0.5, wp2[2] * scale], dtype=np.float32)
            eff_r = float(base_bond_a * r_mult * 0.5 * (pe1 + pe2) * scale)
            eff_r_a = float(base_bond_a * r_mult)

            v = p2 - p1
            L = float(np.linalg.norm(v))
            if L < 1e-3:
                continue
            d = v / L

            x0 = max(0, int(np.floor(min(p1[0], p2[0]) - eff_r - 2)))
            x1 = min(ss_w, int(np.ceil(max(p1[0], p2[0]) + eff_r + 2)))
            y0 = max(0, int(np.floor(min(p1[1], p2[1]) - eff_r - 2)))
            y1 = min(ss_h, int(np.ceil(max(p1[1], p2[1]) + eff_r + 2)))
            if x1 <= x0 or y1 <= y0:
                continue

            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            ox = xx - p1[0]
            oy = yy - p1[1]
            dx, dy, dz = float(d[0]), float(d[1]), float(d[2])
            denom_xy = max(1e-5, 1.0 - dz * dz)

            if denom_xy < 1e-4:
                dist2 = ox * ox + oy * oy
                hit = dist2 <= eff_r * eff_r
                if not np.any(hit):
                    continue
                z_hit = np.maximum(p1[2], p2[2])
                nx_h = ox[hit] / max(eff_r, 1e-4)
                ny_h = oy[hit] / max(eff_r, 1e-4)
                nz_h = np.sqrt(np.maximum(0.0, 1.0 - nx_h * nx_h - ny_h * ny_h))
                z_vals = np.full(nx_h.shape, z_hit, dtype=np.float32)
                u_frac = np.full(nx_h.shape, 0.5, dtype=np.float32)
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
                z_vals = p1[2] + z_rel[hit]
                t_h = t_along[hit]
                nx_h = (ox[hit] - t_h * dx) / eff_r
                ny_h = (oy[hit] - t_h * dy) / eff_r
                nz_h = (z_rel[hit] - t_h * dz) / eff_r
                u_frac = np.clip(t_h / L, 0.0, 1.0)

            sub_z = z_buf[y0:y1, x0:x1]
            vis_hit = z_vals > sub_z[hit]
            if not np.any(vis_hit):
                continue

            u_v = u_frac[vis_hit]
            w_mix = np.clip((u_v - 0.42) / 0.16, 0.0, 1.0)
            w_smooth = w_mix * w_mix * (3.0 - 2.0 * w_mix)
            col_px = colors[i1][None, :] * (1.0 - w_smooth[:, None]) + colors[i2][None, :] * w_smooth[:, None]

            norms = np.stack([nx_h[vis_hit], ny_h[vis_hit], nz_h[vis_hit]], axis=1)
            w_pts = wp1[None, :] + u_v[:, None] * (wp2 - wp1)[None, :] + norms * eff_r_a
            mid_b = 0.5 * (wp1 + wp2)
            nb_dist = np.linalg.norm(vis_world_xyz - mid_b[None, :], axis=1)
            near_mask = nb_dist <= (0.5 * np.linalg.norm(wp2 - wp1) + 3.0)
            ao = _compute_pixel_ao(w_pts, norms, vis_world_xyz[near_mask], vis_world_r[near_mask], strength=float(style_cfg["ao_str"]) * 0.82)

            shaded = _shade_surface_pbr(
                norms[:, 0], norms[:, 1], norms[:, 2],
                base_rgb=col_px, ao=ao,
                spec_power=float(style_cfg["spec_power"]) * 0.85,
                spec_weight=float(style_cfg["spec_weight"]) * 0.82,
                metallic=float(style_cfg["metallic"]),
            )
            hy, hx = np.where(hit)
            vy = hy[vis_hit] + y0
            vx = hx[vis_hit] + x0
            z_buf[vy, vx] = z_vals[vis_hit]
            color_buf[vy, vx] = shaded
            alpha_buf[vy, vx] = 255.0

    # 2. Rasterize atomic spheres with analytical 3D AO
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

        norms = np.stack([dx[hit][vis_hit], dy[hit][vis_hit], nz[vis_hit]], axis=1)
        w_pts = coords_world[idx][None, :] + norms * float(radii_a[idx])
        nb_d = np.linalg.norm(vis_world_xyz - coords_world[idx][None, :], axis=1)
        near_mask = (vis_indices != idx) & (nb_d <= float(radii_a[idx]) + 3.2)
        ao = _compute_pixel_ao(w_pts, norms, vis_world_xyz[near_mask], vis_world_r[near_mask], strength=float(style_cfg["ao_str"]))

        shaded = _shade_surface_pbr(
            norms[:, 0], norms[:, 1], norms[:, 2],
            base_rgb=col, ao=ao,
            spec_power=float(style_cfg["spec_power"]),
            spec_weight=float(style_cfg["spec_weight"]),
            metallic=float(style_cfg["metallic"]),
        )
        hy, hx = np.where(hit)
        vy = hy[vis_hit] + y0
        vx = hx[vis_hit] + x0
        z_buf[vy, vx] = z_vals[vis_hit]
        color_buf[vy, vx] = shaded
        alpha_buf[vy, vx] = 255.0

    # 3. Compose soft Gaussian contact shadow strictly under molecule (corners stay 100% transparent)
    rgba_ss = np.dstack([color_buf, alpha_buf]).astype(np.uint8)
    mol_ss = Image.fromarray(rgba_ss, mode="RGBA")

    vis_pts_x = pts[vis, 0]
    vis_pts_y = pts[vis, 1]
    if len(vis_pts_x) > 0:
        sh_layer = Image.new("RGBA", (ss_w, ss_h), (0, 0, 0, 0))
        sh_cx = float(0.5 * (vis_pts_x.min() + vis_pts_x.max()))
        sh_cy = float(min(ss_h - 14 * supersample, vis_pts_y.max() + radii_px[vis].max() * 0.55))
        sh_rx = max(24.0, float(0.36 * (vis_pts_x.max() - vis_pts_x.min())))
        sh_ry = max(7.0, float(8.5 * supersample))
        sy0 = max(0, int(sh_cy - sh_ry - 2))
        sy1 = min(ss_h, int(sh_cy + sh_ry + 2))
        sx0 = max(0, int(sh_cx - sh_rx - 2))
        sx1 = min(ss_w, int(sh_cx + sh_rx + 2))
        if sy1 > sy0 and sx1 > sx0:
            sh_arr = np.zeros((ss_h, ss_w, 4), dtype=np.uint8)
            syy, sxx = np.mgrid[sy0:sy1, sx0:sx1].astype(np.float32)
            ell = ((sxx - sh_cx) / sh_rx) ** 2 + ((syy - sh_cy) / sh_ry) ** 2
            sh_a = np.clip((1.0 - ell) * 28.0, 0.0, 28.0).astype(np.uint8)
            sh_arr[sy0:sy1, sx0:sx1, 0] = 15
            sh_arr[sy0:sy1, sx0:sx1, 1] = 23
            sh_arr[sy0:sy1, sx0:sx1, 2] = 42
            sh_arr[sy0:sy1, sx0:sx1, 3] = sh_a
            sh_layer = Image.fromarray(sh_arr, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=6 * supersample))
        mol_ss = Image.alpha_composite(sh_layer, mol_ss)

    img_out = mol_ss.resize((ss_w // supersample, ss_h // supersample), resample=Image.Resampling.LANCZOS)

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
