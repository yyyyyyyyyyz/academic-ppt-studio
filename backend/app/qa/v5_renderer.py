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

from ..builder.v5_layouts import (
    _clean_section_heading,
    _split_bilingual,
    extract_visual_metric_bars,
    get_v5_figure_box,
    split_card_head_body,
)
from ..builder.xml_utils import parse_markup_segments
from ..figure_factory.palettes import ScientificPalette, blend_with_white, get_palette, hex_to_rgb
from ..figure_factory.vector_mech import compute_external_bitangents
from ..schemas.deck_spec import DeckSpec, FigureBoxIn, InsightItem, LayoutId, SlideSpec, V5_LAYOUT_IDS
from .font_resolver import resolve_pil_font


SCALE = 144.0  # 13.333 * 144 = 1920 x 1080


def _px(val_in: float) -> int:
    return int(round(val_in * SCALE))


def _resolve_strategy_badge_color(raw: Optional[str], pal: ScientificPalette, idx: int) -> str:
    """Resolve strategy card badge color dynamically against active palette multi-color roles."""
    roles = pal.slide_roles()
    accents = roles["accents"]
    val = (raw or "").strip()
    if not val or val in ("s1", "#00468B", "#D97706"):
        return accents[idx % 4]
    if val == "s2":
        return roles["c2"]
    if val == "s3":
        return roles["c3"]
    if val == "alert":
        return roles["alert"]
    if val in ("s4", "s5", "s6", "ink", "muted"):
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
    tip = max(5, min(int((x1 - x0) * 0.42), int((y1 - y0) * 0.48)))
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


