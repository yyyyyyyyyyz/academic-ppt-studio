"""1920x1080 High-DPI Preview Renderer for the 5 Theme-Adaptive Academic Cover Templates."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from PIL import Image, ImageDraw

from ..builder.v5_covers import _PART_WORDS, _SCENARIO_LABELS, _closing_fields, _cover_meta_fields, _parse_part_number
from ..figure_factory.palettes import ScientificPalette, blend_with_white, darken_hex, get_palette, hex_to_rgb
from ..schemas.deck_spec import CoverTemplateId, DeckSpec, DesignStyle, SlideSpec
from .v5_renderer import (
    _draw_dashed_line,
    _draw_elevated_box,
    _draw_hexagon_outline,
    _draw_rounded_box,
    _draw_text_box,
    _px,
)


def _draw_crest(
    draw: ImageDraw.ImageDraw,
    cx_in: float,
    cy_in: float,
    size_in: float,
    stroke_hex: str,
    ea_f: str,
    lat_f: str,
    monogram: str = "Rx",
    show_l2: bool = True,
    show_l3: bool = True,
) -> None:
    r = size_in * 0.5
    col = hex_to_rgb(stroke_hex)
    if show_l2:
        draw.ellipse([_px(cx_in - r), _px(cy_in - r), _px(cx_in + r), _px(cy_in + r)], outline=col, width=3)
        ir = size_in * 0.36
        hx0, hy0, hx1, hy1 = _px(cx_in - ir), _px(cy_in - ir), _px(cx_in + ir), _px(cy_in + ir)
        hdx = int((hx1 - hx0) * 0.25)
        hym = (hy0 + hy1) // 2
        draw.line(
            [(hx0 + hdx, hy0), (hx1 - hdx, hy0), (hx1, hym), (hx1 - hdx, hy1), (hx0 + hdx, hy1), (hx0, hym), (hx0 + hdx, hy0)],
            fill=col,
            width=2,
        )
    if show_l3:
        _draw_text_box(
            draw,
            cx_in - r,
            cy_in - r,
            size_in,
            size_in,
            monogram,
            size_pt=max(9.5, size_in * 20.0),
            bold=True,
            color_hex=stroke_hex,
            align="center",
            ea_font=ea_f,
            latin_font=lat_f,
        )


def _draw_alpha_ring(canvas: Image.Image, cx_in: float, cy_in: float, diam_in: float, alpha_pct: int) -> None:
    r = diam_in * 0.5
    lx = max(0.05, min(13.28 - diam_in, cx_in - r))
    ty = max(0.05, min(7.45 - diam_in, cy_in - r))
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    alpha_val = max(0, min(255, int(round(255 * (alpha_pct / 100.0)))))
    od.ellipse([_px(lx), _px(ty), _px(lx + diam_in), _px(ty + diam_in)], outline=(255, 255, 255, alpha_val), width=3)
    canvas.alpha_composite(ov)


def _draw_filled_hex(draw: ImageDraw.ImageDraw, l_in: float, t_in: float, w_in: float, h_in: float, fill_hex: str) -> None:
    x0, y0, x1, y1 = _px(l_in), _px(t_in), _px(l_in + w_in), _px(t_in + h_in)
    dx = int(round((x1 - x0) * 0.25))
    ym = (y0 + y1) // 2
    draw.polygon([(x0 + dx, y0), (x1 - dx, y0), (x1, ym), (x1 - dx, y1), (x0 + dx, y1), (x0, ym)], fill=hex_to_rgb(fill_hex))


def render_v5_cover_preview(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Optional[Path]:
    """Render any of the 5 theme-adaptive cover templates at 1920x1080 matching v5_covers.py 1-to-1."""
    tpl = deck.meta.cover_template
    if tpl is None:
        if deck.meta.design_style == DesignStyle.zero_fill_frameless:
            return None
        tpl = CoverTemplateId.hero_band_bottom_bar

    pal: ScientificPalette = get_palette(deck.meta.palette_id)
    fonts = deck.locked_standards.fonts or {}
    ea_f = fonts.get("ea", "微软雅黑")
    lat_f = fonts.get("latin", "Arial")
    show_l2, show_l3 = "L2" in layers, "L3" in layers

    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)
    scen_txt = _SCENARIO_LABELS.get(deck.meta.scenario.value, "学术答辩")

    canvas = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    if tpl == CoverTemplateId.hero_band_bottom_bar:
        tint_strip = blend_with_white(pal.s3, 0.52)
        if show_l2:
            draw.rectangle([0, 0, 1920, _px(5.64)], fill=hex_to_rgb(pal.s1))
            draw.rectangle([0, _px(5.64), 1920, _px(5.78)], fill=hex_to_rgb(tint_strip))
            _draw_hexagon_outline(canvas, 0.42, 0.38, 1.95, 1.72, alpha=34)
            _draw_hexagon_outline(canvas, 1.75, 1.24, 1.26, 1.12, alpha=34)
            _draw_hexagon_outline(canvas, 10.65, 3.22, 2.24, 1.98, alpha=34)
            _draw_hexagon_outline(canvas, 9.75, 0.42, 1.48, 1.32, alpha=34)
            draw = ImageDraw.Draw(canvas)
            _draw_dashed_line(draw, _px(2.20), _px(3.60), _px(11.13), _px(3.60), hex_to_rgb(blend_with_white(pal.s4, 0.40)), width=2)
        _draw_crest(draw, 4.72, 1.32, 0.64, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.18, 1.04, 4.40, 0.56, affiliation, size_pt=20.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.90, 2.02, 11.53, 1.36, title, size_pt=34.0, bold=True, color_hex="#FFFFFF", align="center", line_spacing=1.18, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.40, 3.84, 10.53, 0.88, subtitle, size_pt=18.0, color_hex=blend_with_white(pal.s6, 0.35), align="center", valign="top", line_spacing=1.30, ea_font=ea_f, latin_font=lat_f)

        items = [
            ("01", f"汇报人：{author}"),
            ("02", f"导师：{advisor}" if advisor else f"方向：{scen_txt}"),
            ("03", f"日期：{date_str}"),
        ]
        for (sym, lbl), cx in zip(items, (2.55, 6.66, 10.78)):
            bx, by, rad = cx - 1.34, 6.64, 0.27
            if show_l2:
                draw.ellipse([_px(bx - rad - 0.05), _px(by - rad - 0.05), _px(bx + rad + 0.05), _px(by + rad + 0.05)], outline=hex_to_rgb(blend_with_white(pal.s4, 0.25)), width=2)
                draw.ellipse([_px(bx - rad), _px(by - rad), _px(bx + rad), _px(by + rad)], fill=hex_to_rgb(pal.s1))
            if show_l3:
                _draw_text_box(draw, bx - rad, by - rad, 2 * rad, 2 * rad, sym, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx - 0.94, 6.36, 2.66, 0.56, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align="left", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.top_bottom_bands_framed:
        if show_l2:
            draw.rectangle([0, 0, 1920, _px(1.32)], fill=hex_to_rgb(pal.s1))
            draw.rectangle([0, _px(1.32), 1920, _px(1.38)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.35)))
            draw.rectangle([0, _px(6.12), 1920, _px(6.18)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.35)))
            draw.rectangle([0, _px(6.18), 1920, 1080], fill=hex_to_rgb(pal.s1))
            _draw_filled_hex(draw, 4.78, 1.76, 3.77, 3.38, blend_with_white(pal.s4, 0.80))
            _draw_filled_hex(draw, 5.32, 2.24, 2.69, 2.42, "#FFFFFF")
            draw.line([_px(2.65), _px(3.44), _px(10.68), _px(3.44)], fill=hex_to_rgb(pal.s2), width=3)
        _draw_crest(draw, 4.55, 0.66, 0.58, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.00, 0.38, 4.80, 0.56, affiliation, size_pt=19.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.90, 2.02, 11.53, 1.32, title, size_pt=36.0, bold=True, color_hex=pal.s1, align="center", line_spacing=1.18, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.60, 3.60, 10.13, 0.86, subtitle, size_pt=16.5, color_hex=pal.muted, align="center", valign="top", line_spacing=1.25, ea_font=ea_f, latin_font=lat_f)

        mid_lbl, mid_val = ("导 师", advisor) if advisor else ("场 景", scen_txt)
        pills = [
            ("汇报人", author, 1.05),
            (mid_lbl, mid_val, 4.92),
            ("专 业", "药物化学" if not advisor else "计算药化", 8.79),
        ]
        for pl_k, pl_v, px in pills:
            if show_l2:
                _draw_rounded_box(draw, px, 4.90, 3.48, 0.56, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, radius=0.45)
                _draw_rounded_box(draw, px + 0.04, 4.94, 1.24, 0.48, fill_hex=pal.s1, border_hex=None, radius=0.45)
            if show_l3:
                _draw_text_box(draw, px + 0.04, 4.94, 1.24, 0.48, pl_k, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, px + 1.38, 4.94, 2.02, 0.48, pl_v, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l3:
            _draw_text_box(draw, 3.66, 6.52, 6.00, 0.60, f"日期：{date_str}", size_pt=16.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.floating_rounded_hero_card:
        if show_l2:
            _draw_rounded_box(draw, 0.82, 5.56, 11.69, 0.44, fill_hex=blend_with_white(pal.s3, 0.56), border_hex=None, radius=0.35)
            _draw_elevated_box(canvas, 0.48, 0.42, 12.37, 5.44, fill_hex=pal.s1, border_hex=None, border_px=0, radius=0.05)
            _draw_alpha_ring(canvas, 10.65, 3.65, 3.20, alpha_pct=11)
            _draw_hexagon_outline(canvas, 8.95, 2.38, 1.85, 1.64, alpha=34)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.92, 0.86, 2.02, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45)
            draw.line([_px(0.92), _px(3.62), _px(10.60), _px(3.62)], fill=hex_to_rgb(blend_with_white(pal.s4, 0.45)), width=2)
        _draw_crest(draw, 9.20, 1.08, 0.56, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 0.92, 0.86, 2.02, 0.44, scen_txt, size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 9.58, 0.82, 2.95, 0.52, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.92, 1.64, 10.60, 1.64, title, size_pt=31.0, bold=True, color_hex="#FFFFFF", align="left", line_spacing=1.20, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.92, 3.84, 9.60, 1.24, subtitle, size_pt=18.0, color_hex=blend_with_white(pal.s6, 0.35), align="left", valign="top", line_spacing=1.35, ea_font=ea_f, latin_font=lat_f)

        bot_items = [("01", f"汇报人：{author}"), ("02", f"汇报时间：{date_str}")]
        if advisor:
            bot_items.append(("03", f"指导教师：{advisor}"))
        slot_xs = (3.40, 7.15) if len(bot_items) == 2 else (1.45, 5.25, 9.05)
        for (sym, lbl), bx in zip(bot_items, slot_xs):
            if show_l2:
                _draw_rounded_box(draw, bx, 6.46, 0.38, 0.38, fill_hex=pal.s1, border_hex=None, radius=0.18)
            if show_l3:
                _draw_text_box(draw, bx, 6.46, 0.38, 0.38, sym, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, bx + 0.48, 6.42, 2.95, 0.46, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align="left", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.left_aligned_rounded_panel:
        if show_l2:
            _draw_elevated_box(canvas, 0.28, 0.26, 12.77, 5.56, fill_hex=pal.s1, border_hex=None, border_px=0, radius=0.04)
            _draw_alpha_ring(canvas, 10.62, 3.04, 4.10, alpha_pct=9)
            _draw_alpha_ring(canvas, 10.62, 3.04, 2.75, alpha_pct=9)
            draw = ImageDraw.Draw(canvas)
            draw.line([_px(0.72), _px(4.38), _px(8.85), _px(4.38)], fill=hex_to_rgb(blend_with_white(pal.s4, 0.45)), width=2)
            _draw_rounded_box(draw, 0.72, 4.62, 2.30, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45)
        _draw_crest(draw, 0.86, 0.82, 0.46, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 1.22, 0.60, 5.60, 0.44, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 1.62, 7.80, 0.44, scen_txt, size_pt=19.0, bold=True, color_hex=blend_with_white(pal.s5, 0.35), align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 2.12, 8.90, 1.26, title, size_pt=29.0, bold=True, color_hex="#FFFFFF", align="left", line_spacing=1.18, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 3.44, 8.50, 0.72, subtitle, size_pt=15.0, color_hex=blend_with_white(pal.s6, 0.25), align="left", valign="top", line_spacing=1.28, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 4.62, 2.30, 0.44, f"汇报人：{author}", size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            inline_txt = f"指导教师：{advisor}    {date_str}" if advisor else f"汇报日期：{date_str}"
            _draw_text_box(draw, 3.18, 4.62, 5.80, 0.44, inline_txt, size_pt=14.0, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.62, 6.26, 3.40, 0.78, f"{affiliation}\n{deck.meta.palette_id.upper()} PALETTE EDITION", size_pt=12.0, bold=True, color_hex=pal.ink, align="left", line_spacing=1.22, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 4.20, 6.26, 4.40, 0.78, "计算药物化学与精准合成工作台\n100% Native Editable PPTX Specimen", size_pt=11.5, color_hex=pal.muted, align="left", line_spacing=1.22, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 8.80, 6.38, 3.90, 0.54, f"日期：{date_str}  ·  {author}", size_pt=11.5, color_hex=pal.muted, align="right", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.chevron_v_cut_banner:
        if show_l2:
            draw.polygon(
                [(_px(0.0), _px(5.02)), (_px(6.667), _px(5.84)), (_px(13.333), _px(5.02)), (_px(13.333), _px(5.18)), (_px(6.667), _px(6.00)), (_px(0.0), _px(5.18))],
                fill=hex_to_rgb(blend_with_white(pal.s3, 0.56)),
            )
            draw.polygon(
                [(_px(0.0), 0), (_px(13.333), 0), (_px(13.333), _px(5.02)), (_px(6.667), _px(5.84)), (_px(0.0), _px(5.02))],
                fill=hex_to_rgb(pal.s1),
            )
            draw.line([_px(2.30), _px(2.74), _px(11.03), _px(2.74)], fill=hex_to_rgb(blend_with_white(pal.s5, 0.45)), width=2)
        _draw_crest(draw, 0.92, 0.72, 0.58, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.20, 0.48, 3.60, 0.44, f"日期：{date_str}", size_pt=14.5, bold=True, color_hex="#FFFFFF", align="right", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.90, 1.32, 11.53, 1.34, title, size_pt=36.0, bold=True, color_hex="#FFFFFF", align="center", line_spacing=1.18, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.60, 2.90, 10.13, 0.88, subtitle, size_pt=16.5, color_hex=blend_with_white(pal.s6, 0.35), align="center", valign="top", line_spacing=1.28, ea_font=ea_f, latin_font=lat_f)

        pill_items = [
            f"汇报人：{author}",
            f"场景：{scen_txt}",
            f"指导教师：{advisor}" if advisor else "学科：药物化学",
        ]
        for ptxt, px in zip(pill_items, (1.35, 5.10, 8.85)):
            if show_l2:
                _draw_elevated_box(canvas, px, 4.10, 3.12, 0.50, fill_hex="#FFFFFF", border_hex=None, border_px=0, radius=0.45, shadow_alpha=18, blur_px=4)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, px + 0.08, 4.10, 2.96, 0.50, ptxt, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)

        _draw_crest(draw, 4.55, 6.62, 0.66, pal.s1, ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.02, 6.32, 4.80, 0.60, affiliation, size_pt=20.0, bold=True, color_hex=pal.s1, align="left", ea_font=ea_f, latin_font=lat_f)

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p


def render_v5_part_divider_preview(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Optional[Path]:
    """Render center hero-band Part Divider at 1920x1080 matching v5_covers.py 1-to-1."""
    if deck.meta.cover_template is None and deck.meta.design_style == DesignStyle.zero_fill_frameless:
        return None

    pal: ScientificPalette = get_palette(deck.meta.palette_id)
    fonts = deck.locked_standards.fonts or {}
    ea_f = fonts.get("ea", "微软雅黑")
    lat_f = fonts.get("latin", "Arial")
    show_l2, show_l3 = "L2" in layers, "L3" in layers

    p_num = _parse_part_number(spec)
    num_str = f"{p_num:02d}"
    part_pill_txt = _PART_WORDS.get(p_num, f"PART {num_str}")
    deep_emboss = darken_hex(pal.s1, 0.34)
    chip_fill = darken_hex(pal.s1, 0.24)
    chip_border = blend_with_white(pal.s3, 0.30)

    canvas = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    if show_l2:
        draw.rectangle([0, _px(1.44), 1920, _px(5.75)], fill=hex_to_rgb(pal.s1))
        draw.rectangle([0, _px(1.38), 1920, _px(1.44)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.42)))
        draw.rectangle([0, _px(5.75), 1920, _px(5.81)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.42)))
        _draw_text_box(draw, 5.36, 1.50, 2.61, 1.46, num_str, size_pt=72.0, bold=True, color_hex=deep_emboss, align="center", ea_font=ea_f, latin_font=lat_f)
        _draw_rounded_box(draw, 5.56, 2.40, 2.21, 0.38, fill_hex="#FFFFFF", border_hex=None, radius=0.45)
        draw.line([_px(4.20), _px(4.52), _px(9.13), _px(4.52)], fill=hex_to_rgb(chip_border), width=2)

    if show_l3:
        _draw_text_box(draw, 5.56, 2.40, 2.21, 0.38, part_pill_txt, size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
        _draw_text_box(draw, 1.20, 2.94, 10.93, 1.04, spec.title, size_pt=46.0, bold=True, color_hex="#FFFFFF", align="center", line_spacing=1.10, ea_font=ea_f, latin_font=lat_f)
        sub_txt = (spec.takeaway or "Research Design, Mechanism & Quantitative Milestones").strip()
        _draw_text_box(draw, 1.80, 4.04, 9.73, 0.36, sub_txt, size_pt=14.0, bold=True, color_hex=blend_with_white(pal.s5, 0.38), align="center", ea_font=ea_f, latin_font=lat_f)

    chips = (spec.figure_chips or ["科学问题与假说", "方法路径与表征", "关键进展与验证"])[:3]
    chip_w, gap = 2.24, 0.36
    start_x = 6.667 - (len(chips) * chip_w + max(0, len(chips) - 1) * gap) * 0.5
    for idx, ch_txt in enumerate(chips):
        cx = start_x + idx * (chip_w + gap)
        if show_l2:
            _draw_rounded_box(draw, cx, 4.76, chip_w, 0.38, fill_hex=chip_fill, border_hex=chip_border, border_px=2, radius=0.45)
        if show_l3:
            _draw_text_box(draw, cx + 0.06, 4.76, chip_w - 0.12, 0.38, ch_txt, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p


def render_v5_closing_preview(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Optional[Path]:
    """Render any of the 5 cover-matched Closing slides at 1920x1080 matching v5_covers.py 1-to-1."""
    tpl = deck.meta.cover_template
    if tpl is None:
        if deck.meta.design_style == DesignStyle.zero_fill_frameless:
            return None
        tpl = CoverTemplateId.hero_band_bottom_bar

    pal: ScientificPalette = get_palette(deck.meta.palette_id)
    fonts = deck.locked_standards.fonts or {}
    ea_f = fonts.get("ea", "微软雅黑")
    lat_f = fonts.get("latin", "Arial")
    show_l2, show_l3 = "L2" in layers, "L3" in layers

    c_title, c_sub, author, affiliation, advisor, date_str = _closing_fields(spec, deck)
    canvas = Image.new("RGBA", (1920, 1080), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    if tpl == CoverTemplateId.hero_band_bottom_bar:
        if show_l2:
            draw.rectangle([0, 0, 1920, _px(5.64)], fill=hex_to_rgb(pal.s1))
            draw.rectangle([0, _px(5.64), 1920, _px(5.78)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.52)))
            _draw_hexagon_outline(canvas, 0.42, 0.38, 1.95, 1.72, alpha=34)
            _draw_hexagon_outline(canvas, 10.65, 3.22, 2.24, 1.98, alpha=34)
            draw = ImageDraw.Draw(canvas)
            _draw_dashed_line(draw, _px(2.40), _px(3.54), _px(10.93), _px(3.54), hex_to_rgb(blend_with_white(pal.s4, 0.40)), width=2)
        _draw_crest(draw, 4.82, 1.32, 0.62, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.26, 1.04, 4.20, 0.56, "THANK YOU · Q & A", size_pt=18.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.00, 2.08, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.60, 3.78, 10.13, 0.80, f"{affiliation}  ·  {deck.meta.deck_title}", size_pt=16.0, color_hex=blend_with_white(pal.s6, 0.35), align="center", valign="top", ea_font=ea_f, latin_font=lat_f)

        items = [("01", f"汇报人：{author}"), ("02", f"导师：{advisor}" if advisor else f"单位：{affiliation[:14]}"), ("03", f"日期：{date_str}")]
        for (sym, lbl), cx in zip(items, (2.55, 6.66, 10.78)):
            bx, by, rad = cx - 1.34, 6.64, 0.27
            if show_l2:
                draw.ellipse([_px(bx - rad - 0.05), _px(by - rad - 0.05), _px(bx + rad + 0.05), _px(by + rad + 0.05)], outline=hex_to_rgb(blend_with_white(pal.s4, 0.25)), width=2)
                draw.ellipse([_px(bx - rad), _px(by - rad), _px(bx + rad), _px(by + rad)], fill=hex_to_rgb(pal.s1))
            if show_l3:
                _draw_text_box(draw, bx - rad, by - rad, 2 * rad, 2 * rad, sym, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, cx - 0.94, 6.36, 2.66, 0.56, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align="left", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.top_bottom_bands_framed:
        if show_l2:
            draw.rectangle([0, 0, 1920, _px(1.32)], fill=hex_to_rgb(pal.s1))
            draw.rectangle([0, _px(1.32), 1920, _px(1.38)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.35)))
            draw.rectangle([0, _px(6.12), 1920, _px(6.18)], fill=hex_to_rgb(blend_with_white(pal.s3, 0.35)))
            draw.rectangle([0, _px(6.18), 1920, 1080], fill=hex_to_rgb(pal.s1))
            _draw_filled_hex(draw, 4.78, 1.76, 3.77, 3.38, blend_with_white(pal.s4, 0.80))
            _draw_filled_hex(draw, 5.32, 2.24, 2.69, 2.42, "#FFFFFF")
            draw.line([_px(2.80), _px(3.40), _px(10.53), _px(3.40)], fill=hex_to_rgb(pal.s2), width=3)
        _draw_crest(draw, 4.55, 0.66, 0.58, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.00, 0.38, 4.80, 0.56, affiliation, size_pt=19.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.00, 2.04, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.60, 3.58, 10.13, 0.64, c_sub, size_pt=16.5, color_hex=pal.muted, align="center", ea_font=ea_f, latin_font=lat_f)
        for pk, pv, px in (("汇报人", author, 2.55), ("日 期", date_str, 7.30)):
            if show_l2:
                _draw_rounded_box(draw, px, 4.86, 3.48, 0.56, fill_hex="#FFFFFF", border_hex=pal.s3, border_px=2, radius=0.45)
                _draw_rounded_box(draw, px + 0.04, 4.90, 1.24, 0.48, fill_hex=pal.s1, border_hex=None, radius=0.45)
            if show_l3:
                _draw_text_box(draw, px + 0.04, 4.90, 1.24, 0.48, pk, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, px + 1.38, 4.90, 2.02, 0.48, pv, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)
        if show_l3:
            _draw_text_box(draw, 3.66, 6.52, 6.00, 0.60, f"欢迎各位专家交流指导 · {date_str}", size_pt=16.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.floating_rounded_hero_card:
        if show_l2:
            _draw_rounded_box(draw, 0.82, 5.56, 11.69, 0.44, fill_hex=blend_with_white(pal.s3, 0.56), border_hex=None, radius=0.35)
            _draw_elevated_box(canvas, 0.48, 0.42, 12.37, 5.44, fill_hex=pal.s1, border_hex=None, border_px=0, radius=0.05)
            _draw_alpha_ring(canvas, 10.65, 3.65, 3.20, alpha_pct=11)
            _draw_hexagon_outline(canvas, 8.95, 2.38, 1.85, 1.64, alpha=34)
            draw = ImageDraw.Draw(canvas)
            _draw_rounded_box(draw, 0.92, 0.86, 1.92, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45)
            draw.line([_px(0.92), _px(3.52), _px(10.40), _px(3.52)], fill=hex_to_rgb(blend_with_white(pal.s4, 0.45)), width=2)
        _draw_crest(draw, 9.20, 1.08, 0.56, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 0.92, 0.86, 1.92, 0.44, "Q & A · 致谢", size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 9.58, 0.82, 2.95, 0.52, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.92, 1.78, 10.40, 1.38, c_title, size_pt=38.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.92, 3.78, 9.80, 1.05, f"{c_sub}\n{deck.meta.deck_title}", size_pt=16.5, color_hex=blend_with_white(pal.s6, 0.35), align="left", valign="top", line_spacing=1.35, ea_font=ea_f, latin_font=lat_f)
        bot_items = [("01", f"汇报人：{author}"), ("02", f"汇报时间：{date_str}")]
        if advisor:
            bot_items.append(("03", f"指导教师：{advisor}"))
        slot_xs = (3.40, 7.15) if len(bot_items) == 2 else (1.45, 5.25, 9.05)
        for (sym, lbl), bx in zip(bot_items, slot_xs):
            if show_l2:
                _draw_rounded_box(draw, bx, 6.46, 0.38, 0.38, fill_hex=pal.s1, border_hex=None, radius=0.18)
            if show_l3:
                _draw_text_box(draw, bx, 6.46, 0.38, 0.38, sym, size_pt=14.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
                _draw_text_box(draw, bx + 0.48, 6.42, 2.95, 0.46, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align="left", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.left_aligned_rounded_panel:
        if show_l2:
            _draw_elevated_box(canvas, 0.28, 0.26, 12.77, 5.56, fill_hex=pal.s1, border_hex=None, border_px=0, radius=0.04)
            _draw_alpha_ring(canvas, 10.62, 3.04, 4.10, alpha_pct=9)
            _draw_alpha_ring(canvas, 10.62, 3.04, 2.75, alpha_pct=9)
            draw = ImageDraw.Draw(canvas)
            draw.line([_px(0.72), _px(4.38), _px(8.85), _px(4.38)], fill=hex_to_rgb(blend_with_white(pal.s4, 0.45)), width=2)
            _draw_rounded_box(draw, 0.72, 4.62, 2.30, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45)
        _draw_crest(draw, 0.86, 0.82, 0.46, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 1.22, 0.60, 5.60, 0.44, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 1.62, 7.80, 0.44, c_sub, size_pt=16.5, bold=True, color_hex=blend_with_white(pal.s5, 0.35), align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 2.16, 8.90, 1.20, c_title, size_pt=36.0, bold=True, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 3.44, 8.50, 0.70, deck.meta.deck_title, size_pt=15.0, color_hex=blend_with_white(pal.s6, 0.25), align="left", valign="top", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.72, 4.62, 2.30, 0.44, f"汇报人：{author}", size_pt=14.0, bold=True, color_hex=pal.s1, align="center", ea_font=ea_f, latin_font=lat_f)
            inline_txt = f"指导教师：{advisor}    {date_str}" if advisor else f"汇报日期：{date_str}"
            _draw_text_box(draw, 3.18, 4.62, 5.80, 0.44, inline_txt, size_pt=14.0, color_hex="#FFFFFF", align="left", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 0.62, 6.26, 3.40, 0.78, f"{affiliation}\n{deck.meta.palette_id.upper()} PALETTE EDITION", size_pt=12.0, bold=True, color_hex=pal.ink, align="left", line_spacing=1.22, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 4.20, 6.26, 4.40, 0.78, "计算药物化学与精准合成工作台\n感谢聆听 · 欢迎指正", size_pt=11.5, color_hex=pal.muted, align="left", line_spacing=1.22, ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 8.80, 6.38, 3.90, 0.54, f"日期：{date_str}  ·  {author}", size_pt=11.5, color_hex=pal.muted, align="right", ea_font=ea_f, latin_font=lat_f)

    elif tpl == CoverTemplateId.chevron_v_cut_banner:
        if show_l2:
            draw.polygon([(_px(0.0), _px(5.02)), (_px(6.667), _px(5.84)), (_px(13.333), _px(5.02)), (_px(13.333), _px(5.18)), (_px(6.667), _px(6.00)), (_px(0.0), _px(5.18))], fill=hex_to_rgb(blend_with_white(pal.s3, 0.56)))
            draw.polygon([(_px(0.0), 0), (_px(13.333), 0), (_px(13.333), _px(5.02)), (_px(6.667), _px(5.84)), (_px(0.0), _px(5.02))], fill=hex_to_rgb(pal.s1))
            draw.line([_px(2.40), _px(2.74), _px(10.93), _px(2.74)], fill=hex_to_rgb(blend_with_white(pal.s5, 0.45)), width=2)
        _draw_crest(draw, 0.92, 0.72, 0.58, "#FFFFFF", ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 9.20, 0.48, 3.60, 0.44, f"日期：{date_str}", size_pt=14.5, bold=True, color_hex="#FFFFFF", align="right", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.00, 1.38, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex="#FFFFFF", align="center", ea_font=ea_f, latin_font=lat_f)
            _draw_text_box(draw, 1.60, 2.94, 10.13, 0.64, c_sub, size_pt=16.5, color_hex=blend_with_white(pal.s6, 0.35), align="center", ea_font=ea_f, latin_font=lat_f)
        for ptxt, px in ((f"汇报人：{author}", 2.95), ("欢迎各位专家交流指导", 7.05)):
            if show_l2:
                _draw_elevated_box(canvas, px, 4.06, 3.33, 0.50, fill_hex="#FFFFFF", border_hex=None, border_px=0, radius=0.45, shadow_alpha=18, blur_px=4)
                draw = ImageDraw.Draw(canvas)
            if show_l3:
                _draw_text_box(draw, px + 0.08, 4.06, 3.17, 0.50, ptxt, size_pt=14.0, bold=True, color_hex=pal.ink, align="center", ea_font=ea_f, latin_font=lat_f)
        _draw_crest(draw, 4.55, 6.62, 0.66, pal.s1, ea_f, lat_f, show_l2=show_l2, show_l3=show_l3)
        if show_l3:
            _draw_text_box(draw, 5.02, 6.32, 4.80, 0.60, affiliation, size_pt=20.0, bold=True, color_hex=pal.s1, align="left", ea_font=ea_f, latin_font=lat_f)

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p
