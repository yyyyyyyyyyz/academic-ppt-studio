"""Unified Dark-Navy Line-Art Scientific Geometric Icon Library.

Provides clean, publication-consistent vector SVG and transparent RGBA PNG icons
(flask, prohibited_flask, ball_mill, porous_hex, centrifuge, nmr_spectrum,
cycle_arrows, light_wave, lightning, crystal_cube) unified to active palette colors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw

from .palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb


ICON_NAMES = (
    "flask",
    "prohibited_flask",
    "ball_mill",
    "porous_hex",
    "centrifuge",
    "nmr_spectrum",
    "cycle_arrows",
    "light_wave",
    "lightning",
    "crystal_cube",
)


def _draw_icon_pil(name: str, size: int, stroke: tuple[int, int, int], fill_soft: tuple[int, int, int], alert: tuple[int, int, int]) -> Image.Image:
    s = size
    lw = max(3, int(round(s * 0.045)))
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if name in ("flask", "prohibited_flask"):
        # Round-bottom / Erlenmeyer scientific flask
        neck_l, neck_r = int(0.41 * s), int(0.59 * s)
        d.rectangle([neck_l, int(0.14 * s), neck_r, int(0.38 * s)], outline=stroke, width=lw)
        d.line([int(0.36 * s), int(0.14 * s), int(0.64 * s), int(0.14 * s)], fill=stroke, width=lw)
        poly = [
            (neck_l, int(0.38 * s)),
            (int(0.20 * s), int(0.80 * s)),
            (int(0.24 * s), int(0.86 * s)),
            (int(0.76 * s), int(0.86 * s)),
            (int(0.80 * s), int(0.80 * s)),
            (neck_r, int(0.38 * s)),
        ]
        # Liquid fill inside bottom
        liq = [
            (int(0.29 * s), int(0.64 * s)),
            (int(0.22 * s), int(0.80 * s)),
            (int(0.25 * s), int(0.85 * s)),
            (int(0.75 * s), int(0.85 * s)),
            (int(0.78 * s), int(0.80 * s)),
            (int(0.71 * s), int(0.64 * s)),
        ]
        d.polygon(liq, fill=(*fill_soft, 210))
        d.polygon(poly, outline=stroke, width=lw)
        if name == "prohibited_flask":
            d.ellipse([int(0.10 * s), int(0.10 * s), int(0.90 * s), int(0.90 * s)], outline=alert, width=lw + 1)
            d.line([int(0.22 * s), int(0.22 * s), int(0.78 * s), int(0.78 * s)], fill=alert, width=lw + 2)

    elif name == "ball_mill":
        # Jar capsule + grinding balls
        d.rounded_rectangle([int(0.14 * s), int(0.26 * s), int(0.86 * s), int(0.74 * s)], radius=int(0.16 * s), fill=(*fill_soft, 165), outline=stroke, width=lw)
        for bx, by, br in ((0.33, 0.56, 0.08), (0.50, 0.58, 0.09), (0.66, 0.50, 0.08), (0.43, 0.42, 0.06)):
            cx, cy, r = int(bx * s), int(by * s), int(br * s)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*stroke, 225), outline=(255, 255, 255, 230), width=max(2, lw // 2))
        d.arc([int(0.24 * s), int(0.10 * s), int(0.76 * s), int(0.32 * s)], 200, 340, fill=stroke, width=lw)

    elif name == "porous_hex":
        # Hexagonal zeolite / MOF porous lattice
        import math
        cx0, cy0 = 0.5 * s, 0.5 * s
        rad = 0.21 * s
        offsets = [(0, 0), (1.73 * rad * 0.5, -1.5 * rad * 0.5), (-1.73 * rad * 0.5, -1.5 * rad * 0.5), (0, 1.5 * rad * 0.5)]
        for ox, oy in offsets:
            pts = []
            for k in range(6):
                ang = math.radians(60 * k + 30)
                pts.append((cx0 + ox + rad * 0.62 * math.cos(ang), cy0 + oy + rad * 0.62 * math.sin(ang)))
            d.polygon(pts, fill=(*fill_soft, 170), outline=stroke, width=max(2, lw - 1))

    elif name == "centrifuge":
        d.ellipse([int(0.14 * s), int(0.14 * s), int(0.86 * s), int(0.86 * s)], fill=(*fill_soft, 140), outline=stroke, width=lw)
        d.ellipse([int(0.43 * s), int(0.43 * s), int(0.57 * s), int(0.57 * s)], fill=stroke)
        for ang in (45, 165, 285):
            import math
            tx = int(0.5 * s + 0.23 * s * math.cos(math.radians(ang)))
            ty = int(0.5 * s + 0.23 * s * math.sin(math.radians(ang)))
            d.ellipse([tx - int(0.08 * s), ty - int(0.08 * s), tx + int(0.08 * s), ty + int(0.08 * s)], fill=(255, 255, 255, 255), outline=stroke, width=max(2, lw - 1))

    elif name == "nmr_spectrum":
        d.line([int(0.12 * s), int(0.76 * s), int(0.88 * s), int(0.76 * s)], fill=stroke, width=lw)
        pts = [
            (0.14, 0.76), (0.28, 0.76), (0.31, 0.34), (0.34, 0.76),
            (0.46, 0.76), (0.49, 0.50), (0.52, 0.76),
            (0.62, 0.76), (0.66, 0.20), (0.70, 0.76), (0.86, 0.76),
        ]
        d.line([(int(x * s), int(y * s)) for x, y in pts], fill=stroke, width=lw, joint="curve")

    elif name == "cycle_arrows":
        d.arc([int(0.16 * s), int(0.16 * s), int(0.84 * s), int(0.84 * s)], 20, 155, fill=stroke, width=lw)
        d.arc([int(0.16 * s), int(0.16 * s), int(0.84 * s), int(0.84 * s)], 200, 335, fill=stroke, width=lw)
        d.polygon([(int(0.80 * s), int(0.36 * s)), (int(0.90 * s), int(0.50 * s)), (int(0.70 * s), int(0.47 * s))], fill=stroke)
        d.polygon([(int(0.20 * s), int(0.64 * s)), (int(0.10 * s), int(0.50 * s)), (int(0.30 * s), int(0.53 * s))], fill=stroke)

    elif name == "light_wave":
        import math
        pts = [(int((0.14 + 0.72 * t / 24.0) * s), int((0.50 + 0.16 * math.sin(t * 0.75)) * s)) for t in range(25)]
        d.line(pts, fill=alert, width=lw)
        d.polygon([(int(0.80 * s), int(0.40 * s)), (int(0.92 * s), int(0.50 * s)), (int(0.80 * s), int(0.60 * s))], fill=alert)

    elif name == "lightning":
        bolt = [(0.56, 0.12), (0.28, 0.54), (0.48, 0.54), (0.40, 0.88), (0.74, 0.44), (0.52, 0.44)]
        d.polygon([(int(x * s), int(y * s)) for x, y in bolt], fill=(*fill_soft, 230), outline=stroke, width=lw)

    elif name == "crystal_cube":
        top = [(0.50, 0.14), (0.82, 0.31), (0.50, 0.48), (0.18, 0.31)]
        left = [(0.18, 0.31), (0.50, 0.48), (0.50, 0.86), (0.18, 0.69)]
        right = [(0.82, 0.31), (0.82, 0.69), (0.50, 0.86), (0.50, 0.48)]
        d.polygon([(int(x * s), int(y * s)) for x, y in top], fill=(*fill_soft, 190), outline=stroke, width=lw)
        d.polygon([(int(x * s), int(y * s)) for x, y in left], fill=(*fill_soft, 120), outline=stroke, width=lw)
        d.polygon([(int(x * s), int(y * s)) for x, y in right], fill=(*fill_soft, 235), outline=stroke, width=lw)

    return img


def render_icon(name: str, output_png: Path | str, palette_id: str = "lancet", size_px: int = 160) -> Path:
    """Render a unified dark-navy/theme line-art scientific icon to transparent PNG."""
    pal = get_palette(palette_id)
    stroke = hex_to_rgb(pal.s1)
    fill_soft = hex_to_rgb(blend_with_white(pal.s4, 0.35))
    alert = hex_to_rgb(pal.alert)

    # Render at 2x then downsample for ultra-crisp edges
    ss = _draw_icon_pil(name if name in ICON_NAMES else "flask", size_px * 2, stroke, fill_soft, alert)
    out_img = ss.resize((size_px, size_px), resample=Image.Resampling.LANCZOS)
    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(str(out_p), format="PNG", dpi=(600, 600))
    return out_p
