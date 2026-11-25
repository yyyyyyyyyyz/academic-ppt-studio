"""5 Theme-Adaptive Academic PPT Cover Templates (v5.0 Native python-pptx Builders).

All 5 templates are 100% color-agnostic (dynamically painted from any ScientificPalette)
and 100% natively editable in PowerPoint (AutoShapes, Freeforms, XML dual-font TextBoxes).
"""

from __future__ import annotations

from typing import Tuple

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from ..figure_factory.palettes import ScientificPalette, blend_with_white, darken_hex
from ..schemas.deck_spec import CoverTemplateId, DeckSpec, DesignStyle, SlideSpec
from .v5_layouts import (
    _add_faint_hex,
    _fonts,
    _rgb,
    add_box_text,
    add_line,
    add_rect,
    add_rounded_box,
)

_SCENARIO_LABELS = {
    "defense": "开题 / 学位答辩",
    "midterm": "中期考核进展",
    "group_meeting": "组会文献汇报",
    "literature_review": "顶刊综述研讨",
}


def _cover_meta_fields(spec: SlideSpec, deck: DeckSpec) -> Tuple[str, str, str, str, str, str]:
    title = (deck.meta.deck_title or spec.title or "学术研究汇报").strip()
    subtitle = (deck.meta.deck_subtitle or spec.takeaway or "Scientific Mechanisms & Quantitative Insights").strip()
    author = (deck.meta.author or "研究生").strip()
    affiliation = (deck.meta.affiliation or "药学院计算与合成实验室").strip()
    advisor = (deck.meta.advisor or "").strip()
    date_str = (deck.meta.date_str or "2026 年 11 月").strip()
    return title, subtitle, author, affiliation, advisor, date_str


def _add_vector_crest(
    slide,
    cx_in: float,
    cy_in: float,
    size_in: float,
    stroke_hex: str,
    fill_hex: str | None = None,
    ea_f: str = "微软雅黑",
    lat_f: str = "Arial",
    monogram: str = "Rx",
    name_prefix: str = "L2_cov_crest",
) -> None:
    """Crisp circular + inner hexagon molecular/academic crest monogram."""
    r = size_in * 0.5
    outer = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx_in - r), Inches(cy_in - r), Inches(size_in), Inches(size_in))
    if fill_hex:
        outer.fill.solid()
        outer.fill.fore_color.rgb = _rgb(fill_hex)
    else:
        outer.fill.background()
    outer.line.color.rgb = _rgb(stroke_hex)
    outer.line.width = Pt(1.8)
    outer.name = f"{name_prefix}_outer"

    inner_s = size_in * 0.72
    ir = inner_s * 0.5
    hx = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(cx_in - ir), Inches(cy_in - ir), Inches(inner_s), Inches(inner_s))
    hx.fill.background()
    hx.line.color.rgb = _rgb(stroke_hex)
    hx.line.width = Pt(1.0)
    hx.name = f"{name_prefix}_hex"

    add_box_text(
        slide,
        cx_in - r,
        cy_in - r,
        size_in,
        size_in,
        monogram,
        size_pt=max(9.5, size_in * 20.0),
        bold=True,
        color_hex=stroke_hex,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        line_spacing=1.0,
        name="L3_nav_crest",
        ea_font=ea_f,
        latin_font=lat_f,
    )


def _add_ring_badge(
    slide,
    cx_in: float,
    cy_in: float,
    radius_in: float,
    color_hex: str,
    ring_hex: str,
    symbol: str,
    ea_f: str,
    lat_f: str,
    idx: int,
) -> None:
    halo = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(cx_in - radius_in - 0.05),
        Inches(cy_in - radius_in - 0.05),
        Inches(2 * (radius_in + 0.05)),
        Inches(2 * (radius_in + 0.05)),
    )
    halo.fill.background()
    halo.line.color.rgb = _rgb(ring_hex)
    halo.line.width = Pt(1.2)
    halo.name = f"L2_cov_badge_halo_{idx}"

    core = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(cx_in - radius_in),
        Inches(cy_in - radius_in),
        Inches(2 * radius_in),
        Inches(2 * radius_in),
    )
    core.fill.solid()
    core.fill.fore_color.rgb = _rgb(color_hex)
    core.line.fill.background()
    core.name = f"L2_cov_badge_core_{idx}"

    add_box_text(
        slide,
        cx_in - radius_in,
        cy_in - radius_in,
        2 * radius_in,
        2 * radius_in,
        symbol,
        size_pt=14.0,
        bold=True,
        color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        line_spacing=1.0,
        name=f"L3_cov_badge_ico_{idx}",
        ea_font=ea_f,
        latin_font=lat_f,
    )


def _add_alpha_ring_watermark(slide, cx_in: float, cy_in: float, diam_in: float, alpha_pct: int, name: str) -> None:
    """Subtle low-opacity concentric ring watermark strictly clamped inside canvas."""
    r = diam_in * 0.5
    lx = max(0.05, min(13.28 - diam_in, cx_in - r))
    ty = max(0.05, min(7.45 - diam_in, cy_in - r))
    ring = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(lx), Inches(ty), Inches(diam_in), Inches(diam_in))
    ring.fill.background()
    ring.line.color.rgb = _rgb("#FFFFFF")
    ring.line.width = Pt(2.0)
    ln = ring.line._get_or_add_ln()
    sf = ln.find(qn("a:solidFill"))
    if sf is not None:
        srgb = sf.find(qn("a:srgbClr"))
        if srgb is not None:
            etree.SubElement(srgb, qn("a:alpha")).set("val", str(alpha_pct * 1000))
    ring.name = name