def _draw_left_arrow_shape(draw: ImageDraw.ImageDraw, l_in: float, cy_in: float, w_in: float, h_in: float, fill_hex: str) -> None:
    x0, y0 = _px(l_in), _px(cy_in - h_in / 2)
    x1, y1 = _px(l_in + w_in), _px(cy_in + h_in / 2)
    ym = (y0 + y1) // 2
    sh = max(3, (y1 - y0) // 4)
    x_head = x1 - int((x1 - x0) * 0.48)
    poly = [(x1, ym - sh), (x_head, ym - sh), (x_head, y0), (x0, ym), (x_head, y1), (x_head, ym + sh), (x1, ym + sh)]
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
            reserve_lbl = bool(show_l3 and asset.label and (nb[1] + nb[3] > 0.90) and (nb[3] * box.height > 1.0))
            ah_fig = max(1, ah - _px(0.36)) if reserve_lbl else ah
            with Image.open(asset.png_path) as im:
                rgba = im.convert("RGBA")
                if asset.engine.value == "chemdraw_rdkit" and asset.physical_width_in and asset.physical_height_in:
                    lock_w = _px(asset.physical_width_in * min(sx, sy, 1.0))
                    lock_h = _px(asset.physical_height_in * min(sx, sy, 1.0))
                    sc = min(1.0, aw / max(lock_w, 1), ah_fig / max(lock_h, 1))
                    nw, nh = max(1, int(round(lock_w * sc))), max(1, int(round(lock_h * sc)))
                else:
                    sc = min(aw / max(rgba.width, 1), ah_fig / max(rgba.height, 1))
                    nw, nh = max(1, int(round(rgba.width * sc))), max(1, int(round(rgba.height * sc)))
                resized = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                canvas.alpha_composite(resized, dest=(ax + (aw - nw) // 2, ay + (ah_fig - nh) // 2))

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
    roles = pal.slide_roles()
    accents = roles["accents"]
    fonts = deck.locked_standards.fonts or {}
    ea_f, lat_f = fonts.get("ea", "微软雅黑"), fonts.get("latin", "Arial")
    show_l2, show_l3 = "L2" in layers, "L3" in layers
    sub_tint = blend_with_white(pal.s4, 0.56)
    rule_tint = blend_with_white(roles["c2"], 0.38)

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
        tile_c = accents[idx % len(accents)]
        shadow_tile = blend_with_white(tile_c, 0.76)
        if show_l2:
            _draw_rounded_box(draw, 4.74, ry + 0.06, tile_s, tile_s, fill_hex=shadow_tile, border_hex=None, radius=0.18)
            _draw_rounded_box(draw, 4.66, ry, tile_s, tile_s, fill_hex=tile_c, border_hex=None, radius=0.18)
            draw.line([_px(5.74), _px(ry + tile_s - 0.02), _px(12.44), _px(ry + tile_s - 0.02)], fill=hex_to_rgb(rule_tint), width=2)
        if show_l3:
            _draw_text_box(draw, 4.66, ry, tile_s, tile_s, f"{idx+1:02d}", size_pt=24.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 5.74, ry + 0.04, 5.80, 0.42, cn_clean, size_pt=22.0, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
            if en:
                _draw_text_box(draw, 5.74, ry + 0.46, 5.60, 0.24, en, size_pt=11.5, color_hex="#64748B", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 11.62, ry + 0.12, 0.82, 0.32, f"P.{idx+2:02d}", size_pt=11.5, bold=True, color_hex=tile_c, align="right", ea_font=ea_f, latin_font=lat_f)

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
    roles = pal.slide_roles()
    accents, tints, borders = roles["accents"], roles["tints"], roles["borders"]
    c1, c2, c3, alert_c = roles["c1"], roles["c2"], roles["c3"], roles["alert"]
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
            _draw_chevron(draw, 0.40, 0.94, 0.18, 0.24, c1)
            _draw_chevron(draw, 0.53, 0.96, 0.14, 0.20, c2)
            _draw_elevated_box(canvas, 3.62, 0.84, 9.31, 0.44, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.14)
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([_px(3.70), _px(0.92), _px(3.76), _px(1.20)], fill=hex_to_rgb(c2))
        if show_l3:
            _draw_text_box(draw, 0.74, 0.84, 2.82, 0.44, sec_heading, size_pt=19.5, bold=True, color_hex=c1, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 3.84, 0.85, 8.96, 0.42, spec.takeaway, size_pt=14.0, color_hex=pal.ink, highlight_phrase=spec.takeaway_highlight, highlight_color_hex=alert_c, ea_font=ea_f, latin_font=lat_f)

    # 2. Body Layout Dispatch
    fig_box = get_v5_figure_box(spec.layout_id)

    if spec.layout_id == LayoutId.lit_overview_dual_card:
        if show_l2:
            _draw_rounded_box(draw, 0.40, 1.48, 8.44, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
        p_title_box = (spec.figure_bottom_note or "药物化学结构演进与构效关系").split("|")[0]
        _draw_chamfered_header_tab(canvas, draw, 1.72, 1.35, 5.80, 0.30, p_title_box, fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        assets_n = len(spec.figure_spec.assets) if spec.figure_spec else 0
        if show_l2:
            if assets_n <= 1:
                _draw_elevated_box(canvas, 0.52, 1.84, 8.20, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            else:
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
                        _draw_text_box(draw, tx + 0.04, 1.92, 1.46, 0.24, asset.sublabel, size_pt=14.0, bold=True, color_hex=accents[idx % 4], align="center", ea_font=ea_f, latin_font=lat_f)

        for idx, ins in enumerate(spec.insights[:2]):
            cx = 0.52 + idx * 4.16
            ac_c = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, cx, 4.92, 4.02, 1.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(cx + 0.02), _px(4.94), _px(cx + 4.00), _px(5.28)], fill=hex_to_rgb(tints[idx % 4]))
                _draw_rounded_box(draw, cx + 0.10, 4.97, 0.40, 0.28, fill_hex=ac_c, border_hex=None, radius=0.22)
            if show_l3:
                _draw_text_box(draw, cx + 0.10, 4.97, 0.40, 0.28, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.56, 4.95, 3.38, 0.32, ins.heading, size_pt=14.5, bold=True, color_hex=ac_c, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.14, 5.31, 3.74, 0.65, ins.body, size_pt=14.0, color_hex=pal.ink, highlight_phrase=ins.highlight, highlight_color_hex=alert_c, valign="top", line_spacing=1.10, ea_font=ea_f, latin_font=lat_f)

        prof = spec.profile_card or {}
        if show_l2:
            _draw_elevated_box(canvas, 8.98, 1.48, 3.95, 3.26, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            draw.line([_px(9.12), _px(2.88), _px(12.79), _px(2.88)], fill=hex_to_rgb("#D6E0EC"), width=2)
        _draw_chamfered_header_tab(canvas, draw, 9.38, 1.35, 3.15, 0.30, prof.get("journal_badge", "SCIENCE 2021 · 文献档案"), fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.12, 1.80, 3.67, 0.70, prof.get("paper_title", deck.meta.deck_title[:48]), size_pt=14.0, bold=True, color_hex=c1, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 9.12, 2.52, 3.67, 0.30, prof.get("authors", spec.footer_left), size_pt=11.5, color_hex="#64748B", valign="top", ea_font=ea_f, latin_font=lat_f)
            metrics = prof.get("metrics") or [(k.label, k.value) for k in spec.kpis[:3]] or [("Ki", "3.11 nM"), ("EC50", "74.5 nM")]
            my = 2.96
            for m_i, (m_lbl, m_val) in enumerate(metrics[:4]):
                _draw_text_box(draw, 9.12, my, 1.42, 0.38, str(m_lbl), size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 10.56, my, 2.23, 0.38, str(m_val), size_pt=14.0, bold=True, color_hex=accents[m_i % 4], align="right", ea_font=ea_f, latin_font=lat_f)
                if show_l2:
                    draw.line([_px(9.12), _px(my + 0.40), _px(12.79), _px(my + 0.40)], fill=hex_to_rgb("#E2E8F0"), width=1)
                my += 0.43
        if show_l2:
            _draw_elevated_box(canvas, 8.98, 4.88, 3.95, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 9.95, 4.74, 2.01, 0.30, "设计核心", fill_hex=c2, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.12, 5.14, 3.67, 0.90, prof.get("focus_text", spec.takeaway), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.mechanism_3col_flow:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            _draw_elevated_box(canvas, 3.95, 1.50, 5.44, 4.64, fill_hex="#FFFFFF", border_hex=c2, border_px=2, dashed=True, radius=0.06)
            _draw_elevated_box(canvas, 9.69, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            _draw_right_arrow_shape(draw, 3.71, 3.82, 0.18, 0.24, c1)
            _draw_right_arrow_shape(draw, 9.45, 3.82, 0.18, 0.24, c3)
        _draw_chamfered_header_tab(canvas, draw, 0.88, 1.39, 2.30, 0.30, "关键药效团解析", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _draw_chamfered_header_tab(canvas, draw, 5.02, 1.36, 3.30, 0.30, "三维构象与口袋结合模式", fill_hex=c2, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _draw_chamfered_header_tab(canvas, draw, 10.17, 1.39, 2.30, 0.30, "关键结构优势", fill_hex=c3, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)

        l_cards = spec.left_cards or [{"heading": i.heading, "body": i.body} for i in spec.insights[:3]]
        for idx, lc in enumerate(l_cards[:3]):
            cy = 1.84 + idx * 1.42
            ac_c = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, 0.54, cy, 2.97, 1.16, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(0.56), _px(cy + 0.02), _px(3.49), _px(cy + 0.36)], fill=hex_to_rgb(tints[idx % 4]))
                draw.rectangle([_px(0.54), _px(cy + 0.06), _px(0.60), _px(cy + 1.10)], fill=hex_to_rgb(ac_c))
                if idx < min(len(l_cards), 3) - 1:
                    draw.ellipse([_px(1.90), _px(cy + 1.18), _px(2.14), _px(cy + 1.40)], fill=hex_to_rgb(accents[(idx + 1) % 4]))
            if show_l3:
                _draw_text_box(draw, 0.68, cy + 0.03, 2.78, 0.32, lc.get("heading", ""), size_pt=14.5, bold=True, color_hex=ac_c, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.68, cy + 0.38, 2.78, 0.74, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)
                if idx < min(len(l_cards), 3) - 1:
                    _draw_text_box(draw, 1.90, cy + 1.17, 0.24, 0.24, "+", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

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
            ry = 1.90 + idx * 1.40
            rc_col = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, 9.83, ry, 2.97, 1.06, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(9.85), _px(ry + 0.02), _px(12.78), _px(ry + 0.08)], fill=hex_to_rgb(rc_col))
                if idx < 2:
                    _draw_down_arrow(draw, 11.31, ry + 1.10, 0.24, 0.24, accents[(idx + 1) % 4])
            if show_l3:
                _draw_text_box(draw, 9.93, ry + 0.12, 2.77, 0.34, rc.get("title", ""), size_pt=14.5, bold=True, color_hex=rc_col, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.93, ry + 0.46, 2.77, 0.54, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, align="center", line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.data_dashboard_table:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.50, 7.58, 4.64, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 2.10, 1.36, 4.18, 0.30, "定量指标可视化看板与结构对照", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)

        kpis = spec.kpis[:3] or [{"value": "34–50%", "label": "大鼠口服生物利用度", "color_token": "s1"}, {"value": "35×", "label": "较先导暴露提升", "color_token": "s2"}, {"value": "5.1 h", "label": "大鼠半衰期 t1/2", "color_token": "s3"}]
        kpi_cycle = [c1, c2, alert_c]
        for idx, kp in enumerate(kpis[:3]):
            val = kp.value if hasattr(kp, "value") else kp["value"]
            lbl = kp.label if hasattr(kp, "label") else kp["label"]
            ctok = kp.color_token if hasattr(kp, "color_token") else kp.get("color_token", "s1")
            k_col = alert_c if ctok == "alert" else (accents[idx % 4] if ctok in ("s1", "s2", "s3") else pal.token(ctok))
            if idx == 2 and ctok == "s1":
                k_col = kpi_cycle[2]
            tx = 0.54 + idx * 2.48
            if show_l2:
                _draw_elevated_box(canvas, tx, 1.84, 2.34, 0.88, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(tx + 0.02), _px(1.84), _px(tx + 2.32), _px(1.91)], fill=hex_to_rgb(k_col))
            if show_l3:
                _draw_text_box(draw, tx + 0.12, 1.93, 2.10, 0.40, val, size_pt=21.0, bold=True, color_hex=k_col, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, tx + 0.12, 2.34, 2.10, 0.34, lbl, size_pt=14.0, color_hex=pal.muted, align="center", ea_font=ea_f, latin_font=lat_f)

        bars = extract_visual_metric_bars(spec, max_bars=4)
        if bars:
            dash_fig_box = FigureBoxIn(left=0.54, top=2.86, width=4.02, height=3.16)
            if show_l2:
                _draw_rounded_box(draw, 0.54, 2.86, 4.02, 3.16, fill_hex="#FFFFFF", border_hex="#E2E8F0", border_px=1, radius=0.06)
                _draw_elevated_box(canvas, 4.68, 2.86, 3.16, 3.16, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(4.70), _px(2.88), _px(7.82), _px(3.22)], fill=hex_to_rgb(tints[1]))
            if show_l3:
                _draw_text_box(draw, 4.78, 2.88, 2.96, 0.34, "关键指标柱状对比", size_pt=14.0, bold=True, color_hex=c2, ea_font=ea_f, latin_font=lat_f)
            for b_i, (b_lbl, b_val, b_frac) in enumerate(bars):
                by = 3.30 + b_i * 0.66
                col_b = accents[b_i % 4]
                if show_l3:
                    _draw_text_box(draw, 4.78, by, 1.78, 0.28, b_lbl, size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                    _draw_text_box(draw, 6.58, by, 1.16, 0.28, b_val, size_pt=14.0, bold=True, color_hex=col_b, align="right", ea_font=ea_f, latin_font=lat_f)
                if show_l2:
                    _draw_rounded_box(draw, 4.78, by + 0.32, 2.96, 0.16, fill_hex="#EDF2F7", border_hex=None, radius=0.45)
                    _draw_rounded_box(draw, 4.78, by + 0.32, max(0.32, 2.96 * b_frac), 0.16, fill_hex=col_b, border_hex=None, radius=0.45)
        else:
            dash_fig_box = fig_box

        _composite_figure_assets(canvas, draw, spec, pal, dash_fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)

        td = spec.table_data
        table_bottom = 3.92
        if td and td.headers:
            rows_count = len(td.rows) + 1
            cols_count = len(td.headers)
            row_h = min(0.46, 2.38 / max(rows_count, 2))
            col_w = 4.81 / max(cols_count, 1)
            if show_l2:
                draw.rectangle([_px(8.12), _px(1.50), _px(12.93), _px(1.50 + row_h)], fill=hex_to_rgb(c1))
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
                        _draw_text_box(draw, 8.12 + c_i * col_w + 0.06, ry, col_w - 0.12, row_h, val, size_pt=14.0, bold=is_last, color_hex=c2 if is_last else pal.ink, align="center" if c_i > 0 else "left", ea_font=ea_f, latin_font=lat_f)
            table_bottom = 1.50 + row_h * rows_count

        scards = spec.strategy_cards or [
            {"badge": "策略", "badge_color": "s2" if idx == 0 else "s3", "title": i.heading, "body": i.body}
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
        top_tint = tints[0]
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.48, 12.53, 0.96, fill_hex=top_tint, border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.48, 1.56, 1.28, 0.80, fill_hex=c1, border_hex=None, radius=0.10)
        if show_l3:
            _draw_text_box(draw, 0.48, 1.56, 1.28, 0.80, "核心目标", size_pt=14.5, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            lines = spec.pain_points[:3] or [f"{ins.heading}：{ins.body}" for ins in spec.insights[:3]]
            cols_n = max(1, min(3, len(lines)))
            col_w = 10.90 / cols_n
            for idx, ln in enumerate(lines[:cols_n]):
                lx = 1.88 + idx * col_w
                _draw_text_box(draw, lx + 0.06, 1.54, col_w - 0.12, 0.84, ln, size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
                if show_l2 and idx < cols_n - 1:
                    draw.line([_px(lx + col_w), _px(1.62), _px(lx + col_w), _px(2.30)], fill=hex_to_rgb("#CBD5E1"), width=2)

        boxes = [
            (0.40, 3.82, spec.left_cards[0].get("heading", "01 核心痛点") if spec.left_cards else "01 核心痛点", alert_c),
            (4.50, 4.30, "02 分子设计与机理", c1),
            (9.08, 3.85, spec.right_chain[0].get("title", "03 预期突破") if spec.right_chain else "03 预期突破", c2),
        ]
        for bx, bw, bt, tab_c in boxes:
            if show_l2:
                _draw_elevated_box(canvas, bx, 2.64, bw, 3.46, fill_hex="#FFFFFF", border_hex=blend_with_white(tab_c, 0.52), border_px=2, dashed=True, radius=0.05)
                draw = ImageDraw.Draw(canvas)
            _draw_chamfered_header_tab(canvas, draw, bx + 0.45, 2.52, bw - 0.90, 0.30, bt, fill_hex=tab_c, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l2:
            for ax, ac in ((4.24, alert_c), (8.82, c2)):
                _draw_chevron(draw, ax, 4.24, 0.22, 0.28, ac)
        for idx, ins in enumerate(spec.insights[:2]):
            cy = 3.04 + idx * 1.48
            lc_col = alert_c if idx == 0 else c2
            if show_l2:
                _draw_elevated_box(canvas, 0.56, cy, 3.50, 1.32, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.ellipse([_px(0.68), _px(cy + 0.12), _px(0.98), _px(cy + 0.42)], fill=hex_to_rgb(lc_col))
            if show_l3:
                _draw_text_box(draw, 0.68, cy + 0.12, 0.30, 0.30, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 1.06, cy + 0.10, 2.88, 0.34, ins.heading, size_pt=14.5, bold=True, color_hex=lc_col, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.68, cy + 0.48, 3.26, 0.76, ins.body, size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)
        r_items = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] or [{"title": spec.takeaway[:14], "body": spec.section_name}]
        for idx, rc in enumerate(r_items[:2]):
            cy = 3.04 + idx * 1.48
            rc_col = c1 if idx == 0 else c3
            if show_l2:
                _draw_elevated_box(canvas, 9.24, cy, 3.53, 1.32, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(9.26), _px(cy + 0.02), _px(12.75), _px(cy + 0.10)], fill=hex_to_rgb(rc_col))
            if show_l3:
                _draw_text_box(draw, 9.38, cy + 0.16, 3.25, 0.36, rc.get("title", ""), size_pt=15.0, bold=True, color_hex=rc_col, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.38, cy + 0.54, 3.25, 0.70, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, align="center", valign="top", ea_font=ea_f, latin_font=lat_f)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        if spec.figure_spec:
            eng = spec.figure_spec.assets[0].engine.value if spec.figure_spec.assets else ""
            tag_l = "3D 空间构象" if eng == "cylview_3d" else "2D 化学结构"
            tag_r = f"{spec.kpis[0].label}: {spec.kpis[0].value}"[:18] if spec.kpis else "核心药效骨架"
            if show_l2:
                _draw_rounded_box(draw, 4.64, 5.64, 1.88, 0.34, fill_hex=tints[0], border_hex=pal.s4, border_px=1, radius=0.28)
                _draw_rounded_box(draw, 6.62, 5.64, 2.04, 0.34, fill_hex=tints[1], border_hex=pal.s4, border_px=1, radius=0.28)
            if show_l3:
                _draw_text_box(draw, 4.66, 5.64, 1.84, 0.34, tag_l, size_pt=14.0, bold=True, color_hex=c1, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 6.64, 5.64, 2.00, 0.34, tag_r, size_pt=14.0, bold=True, color_hex=c2, align="center", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.pain_points_left_arrows:
        pts = spec.pain_points or [f"{ins.heading}：{ins.body}" for ins in spec.insights[:3]]
        n = min(3, max(2, len(pts)))
        row_h = min(1.42, (4.58 - 0.14 * (n - 1)) / n)
        pt_cols = [alert_c, c2, c3]
        for idx, pt in enumerate(pts[:n]):
            ry = 1.54 + idx * (row_h + 0.14)
            c_head, c_body = split_card_head_body(pt, f"关键痛点 0{idx + 1}")
            cy_arr = ry + 0.34 + (row_h - 0.34) * 0.5 - 0.16
            p_col = pt_cols[idx % len(pt_cols)]
            if show_l2:
                _draw_elevated_box(canvas, 0.40, ry, 5.06, row_h, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                _draw_rounded_box(draw, 0.40, ry, 5.06, 0.34, fill_hex=p_col, border_hex=None, radius=0.06)
                draw.ellipse([_px(4.98), _px(cy_arr), _px(5.32), _px(cy_arr + 0.34)], fill=hex_to_rgb(p_col))
            if show_l3:
                _draw_text_box(draw, 0.54, ry, 4.78, 0.34, c_head, size_pt=14.0, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.54, ry + 0.38, 4.34, row_h - 0.44, c_body, size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 4.98, cy_arr, 0.34, 0.34, "→", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 5.66, 1.54, 7.27, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 7.46, 1.42, 3.68, 0.30, "关键科学问题与微界面机制", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l2:
            _draw_rounded_box(draw, 5.82, 1.78, 6.94, 0.42, fill_hex=tints[0], border_hex=pal.s3, border_px=1, dashed=True, radius=0.10)
        if show_l3:
            _draw_text_box(draw, 5.92, 1.78, 6.74, 0.42, f"核心瓶颈：{spec.takeaway[:36]}", size_pt=14.0, bold=True, color_hex=c1, align="center", ea_font=ea_f, latin_font=lat_f)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        chips = spec.figure_chips or ["限域调控", "低能垒", "高选择性", "定量互证"]
        cw = 6.94 / max(len(chips[:4]), 1)
        for idx, ch in enumerate(chips[:4]):
            cx = 5.82 + idx * cw
            if show_l2:
                _draw_elevated_box(canvas, cx + 0.04, 5.18, cw - 0.08, 0.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.14)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(cx + 0.12), _px(5.26), _px(cx + 0.18), _px(5.48)], fill=hex_to_rgb(accents[idx % 4]))
            if show_l3:
                _draw_text_box(draw, cx + 0.18, 5.18, cw - 0.24, 0.38, ch, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l3:
            _draw_text_box(draw, 5.82, 5.64, 6.94, 0.40, spec.figure_bottom_note or spec.takeaway, size_pt=14.0, bold=True, color_hex=alert_c, align="center", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.fig_left_3step_chain:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.54, 7.76, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 2.28, 1.41, 4.00, 0.30, spec.section_name[:16] or "多尺度表征与实验验证", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        chain = spec.right_chain or [{"title": ins.heading, "body": ins.body} for ins in spec.insights[:3]]
        for idx, item in enumerate(chain[:3]):
            ry = 1.56 + idx * 1.56
            ac_c = accents[idx % 4]
            if show_l2:
                _draw_rounded_box(draw, 8.34, ry, 1.24, 1.24, fill_hex=ac_c, border_hex=None, radius=0.08)
                draw.ellipse([_px(8.78), _px(ry + 0.12), _px(9.14), _px(ry + 0.46)], fill=(255, 255, 255))
                _draw_elevated_box(canvas, 9.66, ry, 3.27, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(9.66), _px(ry + 0.10), _px(9.72), _px(ry + 1.14)], fill=hex_to_rgb(tints[idx % 4]))
                if idx < 2:
                    _draw_down_arrow(draw, 10.66, ry + 1.27, 0.32, 0.26, accents[(idx + 1) % 4])
            if show_l3:
                _draw_text_box(draw, 8.78, ry + 0.12, 0.36, 0.34, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=ac_c, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 8.38, ry + 0.50, 1.16, 0.68, item.get("title", f"阶段 {idx+1}"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.78, ry + 0.08, 3.04, 1.08, item.get("body", ""), size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.vs_center_wing:
        l_cards = spec.left_cards or [{"heading": ins.heading or "传统路径", "body": ins.body} for ins in spec.insights[:2]]
        r_cards = spec.right_chain or [{"title": k.label, "body": k.value} for k in spec.kpis[:2]] or [{"title": "核心优势", "body": spec.takeaway}]
        for idx, lc in enumerate(l_cards[:2]):
            cy = 1.58 + idx * 2.26
            lc_col = alert_c if idx == 0 else c2
            if show_l2:
                _draw_elevated_box(canvas, 0.40, cy, 3.12, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                _draw_rounded_box(draw, 0.40, cy, 3.12, 0.36, fill_hex=lc_col, border_hex=None, radius=0.06)
                _draw_right_arrow_shape(draw, 3.55, cy + 1.03, 0.18, 0.26, lc_col)
            if show_l3:
                _draw_text_box(draw, 0.48, cy, 2.96, 0.36, lc.get("heading", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.54, cy + 0.44, 2.84, 1.54, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 3.76, 1.54, 5.80, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 4.96, 1.40, 3.40, 0.30, "核心结构与机制对比", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_rounded_box(draw, 4.06, 5.62, 5.20, 0.38, fill_hex=tints[0], border_hex=pal.s4, border_px=1, radius=0.24)
        if show_l3:
            _draw_text_box(draw, 4.16, 5.62, 5.00, 0.38, "⇄  结构演进与定量性能双向印证", size_pt=14.0, bold=True, color_hex=c1, align="center", ea_font=ea_f, latin_font=lat_f)
        for idx, rc in enumerate(r_cards[:2]):
            cy = 1.58 + idx * 2.26
            rc_col = c1 if idx == 0 else c3
            if show_l2:
                _draw_elevated_box(canvas, 9.81, cy, 3.12, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                _draw_rounded_box(draw, 9.81, cy, 3.12, 0.36, fill_hex=rc_col, border_hex=None, radius=0.06)
                _draw_left_arrow_shape(draw, 9.59, cy + 1.03, 0.18, 0.26, rc_col)
            if show_l3:
                _draw_text_box(draw, 9.89, cy, 2.96, 0.36, rc.get("title", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.95, cy + 0.44, 2.84, 1.54, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.roadmap_layered_matrix:
        for ry, rh, tag, r_col in ((1.52, 1.30, "研究目标", accents[0]), (2.94, 1.82, "技术路线", accents[1]), (4.88, 1.24, "核心指标", accents[2])):
            if show_l2:
                _draw_rounded_box(draw, 0.40, ry, 0.82, rh, fill_hex=r_col, border_hex=None, radius=0.08)
                _draw_elevated_box(canvas, 1.30, ry, 7.58, rh, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, 0.42, ry, 0.78, rh, tag, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

        row1_items = spec.insights[:3] or [InsightItem(index="01", heading="目标聚焦", body=spec.takeaway[:24])]
        for idx, ins in enumerate(row1_items):
            cx = 1.42 + idx * 2.48
            ac_c = accents[idx % 4]
            if show_l2:
                _draw_rounded_box(draw, cx, 1.62, 2.26, 1.10, fill_hex=tints[idx % 4], border_hex="#D6E0EC", border_px=1, radius=0.06)
                _draw_rounded_box(draw, cx + 0.08, 1.68, 2.10, 0.30, fill_hex=ac_c, border_hex=None, radius=0.10)
                if idx < len(row1_items) - 1:
                    _draw_right_arrow_shape(draw, cx + 2.29, 2.17, 0.16, 0.22, ac_c)
            if show_l3:
                _draw_text_box(draw, cx + 0.12, 1.68, 2.02, 0.30, f"{ins.index} {ins.heading[:8]}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.08, 2.02, 2.10, 0.64, ins.body[:26], size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.05, ea_font=ea_f, latin_font=lat_f)

        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        wf_steps = [
            ("设计合成与骨架修饰", spec.insights[0].body[:22] if spec.insights else "构建代表分子与路线"),
            ("表征验证与性能评估", spec.insights[-1].body[:22] if spec.insights else "活性、选择性与构象"),
        ]
        for idx, (wt, wb) in enumerate(wf_steps):
            wy = 3.04 + idx * 0.94
            wf_c = accents[idx % 4]
            if show_l2:
                _draw_rounded_box(draw, 5.22, wy, 3.52, 0.68, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=1, radius=0.08)
                draw.rectangle([_px(5.28), _px(wy + 0.08), _px(5.34), _px(wy + 0.60)], fill=hex_to_rgb(wf_c))
                if idx == 0:
                    _draw_down_arrow(draw, 6.99, wy + 0.71, 0.22, 0.20, accents[1])
            if show_l3:
                _draw_text_box(draw, 5.42, wy + 0.04, 3.24, 0.30, wt, size_pt=14.0, bold=True, color_hex=wf_c, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 5.42, wy + 0.34, 3.24, 0.30, wb, size_pt=14.0, color_hex=pal.muted, ea_font=ea_f, latin_font=lat_f)

        row3_kpis = (
            [(k.value, k.label, alert_c if k.color_token == "alert" else accents[i % 4]) for i, k in enumerate(spec.kpis[:3])]
            if spec.kpis
            else [(ins.highlight or ins.heading[:8], ins.heading[:12], accents[i % 4]) for i, ins in enumerate(spec.insights[:3])]
        )
        if not row3_kpis:
            row3_kpis = [("目标达成", "阶段验证", accents[0])]
        r3_w = 7.34 / max(len(row3_kpis), 1) - 0.10
        for idx, (mv, ml, mc) in enumerate(row3_kpis[:3]):
            mx = 1.42 + idx * (r3_w + 0.14)
            if show_l2:
                _draw_rounded_box(draw, mx, 4.98, r3_w, 1.04, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw.rectangle([_px(mx + 0.02), _px(5.00), _px(mx + r3_w - 0.02), _px(5.06)], fill=hex_to_rgb(mc))
            if show_l3:
                _draw_text_box(draw, mx + 0.08, 5.10, r3_w - 0.16, 0.44, str(mv)[:12], size_pt=18.0, bold=True, color_hex=mc, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, mx + 0.08, 5.56, r3_w - 0.16, 0.36, str(ml)[:14], size_pt=14.0, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)

        if show_l2:
            _draw_elevated_box(canvas, 9.06, 1.54, 3.87, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 9.72, 1.39, 2.55, 0.30, "闭环实施与转化路径", fill_hex=c2, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        nodes = spec.right_chain or [{"title": ins.heading} for ins in spec.insights[:3]] + [{"title": "定量成果产出"}]
        for idx, nd in enumerate(nodes[:4]):
            ny = 1.94 + idx * 1.04
            is_last = idx == min(len(nodes[:4]), 4) - 1
            nd_c = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, 9.26, ny, 3.47, 0.72, fill_hex=c1 if is_last else "#FFFFFF", border_hex=c1 if is_last else "#D6E0EC", border_px=2 if is_last else 1, radius=0.45)
                draw = ImageDraw.Draw(canvas)
                draw.ellipse([_px(9.38), _px(ny + 0.17), _px(9.76), _px(ny + 0.55)], fill=(255, 255, 255) if is_last else hex_to_rgb(nd_c))
                if not is_last:
                    _draw_down_arrow(draw, 11.00, ny + 0.75, 0.24, 0.24, nd_c)
            if show_l3:
                _draw_text_box(draw, 9.38, ny + 0.17, 0.38, 0.38, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=c1 if is_last else "#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.84, ny, 2.76, 0.72, nd.get("title", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF" if is_last else pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.timeline_chevron_flow:
        steps = (spec.chevron_steps[:4] if spec.chevron_steps else [f"{ins.index} {ins.heading[:10]}" for ins in spec.insights[:4]]) or ["01 问题提出", "02 分子设计", "03 机理验证", "04 定量突破"]
        while len(steps) < 4:
            steps.append(f"0{len(steps) + 1} 阶段推进")
        for idx, st in enumerate(steps[:4]):
            sx = 0.40 + idx * 3.17
            if show_l2:
                _draw_chevron(draw, sx, 1.46, 3.02, 0.56, accents[idx % 4])
            if show_l3:
                _draw_text_box(draw, sx + 0.22, 1.48, 2.58, 0.52, st[:14], size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 2.24, 6.82, 3.88, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 1.91, 2.12, 3.80, 0.30, "核心结构与阶段流程", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        right_items = spec.insights[:3] or [InsightItem(index="01", heading="阶段目标", body=spec.takeaway)]
        for idx, ins in enumerate(right_items[:3]):
            cy = 2.24 + idx * 1.34
            badge_c = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, 7.42, cy, 5.51, 1.20, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(7.48), _px(cy + 0.12), _px(7.54), _px(cy + 1.08)], fill=hex_to_rgb(badge_c))
                draw.ellipse([_px(7.66), _px(cy + 0.12), _px(8.00), _px(cy + 0.46)], fill=hex_to_rgb(badge_c))
            if show_l3:
                _draw_text_box(draw, 7.66, cy + 0.12, 0.34, 0.34, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 8.10, cy + 0.10, 4.68, 0.36, ins.heading, size_pt=14.5, bold=True, color_hex=badge_c, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 7.66, cy + 0.50, 5.12, 0.62, ins.body, size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.quadrant_2x2_matrix:
        cards = spec.left_cards[:4] if len(spec.left_cards) >= 4 else [{"heading": ins.heading, "body": ins.body} for ins in spec.insights[:4]]
        defaults = [
            {"heading": "科学假说与立题", "body": spec.takeaway[:36] or "聚焦关键科学痛点与分子切入点。"},
            {"heading": "先导结构优化", "body": "精准调控药效团取代基与理化性质平衡。"},
            {"heading": "作用机制与互证", "body": "结合动力学与结构表征验证结合模式。"},
            {"heading": "定量性能评估", "body": "系统评测活性、选择性与成药性窗口。"},
        ]
        while len(cards) < 4:
            cards.append(defaults[len(cards)])
        for idx, cd in enumerate(cards[:4]):
            col, row = idx % 2, idx // 2
            cx, cy = 0.40 + col * 3.96, 1.48 + row * 2.42
            hdr_c = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, cx, cy, 3.78, 2.22, fill_hex="#FFFFFF", border_hex=borders[idx % 4], border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                _draw_rounded_box(draw, cx, cy, 3.78, 0.40, fill_hex=hdr_c, border_hex=None, radius=0.06)
                _draw_rounded_box(draw, cx + 0.10, cy + 0.06, 0.42, 0.28, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
            if show_l3:
                _draw_text_box(draw, cx + 0.10, cy + 0.06, 0.42, 0.28, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=hdr_c, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.60, cy + 0.02, 3.08, 0.36, cd.get("heading", ""), size_pt=14.5, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.14, cy + 0.48, 3.50, 1.64, cd.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.12, ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 8.34, 1.48, 4.59, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 9.14, 1.35, 3.00, 0.30, "代表分子与定量指标", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        kpis = spec.kpis[:2] or [
            {"value": spec.insights[0].highlight or "关键聚焦", "label": spec.insights[0].heading[:10] if spec.insights else "核心指标", "color_token": "s1"},
            {"value": spec.insights[-1].highlight or "定量验证", "label": spec.insights[-1].heading[:10] if spec.insights else "研究优势", "color_token": "s2"},
        ]
        for idx, kp in enumerate(kpis[:2]):
            val = kp.value if hasattr(kp, "value") else kp["value"]
            lbl = kp.label if hasattr(kp, "label") else kp["label"]
            ctok = kp.color_token if hasattr(kp, "color_token") else kp.get("color_token", "s1")
            k_col = alert_c if ctok == "alert" else accents[idx % 4]
            kx = 8.48 + idx * 2.23
            if show_l2:
                _draw_rounded_box(draw, kx, 4.92, 2.08, 1.08, fill_hex=tints[idx % 4], border_hex="#D6E0EC", border_px=1, radius=0.08)
                draw.rectangle([_px(kx + 0.04), _px(4.94), _px(kx + 2.04), _px(4.99)], fill=hex_to_rgb(k_col))
            if show_l3:
                _draw_text_box(draw, kx + 0.08, 5.02, 1.92, 0.44, str(val)[:14], size_pt=17.0, bold=True, color_hex=k_col, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, kx + 0.08, 5.48, 1.92, 0.44, str(lbl)[:14], size_pt=14.0, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.hub_spoke_radial:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.48, 4.88, 4.64, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            draw.ellipse([_px(0.76), _px(1.72), _px(4.92), _px(5.88)], fill=hex_to_rgb(tints[0]), outline=hex_to_rgb(pal.s4), width=2)
            draw.ellipse([_px(1.06), _px(2.02), _px(4.62), _px(5.58)], fill=(255, 255, 255), outline=hex_to_rgb(c2), width=3)
            draw.ellipse([_px(1.35), _px(2.31), _px(4.33), _px(5.29)], fill=(255, 255, 255), outline=hex_to_rgb(c1), width=2)
        _draw_chamfered_header_tab(canvas, draw, 1.54, 1.35, 2.60, 0.30, "核心体系构筑", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        spoke_items = spec.insights[:3] or [InsightItem(index="01", heading="体系协同", body=spec.takeaway)]
        for idx, ins in enumerate(spoke_items[:3]):
            cy = 1.54 + idx * 1.56
            mid_y = cy + 0.69
            hdr_c = accents[idx % 4]
            if show_l2:
                _draw_dashed_line(draw, _px(4.92), _px(mid_y), _px(5.52), _px(mid_y), hex_to_rgb(hdr_c), width=2)
                draw.ellipse([_px(4.84), _px(mid_y - 0.08), _px(5.00), _px(mid_y + 0.08)], fill=hex_to_rgb(hdr_c), outline=(255, 255, 255), width=2)
                _draw_elevated_box(canvas, 5.52, cy, 7.41, 1.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                _draw_rounded_box(draw, 5.52, cy, 7.41, 0.38, fill_hex=hdr_c, border_hex=None, radius=0.06)
                _draw_rounded_box(draw, 5.62, cy + 0.05, 0.42, 0.28, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
            if show_l3:
                _draw_text_box(draw, 5.62, cy + 0.05, 0.42, 0.28, ins.index, size_pt=14.0, bold=True, color_hex=hdr_c, align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 6.14, cy + 0.02, 6.66, 0.34, ins.heading, size_pt=14.5, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 5.66, cy + 0.44, 7.12, 0.86, ins.body, size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.10, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.dual_compare_cards:
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 1.46, 12.53, 0.56, fill_hex=tints[0], border_hex="#D6E0EC", border_px=1, radius=0.08)
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([_px(0.48), _px(1.54), _px(0.56), _px(1.94)], fill=hex_to_rgb(c1))
        if show_l3:
            _draw_text_box(draw, 0.66, 1.48, 12.14, 0.52, spec.takeaway or spec.title, size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

        if show_l2:
            _draw_elevated_box(canvas, 0.40, 2.18, 5.82, 3.94, fill_hex="#FFFFFF", border_hex=roles["alert_border"], border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.40, 2.18, 5.82, 0.42, fill_hex=alert_c, border_hex=None, radius=0.06)
        if show_l3:
            _draw_text_box(draw, 0.52, 2.20, 5.58, 0.38, "现有方案与研究瓶颈", size_pt=14.5, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

        l_cards = spec.left_cards or [{"heading": i.heading, "body": i.body} for i in spec.insights[:3]]
        for idx, lc in enumerate(l_cards[:3]):
            sy = 2.72 + idx * 1.10
            if show_l2:
                _draw_rounded_box(draw, 0.56, sy, 5.50, 0.98, fill_hex=roles["alert_tint"], border_hex="#E2E8F0", border_px=1, radius=0.06)
                draw.ellipse([_px(0.68), _px(sy + 0.12), _px(0.98), _px(sy + 0.42)], fill=hex_to_rgb(alert_c))
            if show_l3:
                _draw_text_box(draw, 0.68, sy + 0.12, 0.30, 0.30, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 1.06, sy + 0.10, 4.86, 0.34, lc.get("heading", ""), size_pt=14.5, bold=True, color_hex=alert_c, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 0.68, sy + 0.46, 5.24, 0.46, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.05, ea_font=ea_f, latin_font=lat_f)

        if show_l2:
            draw.line([_px(6.22), _px(4.16), _px(6.35), _px(4.16)], fill=hex_to_rgb(alert_c), width=3)
            draw.line([_px(6.98), _px(4.16), _px(7.11), _px(4.16)], fill=hex_to_rgb(c1), width=3)
            draw.ellipse([_px(6.345), _px(3.84), _px(6.985), _px(4.48)], fill=hex_to_rgb(c2), outline=(255, 255, 255), width=3)
            _draw_elevated_box(canvas, 7.11, 2.18, 5.82, 3.94, fill_hex="#FFFFFF", border_hex=borders[0], border_px=2, radius=0.06)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 7.11, 2.18, 5.82, 0.42, fill_hex=c1, border_hex=None, radius=0.06)
            _draw_rounded_box(draw, 7.27, 2.74, 5.50, 2.28, fill_hex="#FFFFFF", border_hex="#E2E8F0", border_px=1, radius=0.05)
        if show_l3:
            _draw_text_box(draw, 6.345, 3.84, 0.64, 0.64, "VS", size_pt=16.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 7.23, 2.20, 5.58, 0.38, "本研究突破与分子验证", size_pt=14.5, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        r_cards = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] or [{"title": spec.insights[-1].highlight or "关键突破", "body": spec.insights[-1].heading if spec.insights else "选择性提升"}]
        for idx, rc in enumerate(r_cards[:2]):
            rx = 7.27 + idx * 2.84
            rc_col = c2 if idx == 0 else c3
            if show_l2:
                _draw_rounded_box(draw, rx, 5.12, 2.66, 0.88, fill_hex=tints[idx + 1], border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw.rectangle([_px(rx + 0.06), _px(5.20), _px(rx + 0.12), _px(5.92)], fill=hex_to_rgb(rc_col))
            if show_l3:
                _draw_text_box(draw, rx + 0.18, 5.16, 2.38, 0.38, str(rc.get("title", ""))[:14], size_pt=15.5, bold=True, color_hex=rc_col, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, rx + 0.18, 5.54, 2.38, 0.38, str(rc.get("body", ""))[:18], size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

    elif spec.layout_id == LayoutId.tri_column_showcase:
        top_cards = spec.insights[:3] or [InsightItem(index="01", heading="核心创新", body=spec.takeaway)]
        defaults = [
            InsightItem(index="01", heading="理性设计与构筑", body="面向关键靶点口袋精确构建先导骨架。"),
            InsightItem(index="02", heading="表征与机制阐明", body="多维光谱与构象分析互证作用机制。"),
            InsightItem(index="03", heading="定量性能突破", body="显著提升活性、选择性与成药性窗口。"),
        ]
        while len(top_cards) < 3:
            top_cards.append(defaults[len(top_cards)])
        for idx, ins in enumerate(top_cards[:3]):
            cx = 0.40 + idx * 4.285
            accent = accents[idx % 4]
            if show_l2:
                _draw_elevated_box(canvas, cx, 1.48, 3.96, 1.62, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([_px(cx + 0.02), _px(1.50), _px(cx + 3.94), _px(1.57)], fill=hex_to_rgb(accent))
                draw.ellipse([_px(cx + 0.14), _px(1.64), _px(cx + 0.46), _px(1.96)], fill=hex_to_rgb(accent))
                if idx < 2:
                    _draw_chevron(draw, cx + 4.02, 2.15, 0.21, 0.28, accents[(idx + 1) % 4])
            if show_l3:
                _draw_text_box(draw, cx + 0.14, 1.64, 0.32, 0.32, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.54, 1.62, 3.28, 0.36, ins.heading, size_pt=14.5, bold=True, color_hex=accent, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx + 0.14, 2.04, 3.68, 0.98, ins.body, size_pt=14.0, color_hex=pal.ink, valign="top", line_spacing=1.10, ea_font=ea_f, latin_font=lat_f)
        if show_l2:
            _draw_elevated_box(canvas, 0.40, 3.34, 8.22, 2.78, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, dashed=True, radius=0.05)
            _draw_elevated_box(canvas, 8.82, 3.34, 4.11, 2.78, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_px=1, radius=0.06)
            draw = ImageDraw.Draw(canvas)
        _draw_chamfered_header_tab(canvas, draw, 2.71, 3.21, 3.60, 0.30, "分子结构与机制示意", fill_hex=c1, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        _composite_figure_assets(canvas, draw, spec, pal, fig_box, show_l1, show_l2, show_l3, ea_font=ea_f, latin_font=lat_f)
        _draw_chamfered_header_tab(canvas, draw, 9.58, 3.21, 2.60, 0.30, "核心结论与指标", fill_hex=c2, ea_font=ea_f, latin_font=lat_f, show_l2=show_l2, show_l3=show_l3)
        right_rows = [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] if spec.kpis else [{"title": ins.highlight or ins.heading[:10], "body": ins.heading[:14]} for ins in spec.insights[:2]]
        for idx, rr in enumerate(right_rows[:2]):
            ky = 3.64 + idx * 1.24
            col = accents[idx % 4]
            if show_l2:
                _draw_rounded_box(draw, 8.98, ky, 3.79, 1.10, fill_hex=tints[idx % 4], border_hex="#D6E0EC", border_px=1, radius=0.06)
                draw.rectangle([_px(9.04), _px(ky + 0.12), _px(9.10), _px(ky + 0.98)], fill=hex_to_rgb(col))
            if show_l3:
                _draw_text_box(draw, 9.18, ky + 0.10, 3.48, 0.42, str(rr.get("title", ""))[:16], size_pt=16.5, bold=True, color_hex=col, ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, 9.18, ky + 0.54, 3.48, 0.48, str(rr.get("body", ""))[:20], size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

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
    elif mode == "solid_bar":
        if show_l2:
            _draw_elevated_box(canvas, 0.40, y, 12.53, h, fill_hex=pal.s1, border_hex=None, border_px=0, radius=0.18)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.48, y + 0.07, 1.38, h - 0.14, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
        if show_l3:
            _draw_text_box(draw, 0.48, y + 0.07, 1.38, h - 0.14, banner.get("badge", "突破"), size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 2.02, y, 10.76, h, banner.get("text", spec.takeaway), size_pt=14.0, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
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
