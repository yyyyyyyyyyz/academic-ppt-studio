"""Engine 4: Sci3DArtEngine — Aesthetic Prompt Compiler + Best-of-N + True Alpha Matting.

Supports:
- Structured Prompt Compilation for A01, A02, A03, A07, A08 with locked palette terms & STRICTLY ZERO TEXT gate
- Pluggable Gemini / OpenAI image generation
- High-Craft Local Studio 3D/Editorial Renderer fallback (zero external billing/network required)
- Mandatory true Alpha Matting & white-halo decontamination
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..providers.llm_image_provider import ModelProvider
from .alpha_matting import matte_white_background
from .palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb


STRICT_ZERO_TEXT_NEGATIVE = (
    "STRICTLY ZERO TEXT, no letters, no words, no numbers, no chemical formulas, "
    "no labels, no arrows with text, no watermark, no messy clutter, "
    "no dark muddy drop shadows, no cartoon faces, no frame border."
)

STYLE_SLOTS = {
    "c4d_octane_cutaway": (
        "Cinema 4D Octane render, scientific magazine cover quality, clean studio softbox lighting "
        "from top-left 45 degrees, subtle ambient occlusion, translucent optical borosilicate glass, "
        "matte pastel ceramic, satin metallic nanospheres, translucent porous zeolite polyhedron framework, "
        "isolated on pure solid #FFFFFF white background, orthographic-like slight isometric cutaway view"
    ),
    "editorial_flat_3d": (
        "Nature Reviews / Cell Press clean scientific vector illustration, uniform crisp dark navy outlines (#1E3A5F), "
        "soft directional gradient shading, subtle glossy specular highlights on catalyst spheres and capsule substrates, "
        "ultra-clean minimalist flat-3D hybrid style, isolated on pure #FFFFFF white background"
    ),
    "vesta_polyhedra": (
        "VESTA crystallographic coordination polyhedra and layered catalytic slab interface, "
        "crisp faceted octahedra and tetrahedra with clean edge highlights, studio top-left illumination, "
        "isolated on pure #FFFFFF white background"
    ),
    "nature_line_art": (
        "Nature Reviews black and deep-navy thin-line scientific schematic, crisp uniform strokes (#1E3A5F), "
        "low-saturation pastel fills, minimalist multi-scale visual clarity, isolated on pure #FFFFFF white background"
    ),
}


def compile_sci3d_prompt(
    archetype: str,
    render_mode: str,
    palette_id: str,
    scene_description: Optional[str] = None,
    refinement_note: Optional[str] = None,
) -> str:
    pal = get_palette(palette_id)
    style = STYLE_SLOTS.get(render_mode, STYLE_SLOTS["c4d_octane_cutaway"])
    base_scene = scene_description or _default_scene_for_archetype(archetype)
    refine_part = f" Refinement adjustment: {refinement_note.strip()}." if refinement_note else ""
    return (
        f"{style}. Color palette and materials strictly harmonized to: {pal.material_prompt_terms}. "
        f"Scientific scene: {base_scene}.{refine_part} {STRICT_ZERO_TEXT_NEGATIVE}"
    )


def _default_scene_for_archetype(archetype: str) -> str:
    if archetype.startswith("A01"):
        return (
            "Cross-section cutaway borosilicate catalytic reactor jar on the left containing swirling satin "
            "nanospheres and pastel ceramic milling beads, connected seamlessly to an enlarged crystalline "
            "porous molecular cage micro-environment on the right trapping tri-atomic guest molecules"
        )
    if archetype.startswith("A02"):
        return (
            "Left-right scientific contrast without labels: sintered agglomerated dull metal cluster on the left "
            "repelling frosted substrate capsules, versus translucent porous polyhedral MOF cage on the right "
            "uniformly anchoring bright single-dispersed metallic nanospheres"
        )
    if archetype.startswith("A03"):
        return (
            "Minimalist flat-3D editorial scientific illustration showing an activated faceted piezoelectric crystal "
            "delivering energy pulses to satin spherical catalyst particles and rounded pill-shaped organic substrates"
        )
    if archetype.startswith("A07"):
        return (
            "Isometric crystallographic coordination polyhedral slab surface with ordered octahedral metal sites "
            "and dual-layer interfacial gradient zone with clean glowing surface-adsorbed spheres"
        )
    return (
        "Clean multi-scale minimalist scientific schematic showing macro reactor vessel, mesoscale electrode "
        "interface cross-section, and nanoscale porous catalytic cavity"
    )


# ---------------------------------------------------------------------------
# High-Craft Local Studio 3D & Editorial Renderers (Zero Text, True Alpha)
# ---------------------------------------------------------------------------

def _sphere_patch(
    radius: int,
    base_rgb: Tuple[int, int, int],
    outline_rgb: Optional[Tuple[int, int, int]] = None,
    gloss: float = 0.72,
    alpha_scale: float = 1.0,
) -> Image.Image:
    """Render an anti-aliased Phong-shaded studio sphere sprite."""
    r = max(4, radius)
    size = 2 * r + 4
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size * 0.5 - 0.5
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    r2 = dx * dx + dy * dy
    inside = r2 <= 1.0
    nz = np.sqrt(np.maximum(0.0, 1.0 - r2))

    # Top-left 45-degree softbox light
    k = np.array([-0.54, -0.58, 0.61], dtype=np.float32)
    k /= np.linalg.norm(k)
    h_vec = k + np.array([0.0, 0.0, 1.0], dtype=np.float32)
    h_vec /= np.linalg.norm(h_vec)

    diff = np.maximum(0.0, dx * k[0] + dy * k[1] + nz * k[2])
    bounce = np.maximum(0.0, dx * 0.5 + dy * 0.5 + nz * 0.65)
    spec = (np.maximum(0.0, dx * h_vec[0] + dy * h_vec[1] + nz * h_vec[2]) ** 36) * gloss

    shade = 0.34 + 0.56 * diff + 0.16 * bounce
    b = np.array(base_rgb, dtype=np.float32)
    rgb = b[None, None, :] * shade[:, :, None] + 255.0 * spec[:, :, None]

    if outline_rgb is not None:
        rim = np.clip((0.28 - nz) / 0.14, 0.0, 1.0)
        o = np.array(outline_rgb, dtype=np.float32)
        rgb = rgb * (1.0 - rim[:, :, None]) + o[None, None, :] * rim[:, :, None]

    edge_aa = np.clip((1.0 - np.sqrt(r2)) * r * 1.4, 0.0, 1.0)
    alpha = np.where(inside, edge_aa * 255.0 * alpha_scale, 0.0)
    arr = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 255)]).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def _capsule_patch(
    w: int,
    h: int,
    base_rgb: Tuple[int, int, int],
    outline_rgb: Optional[Tuple[int, int, int]] = None,
    angle_deg: float = 0.0,
) -> Image.Image:
    """Render a frosted pastel 3D pill/capsule substrate sprite."""
    ss = 2
    sw, sh = w * ss, h * ss
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 4
    rad = (sh - 2 * pad) // 2
    d.rounded_rectangle([pad, pad, sw - pad, sh - pad], radius=rad, fill=(*base_rgb, 248))

    # Top-left highlight streak
    hi = tuple(min(255, int(c + (255 - c) * 0.58)) for c in base_rgb)
    d.rounded_rectangle(
        [pad + rad // 2, pad + 4, sw - pad - rad // 2, pad + max(6, sh // 4)],
        radius=max(3, sh // 8),
        fill=(*hi, 175),
    )
    if outline_rgb is not None:
        d.rounded_rectangle([pad, pad, sw - pad, sh - pad], radius=rad, outline=(*outline_rgb, 255), width=3)

    img = img.resize((w, h), resample=Image.Resampling.LANCZOS)
    if abs(angle_deg) > 0.5:
        img = img.rotate(angle_deg, expand=True, resample=Image.Resampling.BICUBIC)
    return img


def _paste_centered(canvas: Image.Image, sprite: Image.Image, cx: int, cy: int) -> None:
    canvas.alpha_composite(sprite, dest=(int(cx - sprite.width // 2), int(cy - sprite.height // 2)))


def _draw_polyhedron_cage(
    canvas: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    edge_rgb: Tuple[int, int, int],
    fill_rgb: Tuple[int, int, int],
    lw: int = 4,
) -> None:
    """Draw a translucent icosahedral / zeolite porous cage structure."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    outer_pts = []
    inner_pts = []
    for k in range(6):
        ang = math.radians(60 * k - 30)
        outer_pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
        ang2 = math.radians(60 * k)
        inner_pts.append((cx + radius * 0.54 * math.cos(ang2), cy + radius * 0.54 * math.sin(ang2)))

    # Translucent facets
    d.polygon(outer_pts, fill=(*fill_rgb, 72))
    for k in range(6):
        k_next = (k + 1) % 6
        tri = [outer_pts[k], outer_pts[k_next], inner_pts[k]]
        facet_alpha = 52 if k % 2 == 0 else 86
        d.polygon(tri, fill=(*fill_rgb, facet_alpha))

    # Edges (back edges lighter, front edges crisp)
    for k in range(6):
        k_next = (k + 1) % 6
        d.line([outer_pts[k], outer_pts[k_next]], fill=(*edge_rgb, 195), width=lw)
        d.line([inner_pts[k], inner_pts[k_next]], fill=(*edge_rgb, 130), width=max(2, lw - 1))
        d.line([outer_pts[k], inner_pts[k]], fill=(*edge_rgb, 155), width=max(2, lw - 1))
        d.line([outer_pts[k_next], inner_pts[k]], fill=(*edge_rgb, 155), width=max(2, lw - 1))

    # Vertex nodes
    for px, py in outer_pts + inner_pts:
        nr = max(4, lw + 1)
        d.ellipse([px - nr, py - nr, px + nr, py + nr], fill=(*edge_rgb, 210))

    canvas.alpha_composite(layer)