def _add_freeform_polygon(slide, pts: list[tuple[float, float]], fill_hex: str, border_hex: str | None, name: str) -> None:
    builder = slide.shapes.build_freeform(Inches(pts[0][0]), Inches(pts[0][1]))
    builder.add_line_segments([(Inches(x), Inches(y)) for x, y in pts[1:]], close=True)
    shp = builder.convert_to_shape()
    shp.fill.solid()
    shp.fill.fore_color.rgb = _rgb(fill_hex)
    if border_hex:
        shp.line.color.rgb = _rgb(border_hex)
        shp.line.width = Pt(1.0)
    else:
        shp.line.fill.background()
    shp.name = name


# ---------------------------------------------------------------------------
# Template 1: 经典横幅底栏式 (hero_band_bottom_bar)
# ---------------------------------------------------------------------------

def _build_cover_hero_band_bottom_bar(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    ea_f, lat_f = _fonts(deck)
    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)
    tint_strip = blend_with_white(pal.s3, 0.52)

    add_rect(slide, 0.0, 0.0, 13.333, 5.64, fill_hex=pal.s1, name="L2_cov_hero_bg")
    add_rect(slide, 0.0, 5.64, 13.333, 0.14, fill_hex=tint_strip, name="L2_cov_divider_strip")
    add_rect(slide, 0.0, 5.78, 13.333, 1.72, fill_hex="#FFFFFF", name="L2_cov_bottom_bar")

    # Subtle geometric hexagonal watermarks inside hero area
    _add_faint_hex(slide, 0.42, 0.38, 1.95, 1.72, "L2_cov_hex_1")
    _add_faint_hex(slide, 1.75, 1.24, 1.26, 1.12, "L2_cov_hex_2")
    _add_faint_hex(slide, 10.65, 3.22, 2.24, 1.98, "L2_cov_hex_3")
    _add_faint_hex(slide, 9.75, 0.42, 1.48, 1.32, "L2_cov_hex_4")

    # Centered Crest + Affiliation Row
    _add_vector_crest(slide, 4.72, 1.32, 0.64, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cov_crest")
    add_box_text(
        slide, 5.18, 1.04, 4.40, 0.56,
        affiliation, size_pt=20.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_affil", ea_font=ea_f, latin_font=lat_f,
    )

    # Centered Hero Title + Dashed Rule + Subtitle
    add_box_text(
        slide, 0.90, 2.02, 11.53, 1.36,
        title, size_pt=34.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.18,
        name="L3_cov_title", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 2.20, 3.60, 11.13, 3.60, color_hex=blend_with_white(pal.s4, 0.40), width_pt=1.2, dashed=True)
    add_box_text(
        slide, 1.40, 3.84, 10.53, 0.88,
        subtitle, size_pt=18.0, bold=False, color_hex=blend_with_white(pal.s6, 0.35),
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP, line_spacing=1.30,
        name="L3_cov_sub", ea_font=ea_f, latin_font=lat_f,
    )

    # Bottom 3 Circular Icon + Text Metadata Columns (zero overlap)
    items = [
        ("01", f"汇报人：{author}"),
        ("02", f"导师：{advisor}" if advisor else f"方向：{_SCENARIO_LABELS.get(deck.meta.scenario.value, '学术汇报')}"),
        ("03", f"日期：{date_str}"),
    ]
    centers = (2.55, 6.66, 10.78)
    for idx, ((sym, lbl), cx) in enumerate(zip(items, centers)):
        _add_ring_badge(slide, cx - 1.34, 6.64, 0.27, pal.s1, blend_with_white(pal.s4, 0.25), sym, ea_f, lat_f, idx)
        add_box_text(
            slide, cx - 0.94, 6.36, 2.66, 0.56,
            lbl, size_pt=15.0, bold=True, color_hex=pal.ink,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE,
            name=f"L3_cov_meta_{idx}", ea_font=ea_f, latin_font=lat_f,
        )


# ---------------------------------------------------------------------------
# Template 2: 上下双带纯白夹心式 (top_bottom_bands_framed)
# ---------------------------------------------------------------------------

def _build_cover_top_bottom_bands_framed(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    ea_f, lat_f = _fonts(deck)
    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)

    add_rect(slide, 0.0, 0.0, 13.333, 1.32, fill_hex=pal.s1, name="L2_cov_top_band")
    add_rect(slide, 0.0, 1.32, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.35), name="L2_cov_top_rule")
    add_rect(slide, 0.0, 6.12, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.35), name="L2_cov_bot_rule")
    add_rect(slide, 0.0, 6.18, 13.333, 1.32, fill_hex=pal.s1, name="L2_cov_bot_band")

    # Top Band Crest & Affiliation
    _add_vector_crest(slide, 4.55, 0.66, 0.58, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cov_crest")
    add_box_text(
        slide, 5.00, 0.38, 4.80, 0.56,
        affiliation, size_pt=19.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_affil", ea_font=ea_f, latin_font=lat_f,
    )

    # Center Stage Soft Pale Geometric Book/Hex Emblem Watermark
    wm_fill = blend_with_white(pal.s4, 0.80)
    hx = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(4.78), Inches(1.76), Inches(3.77), Inches(3.38))
    hx.fill.solid()
    hx.fill.fore_color.rgb = _rgb(wm_fill)
    hx.line.fill.background()
    hx.name = "L2_cov_center_wm"
    hx_in = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(5.32), Inches(2.24), Inches(2.69), Inches(2.42))
    hx_in.fill.solid()
    hx_in.fill.fore_color.rgb = _rgb("#FFFFFF")
    hx_in.line.fill.background()
    hx_in.name = "L2_cov_center_wm_hole"

    # Centered Title + Hairline Rule + Subtitle
    add_box_text(
        slide, 0.90, 2.02, 11.53, 1.32,
        title, size_pt=36.0, bold=True, color_hex=pal.s1,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.18,
        name="L3_cov_title", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 2.65, 3.44, 10.68, 3.44, color_hex=pal.s2, width_pt=1.5)
    add_box_text(
        slide, 1.60, 3.60, 10.13, 0.86,
        subtitle, size_pt=16.5, bold=False, color_hex=pal.muted,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP, line_spacing=1.25,
        name="L3_cov_sub", ea_font=ea_f, latin_font=lat_f,
    )

    # 3 Split-Pill Capsules along y=4.90 (zero overlap between label & value boxes)
    mid_lbl, mid_val = ("导 师", advisor) if advisor else ("场 景", _SCENARIO_LABELS.get(deck.meta.scenario.value, "学术答辩"))
    pills = [
        ("汇报人", author, 1.05),
        (mid_lbl, mid_val, 4.92),
        ("专 业", "药物化学" if not advisor else "计算药化", 8.79),
    ]
    for idx, (pl_k, pl_v, px) in enumerate(pills):
        add_rounded_box(slide, px, 4.90, 3.48, 0.56, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, radius=0.45, name=f"L2_cov_pill_outer_{idx}")
        add_rounded_box(slide, px + 0.04, 4.94, 1.24, 0.48, fill_hex=pal.s1, border_hex=None, radius=0.45, name=f"L2_cov_pill_left_{idx}")
        add_box_text(
            slide, px + 0.04, 4.94, 1.24, 0.48,
            pl_k, size_pt=14.0, bold=True, color_hex="#FFFFFF",
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
            name=f"L3_cov_pill_k_{idx}", ea_font=ea_f, latin_font=lat_f,
        )
        add_box_text(
            slide, px + 1.38, 4.94, 2.02, 0.48,
            pl_v, size_pt=14.0, bold=True, color_hex=pal.ink,
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
            name=f"L3_cov_pill_v_{idx}", ea_font=ea_f, latin_font=lat_f,
        )

    # Bottom Band Date
    add_box_text(
        slide, 3.66, 6.52, 6.00, 0.60,
        f"日期：{date_str}", size_pt=16.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_date", ea_font=ea_f, latin_font=lat_f,
    )


