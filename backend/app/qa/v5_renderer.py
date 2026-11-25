"""1920x1080 High-DPI Preview Renderer for v5.0 Defense Modular & Consulting Layouts.

Matches v5_layouts.py & native_visuals.py 1-to-1 (at 144 px/in) including:
- Elevated pure-white (#FFFFFF) cards with soft Gaussian drop shadows and crisp #D6E0EC borders
- Dedicated split-panel 目录 (TOC) preview with geometric hexagons & full wrapped title
- Deep-navy bilingual trapezoid cutout top header bar + double vector chevrons
- True native-style lowered subscripts and raised superscripts via parse_markup_segments
- Edge-anchored 3D callout leaders with target anchor dots & pocket subsite overlays
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..builder.v5_layouts import _clean_section_heading, _split_bilingual, get_v5_figure_box
from ..builder.xml_utils import parse_markup_segments
from ..figure_factory.palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb
from ..figure_factory.vector_mech import compute_external_bitangents
from ..schemas.deck_spec import DeckSpec, FigureBoxIn, LayoutId, SlideSpec, V5_LAYOUT_IDS
from .font_resolver import resolve_pil_font


SCALE = 144.0  # 13.333 * 144 = 1920 x 1080


def _px(val_in: float) -> int:
    return int(round(val_in * SCALE))


def _resolve_strategy_badge_color(raw: Optional[str], pal: ScientificPalette, idx: int) -> str:
    """Resolve strategy card badge color dynamically against active palette unless custom hex."""
    val = (raw or "").strip()
    if not val or val in ("s1", "#00468B", "#D97706"):
        return pal.s1 if idx == 0 else pal.s2
    if val in ("s2", "s3", "s4", "s5", "s6", "alert", "ink", "muted"):
        return pal.token(val)
    return val


def _has_cjk(text: str) -> bool:
    return any(
        "\u3000" <= ch <= "\u303f" or "\u4e00" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef"
        for ch in text
    )


def _font(
    size_pt: float,
    bold: bool = False,
    text_hint: str = "",
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> ImageFont.FreeTypeFont:
    px = max(10, int(round(max(7.5, size_pt) * (SCALE / 72.0))))
    return resolve_pil_font(
        px,
        is_cjk=_has_cjk(text_hint),
        bold=bold,
        ea_font=ea_font,
        latin_font=latin_font,
    )


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    x1: int, y1: int, x2: int, y2: int,
    fill: Tuple[int, int, int],
    width: int = 2,
    dash: int = 10,
    gap: int = 7,
) -> None:
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    ux, uy = dx / dist, dy / dist
    pos = 0.0
    while pos < dist:
        end = min(pos + dash, dist)
        draw.line([x1 + ux * pos, y1 + uy * pos, x1 + ux * end, y1 + uy * end], fill=fill, width=width)
        pos += dash + gap


def _draw_rounded_box(
    draw: ImageDraw.ImageDraw,
    l_in: float, t_in: float, w_in: float, h_in: float,
    fill_hex: Optional[str] = "#FFFFFF",
    border_hex: Optional[str] = "#D6E0EC",
    border_px: int = 1,
    dashed: bool = False,
    radius: float = 0.08,
) -> None:
    x0, y0 = _px(l_in), _px(t_in)
    x1, y1 = _px(l_in + w_in), _px(t_in + h_in)
    rad = max(4, int(round(min(x1 - x0, y1 - y0) * radius)))
    fill_rgb = (*hex_to_rgb(fill_hex), 255) if fill_hex else None

    if not dashed:
        out_rgb = (*hex_to_rgb(border_hex), 255) if (border_hex and border_px > 0) else None
        draw.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fill_rgb, outline=out_rgb, width=border_px)
    else:
        if fill_rgb:
            draw.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fill_rgb)
        if border_hex:
            bc = hex_to_rgb(border_hex)
            _draw_dashed_line(draw, x0 + rad, y0, x1 - rad, y0, bc, width=border_px)
            _draw_dashed_line(draw, x0 + rad, y1, x1 - rad, y1, bc, width=border_px)
            _draw_dashed_line(draw, x0, y0 + rad, x0, y1 - rad, bc, width=border_px)
            _draw_dashed_line(draw, x1, y0 + rad, x1, y1 - rad, bc, width=border_px)
            draw.arc([x0, y0, x0 + 2 * rad, y0 + 2 * rad], 180, 270, fill=bc, width=border_px)
            draw.arc([x1 - 2 * rad, y0, x1, y0 + 2 * rad], 270, 360, fill=bc, width=border_px)
            draw.arc([x0, y1 - 2 * rad, x0 + 2 * rad, y1], 90, 180, fill=bc, width=border_px)
            draw.arc([x1 - 2 * rad, y1 - 2 * rad, x1, y1], 0, 90, fill=bc, width=border_px)


def _draw_elevated_box(
    canvas: Image.Image,
    l_in: float, t_in: float, w_in: float, h_in: float,
    fill_hex: str = "#FFFFFF",
    border_hex: Optional[str] = "#D6E0EC",
    border_px: int = 1,
    dashed: bool = False,
    radius: float = 0.08,
    shadow_alpha: int = 16,
    blur_px: int = 6,
) -> None:
    """Draw a pure-white card with a soft Gaussian drop shadow beneath it."""
    x0, y0 = _px(l_in), _px(t_in)
    x1, y1 = _px(l_in + w_in), _px(t_in + h_in)
    rad = max(4, int(round(min(x1 - x0, y1 - y0) * radius)))
    pad = blur_px * 2 + 6
    bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
    bx1, by1 = min(1920, x1 + pad), min(1080, y1 + pad + 4)
    sh_patch = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh_patch)
    sd.rounded_rectangle(
        [x0 - bx0, y0 - by0 + 3, x1 - bx0, y1 - by0 + 3],
        radius=rad,
        fill=(15, 23, 42, shadow_alpha),
    )
    sh_patch = sh_patch.filter(ImageFilter.GaussianBlur(radius=blur_px))
    canvas.alpha_composite(sh_patch, dest=(bx0, by0))

    d = ImageDraw.Draw(canvas)
    _draw_rounded_box(d, l_in, t_in, w_in, h_in, fill_hex=fill_hex, border_hex=border_hex, border_px=border_px, dashed=dashed, radius=radius)


def _draw_chamfered_header_tab(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    l_in: float, t_in: float, w_in: float, h_in: float,
    text: str,
    fill_hex: str,
    text_color: str = "#FFFFFF",
    radius: float = 0.18,
    size_pt: float = 14.0,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
    show_l2: bool = True,
    show_l3: bool = True,
) -> None:
    if show_l2:
        _draw_elevated_box(canvas, l_in, t_in, w_in, h_in, fill_hex=fill_hex, border_hex=None, border_px=0, radius=radius, shadow_alpha=18, blur_px=4)
        hi_rgb = hex_to_rgb(blend_with_white(fill_hex, 0.55))
        draw.line([_px(l_in + 0.16), _px(t_in + 0.03), _px(l_in + w_in - 0.16), _px(t_in + 0.03)], fill=hi_rgb, width=1)
    if show_l3:
        _draw_text_box(draw, l_in + 0.06, t_in, w_in - 0.12, h_in, text, size_pt=size_pt, bold=True, color_hex=text_color, align="center", ea_font=ea_font, latin_font=latin_font)


def _draw_trapezoid_cutout(draw: ImageDraw.ImageDraw, l_in: float, t_in: float, w_in: float, h_in: float, fill_hex: str = "#FFFFFF", slope: float = 0.055) -> None:
    x0, y0, x1, y1 = _px(l_in), _px(t_in), _px(l_in + w_in), _px(t_in + h_in)
    dx = int(round((x1 - x0) * slope))
    poly = [(x0 + dx, y0), (x1 - dx, y0), (x1, y1), (x0, y1)]
    draw.polygon(poly, fill=(*hex_to_rgb(fill_hex), 255))


def _draw_chevron(draw: ImageDraw.ImageDraw, l_in: float, t_in: float, w_in: float, h_in: float, fill_hex: str) -> None:
    x0, y0, x1, y1 = _px(l_in), _px(t_in), _px(l_in + w_in), _px(t_in + h_in)
    ym = (y0 + y1) // 2
    tip = max(5, int((x1 - x0) * 0.42))
    poly = [(x0, y0), (x1 - tip, y0), (x1, ym), (x1 - tip, y1), (x0, y1), (x0 + tip, ym)]
    draw.polygon(poly, fill=(*hex_to_rgb(fill_hex), 255))


def _draw_hexagon_outline(canvas: Image.Image, l_in: float, t_in: float, w_in: float, h_in: float, alpha: int = 36) -> None:
    x0, y0, x1, y1 = _px(l_in), _px(t_in), _px(l_in + w_in), _px(t_in + h_in)
    dx = int(round((x1 - x0) * 0.25))
    ym = (y0 + y1) // 2
    pts = [(x0 + dx, y0), (x1 - dx, y0), (x1, ym), (x1 - dx, y1), (x0 + dx, y1), (x0, ym), (x0 + dx, y0)]
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.line(pts, fill=(255, 255, 255, alpha), width=2)
    canvas.alpha_composite(ov)


def _draw_down_arrow(draw: ImageDraw.ImageDraw, cx_in: float, top_in: float, w_in: float, h_in: float, fill_hex: str) -> None:
    x0, y0 = _px(cx_in - w_in / 2), _px(top_in)
    x1, y1 = _px(cx_in + w_in / 2), _px(top_in + h_in)
    xm = (x0 + x1) // 2
    sw = max(4, (x1 - x0) // 4)
    y_head = y0 + int((y1 - y0) * 0.45)
    poly = [(xm - sw, y0), (xm + sw, y0), (xm + sw, y_head), (x1, y_head), (xm, y1), (x0, y_head), (xm - sw, y_head)]
    draw.polygon(poly, fill=(*hex_to_rgb(fill_hex), 255))


def _draw_right_arrow_shape(draw: ImageDraw.ImageDraw, l_in: float, cy_in: float, w_in: float, h_in: float, fill_hex: str) -> None:
    x0, y0 = _px(l_in), _px(cy_in - h_in / 2)
    x1, y1 = _px(l_in + w_in), _px(cy_in + h_in / 2)
    ym = (y0 + y1) // 2
    sh = max(3, (y1 - y0) // 4)
    x_head = x0 + int((x1 - x0) * 0.48)
    poly = [(x0, ym - sh), (x_head, ym - sh), (x_head, y0), (x1, ym), (x_head, y1), (x_head, ym + sh), (x0, ym + sh)]
    draw.polygon(poly, fill=(*hex_to_rgb(fill_hex), 255))


def _tokenize_rich_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    eff_pt: float,
    bold: bool,
    highlight_phrase: Optional[str],
    ea_font: str,
    latin_font: str,
) -> List[List[Tuple[str, ImageFont.FreeTypeFont, Optional[str], bool]]]:
    """Split text into wrapped visual lines of (token_text, font, base_kind, is_hi) preserving sub/sup."""
    chunks: List[Tuple[str, bool]] = []
    if highlight_phrase and highlight_phrase in text:
        idx = text.index(highlight_phrase)
        if idx > 0:
            chunks.append((text[:idx], False))
        chunks.append((highlight_phrase, True))
        if idx + len(highlight_phrase) < len(text):
            chunks.append((text[idx + len(highlight_phrase):], False))
    else:
        chunks.append((text, False))

    # Build raw spans across explicit newlines
    raw_lines: List[List[Tuple[str, Optional[str], bool]]] = [[]]
    for c_txt, is_hi in chunks:
        for seg_txt, b_kind in parse_markup_segments(c_txt):
            if not seg_txt:
                continue
            sub_parts = seg_txt.split("\n")
            for p_i, sp in enumerate(sub_parts):
                if p_i > 0:
                    raw_lines.append([])
                if sp:
                    raw_lines[-1].append((sp, b_kind, is_hi))

    wrapped_lines: List[List[Tuple[str, ImageFont.FreeTypeFont, Optional[str], bool]]] = []
    for r_spans in raw_lines:
        if not r_spans:
            wrapped_lines.append([])
            continue
        cur_line: List[Tuple[str, ImageFont.FreeTypeFont, Optional[str], bool]] = []
        cur_w = 0.0

        def _flush():
            nonlocal cur_line, cur_w
            wrapped_lines.append(cur_line)
            cur_line = []
            cur_w = 0.0

        for sp_txt, b_kind, is_hi in r_spans:
            pt_use = eff_pt * (0.72 if b_kind in ("sub", "sup") else 1.0)
            fnt_use = _font(pt_use, bold=(bold or is_hi), text_hint=sp_txt, ea_font=ea_font, latin_font=latin_font)

            if b_kind in ("sub", "sup"):
                w_tok = draw.textlength(sp_txt, font=fnt_use)
                if cur_line and cur_w + w_tok > max_w:
                    _flush()
                cur_line.append((sp_txt, fnt_use, b_kind, is_hi))
                cur_w += w_tok
                continue

            # Wrap plain span smoothly (word-level for Latin, char-level for CJK)
            pieces = re.findall(r"\s+|[^\s\u4e00-\u9fff]+|[\u4e00-\u9fff]", sp_txt)
            for piece in pieces:
                w_p = draw.textlength(piece, font=fnt_use)
                if cur_line and cur_w + w_p > max_w:
                    if not piece.strip():
                        continue
                    _flush()
                if cur_line and cur_line[-1][2] is None and cur_line[-1][3] == is_hi and cur_line[-1][1] == fnt_use:
                    prev_t, prev_f, _, _ = cur_line[-1]
                    cur_line[-1] = (prev_t + piece, prev_f, None, is_hi)
                else:
                    cur_line.append((piece, fnt_use, None, is_hi))
                cur_w += w_p

        if cur_line:
            wrapped_lines.append(cur_line)
    return wrapped_lines or [[]]


def _draw_text_box(
    draw: ImageDraw.ImageDraw,
    l_in: float, t_in: float, w_in: float, h_in: float,
    text: str,
    size_pt: float = 14.0,
    bold: bool = False,
    color_hex: str = "#162032",
    highlight_phrase: Optional[str] = None,
    highlight_color_hex: Optional[str] = None,
    align: str = "left",
    valign: str = "middle",
    line_spacing: float = 1.15,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> None:
    if not text:
        return
    eff_pt = max(9.0, size_pt)
    x0, y0, mw, mh = _px(l_in), _px(t_in), _px(w_in), _px(h_in)
    base_fnt = _font(eff_pt, bold=bold, text_hint=text, ea_font=ea_font, latin_font=latin_font)
    lines = _tokenize_rich_lines(draw, text, mw, eff_pt, bold, highlight_phrase, ea_font, latin_font)
    base_sz = getattr(base_fnt, "size", 24)
    line_h = int(round(base_sz * line_spacing))
    total_h = line_h * len(lines)

    if valign == "middle":
        cy = y0 + max(0, (mh - total_h) // 2)
    elif valign == "bottom":
        cy = y0 + max(0, mh - total_h)
    else:
        cy = y0

    base_rgb = hex_to_rgb(color_hex)
    hi_rgb = hex_to_rgb(highlight_color_hex or color_hex)

    for tokens in lines:
        lw = sum(draw.textlength(t_txt, font=t_fnt) for t_txt, t_fnt, _, _ in tokens)
        if align == "center":
            cx = x0 + (mw - lw) * 0.5
        elif align == "right":
            cx = x0 + mw - lw
        else:
            cx = float(x0)

        for t_txt, t_fnt, b_kind, is_hi in tokens:
            dy = 0
            if b_kind == "sub":
                dy = int(round(base_sz * 0.28))
            elif b_kind == "sup":
                dy = -int(round(base_sz * 0.14))
            draw.text((cx, cy + dy), t_txt, font=t_fnt, fill=hi_rgb if is_hi else base_rgb)
            cx += draw.textlength(t_txt, font=t_fnt)
        cy += line_h


def _composite_figure_assets(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    spec: SlideSpec,
    pal: ScientificPalette,
    box: FigureBoxIn,
    show_l1: bool,
    show_l2: bool,
    show_l3: bool,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> None:
    if not spec.figure_spec:
        return
    src = spec.figure_spec.box_in
    sx = box.width / max(src.width, 1e-4)
    sy = box.height / max(src.height, 1e-4)

    def remap(pt: List[float]) -> List[float]:
        return [
            box.left + ((pt[0] - src.left) / max(src.width, 1e-4)) * box.width,
            box.top + ((pt[1] - src.top) / max(src.height, 1e-4)) * box.height,
        ]

    if show_l1:
        for asset in spec.figure_spec.assets:
            if not asset.png_path or not Path(asset.png_path).exists():
                continue
            nb = asset.norm_box if len(asset.norm_box) == 4 else [0.0, 0.0, 1.0, 1.0]
            ax = _px(box.left + nb[0] * box.width)
            ay = _px(box.top + nb[1] * box.height)
            aw = _px(nb[2] * box.width)
            ah = _px(nb[3] * box.height)
            with Image.open(asset.png_path) as im:
                rgba = im.convert("RGBA")
                if asset.engine.value == "chemdraw_rdkit" and asset.physical_width_in and asset.physical_height_in:
                    lock_w = _px(asset.physical_width_in * min(sx, sy, 1.0))
                    lock_h = _px(asset.physical_height_in * min(sx, sy, 1.0))
                    sc = min(1.0, aw / max(lock_w, 1), ah / max(lock_h, 1))
                    nw, nh = max(1, int(round(lock_w * sc))), max(1, int(round(lock_h * sc)))
                else:
                    sc = min(aw / max(rgba.width, 1), ah / max(rgba.height, 1))
                    nw, nh = max(1, int(round(rgba.width * sc))), max(1, int(round(rgba.height * sc)))
                resized = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                canvas.alpha_composite(resized, dest=(ax + (aw - nw) // 2, ay + (ah - nh) // 2))

            if show_l3 and asset.label:
                lbl_top = (box.top + nb[1] * box.height + nb[3] * box.height + 0.02) if (nb[1] + nb[3] <= 0.90) else (box.top + (nb[1] + nb[3]) * box.height - 0.34)
                _draw_text_box(draw, box.left + nb[0] * box.width, lbl_top, nb[2] * box.width, 0.34, asset.label, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", line_spacing=1.10, ea_font=ea_font, latin_font=latin_font)

    for ov in spec.figure_spec.native_overlays:
        col_hex = pal.token(ov.color_token)
        col = hex_to_rgb(col_hex)
        if ov.type == "zoom_lens_frame" and ov.source_circle_in and ov.target_circle_in and show_l2:
            s_xy = remap(ov.source_circle_in[:2])
            t_xy = remap(ov.target_circle_in[:2])
            rs = min(sx, sy)
            sr, tr = ov.source_circle_in[2] * rs, ov.target_circle_in[2] * rs
            draw.ellipse([_px(s_xy[0] - sr), _px(s_xy[1] - sr), _px(s_xy[0] + sr), _px(s_xy[1] + sr)], outline=col, width=2)
            draw.ellipse([_px(t_xy[0] - tr), _px(t_xy[1] - tr), _px(t_xy[0] + tr), _px(t_xy[1] + tr)], outline=col, width=3)
            for p1, p2 in compute_external_bitangents((s_xy[0], s_xy[1], sr), (t_xy[0], t_xy[1], tr)):
                _draw_dashed_line(draw, _px(p1[0]), _px(p1[1]), _px(p2[0]), _px(p2[1]), col, width=2)
        elif ov.type in ("arrow", "dashed_connector", "reaction_arrow") and ov.from_in and ov.to_in:
            fp, tp = remap(ov.from_in), remap(ov.to_in)
            if show_l2:
                x1, y1, x2, y2 = _px(fp[0]), _px(fp[1]), _px(tp[0]), _px(tp[1])
                draw.line([x1, y1, x2, y2], fill=col, width=3)
                ang = math.atan2(y2 - y1, x2 - x1)
                ah = 14
                draw.polygon([(x2, y2), (x2 - ah * math.cos(ang - 0.45), y2 - ah * math.sin(ang - 0.45)), (x2 - ah * math.cos(ang + 0.45), y2 - ah * math.sin(ang + 0.45))], fill=col)
            if ov.label:
                if ov.type == "reaction_arrow":
                    parts = [p.strip() for p in ov.label.split("|", 1)]
                    top_lbl = parts[0]
                    bot_lbl = parts[1] if len(parts) > 1 else ""
                    span_w = abs(tp[0] - fp[0])
                    pill_w = min(1.30, max(1.04, span_w + 0.28))
                    cx_a = 0.5 * (fp[0] + tp[0])
                    cy_a = 0.5 * (fp[1] + tp[1])
                    if show_l2:
                        _draw_rounded_box(draw, cx_a - pill_w * 0.5, cy_a - 0.36, pill_w, 0.28, fill_hex="#FFFFFF", border_hex=col_hex, border_px=1, radius=0.45)
                    if show_l3:
                        _draw_text_box(draw, cx_a - pill_w * 0.5, cy_a - 0.36, pill_w, 0.28, top_lbl, size_pt=14.0, bold=True, color_hex=col_hex, align="center", line_spacing=1.0, ea_font=ea_font, latin_font=latin_font)
                        if bot_lbl:
                            _draw_text_box(draw, cx_a - pill_w * 0.5, cy_a + 0.10, pill_w, 0.26, bot_lbl, size_pt=14.0, bold=True, color_hex=pal.s2, align="center", line_spacing=1.0, ea_font=ea_font, latin_font=latin_font)
                elif show_l3:
                    mx = 0.5 * (fp[0] + tp[0]) - 0.95
                    my = min(fp[1], tp[1]) - 0.38
                    _draw_text_box(draw, mx, my, 1.90, 0.32, ov.label, size_pt=14.0, bold=True, color_hex=col_hex, align="center", line_spacing=1.1, ea_font=ea_font, latin_font=latin_font)
        elif ov.type == "pocket_subsite":
            if ov.source_circle_in:
                s_xy = remap(ov.source_circle_in[:2])
                rs = min(sx, sy)
                sr = ov.source_circle_in[2] * rs
                if show_l2:
                    # Subtle dashed pocket arc
                    cx_p, cy_p, r_p = _px(s_xy[0]), _px(s_xy[1]), _px(sr)
                    for deg in range(0, 360, 18):
                        draw.arc([cx_p - r_p, cy_p - r_p, cx_p + r_p, cy_p + r_p], deg, deg + 10, fill=col, width=2)
                if show_l3 and ov.label:
                    _draw_text_box(draw, s_xy[0] - 0.52, s_xy[1] - sr - 0.22, 1.04, 0.22, ov.label, size_pt=10.5, bold=True, color_hex=col_hex, align="center", ea_font=ea_font, latin_font=latin_font)
            if ov.from_in and ov.to_in:
                fp, tp = remap(ov.from_in), remap(ov.to_in)
                if show_l2:
                    x1, y1, x2, y2 = _px(fp[0]), _px(fp[1]), _px(tp[0]), _px(tp[1])
                    _draw_dashed_line(draw, x1, y1, x2, y2, col, width=2, dash=8, gap=5)
                    ang = math.atan2(y2 - y1, x2 - x1)
                    ah = 11
                    draw.polygon([(x2, y2), (x2 - ah * math.cos(ang - 0.45), y2 - ah * math.sin(ang - 0.45)), (x2 - ah * math.cos(ang + 0.45), y2 - ah * math.sin(ang + 0.45))], fill=col)
                    r_d = _px(0.045)
                    draw.ellipse([x1 - r_d, y1 - r_d, x1 + r_d, y1 + r_d], fill=(*col, 255), outline=(255, 255, 255, 255), width=2)
                if show_l3 and ov.sublabel:
                    _draw_text_box(draw, fp[0] - 0.65, fp[1] - 0.26, 1.30, 0.22, ov.sublabel, size_pt=10.5, bold=True, color_hex=col_hex, align="center", ea_font=ea_font, latin_font=latin_font)


def render_v5_toc_preview(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Path:
    """Render the split-panel 目录 slide at 1920x1080 matching v5_layouts.py 1-to-1."""
    pal = get_palette(deck.meta.palette_id)
    fonts = deck.locked_standards.fonts or {}
    ea_f, lat_f = fonts.get("ea", "微软雅黑"), fonts.get("latin", "Arial")
    show_l2, show_l3 = "L2" in layers, "L3" in layers
    sub_tint = blend_with_white(pal.s4, 0.56)
    shadow_tile = blend_with_white(pal.s1, 0.78)
    rule_tint = blend_with_white(pal.s1, 0.35)

    canvas = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    if show_l2:
        draw.rectangle([0, 0, _px(3.50), 1080], fill=hex_to_rgb(pal.s1))
        _draw_hexagon_outline(canvas, 0.12, 0.22, 1.38, 1.22, alpha=36)
        _draw_hexagon_outline(canvas, 1.02, 0.72, 0.86, 0.76, alpha=36)
        _draw_hexagon_outline(canvas, 1.98, 5.84, 1.42, 1.24, alpha=36)
        draw = ImageDraw.Draw(canvas)
    if show_l3:
        _draw_text_box(draw, 0.34, 0.36, 2.82, 0.30, "LITERATURE SEMINAR", size_pt=10.5, bold=True, color_hex=sub_tint, ea_font=ea_f, latin_font=lat_f)
        _draw_text_box(draw, 0.58, 1.88, 1.10, 2.95, "目\n录", size_pt=72.0, bold=True, color_hex="#FFFFFF", align="center", line_spacing=1.02, ea_font=ea_f, latin_font=lat_f)

        # Render horizontal "CONTENTS" on transparent patch then rotate 90deg clockwise
        tw, th = _px(1.60), _px(0.44)
        tmp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        _draw_text_box(td, 0.0, 0.0, 1.60, 0.44, "CONTENTS", size_pt=16.5, bold=True, color_hex=sub_tint, align="center", ea_font=ea_f, latin_font=lat_f)
        rot_patch = tmp.rotate(-90, expand=True)
        cx_rot = _px(1.78 + 0.80) - rot_patch.width // 2
        cy_rot = _px(3.12 + 0.22) - rot_patch.height // 2
        canvas.alpha_composite(rot_patch, dest=(cx_rot, cy_rot))
        draw = ImageDraw.Draw(canvas)

        _draw_text_box(draw, 0.34, 6.02, 2.86, 0.68, deck.meta.deck_title, size_pt=11.0, bold=True, color_hex="#FFFFFF", valign="bottom", line_spacing=1.15, ea_font=ea_f, latin_font=lat_f)
        if deck.meta.deck_subtitle:
            _draw_text_box(draw, 0.34, 6.76, 2.86, 0.38, deck.meta.deck_subtitle, size_pt=9.5, color_hex=sub_tint, valign="top", line_spacing=1.1, ea_font=ea_f, latin_font=lat_f)
        _draw_text_box(draw, 8.60, 0.30, 4.30, 0.32, deck.meta.affiliation, size_pt=11.5, bold=True, color_hex=pal.s1, align="right", ea_font=ea_f, latin_font=lat_f)

    items = spec.toc_items or [f"{s.section_name}|Section {i+1:02d}" for i, s in enumerate(deck.slides) if s.section_name] or [
        "弹头与构效演进|SAR & Warhead Evolution",
        "三维构象与机理|3D Conformation & Binding",
        "药代与临床转化|Oral PK & Translation",
    ]
    items = items[:6]
    n = len(items)
    tile_s = 0.78 if n <= 4 else 0.72
    step_y = 1.32 if n <= 3 else (1.16 if n == 4 else (1.04 if n == 5 else 0.94))
    total_h = (n - 1) * step_y + tile_s
    start_y = max(0.86, 3.82 - total_h * 0.5)

    for idx, raw in enumerate(items):
        ry = start_y + idx * step_y
        cn, en = _split_bilingual(raw, idx)
        cn_clean = re.sub(r"^\d{1,2}\s*", "", cn).strip() or cn
        if show_l2:
            _draw_rounded_box(draw, 4.74, ry + 0.06, tile_s, tile_s, fill_hex=shadow_tile, border_hex=None, radius=0.18)
            _draw_rounded_box(draw, 4.66, ry, tile_s, tile_s, fill_hex=pal.s1, border_hex=None, radius=0.18)
            draw.line([_px(5.74), _px(ry + tile_s - 0.02), _px(12.44), _px(ry + tile_s - 0.02)], fill=hex_to_rgb(rule_tint), width=2)
        if show_l3:
            _draw_text_box(draw, 4.66, ry, tile_s, tile_s, f"{idx+1:02d}", size_pt=24.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 5.74, ry + 0.04, 5.80, 0.42, cn_clean, size_pt=22.0, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
            if en:
                _draw_text_box(draw, 5.74, ry + 0.46, 5.60, 0.24, en, size_pt=11.5, color_hex="#64748B", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 11.62, ry + 0.12, 0.82, 0.32, f"P.{idx+2:02d}", size_pt=11.5, bold=True, color_hex=pal.s3, align="right", ea_font=ea_f, latin_font=lat_f)

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p


def render_v5_slide_preview(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Optional[Path]:
    """Render any v5.0 pure-white elevated slide at 1920x1080 matching v5_layouts.py 1-to-1."""
    if spec.layout_id not in V5_LAYOUT_IDS:
        return None

    pal = get_palette(deck.meta.palette_id)
    fonts = deck.locked_standards.fonts or {}
    ea_f = fonts.get("ea", "微软雅黑")
    lat_f = fonts.get("latin", "Arial")
    total = len(deck.slides)
    show_l1, show_l2, show_l3 = "L1" in layers, "L2" in layers, "L3" in layers

    canvas = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # 1. Header Chrome
    variant = spec.header_variant or "nav_tabs"
    if variant == "editorial":
        if show_l2:
            draw.rectangle([_px(0.42), _px(0.20), _px(1.77), _px(0.25)], fill=hex_to_rgb(pal.s1))
            draw.line([_px(0.42), _px(1.26), _px(12.91), _px(1.26)], fill=hex_to_rgb(pal.line), width=2)
        if show_l3:
            _draw_text_box(draw, 0.42, 0.28, 11.20, 0.46, spec.title, size_pt=20.5, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 11.75, 0.34, 1.16, 0.32, f"{spec.slide_no:02d} / {total:02d}", size_pt=12.0, bold=True, color_hex=pal.s1, align="right", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.42, 0.78, 12.48, 0.42, spec.takeaway, size_pt=14.0, color_hex=pal.muted, highlight_phrase=spec.takeaway_highlight, highlight_color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    else:
        if show_l2:
            draw.rectangle([0, 0, 1920, _px(0.70)], fill=hex_to_rgb(pal.s1))
            draw.line([0, _px(0.70), 1920, _px(0.70)], fill=hex_to_rgb("#E2E8F0"), width=2)
            draw.ellipse([_px(0.24), _px(0.10), _px(0.74), _px(0.60)], outline=(255, 255, 255), width=3)
            # Inner hexagon crest
            hx0, hy0, hx1, hy1 = _px(0.32), _px(0.18), _px(0.66), _px(0.52)
            hdx = int((hx1 - hx0) * 0.25)
            hym = (hy0 + hy1) // 2
            draw.line([(hx0 + hdx, hy0), (hx1 - hdx, hy0), (hx1, hym), (hx1 - hdx, hy1), (hx0 + hdx, hy1), (hx0, hym), (hx0 + hdx, hy0)], fill=(255, 255, 255), width=2)
        if show_l3:
            _draw_text_box(draw, 0.24, 0.10, 0.50, 0.50, "Rx", size_pt=10.5, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

        tabs_raw = (spec.nav_sections or [s.section_name for s in deck.slides if s.section_name] or ["01 背景演进", "02 构象机理", "03 药代转化"])[:6]
        tab_w = 12.08 / max(len(tabs_raw), 1)
        active_idx = max(0, min(spec.active_nav_idx, len(tabs_raw) - 1))
        for t_i, raw_tab in enumerate(tabs_raw):
            tx = 0.96 + t_i * tab_w
            cn_lbl, en_lbl = _split_bilingual(raw_tab, t_i)
            if t_i == active_idx:
                if show_l2:
                    _draw_trapezoid_cutout(draw, tx + 0.04, 0.06, tab_w - 0.08, 0.66, fill_hex="#FFFFFF", slope=0.055)
                if show_l3:
                    _draw_text_box(draw, tx + 0.14, 0.09, tab_w - 0.28, 0.30, cn_lbl, size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
                    _draw_text_box(draw, tx + 0.14, 0.39, tab_w - 0.28, 0.24, en_lbl, size_pt=9.5, color_hex="#64748B", align="center", ea_font=ea_f, latin_font=lat_f)
            else:
                if show_l3:
                    sub_tint = blend_with_white(pal.s4, 0.56)
                    _draw_text_box(draw, tx + 0.10, 0.09, tab_w - 0.20, 0.30, cn_lbl, size_pt=13.5, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                    _draw_text_box(draw, tx + 0.10, 0.39, tab_w - 0.20, 0.24, en_lbl, size_pt=9.5, color_hex=sub_tint, align="center", ea_font=ea_f, latin_font=lat_f)
                if show_l2 and t_i < len(tabs_raw) - 1 and t_i + 1 != active_idx:
                    draw.line([_px(tx + tab_w), _px(0.16), _px(tx + tab_w), _px(0.54)], fill=hex_to_rgb(pal.s3), width=2)

        sec_heading = _clean_section_heading(spec)
        if show_l2:
            _draw_chevron(draw, 0.40, 0.94, 0.18, 0.24, pal.s1)
            _draw_chevron(draw, 0.53, 0.96, 0.14, 0.20, pal.s3)
            _draw_elevated_box(canvas, 3.62, 0.84, 9.31, 0.44, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.14)
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([_px(3.70), _px(0.92), _px(3.76), _px(1.20)], fill=hex_to_rgb(pal.s1))
        if show_l3:
            _draw_text_box(draw, 0.74, 0.84, 2.82, 0.44, sec_heading, size_pt=19.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 3.84, 0.85, 8.96, 0.42, spec.takeaway, size_pt=14.0, color_hex=pal.ink, highlight_phrase=spec.takeaway_highlight, highlight_color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    # 2. Body Layout Dispatch
    fig_box = get_v5_figure_box(spec.layout_id)

    if spec.layout_id == LayoutId.lit_overview_dual_card:
        if show_l2:
            _draw_rounded_box(draw, 0.40, 1.48, 8.44, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
        p_title_box = (spec.figure_bottom_note or "药物化学结构演进与构效关系").split("|")[0]
        _draw_chamfered_header_tab(canvas, draw, 1.72, 1.35, 5.80, 0.30, p_title_box, fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l2:
            _draw_elevated_box(canvas, 0.52, 1.84, 3.42, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            _draw_elevated_box(canvas, 5.28, 1.84, 3.42, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)

        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)

        if spec.figure_spec:
            tag_xs = (0.62, 5.38)
            for idx, asset in enumerate(spec.figure_spec.assets[:2]):
                if asset.sublabel:
                    tx = tag_xs[idx]
                    if show_l2:
                        _draw_rounded_box(draw, tx, 1.92, 1.54, 0.24, fill_hex="#FFFFFF", border_hex=pal.s4, border_px=1, radius=0.45)
                    if show_l3:
                        _draw_text_box(draw, tx + 0.04, 1.92, 1.46, 0.24, asset.sublabel, size_pt=10.5, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)

        for idx, ins in enumerate(spec.insights[:2]):
            cx = 0.52 + idx * 4.16
            if show_l2:
                _draw_elevated_box(canvas, cx, 4.92, 4.02, 1.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(cx + 0.09), _px(5.04), _px(cx + 0.145), _px(5.88)], fill=hex_to_rgb(pal.s1))
            if show_l3:
                _draw_text_box(draw, cx + 0.24, 4.96, 3.68, 0.30, f"{ins.index}  {ins.heading}", size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.24, 5.28, 3.68, 0.68, ins.body, size_pt=14.0, color_hex=pal.ink, highlight_phrase=ins.highlight, highlight_color_hex=pal.s1, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)

        prof = spec.profile_card or {}
        if show_l2:
            _draw_elevated_box(canvas, 8.98, 1.48, 3.95, 3.26, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            draw.line([_px(9.12), _px(2.88), _px(12.79), _px(2.88)], fill=hex_to_rgb("#D6E0EC"), width=2)
        _draw_chamfered_header_tab(canvas, draw, 9.38, 1.35, 3.15, 0.30, prof.get("journal_badge", "SCIENCE 2021 · 文献档案"), fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.12, 1.80, 3.67, 0.70, prof.get("paper_title", deck.meta.deck_title[:48]), size_pt=14.0, bold=True, color_hex=pal.s1, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 9.12, 2.52, 3.67, 0.30, prof.get("authors", spec.footer_left), size_pt=11.5, color_hex="#64748B", valign="top", ea_font=ea_f, latin_font=lat_f)
            metrics = prof.get("metrics") or [(k.label, k.value) for k in spec.kpis[:3]] or [("Ki", "3.11 nM"), ("EC50", "74.5 nM")]
            my = 2.96
            for m_lbl, m_val in metrics[:4]:
                _draw_text_box(draw, 9.12, my, 1.42, 0.38, str(m_lbl), size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 10.56, my, 2.23, 0.38, str(m_val), size_pt=14.0, bold=True, color_hex=pal.s1, align="right", ea_font=ea_f, latin_font=lat_f)
                if show_l2:
                    draw.line([_px(9.12), _px(my + 0.40), _px(12.79), _px(my + 0.40)], fill=hex_to_rgb("#E2E8F0"), width=1)
                my += 0.43
        if show_l2:
            _draw_elevated_box(canvas, 8.98, 4.88, 3.95, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 9.95, 4.74, 2.01, 0.30, "设计核心", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.12, 5.14, 3.67, 0.90, prof.get("focus_text", spec.takeaway), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.mechanism_3col_flow:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            _draw_elevated_box(canvas, 3.95, 1.50, 5.44, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.06)
            _draw_elevated_box(canvas, 9.69, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            _draw_right_arrow_shape(draw, 3.71, 3.82, 0.18, 0.24, pal.s1)
            _draw_right_arrow_shape(draw, 9.45, 3.82, 0.18, 0.24, pal.s1)
        _draw_chamfered_header_tab(canvas, draw, 0.88, 1.39, 2.30, 0.30, "关键药效团解析", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _draw_chamfered_header_tab(canvas, draw, 5.02, 1.36, 3.30, 0.30, "三维构象与口袋结合模式", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _draw_chamfered_header_tab(canvas, draw, 10.17, 1.39, 2.30, 0.30, "关键结构优势", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)

        l_cards = spec.left_cards or [{"heading": i.heading, "body": i.body} for i in spec.insights[:3]]
        for idx, lc in enumerate(l_cards[:3]):
            cy = 1.90 + idx * 1.38
            if show_l2:
                draw.rectangle([_px(0.54), _px(cy + 0.08), _px(0.595), _px(cy + 1.14)], fill=hex_to_rgb(pal.s1))
                if idx < 2:
                    draw.line([_px(0.56), _px(cy + 1.28), _px(3.48), _px(cy + 1.28)], fill=hex_to_rgb("#E2E8F0"), width=1)
            if show_l3:
                _draw_text_box(draw, 0.68, cy, 2.84, 0.34, lc.get("heading", ""), size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.68, cy + 0.36, 2.84, 0.84, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)

        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)

        for cb in spec.callout_badges[:4]:
            bx, by, bw = float(cb.get("x_in", 4.05)), float(cb.get("y_in", 1.78)), max(1.68, float(cb.get("w_in", 1.82)))
            bh = 0.34
            c_hex = pal.token(cb.get("color_token", "s1"))
            if show_l2:
                if "target_x_in" in cb and "target_y_in" in cb:
                    tx_t, ty_t = float(cb["target_x_in"]), float(cb["target_y_in"])
                    start_y = (by + bh) if ty_t > (by + bh * 0.5) else by
                    _draw_dashed_line(draw, _px(bx + bw * 0.5), _px(start_y), _px(tx_t), _px(ty_t), hex_to_rgb(c_hex), width=2)
                    r_d = _px(0.045)
                    dx_p, dy_p = _px(tx_t), _px(ty_t)
                    draw.ellipse([dx_p - r_d, dy_p - r_d, dx_p + r_d, dy_p + r_d], fill=(*hex_to_rgb(c_hex), 255), outline=(255, 255, 255, 255), width=2)
                _draw_elevated_box(canvas, bx, by, bw, bh, fill_hex="#FFFFFF", border_hex=c_hex, border_px=2, radius=0.45, shadow_alpha=14, blur_px=4)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, bx + 0.04, by, bw - 0.08, bh, str(cb.get("text", "")), size_pt=14.0, bold=True, color_hex=c_hex, align="center", ea_font=ea_f, latin_font=lat_f)

        r_chain = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] + [{"title": "高选择性", "body": "低脱靶与口服稳定"}]
        for idx, rc in enumerate(r_chain[:3]):
            ry = 1.94 + idx * 1.38
            if show_l2:
                _draw_elevated_box(canvas, 9.83, ry, 2.97, 1.04, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                if idx < 2:
                    _draw_down_arrow(draw, 11.31, ry + 1.08, 0.24, 0.24, pal.s2)
            if show_l3:
                _draw_text_box(draw, 9.93, ry + 0.08, 2.77, 0.34, rc.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.93, ry + 0.44, 2.77, 0.54, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, align="center", line_spacing=1.10, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.data_dashboard_table:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.50, 7.58, 4.64, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 2.10, 1.36, 4.18, 0.30, "定量药代动力学指标与可编辑柱图", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)

        kpis = spec.kpis[:3] or [{"value": "34–50%", "label": "大鼠口服生物利用度", "color_token": "s1"}, {"value": "35×", "label": "较先导暴露提升", "color_token": "s2"}, {"value": "5.1 h", "label": "大鼠半衰期 t1/2", "color_token": "s1"}]
        for idx, kp in enumerate(kpis[:3]):
            val = kp.value if hasattr(kp, "value") else kp["value"]
            lbl = kp.label if hasattr(kp, "label") else kp["label"]
            ctok = kp.color_token if hasattr(kp, "color_token") else kp.get("color_token", "s1")
            tx = 0.54 + idx * 2.48
            if show_l2:
                _draw_elevated_box(canvas, tx, 1.84, 2.34, 0.88, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(tx + 0.08), _px(1.96), _px(tx + 0.14), _px(2.60)], fill=hex_to_rgb(pal.token(ctok)))
            if show_l3:
                _draw_text_box(draw, tx + 0.16, 1.90, 2.10, 0.42, val, size_pt=22.0, bold=True, color_hex=pal.token(ctok), align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, tx + 0.16, 2.34, 2.10, 0.34, lbl, size_pt=14.0, color_hex=pal.muted, align="center", ea_font=ea_f, latin_font=lat_f)

        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)

        td = spec.table_data
        table_bottom = 3.92
        if td and td.headers:
            rows_count = len(td.rows) + 1
            cols_count = len(td.headers)
            row_h = min(0.46, 2.38 / max(rows_count, 2))
            col_w = 4.81 / max(cols_count, 1)
            if show_l2:
                draw.rectangle([_px(8.12), _px(1.50), _px(12.93), _px(1.50 + row_h)], fill=hex_to_rgb(pal.s1))
                for r_i in range(len(td.rows)):
                    ry = 1.50 + (r_i + 1) * row_h
                    draw.rectangle([_px(8.12), _px(ry), _px(12.93), _px(ry + row_h)], fill=(255, 255, 255))
                    draw.line([_px(8.12), _px(ry + row_h), _px(12.93), _px(ry + row_h)], fill=hex_to_rgb("#E2E8F0"), width=1)
            if show_l3:
                for c_i, hdr in enumerate(td.headers):
                    _draw_text_box(draw, 8.12 + c_i * col_w + 0.06, 1.50, col_w - 0.12, row_h, hdr, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center" if c_i > 0 else "left", ea_font=ea_f, latin_font=lat_f)
                for r_i, row in enumerate(td.rows):
                    ry = 1.50 + (r_i + 1) * row_h
                    for c_i, val in enumerate(row[:cols_count]):
                        is_last = c_i == cols_count - 1
                        _draw_text_box(draw, 8.12 + c_i * col_w + 0.06, ry, col_w - 0.12, row_h, val, size_pt=14.0, bold=is_last, color_hex=pal.s1 if is_last else pal.ink, align="center" if c_i > 0 else "left", ea_font=ea_f, latin_font=lat_f)
            table_bottom = 1.50 + row_h * rows_count

        scards = spec.strategy_cards or [
            {"badge": "策略", "badge_color": "s1" if idx == 0 else "s2", "title": i.heading, "body": i.body}
            for idx, i in enumerate(spec.insights[:2])
        ]
        cur_y = table_bottom + 0.14
        avail_h = max(0.88, (6.14 - cur_y - 0.10 * max(len(scards) - 1, 0)) / max(len(scards), 1))
        for idx, sc in enumerate(scards[:2]):
            sy = cur_y + idx * (avail_h + 0.10)
            bcol = _resolve_strategy_badge_color(sc.get("badge_color"), pal, idx)
            if show_l2:
                _draw_elevated_box(canvas, 8.12, sy, 4.81, avail_h, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(8.20), _px(sy + 0.12), _px(8.26), _px(sy + avail_h - 0.12)], fill=hex_to_rgb(bcol))
                _draw_rounded_box(draw, 8.34, sy + 0.10, 1.14, 0.28, fill_hex=bcol, border_hex=None, radius=0.14)
            if show_l3:
                _draw_text_box(draw, 8.34, sy + 0.10, 1.14, 0.28, sc.get("badge", "策略"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.56, sy + 0.08, 3.26, 0.32, sc.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 8.34, sy + 0.44, 4.46, avail_h - 0.50, sc.get("body", ""), size_pt=14.0, color_hex=pal.muted, valign="top", line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.bg_top_summary_3box:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.54, 12.53, 1.04, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        if show_l3:
            lines = spec.pain_points[:3] or [f"•  {ins.heading}：{ins.body}" for ins in spec.insights[:3]]
            for idx, ln in enumerate(lines[:3]):
                _draw_text_box(draw, 0.58, 1.58 + idx * 0.32, 12.16, 0.32, ln, size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
        boxes = [(0.40, 3.82, "01 核心痛点"), (4.50, 4.30, "02 多尺度科研图解"), (9.08, 3.85, "03 预期突破")]
        for bx, bw, bt in boxes:
            if show_l2:
                _draw_elevated_box(canvas, bx, 2.74, bw, 3.36, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
                draw = ImageDraw.Draw(canvas)
            _draw_chamfered_header_tab(canvas, draw, bx + 0.45, 2.64, bw - 0.90, 0.30, bt, fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l2:
            for ax in (4.24, 8.82):
                _draw_right_arrow_shape(draw, ax, 4.40, 0.22, 0.28, pal.s1)
        for idx, ins in enumerate(spec.insights[:2]):
            if show_l2:
                _draw_elevated_box(canvas, 0.56, 3.16 + idx * 1.38, 3.50, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, 0.70, 3.22 + idx * 1.38, 3.22, 0.32, ins.heading, size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.70, 3.56 + idx * 1.38, 3.22, 0.78, ins.body, size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)
        r_items = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]]
        for idx, rc in enumerate(r_items[:2]):
            if show_l2:
                _draw_elevated_box(canvas, 9.24, 3.16 + idx * 1.38, 3.53, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, 9.38, 3.24 + idx * 1.38, 3.25, 0.34, rc.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.38, 3.60 + idx * 1.38, 3.25, 0.72, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, align="center", valign="top", ea_font=ea_f, latin_font=lat_f)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.pain_points_left_arrows:
        pts = spec.pain_points or [f"{ins.heading}：{ins.body}" for ins in spec.insights[:4]]
        n = min(4, max(2, len(pts)))
        row_h = min(1.04, (4.48 - 0.14 * (n - 1)) / n)
        for idx, pt in enumerate(pts[:4]):
            ry = 1.56 + idx * (row_h + 0.14)
            if show_l2:
                _draw_elevated_box(canvas, 0.40, ry, 5.06, row_h, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(0.48), _px(ry + 0.14), _px(0.54), _px(ry + row_h - 0.14)], fill=hex_to_rgb(pal.s1))
                draw.ellipse([_px(4.98), _px(ry + row_h / 2 - 0.18), _px(5.34), _px(ry + row_h / 2 + 0.18)], fill=hex_to_rgb(pal.s1))
            if show_l3:
                _draw_text_box(draw, 0.64, ry + 0.06, 4.28, row_h - 0.12, pt, size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 4.98, ry + row_h / 2 - 0.18, 0.36, 0.36, "→", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 5.66, 1.54, 7.27, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 7.46, 1.42, 3.68, 0.30, "关键科学问题与微界面机制", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        chips = spec.figure_chips or ["限域调控", "低能垒", "高分散", "定量互证"]
        cw = 6.94 / max(len(chips[:4]), 1)
        for idx, ch in enumerate(chips[:4]):
            cx = 5.82 + idx * cw
            if show_l2:
                _draw_elevated_box(canvas, cx + 0.04, 5.18, cw - 0.08, 0.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.14)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, cx + 0.04, 5.18, cw - 0.08, 0.38, ch, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l3:
            _draw_text_box(draw, 5.82, 5.64, 6.94, 0.40, spec.figure_bottom_note or spec.takeaway, size_pt=14.0, bold=True, color_hex=pal.alert, align="center", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.fig_left_3step_chain:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.54, 7.76, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 2.28, 1.41, 4.00, 0.30, spec.section_name[:16] or "多尺度表征与实验验证", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        chain = spec.right_chain or [{"title": ins.heading, "body": ins.body} for ins in spec.insights[:3]]
        for idx, item in enumerate(chain[:3]):
            ry = 1.56 + idx * 1.56
            if show_l2:
                _draw_rounded_box(draw, 8.34, ry, 1.16, 1.24, fill_hex=pal.s1, border_hex=None, radius=0.08)
                _draw_elevated_box(canvas, 9.58, ry, 3.35, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                if idx < 2:
                    _draw_down_arrow(draw, 10.66, ry + 1.27, 0.32, 0.26, pal.s2)
            if show_l3:
                _draw_text_box(draw, 8.38, ry, 1.08, 1.24, item.get("title", f"阶段 {idx+1}"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.70, ry + 0.08, 3.11, 1.08, item.get("body", ""), size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.vs_center_wing:
        l_cards = spec.left_cards or [{"heading": "传统路径 / 对照", "body": ins.body} for ins in spec.insights[:2]]
        r_cards = spec.right_chain or [{"title": "创新策略 / 优势", "body": k.label + " " + k.value} for k in spec.kpis[:2]]
        for idx, lc in enumerate(l_cards[:2]):
            cy = 1.58 + idx * 2.26
            if show_l2:
                _draw_elevated_box(canvas, 0.40, cy, 3.20, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
            _draw_chamfered_header_tab(canvas, draw, 0.72, cy - 0.12, 2.56, 0.30, lc.get("heading", ""), fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
            if show_l3:
                _draw_text_box(draw, 0.54, cy + 0.34, 2.92, 1.62, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 3.76, 1.54, 5.80, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        for idx, rc in enumerate(r_cards[:2]):
            cy = 1.58 + idx * 2.26
            if show_l2:
                _draw_elevated_box(canvas, 9.72, cy, 3.21, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
            _draw_chamfered_header_tab(canvas, draw, 10.04, cy - 0.12, 2.56, 0.30, rc.get("title", ""), fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
            if show_l3:
                _draw_text_box(draw, 9.86, cy + 0.34, 2.93, 1.62, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.roadmap_layered_matrix:
        for idx, tag in enumerate(["研究目标", "技术路线", "验证方案"]):
            ry = 1.54 + idx * 1.54
            if show_l2:
                _draw_rounded_box(draw, 0.40, ry, 0.82, 1.38, fill_hex=pal.s1, border_hex=None, radius=0.08)
                _draw_elevated_box(canvas, 1.30, ry, 7.58, 1.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, 0.42, ry, 0.78, 1.38, tag, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 9.06, 1.54, 3.87, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 9.72, 1.39, 2.55, 0.30, "闭环实施与转化路径", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        nodes = spec.right_chain or [{"title": ins.heading} for ins in spec.insights[:3]] + [{"title": "定量成果产出"}]
        for idx, nd in enumerate(nodes[:4]):
            ny = 2.02 + idx * 0.98
            if show_l2:
                _draw_elevated_box(canvas, 9.30, ny, 3.39, 0.68, fill_hex="#FFFFFF", border_hex=pal.s1 if idx == 3 else "#D6E0EC", border_px=2 if idx == 3 else 1, radius=0.45)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, 9.42, ny, 3.15, 0.68, nd.get("title", ""), size_pt=14.0, bold=True, color_hex=pal.s1 if idx == 3 else pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)

    # 3. Elevated Pure-White Bottom Banner + Footer
    banner = spec.bottom_banner or {}
    mode = banner.get("mode", "bar")
    y, h = 6.26, 0.48
    if mode == "triple_pill":
        if show_l2:
            _draw_elevated_box(canvas, 0.40, y, 3.65, h, fill_hex="#FFFFFF", border_hex=pal.s4, border_px=1, radius=0.45)
            _draw_elevated_box(canvas, 4.46, y - 0.02, 4.41, h + 0.04, fill_hex="#FFFFFF", border_hex=pal.s1, border_px=2, radius=0.45)
            _draw_elevated_box(canvas, 9.28, y, 3.65, h, fill_hex="#FFFFFF", border_hex=pal.s4, border_px=1, radius=0.45)
            draw = ImageDraw.Draw(canvas)
            _draw_right_arrow_shape(draw, 4.12, y + h / 2, 0.28, 0.16, pal.s2)
            _draw_right_arrow_shape(draw, 8.94, y + h / 2, 0.28, 0.16, pal.s2)
        if show_l3:
            _draw_text_box(draw, 0.50, y, 3.45, h, banner.get("left", "高选择性构象预组织"), size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 4.58, y - 0.02, 4.17, h + 0.04, banner.get("center", spec.takeaway[:26] or "核心机理突破"), size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 9.38, y, 3.45, h, banner.get("right", "可逆共价低脱靶风险"), size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
    else:
        border_c = "#FECACA" if mode == "rose_quote" else "#D6E0EC"
        badge_c = "#B91C1C" if mode == "rose_quote" else pal.s1
        if show_l2:
            _draw_elevated_box(canvas, 0.40, y, 12.53, h, fill_hex="#FFFFFF", border_hex=border_c, border_px=1, radius=0.16)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.48, y + 0.07, 1.44, h - 0.14, fill_hex=badge_c, border_hex=None, radius=0.18)
        if show_l3:
            _draw_text_box(draw, 0.48, y + 0.07, 1.44, h - 0.14, banner.get("badge", "核心总结"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 2.08, y, 10.72, h, banner.get("text", spec.takeaway), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

    if show_l3:
        _draw_text_box(draw, 0.40, 6.90, 9.20, 0.32, spec.footer_left, size_pt=11.0, color_hex="#64748B", ea_font=ea_f, latin_font=lat_f)
        _draw_text_box(draw, 9.80, 6.90, 3.13, 0.32, f"{deck.meta.affiliation} · {spec.slide_no:02d}/{total:02d}", size_pt=11.0, color_hex="#64748B", align="right", ea_font=ea_f, latin_font=lat_f)

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p