def _render_a01_cutaway(w: int, h: int, pal: ScientificPalette, variant: int) -> Image.Image:
    """A01: 3D Borosilicate Cutaway Reactor + Porous Micro-Cavity Host (zero text)."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    s1 = hex_to_rgb(pal.s1)
    s2 = hex_to_rgb(pal.s2)
    s3 = hex_to_rgb(pal.s3)
    s4 = hex_to_rgb(pal.s4)
    s5 = hex_to_rgb(pal.s5)
    alert = hex_to_rgb(pal.alert)
    glass_edge = hex_to_rgb(pal.s2)

    # Left: 3D cutaway glass reactor / ball-mill chamber
    rx = int(w * (0.28 + 0.015 * variant))
    ry = int(h * 0.56)
    rr = int(min(w, h) * 0.28)

    # Soft studio floor shadow directly beneath vessel (ultra-light, transparent fade)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([rx - int(rr * 0.85), ry + rr - 8, rx + int(rr * 0.85), ry + rr + 24], fill=(140, 160, 185, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
    canvas.alpha_composite(shadow)

    # Reactor neck (borosilicate glass tube)
    neck_w = int(rr * 0.36)
    neck_top = int(ry - rr * 1.48)
    d.rounded_rectangle([rx - neck_w, neck_top, rx + neck_w, ry - rr + 24], radius=14, fill=(*s5, 95), outline=(*glass_edge, 190), width=4)
    # Glass flange lip
    d.rounded_rectangle([rx - neck_w - 14, neck_top - 10, rx + neck_w + 14, neck_top + 14], radius=10, fill=(*s4, 150), outline=(*glass_edge, 210), width=4)

    # Outer glass sphere + liquid cutaway meniscus
    d.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=(*s5, 80), outline=(*glass_edge, 200), width=5)
    # Cutaway inner reaction medium crescent
    d.pieslice([rx - rr + 14, ry - rr + 14, rx + rr - 14, ry + rr - 14], start=12, end=168, fill=(*s4, 125))
    # Specular Fresnel highlight arc on left glass wall
    d.arc([rx - rr + 24, ry - rr + 24, rx + rr - 24, ry + rr - 24], start=198, end=250, fill=(255, 255, 255, 210), width=10)

    # Ceramic milling spheres & satin catalyst nanospheres inside reactor
    bead_positions = [(-0.42, 0.34, 24, s3), (0.36, 0.36, 26, s3), (-0.10, 0.48, 22, s2), (0.14, 0.14, 28, s1), (-0.34, -0.02, 20, s1)]
    if variant % 2 == 1:
        bead_positions = [(-0.36, 0.38, 26, s2), (0.32, 0.28, 24, s3), (0.04, 0.44, 28, s1), (-0.22, 0.06, 22, s1), (0.28, -0.06, 20, s3)]
    for dx_f, dy_f, rad_s, col in bead_positions:
        sp = _sphere_patch(rad_s, col, gloss=0.80)
        _paste_centered(canvas, sp, int(rx + dx_f * rr), int(ry + dy_f * rr))

    # Substrate capsules inside medium
    cap1 = _capsule_patch(70, 28, alert, angle_deg=-22 + variant * 8)
    cap2 = _capsule_patch(64, 26, s2, angle_deg=18 - variant * 5)
    _paste_centered(canvas, cap1, int(rx - 0.12 * rr), int(ry + 0.18 * rr))
    _paste_centered(canvas, cap2, int(rx + 0.28 * rr), int(ry + 0.12 * rr))

    # Right: Microscale porous zeolite cage trapping guest molecules (zoom-window core)
    mx = int(w * 0.74)
    my = int(h * 0.50)
    mr = int(min(w, h) * 0.26)
    _draw_polyhedron_cage(canvas, mx, my, mr, edge_rgb=s2, fill_rgb=s5, lw=5)

    # Central active metal nanocluster + confined H2O-like triatomic guests inside cage
    center_sp = _sphere_patch(34, s1, gloss=0.85)
    _paste_centered(canvas, center_sp, mx, my + 8)
    for gx, gy, ang in ((-64, -44, 15), (62, -38, -20), (0, -76, 0)):
        o_sp = _sphere_patch(16, alert, gloss=0.75)
        h_sp1 = _sphere_patch(10, (242, 246, 252), outline_rgb=(110, 125, 145), gloss=0.6)
        h_sp2 = _sphere_patch(10, (242, 246, 252), outline_rgb=(110, 125, 145), gloss=0.6)
        _paste_centered(canvas, o_sp, mx + gx, my + gy)
        _paste_centered(canvas, h_sp1, mx + gx - 16, my + gy + 12)
        _paste_centered(canvas, h_sp2, mx + gx + 16, my + gy + 12)

    return canvas


def _render_a02_dispersion(w: int, h: int, pal: ScientificPalette, variant: int) -> Image.Image:
    """A02: Sintered Agglomeration (left) vs Confined Single-Dispersed Porous Cage (right)."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s1 = hex_to_rgb(pal.s1)
    s2 = hex_to_rgb(pal.s2)
    s3 = hex_to_rgb(pal.s3)
    s4 = hex_to_rgb(pal.s4)
    s5 = hex_to_rgb(pal.s5)
    muted = hex_to_rgb(pal.muted)
    alert = hex_to_rgb(pal.alert)

    # Left: agglomerated dull cluster repelling substrates
    lx, ly = int(w * 0.26), int(h * 0.52)
    offsets = [(-44, -22), (0, -34), (42, -16), (-26, 22), (24, 26), (-4, 2), (48, 30), (-52, 16)]
    for ox, oy in offsets:
        sp = _sphere_patch(34, muted, gloss=0.35)
        _paste_centered(canvas, sp, lx + ox + (variant * 4), ly + oy)
    for cx, cy, ang in ((-110, -85, -35), (105, -95, 38), (95, 95, -24)):
        cap = _capsule_patch(66, 26, alert, angle_deg=ang)
        _paste_centered(canvas, cap, lx + cx, ly + cy)

    # Right: porous polyhedral cage uniformly anchoring single dispersed active spheres
    rx, ry = int(w * 0.74), int(h * 0.50)
    cage_r = int(min(w, h) * 0.30)
    _draw_polyhedron_cage(canvas, rx, ry, cage_r, edge_rgb=s2, fill_rgb=s5, lw=5)
    nodes = [(-78, -56), (72, -62), (0, -10), (-82, 46), (76, 48), (0, 78)]
    for nx, ny in nodes:
        sp = _sphere_patch(24, s1, gloss=0.88)
        _paste_centered(canvas, sp, rx + nx, ry + ny)
    for cx, cy, ang in ((-38, -32, 15), (42, 14, -18), (-34, 62, 10)):
        cap = _capsule_patch(54, 22, s4, outline_rgb=s1, angle_deg=ang)
        _paste_centered(canvas, cap, rx + cx, ry + cy)

    return canvas