# ---------------------------------------------------------------------------
# Template 3: 悬浮圆角主色卡式 (floating_rounded_hero_card)
# ---------------------------------------------------------------------------

def _build_cover_floating_rounded_hero_card(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    ea_f, lat_f = _fonts(deck)
    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)

    add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cov_canvas_bg")
    # Subtle depth shelf beneath floating hero card
    add_rounded_box(
        slide, 0.82, 5.56, 11.69, 0.44,
        fill_hex=blend_with_white(pal.s3, 0.56), border_hex=None, radius=0.35,
        name="L2_cov_card_shelf",
    )
    add_rounded_box(
        slide, 0.48, 0.42, 12.37, 5.44,
        fill_hex=pal.s1, border_hex=None, radius=0.05, shadow=True,
        name="L2_cov_floating_card",
    )

    # Subtle translucent geometric highlights on right side inside floating card
    _add_alpha_ring_watermark(slide, 10.65, 3.65, 3.20, alpha_pct=11, name="L2_cov_ring_wm_1")
    _add_faint_hex(slide, 8.95, 2.38, 1.85, 1.64, "L2_cov_hex_wm_1")

    # Top-left white pill scenario badge + Top-right crest & affiliation
    scen_txt = _SCENARIO_LABELS.get(deck.meta.scenario.value, "答辩汇报")
    add_rounded_box(slide, 0.92, 0.86, 2.02, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45, name="L2_cov_scen_pill")
    add_box_text(
        slide, 0.92, 0.86, 2.02, 0.44,
        scen_txt, size_pt=14.0, bold=True, color_hex=pal.s1,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_scen_lbl", ea_font=ea_f, latin_font=lat_f,
    )

    _add_vector_crest(slide, 9.20, 1.08, 0.56, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cov_crest")
    add_box_text(
        slide, 9.58, 0.82, 2.95, 0.52,
        affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_affil", ea_font=ea_f, latin_font=lat_f,
    )

    # Left-aligned Heavy Title + Hairline Rule + Subtitle
    add_box_text(
        slide, 0.92, 1.64, 10.60, 1.64,
        title, size_pt=31.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.20,
        name="L3_cov_title", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 0.92, 3.62, 10.60, 3.62, color_hex=blend_with_white(pal.s4, 0.45), width_pt=1.0)
    add_box_text(
        slide, 0.92, 3.84, 9.60, 1.24,
        subtitle, size_pt=18.0, bold=False, color_hex=blend_with_white(pal.s6, 0.35),
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.35,
        name="L3_cov_sub", ea_font=ea_f, latin_font=lat_f,
    )

    # Bottom white metadata strip with rounded-square theme icons
    bot_items = [
        ("01", f"汇报人：{author}"),
        ("02", f"汇报时间：{date_str}"),
    ]
    if advisor:
        bot_items.append(("03", f"指导教师：{advisor}"))
    slot_xs = (3.40, 7.15) if len(bot_items) == 2 else (1.45, 5.25, 9.05)
    for idx, ((sym, lbl), bx) in enumerate(zip(bot_items, slot_xs)):
        add_rounded_box(slide, bx, 6.46, 0.38, 0.38, fill_hex=pal.s1, border_hex=None, radius=0.18, name=f"L2_cov_sq_ico_{idx}")
        add_box_text(
            slide, bx, 6.46, 0.38, 0.38,
            sym, size_pt=14.0, bold=True, color_hex="#FFFFFF",
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cov_sq_sym_{idx}", ea_font=ea_f, latin_font=lat_f,
        )
        add_box_text(
            slide, bx + 0.48, 6.42, 2.95, 0.46,
            lbl, size_pt=15.0, bold=True, color_hex=pal.ink,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cov_meta_{idx}", ea_font=ea_f, latin_font=lat_f,
        )


# ---------------------------------------------------------------------------
# Template 4: 精致留白圆角大板式 (left_aligned_rounded_panel)
# ---------------------------------------------------------------------------

def _build_cover_left_aligned_rounded_panel(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    ea_f, lat_f = _fonts(deck)
    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)

    add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cov_canvas_bg")
    add_rounded_box(
        slide, 0.28, 0.26, 12.77, 5.56,
        fill_hex=pal.s1, border_hex=None, radius=0.04, shadow=True,
        name="L2_cov_main_panel",
    )

    # Large oversized low-opacity concentric ring watermark strictly inside right half
    _add_alpha_ring_watermark(slide, 10.62, 3.04, 4.10, alpha_pct=9, name="L2_cov_big_wm_outer")
    _add_alpha_ring_watermark(slide, 10.62, 3.04, 2.75, alpha_pct=9, name="L2_cov_big_wm_inner")

    # Top-left crest + affiliation
    _add_vector_crest(slide, 0.86, 0.82, 0.46, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cov_crest")
    add_box_text(
        slide, 1.22, 0.60, 5.60, 0.44,
        affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_affil", ea_font=ea_f, latin_font=lat_f,
    )

    # Left-aligned Kicker, Heavy Title, Subtitle, Rule, and Metadata Pill Row
    kicker = _SCENARIO_LABELS.get(deck.meta.scenario.value, "阶段性学术汇报")
    add_box_text(
        slide, 0.72, 1.62, 7.80, 0.44,
        kicker, size_pt=19.0, bold=True, color_hex=blend_with_white(pal.s5, 0.35),
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_kicker", ea_font=ea_f, latin_font=lat_f,
    )
    add_box_text(
        slide, 0.72, 2.12, 8.90, 1.26,
        title, size_pt=29.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.18,
        name="L3_cov_title", ea_font=ea_f, latin_font=lat_f,
    )
    add_box_text(
        slide, 0.72, 3.44, 8.50, 0.72,
        subtitle, size_pt=15.0, bold=False, color_hex=blend_with_white(pal.s6, 0.25),
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.28,
        name="L3_cov_sub", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 0.72, 4.38, 8.85, 4.38, color_hex=blend_with_white(pal.s4, 0.45), width_pt=0.9)

    add_rounded_box(slide, 0.72, 4.62, 2.30, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45, name="L2_cov_author_pill")
    add_box_text(
        slide, 0.72, 4.62, 2.30, 0.44,
        f"汇报人：{author}", size_pt=14.0, bold=True, color_hex=pal.s1,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_author", ea_font=ea_f, latin_font=lat_f,
    )
    inline_txt = f"指导教师：{advisor}    {date_str}" if advisor else f"汇报日期：{date_str}"
    add_box_text(
        slide, 3.18, 4.62, 5.80, 0.44,
        inline_txt, size_pt=14.0, bold=False, color_hex="#FFFFFF",
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_inline_meta", ea_font=ea_f, latin_font=lat_f,
    )

    # Bottom Pure-White Two-Column Institutional Footer Bar
    add_box_text(
        slide, 0.62, 6.26, 3.40, 0.78,
        f"{affiliation}\n{deck.meta.palette_id.upper()} PALETTE EDITION", size_pt=12.0, bold=True, color_hex=pal.ink,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.22,
        name="L3_footer_left", ea_font=ea_f, latin_font=lat_f,
    )
    add_box_text(
        slide, 4.20, 6.26, 4.40, 0.78,
        "计算药物化学与精准合成工作台\n100% Native Editable PPTX Specimen", size_pt=11.5, bold=False, color_hex=pal.muted,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.22,
        name="L3_footer_mid", ea_font=ea_f, latin_font=lat_f,
    )
    add_box_text(
        slide, 8.80, 6.38, 3.90, 0.54,
        f"日期：{date_str}  ·  {author}", size_pt=11.5, bold=False, color_hex=pal.muted,
        align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE,
        name="L3_footer_right", ea_font=ea_f, latin_font=lat_f,
    )


# ---------------------------------------------------------------------------
# Template 5: 顶部 V 型尖角裁切式 (chevron_v_cut_banner)
# ---------------------------------------------------------------------------

def _build_cover_chevron_v_cut_banner(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    ea_f, lat_f = _fonts(deck)
    title, subtitle, author, affiliation, advisor, date_str = _cover_meta_fields(spec, deck)

    add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cov_canvas_bg")
    # Parallel lighter V-chevron accent ribbon directly below main chevron
    _add_freeform_polygon(
        slide,
        [(0.0, 5.02), (6.667, 5.84), (13.333, 5.02), (13.333, 5.18), (6.667, 6.00), (0.0, 5.18)],
        fill_hex=blend_with_white(pal.s3, 0.56),
        border_hex=None,
        name="L2_cov_v_ribbon",
    )
    # Main full-bleed top V-chevron hero banner
    _add_freeform_polygon(
        slide,
        [(0.0, 0.0), (13.333, 0.0), (13.333, 5.02), (6.667, 5.84), (0.0, 5.02)],
        fill_hex=pal.s1,
        border_hex=None,
        name="L2_cov_v_banner",
    )

    # Top-left geometric emblem + Top-right date
    _add_vector_crest(slide, 0.92, 0.72, 0.58, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, monogram="Rx", name_prefix="L2_cov_crest_tl")
    add_box_text(
        slide, 9.20, 0.48, 3.60, 0.44,
        f"日期：{date_str}", size_pt=14.5, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_date", ea_font=ea_f, latin_font=lat_f,
    )

    # Centered Heavy Title + White Rule + Subtitle inside V-banner
    add_box_text(
        slide, 0.90, 1.32, 11.53, 1.34,
        title, size_pt=36.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.18,
        name="L3_cov_title", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 2.30, 2.74, 11.03, 2.74, color_hex=blend_with_white(pal.s5, 0.45), width_pt=1.2)
    add_box_text(
        slide, 1.60, 2.90, 10.13, 0.88,
        subtitle, size_pt=16.5, bold=False, color_hex=blend_with_white(pal.s6, 0.35),
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP, line_spacing=1.28,
        name="L3_cov_sub", ea_font=ea_f, latin_font=lat_f,
    )

    # 3 Centered Pure-White Pill Capsules
    pill_items = [
        f"汇报人：{author}",
        f"场景：{_SCENARIO_LABELS.get(deck.meta.scenario.value, '学术答辩')}",
        f"指导教师：{advisor}" if advisor else "学科：药物化学",
    ]
    pill_xs = (1.35, 5.10, 8.85)
    for idx, (ptxt, px) in enumerate(zip(pill_items, pill_xs)):
        add_rounded_box(slide, px, 4.10, 3.12, 0.50, fill_hex="#FFFFFF", border_hex=None, radius=0.45, shadow=True, name=f"L2_cov_pill_{idx}")
        add_box_text(
            slide, px + 0.08, 4.10, 2.96, 0.50,
            ptxt, size_pt=14.0, bold=True, color_hex=pal.ink,
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cov_pill_{idx}", ea_font=ea_f, latin_font=lat_f,
        )

    # Bottom V-cradled pure-white centered Crest + Affiliation
    _add_vector_crest(slide, 4.55, 6.62, 0.66, pal.s1, ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cov_crest_bot")
    add_box_text(
        slide, 5.02, 6.32, 4.80, 0.60,
        affiliation, size_pt=20.0, bold=True, color_hex=pal.s1,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cov_affil", ea_font=ea_f, latin_font=lat_f,
    )


_COVER_DISPATCH = {
    CoverTemplateId.hero_band_bottom_bar: _build_cover_hero_band_bottom_bar,
    CoverTemplateId.top_bottom_bands_framed: _build_cover_top_bottom_bands_framed,
    CoverTemplateId.floating_rounded_hero_card: _build_cover_floating_rounded_hero_card,
    CoverTemplateId.left_aligned_rounded_panel: _build_cover_left_aligned_rounded_panel,
    CoverTemplateId.chevron_v_cut_banner: _build_cover_chevron_v_cut_banner,
}


def build_v5_cover_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> bool:
    """Render any of the 5 theme-adaptive cover templates if selected (or default on v5.0 styles)."""
    tpl = deck.meta.cover_template
    if tpl is None:
        if deck.meta.design_style == DesignStyle.zero_fill_frameless:
            return False
        tpl = CoverTemplateId.hero_band_bottom_bar

    builder = _COVER_DISPATCH.get(tpl, _build_cover_hero_band_bottom_bar)
    builder(slide, spec, deck, pal)
    return True


# ---------------------------------------------------------------------------
# Reference Hero-Band Part Divider Slide (过渡页)
# ---------------------------------------------------------------------------

_PART_WORDS = {1: "PART ONE", 2: "PART TWO", 3: "PART THREE", 4: "PART FOUR", 5: "PART FIVE", 6: "PART SIX"}


def _parse_part_number(spec: SlideSpec) -> int:
    import re
    m = re.search(r"(\d+)", spec.eyebrow or "")
    if m:
        return max(1, min(6, int(m.group(1))))
    return 1


def build_v5_part_divider_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> bool:
    """Render theme-adaptive center hero-band Part Divider modeled on reference PPTX Slide 2."""
    if deck.meta.cover_template is None and deck.meta.design_style == DesignStyle.zero_fill_frameless:
        return False

    ea_f, lat_f = _fonts(deck)
    p_num = _parse_part_number(spec)
    num_str = f"{p_num:02d}"
    part_pill_txt = _PART_WORDS.get(p_num, f"PART {num_str}")
    deep_emboss = darken_hex(pal.s1, 0.34)
    chip_fill = darken_hex(pal.s1, 0.24)
    chip_border = blend_with_white(pal.s3, 0.30)

    # Full-width centered hero band
    add_rect(slide, 0.0, 1.44, 13.333, 4.31, fill_hex=pal.s1, name="L2_div_hero_band")
    add_rect(slide, 0.0, 1.38, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.42), name="L2_div_top_rim")
    add_rect(slide, 0.0, 5.75, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.42), name="L2_div_bot_rim")

    # Subtle large darkened embossed numeral behind pure-white PART pill (L2_ prefix avoids false L3 overlap)
    add_box_text(
        slide, 5.36, 1.50, 2.61, 1.46,
        num_str, size_pt=72.0, bold=True, color_hex=deep_emboss,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
        name="L2_div_watermark_num", ea_font=ea_f, latin_font=lat_f,
    )
    add_rounded_box(slide, 5.56, 2.40, 2.21, 0.38, fill_hex="#FFFFFF", border_hex=None, radius=0.45, name="L2_div_part_pill")
    add_box_text(
        slide, 5.56, 2.40, 2.21, 0.38,
        part_pill_txt, size_pt=14.0, bold=True, color_hex=pal.s1,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
        name="L3_div_part_pill", ea_font=ea_f, latin_font=lat_f,
    )

    # Main Chinese Section Title + Subtitle + Hairline
    add_box_text(
        slide, 1.20, 2.94, 10.93, 1.04,
        spec.title, size_pt=46.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.10,
        name="L3_div_title", ea_font=ea_f, latin_font=lat_f,
    )
    sub_txt = (spec.takeaway or "Research Design, Mechanism & Quantitative Milestones").strip()
    add_box_text(
        slide, 1.80, 4.04, 9.73, 0.36,
        sub_txt, size_pt=14.0, bold=True, color_hex=blend_with_white(pal.s5, 0.38),
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05,
        name="L3_div_sub", ea_font=ea_f, latin_font=lat_f,
    )
    add_line(slide, 4.20, 4.52, 9.13, 4.52, color_hex=chip_border, width_pt=1.1)

    # 3 Outlined Dark-Tinted Keyword Pills
    chips = (spec.figure_chips or ["科学问题与假说", "方法路径与表征", "关键进展与验证"])[:3]
    chip_w = 2.24
    gap = 0.36
    start_x = 6.667 - (len(chips) * chip_w + max(0, len(chips) - 1) * gap) * 0.5
    for idx, ch_txt in enumerate(chips):
        cx = start_x + idx * (chip_w + gap)
        add_rounded_box(slide, cx, 4.76, chip_w, 0.38, fill_hex=chip_fill, border_hex=chip_border, border_pt=0.95, radius=0.45, name=f"L2_div_chip_{idx}")
        add_box_text(
            slide, cx + 0.06, 4.76, chip_w - 0.12, 0.38,
            ch_txt, size_pt=14.0, bold=True, color_hex="#FFFFFF",
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
            name=f"L3_div_chip_{idx}", ea_font=ea_f, latin_font=lat_f,
        )
    return True


# ---------------------------------------------------------------------------
# 5 Cover-Matched Closing Slides (尾页设计呼应封面模板)
# ---------------------------------------------------------------------------

def _closing_fields(spec: SlideSpec, deck: DeckSpec) -> Tuple[str, str, str, str, str, str]:
    c_title = (spec.title or "感谢聆听  敬请各位专家批评指正").strip()
    c_sub = "THANK YOU FOR YOUR ATTENTION · Q & A"
    author = (deck.meta.author or "研究生").strip()
    affiliation = (deck.meta.affiliation or "药学院计算与合成实验室").strip()
    advisor = (deck.meta.advisor or "").strip()
    date_str = (deck.meta.date_str or "2026 年 11 月").strip()
    return c_title, c_sub, author, affiliation, advisor, date_str


def build_v5_closing_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> bool:
    """Render a Closing slide structurally echoing the active CoverTemplateId & palette."""
    tpl = deck.meta.cover_template
    if tpl is None:
        if deck.meta.design_style == DesignStyle.zero_fill_frameless:
            return False
        tpl = CoverTemplateId.hero_band_bottom_bar

    ea_f, lat_f = _fonts(deck)
    c_title, c_sub, author, affiliation, advisor, date_str = _closing_fields(spec, deck)

    if tpl == CoverTemplateId.hero_band_bottom_bar:
        add_rect(slide, 0.0, 0.0, 13.333, 5.64, fill_hex=pal.s1, name="L2_cls_hero_bg")
        add_rect(slide, 0.0, 5.64, 13.333, 0.14, fill_hex=blend_with_white(pal.s3, 0.52), name="L2_cls_divider")
        add_rect(slide, 0.0, 5.78, 13.333, 1.72, fill_hex="#FFFFFF", name="L2_cls_bottom_bar")
        _add_faint_hex(slide, 0.42, 0.38, 1.95, 1.72, "L2_cls_hex_1")
        _add_faint_hex(slide, 10.65, 3.22, 2.24, 1.98, "L2_cls_hex_2")

        _add_vector_crest(slide, 4.82, 1.32, 0.62, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cls_crest")
        add_box_text(slide, 5.26, 1.04, 4.20, 0.56, "THANK YOU · Q & A", size_pt=18.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_kicker", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 1.00, 2.08, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_title", ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 2.40, 3.54, 10.93, 3.54, color_hex=blend_with_white(pal.s4, 0.40), width_pt=1.2, dashed=True)
        add_box_text(slide, 1.60, 3.78, 10.13, 0.80, f"{affiliation}  ·  {deck.meta.deck_title}", size_pt=16.0, color_hex=blend_with_white(pal.s6, 0.35), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP, name="L3_cls_sub", ea_font=ea_f, latin_font=lat_f)

        items = [("01", f"汇报人：{author}"), ("02", f"导师：{advisor}" if advisor else f"单位：{affiliation[:14]}"), ("03", f"日期：{date_str}")]
        for idx, ((sym, lbl), cx) in enumerate(zip(items, (2.55, 6.66, 10.78))):
            _add_ring_badge(slide, cx - 1.34, 6.64, 0.27, pal.s1, blend_with_white(pal.s4, 0.25), sym, ea_f, lat_f, idx)
            add_box_text(slide, cx - 0.94, 6.36, 2.66, 0.56, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_meta_{idx}", ea_font=ea_f, latin_font=lat_f)
        return True

    if tpl == CoverTemplateId.top_bottom_bands_framed:
        add_rect(slide, 0.0, 0.0, 13.333, 1.32, fill_hex=pal.s1, name="L2_cls_top_band")
        add_rect(slide, 0.0, 1.32, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.35), name="L2_cls_top_rule")
        add_rect(slide, 0.0, 6.12, 13.333, 0.06, fill_hex=blend_with_white(pal.s3, 0.35), name="L2_cls_bot_rule")
        add_rect(slide, 0.0, 6.18, 13.333, 1.32, fill_hex=pal.s1, name="L2_cls_bot_band")
        _add_vector_crest(slide, 4.55, 0.66, 0.58, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cls_crest")
        add_box_text(slide, 5.00, 0.38, 4.80, 0.56, affiliation, size_pt=19.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_affil", ea_font=ea_f, latin_font=lat_f)

        wm_fill = blend_with_white(pal.s4, 0.80)
        hx = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(4.78), Inches(1.76), Inches(3.77), Inches(3.38))
        hx.fill.solid(); hx.fill.fore_color.rgb = _rgb(wm_fill); hx.line.fill.background(); hx.name = "L2_cls_wm"
        hx_in = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(5.32), Inches(2.24), Inches(2.69), Inches(2.42))
        hx_in.fill.solid(); hx_in.fill.fore_color.rgb = _rgb("#FFFFFF"); hx_in.line.fill.background(); hx_in.name = "L2_cls_wm_hole"

        add_box_text(slide, 1.00, 2.04, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_title", ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 2.80, 3.40, 10.53, 3.40, color_hex=pal.s2, width_pt=1.5)
        add_box_text(slide, 1.60, 3.58, 10.13, 0.64, c_sub, size_pt=16.5, color_hex=pal.muted, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_sub", ea_font=ea_f, latin_font=lat_f)

        pills = [("汇报人", author, 2.55), ("日 期", date_str, 7.30)]
        for idx, (pk, pv, px) in enumerate(pills):
            add_rounded_box(slide, px, 4.86, 3.48, 0.56, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, radius=0.45, name=f"L2_cls_pill_{idx}")
            add_rounded_box(slide, px + 0.04, 4.90, 1.24, 0.48, fill_hex=pal.s1, border_hex=None, radius=0.45, name=f"L2_cls_pill_l_{idx}")
            add_box_text(slide, px + 0.04, 4.90, 1.24, 0.48, pk, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_pk_{idx}", ea_font=ea_f, latin_font=lat_f)
            add_box_text(slide, px + 1.38, 4.90, 2.02, 0.48, pv, size_pt=14.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_pv_{idx}", ea_font=ea_f, latin_font=lat_f)

        add_box_text(slide, 3.66, 6.52, 6.00, 0.60, f"欢迎各位专家交流指导 · {date_str}", size_pt=16.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_bot_date", ea_font=ea_f, latin_font=lat_f)
        return True

    if tpl == CoverTemplateId.floating_rounded_hero_card:
        add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cls_bg")
        add_rounded_box(slide, 0.82, 5.56, 11.69, 0.44, fill_hex=blend_with_white(pal.s3, 0.56), border_hex=None, radius=0.35, name="L2_cls_shelf")
        add_rounded_box(slide, 0.48, 0.42, 12.37, 5.44, fill_hex=pal.s1, border_hex=None, radius=0.05, shadow=True, name="L2_cls_card")
        _add_alpha_ring_watermark(slide, 10.65, 3.65, 3.20, alpha_pct=11, name="L2_cls_ring_wm")
        _add_faint_hex(slide, 8.95, 2.38, 1.85, 1.64, "L2_cls_hex_wm")

        add_rounded_box(slide, 0.92, 0.86, 1.92, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45, name="L2_cls_qa_pill")
        add_box_text(slide, 0.92, 0.86, 1.92, 0.44, "Q & A · 致谢", size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_qa", ea_font=ea_f, latin_font=lat_f)
        _add_vector_crest(slide, 9.20, 1.08, 0.56, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cls_crest")
        add_box_text(slide, 9.58, 0.82, 2.95, 0.52, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_affil", ea_font=ea_f, latin_font=lat_f)

        add_box_text(slide, 0.92, 1.78, 10.40, 1.38, c_title, size_pt=38.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_title", ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 0.92, 3.52, 10.40, 3.52, color_hex=blend_with_white(pal.s4, 0.45), width_pt=1.0)
        add_box_text(slide, 0.92, 3.78, 9.80, 1.05, f"{c_sub}\n{deck.meta.deck_title}", size_pt=16.5, color_hex=blend_with_white(pal.s6, 0.35), align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.35, name="L3_cls_sub", ea_font=ea_f, latin_font=lat_f)

        bot_items = [("01", f"汇报人：{author}"), ("02", f"汇报时间：{date_str}")]
        if advisor:
            bot_items.append(("03", f"指导教师：{advisor}"))
        slot_xs = (3.40, 7.15) if len(bot_items) == 2 else (1.45, 5.25, 9.05)
        for idx, ((sym, lbl), bx) in enumerate(zip(bot_items, slot_xs)):
            add_rounded_box(slide, bx, 6.46, 0.38, 0.38, fill_hex=pal.s1, border_hex=None, radius=0.18, name=f"L2_cls_sq_{idx}")
            add_box_text(slide, bx, 6.46, 0.38, 0.38, sym, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_sym_{idx}", ea_font=ea_f, latin_font=lat_f)
            add_box_text(slide, bx + 0.48, 6.42, 2.95, 0.46, lbl, size_pt=15.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_meta_{idx}", ea_font=ea_f, latin_font=lat_f)
        return True

    if tpl == CoverTemplateId.left_aligned_rounded_panel:
        add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cls_bg")
        add_rounded_box(slide, 0.28, 0.26, 12.77, 5.56, fill_hex=pal.s1, border_hex=None, radius=0.04, shadow=True, name="L2_cls_panel")
        _add_alpha_ring_watermark(slide, 10.62, 3.04, 4.10, alpha_pct=9, name="L2_cls_wm_1")
        _add_alpha_ring_watermark(slide, 10.62, 3.04, 2.75, alpha_pct=9, name="L2_cls_wm_2")
        _add_vector_crest(slide, 0.86, 0.82, 0.46, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cls_crest")
        add_box_text(slide, 1.22, 0.60, 5.60, 0.44, affiliation, size_pt=16.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_affil", ea_font=ea_f, latin_font=lat_f)

        add_box_text(slide, 0.72, 1.62, 7.80, 0.44, c_sub, size_pt=16.5, bold=True, color_hex=blend_with_white(pal.s5, 0.35), align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_kicker", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.72, 2.16, 8.90, 1.20, c_title, size_pt=36.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_title", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.72, 3.44, 8.50, 0.70, deck.meta.deck_title, size_pt=15.0, color_hex=blend_with_white(pal.s6, 0.25), align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, name="L3_cls_sub", ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 0.72, 4.38, 8.85, 4.38, color_hex=blend_with_white(pal.s4, 0.45), width_pt=0.9)

        add_rounded_box(slide, 0.72, 4.62, 2.30, 0.44, fill_hex="#FFFFFF", border_hex=None, radius=0.45, name="L2_cls_pill")
        add_box_text(slide, 0.72, 4.62, 2.30, 0.44, f"汇报人：{author}", size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_author", ea_font=ea_f, latin_font=lat_f)
        inline_txt = f"指导教师：{advisor}    {date_str}" if advisor else f"汇报日期：{date_str}"
        add_box_text(slide, 3.18, 4.62, 5.80, 0.44, inline_txt, size_pt=14.0, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_meta", ea_font=ea_f, latin_font=lat_f)

        add_box_text(slide, 0.62, 6.26, 3.40, 0.78, f"{affiliation}\n{deck.meta.palette_id.upper()} PALETTE EDITION", size_pt=12.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.22, name="L3_footer_left", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 4.20, 6.26, 4.40, 0.78, "计算药物化学与精准合成工作台\n感谢聆听 · 欢迎指正", size_pt=11.5, color_hex=pal.muted, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.22, name="L3_footer_mid", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 8.80, 6.38, 3.90, 0.54, f"日期：{date_str}  ·  {author}", size_pt=11.5, color_hex=pal.muted, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, name="L3_footer_right", ea_font=ea_f, latin_font=lat_f)
        return True

    # CoverTemplateId.chevron_v_cut_banner
    add_rect(slide, 0.0, 0.0, 13.333, 7.50, fill_hex="#FFFFFF", name="L2_cls_bg")
    _add_freeform_polygon(
        slide,
        [(0.0, 5.02), (6.667, 5.84), (13.333, 5.02), (13.333, 5.18), (6.667, 6.00), (0.0, 5.18)],
        fill_hex=blend_with_white(pal.s3, 0.56), border_hex=None, name="L2_cls_v_ribbon",
    )
    _add_freeform_polygon(
        slide,
        [(0.0, 0.0), (13.333, 0.0), (13.333, 5.02), (6.667, 5.84), (0.0, 5.02)],
        fill_hex=pal.s1, border_hex=None, name="L2_cls_v_banner",
    )
    _add_vector_crest(slide, 0.92, 0.72, 0.58, "#FFFFFF", ea_f=ea_f, lat_f=lat_f, monogram="Rx", name_prefix="L2_cls_crest_tl")
    add_box_text(slide, 9.20, 0.48, 3.60, 0.44, f"日期：{date_str}", size_pt=14.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_date", ea_font=ea_f, latin_font=lat_f)
    add_box_text(slide, 1.00, 1.38, 11.33, 1.24, c_title, size_pt=40.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_title", ea_font=ea_f, latin_font=lat_f)
    add_line(slide, 2.40, 2.74, 10.93, 2.74, color_hex=blend_with_white(pal.s5, 0.45), width_pt=1.2)
    add_box_text(slide, 1.60, 2.94, 10.13, 0.64, c_sub, size_pt=16.5, color_hex=blend_with_white(pal.s6, 0.35), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_sub", ea_font=ea_f, latin_font=lat_f)

    for idx, (ptxt, px) in enumerate(zip((f"汇报人：{author}", f"欢迎各位专家交流指导"), (2.95, 7.05))):
        add_rounded_box(slide, px, 4.06, 3.33, 0.50, fill_hex="#FFFFFF", border_hex=None, radius=0.45, shadow=True, name=f"L2_cls_pill_{idx}")
        add_box_text(slide, px + 0.08, 4.06, 3.17, 0.50, ptxt, size_pt=14.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_cls_pill_{idx}", ea_font=ea_f, latin_font=lat_f)

    _add_vector_crest(slide, 4.55, 6.62, 0.66, pal.s1, ea_f=ea_f, lat_f=lat_f, name_prefix="L2_cls_crest_bot")
    add_box_text(slide, 5.02, 6.32, 4.80, 0.60, affiliation, size_pt=20.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, name="L3_cls_affil", ea_font=ea_f, latin_font=lat_f)
    return True