def _render_a03_editorial(w: int, h: int, pal: ScientificPalette, variant: int) -> Image.Image:
    """A03: Nature Reviews / Cell Press Flat-3D Editorial Vector Illustration (zero text)."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    navy = (30, 58, 95)
    s1 = hex_to_rgb(pal.s1)
    s3 = hex_to_rgb(pal.s3)
    s4 = hex_to_rgb(pal.s4)
    s5 = hex_to_rgb(pal.s5)
    alert = hex_to_rgb(pal.alert)

    # Isometric piezoelectric/photocatalytic faceted cube on left
    cx, cy = int(w * 0.25), int(h * 0.55)
    sz = int(min(w, h) * 0.23)
    top_f = [(cx, cy - sz), (cx + sz, cy - sz // 2), (cx, cy), (cx - sz, cy - sz // 2)]
    left_f = [(cx - sz, cy - sz // 2), (cx, cy), (cx, cy + sz), (cx - sz, cy + sz // 2)]
    right_f = [(cx + sz, cy - sz // 2), (cx + sz, cy + sz // 2), (cx, cy + sz), (cx, cy)]
    d.polygon(top_f, fill=(*s5, 250), outline=(*navy, 255), width=4)
    d.polygon(left_f, fill=(*s4, 250), outline=(*navy, 255), width=4)
    d.polygon(right_f, fill=(*s3, 250), outline=(*navy, 255), width=4)

    # Lightning / energy pulse wave toward center catalyst cluster
    bolt = [(cx + sz + 26, cy - 34), (cx + sz + 64, cy - 68), (cx + sz + 54, cy - 28), (cx + sz + 96, cy - 42), (cx + sz + 52, cy + 4), (cx + sz + 64, cy - 24)]
    d.polygon(bolt, fill=(*alert, 235), outline=(*navy, 255), width=3)

    # Center active satin spheres with crisp #1E3A5F outlines
    mx, my = int(w * 0.54), int(h * 0.52)
    for ox, oy, rad in ((-38, -22, 34), (36, -18, 30), (0, 32, 38)):
        sp = _sphere_patch(rad, s1, outline_rgb=navy, gloss=0.72)
        _paste_centered(canvas, sp, mx + ox, my + oy)

    # Right: clean capsule substrate -> transformed product capsules
    cap_in = _capsule_patch(105, 42, s5, outline_rgb=navy, angle_deg=-10 + variant * 5)
    cap_out = _capsule_patch(115, 46, s3, outline_rgb=navy, angle_deg=12 - variant * 5)
    _paste_centered(canvas, cap_in, int(w * 0.80), int(h * 0.34))
    _paste_centered(canvas, cap_out, int(w * 0.82), int(h * 0.68))
    return canvas


def _render_a07_vesta_polyhedra(w: int, h: int, pal: ScientificPalette, variant: int) -> Image.Image:
    """A07: VESTA Coordination Octahedra Slab + Interfacial Double-Layer Contrast."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    navy = (30, 58, 95)
    s1 = hex_to_rgb(pal.s1)
    s2 = hex_to_rgb(pal.s2)
    s3 = hex_to_rgb(pal.s3)
    s4 = hex_to_rgb(pal.s4)
    s5 = hex_to_rgb(pal.s5)
    alert = hex_to_rgb(pal.alert)

    # Periodic octahedral slab row
    cols = 4
    start_x = int(w * 0.16)
    step_x = int(w * 0.22)
    y_slab = int(h * 0.34)
    sz = int(min(w, h) * 0.11)
    for i in range(cols):
        ox = start_x + i * step_x
        top = (ox, y_slab - sz)
        left = (ox - sz, y_slab)
        right = (ox + sz, y_slab)
        bot = (ox, y_slab + sz)
        center = (ox + 12, y_slab + 10)
        d.polygon([top, left, center], fill=(*s4, 220), outline=(*navy, 255), width=3)
        d.polygon([top, right, center], fill=(*s5, 235), outline=(*navy, 255), width=3)
        d.polygon([left, bot, center], fill=(*s2, 225), outline=(*navy, 255), width=3)
        d.polygon([right, bot, center], fill=(*s1, 225), outline=(*navy, 255), width=3)
        sp_m = _sphere_patch(14, s1 if i % 2 == 0 else alert, outline_rgb=navy)
        _paste_centered(canvas, sp_m, ox, y_slab - sz - 22)

    # Bi-color bottom split zone (soft blue control vs soft coral modified)
    split_y = int(h * 0.56)
    mid_x = w // 2
    d.rounded_rectangle([int(w * 0.06), split_y, mid_x - 12, int(h * 0.90)], radius=18, fill=(*s5, 110), outline=(*s3, 180), width=3)
    d.rounded_rectangle([mid_x + 12, split_y, int(w * 0.94), int(h * 0.90)], radius=18, fill=(*alert, 42), outline=(*alert, 165), width=3)
    for dx in (-90, 0, 90):
        _paste_centered(canvas, _sphere_patch(18, s2, gloss=0.7), mid_x // 2 + 24 + dx, split_y + int(h * 0.17))
        _paste_centered(canvas, _capsule_patch(62, 24, s1, outline_rgb=navy, angle_deg=(dx // 8)), int(w * 0.72) + dx, split_y + int(h * 0.17))
    return canvas


def _render_a08_lineart_trio(w: int, h: int, pal: ScientificPalette, variant: int) -> Image.Image:
    """A08: Nature Reviews Crisp Line-Art Multi-Scale Trio (macro -> meso -> micro, zero text)."""
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    navy = (30, 58, 95)
    s2 = hex_to_rgb(pal.s2)
    s4 = hex_to_rgb(pal.s4)
    s5 = hex_to_rgb(pal.s5)
    alert = hex_to_rgb(pal.alert)

    # Panel a: Macro circular cycle with clean reactor & green leaf/drop symbol
    r1 = int(min(w, h) * 0.22)
    c1x, c1y = int(w * 0.18), int(h * 0.50)
    d.ellipse([c1x - r1, c1y - r1, c1x + r1, c1y + r1], fill=(*s5, 95), outline=(*navy, 255), width=4)
    d.arc([c1x - r1 + 18, c1y - r1 + 18, c1x + r1 - 18, c1y + r1 - 18], 25, 155, fill=(*s2, 255), width=5)
    d.arc([c1x - r1 + 18, c1y - r1 + 18, c1x + r1 - 18, c1y + r1 - 18], 205, 335, fill=(*s2, 255), width=5)
    _paste_centered(canvas, _sphere_patch(24, s2, outline_rgb=navy, gloss=0.5), c1x, c1y)

    # Panel b: Mesoscale split device cross-section
    bx0, by0, bx1, by1 = int(w * 0.37), int(h * 0.26), int(w * 0.62), int(h * 0.74)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill=(255, 255, 255, 235), outline=(*navy, 255), width=4)
    mid_by = (by0 + by1) // 2
    d.rectangle([bx0 + 12, by0 + 12, bx1 - 12, mid_by - 4], fill=(*s5, 165), outline=(*s2, 220), width=2)
    d.rectangle([bx0 + 12, mid_by + 4, bx1 - 12, by1 - 12], fill=(*alert, 50), outline=(*alert, 190), width=2)

    # Panel c: Microscale split Problem / Solution circle
    c3x, c3y = int(w * 0.82), int(h * 0.50)
    r3 = int(min(w, h) * 0.26)
    d.pieslice([c3x - r3, c3y - r3, c3x + r3, c3y + r3], 180, 360, fill=(*s5, 145), outline=(*navy, 255), width=4)
    d.pieslice([c3x - r3, c3y - r3, c3x + r3, c3y + r3], 0, 180, fill=(*alert, 45), outline=(*navy, 255), width=4)
    _paste_centered(canvas, _sphere_patch(18, s4, outline_rgb=navy), c3x - 32, c3y - 42)
    _paste_centered(canvas, _sphere_patch(18, s2, outline_rgb=navy), c3x + 32, c3y - 42)
    _paste_centered(canvas, _capsule_patch(76, 26, s2, outline_rgb=navy), c3x, c3y + 44)
    return canvas


def _render_local_studio_candidate(
    archetype: str,
    render_mode: str,
    palette_id: str,
    output_png: Path,
    variant: int = 0,
    width_px: int = 1280,
    height_px: int = 780,
    dpi: int = 600,
) -> Path:
    pal = get_palette(palette_id)
    if archetype.startswith("A02"):
        img = _render_a02_dispersion(width_px, height_px, pal, variant)
    elif archetype.startswith("A03") or render_mode == "editorial_flat_3d":
        img = _render_a03_editorial(width_px, height_px, pal, variant)
    elif archetype.startswith("A07") or render_mode == "vesta_polyhedra":
        img = _render_a07_vesta_polyhedra(width_px, height_px, pal, variant)
    elif archetype.startswith("A08") or render_mode == "nature_line_art":
        img = _render_a08_lineart_trio(width_px, height_px, pal, variant)
    else:
        img = _render_a01_cutaway(width_px, height_px, pal, variant)

    # Run consistent alpha matting + tight crop so edge cleanliness matches cloud pipeline
    matte_white_background(img, output_path=output_png, crop_padding=14, dpi=dpi)
    return output_png


def generate_sci3d_candidates(
    archetype: str,
    render_mode: str,
    palette_id: str,
    output_dir: Path | str,
    asset_id: str,
    scene_description: Optional[str] = None,
    refinement_note: Optional[str] = None,
    best_of_n: int = 2,
    alpha_matting: bool = True,
    provider: Optional[ModelProvider] = None,
) -> Tuple[str, List[Tuple[Path, Optional[Path]]]]:
    """Compile prompt, render Best-of-N candidates (cloud or local studio), and matte to true Alpha."""
    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)
    compiled = compile_sci3d_prompt(
        archetype=archetype,
        render_mode=render_mode,
        palette_id=palette_id,
        scene_description=scene_description,
        refinement_note=refinement_note,
    )
    prov = provider or ModelProvider()
    results: List[Tuple[Path, Optional[Path]]] = []

    for idx in range(max(1, best_of_n)):
        raw_path = out_d / f"{asset_id}_cand{idx}_raw.png"
        alpha_path = out_d / f"{asset_id}_cand{idx}_alpha.png"

        cloud_ok = False
        if prov.active_image_backend() != "local":
            prompt_var = f"{compiled} (Composition variation {idx + 1})"
            cloud_ok = prov.generate_image(prompt_var, raw_path)

        if cloud_ok and raw_path.exists():
            if alpha_matting:
                matte_white_background(raw_path, output_path=alpha_path, dpi=600)
                results.append((alpha_path, raw_path))
            else:
                results.append((raw_path, raw_path))
        else:
            _render_local_studio_candidate(
                archetype=archetype,
                render_mode=render_mode,
                palette_id=palette_id,
                output_png=alpha_path,
                variant=idx,
            )
            results.append((alpha_path, None))

    return compiled, results
