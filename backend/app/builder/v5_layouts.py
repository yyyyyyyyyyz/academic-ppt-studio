"""v5.0 Native python-pptx Academic Defense & Consulting Layout Engine.

Implements:
- Dedicated split-panel 目录 (TOC) slide (deep-navy left block with subtle geometric rings + elevated white chapter cards)
- Deep-navy bilingual cutout-trapezoid header bar with hairline divider & double-chevron Row 2 heading
- Elevated pure-white (#FFFFFF) cards/containers with soft OOXML drop shadows, thin #D6E0EC borders & chamfered header tabs
- Strictly微软雅黑 + Arial XML dual-font binding (>= 14pt body/charts/tables, refined 9.5–12pt micro-chrome)
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Tuple

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from ..figure_factory.palettes import ScientificPalette, blend_with_white, hex_to_rgb
from ..schemas.deck_spec import DeckSpec, FigureBoxIn, InsightItem, LayoutId, SlideSpec
from .xml_utils import (
    apply_soft_card_shadow,
    apply_zebra_table_borders,
    configure_zero_fill_textbox,
    populate_paragraph,
)


_DEFAULT_EN_SUBS = [
    "Background & Evolution",
    "Conformation & Mechanism",
    "Quantitative & PK Data",
    "Research Outlook",
    "Methodology & Design",
    "Experimental Outcomes",
]


def _rgb(hex_str: str) -> RGBColor:
    r, g, b = hex_to_rgb(hex_str)
    return RGBColor(r, g, b)


def _fonts(deck: DeckSpec) -> Tuple[str, str]:
    fonts = deck.locked_standards.fonts or {}
    return fonts.get("ea", "微软雅黑"), fonts.get("latin", "Arial")


def _split_bilingual(raw: str, idx: int) -> Tuple[str, str]:
    if "|" in raw:
        cn, en = raw.split("|", 1)
        return cn.strip(), en.strip()
    return raw.strip(), _DEFAULT_EN_SUBS[idx % len(_DEFAULT_EN_SUBS)]


def _clean_section_heading(spec: SlideSpec) -> str:
    sec = (spec.section_name or "").strip()
    if sec:
        stripped = sec.lstrip("0123456789.- ")
        return stripped or sec
    return spec.title[:10]


def get_v5_figure_box(layout_id: LayoutId) -> FigureBoxIn:
    """Return canonical Layer 1 figure slot coordinates (in) for each v5.0 pure-white layout."""
    mapping = {
        LayoutId.lit_overview_dual_card: FigureBoxIn(left=0.52, top=1.86, width=8.18, height=2.92),
        LayoutId.mechanism_3col_flow: FigureBoxIn(left=4.05, top=1.98, width=5.24, height=3.84),
        LayoutId.data_dashboard_table: FigureBoxIn(left=0.54, top=2.86, width=7.30, height=3.18),
        LayoutId.bg_top_summary_3box: FigureBoxIn(left=4.58, top=3.04, width=4.14, height=2.52),
        LayoutId.pain_points_left_arrows: FigureBoxIn(left=5.82, top=2.26, width=6.94, height=2.82),
        LayoutId.fig_left_3step_chain: FigureBoxIn(left=0.56, top=2.00, width=7.44, height=3.92),
        LayoutId.vs_center_wing: FigureBoxIn(left=3.90, top=1.94, width=5.52, height=3.60),
        LayoutId.roadmap_layered_matrix: FigureBoxIn(left=1.42, top=3.00, width=3.66, height=1.70),
        LayoutId.timeline_chevron_flow: FigureBoxIn(left=0.54, top=2.56, width=6.54, height=3.42),
        LayoutId.quadrant_2x2_matrix: FigureBoxIn(left=8.48, top=1.86, width=4.31, height=2.92),
        LayoutId.hub_spoke_radial: FigureBoxIn(left=1.50, top=2.48, width=2.68, height=2.64),
        LayoutId.dual_compare_cards: FigureBoxIn(left=7.27, top=2.82, width=5.50, height=2.16),
        LayoutId.tri_column_showcase: FigureBoxIn(left=0.56, top=3.62, width=7.90, height=2.36),
    }
    return mapping.get(layout_id, FigureBoxIn(left=0.46, top=1.68, width=7.75, height=4.42))


def extract_visual_metric_bars(spec: SlideSpec, max_bars: int = 4) -> list[Tuple[str, str, float]]:
    """Extract numeric bar rows (label, display_val, fraction_0_to_1) from table_data or kpis for infographic bars."""
    items: list[Tuple[str, str, float]] = []
    num_pat = re.compile(r"(-?\d+(?:\.\d+)?)")
    raw_pairs: list[Tuple[str, str, float]] = []
    if spec.table_data and spec.table_data.rows:
        for row in spec.table_data.rows[:max_bars]:
            if len(row) >= 2:
                lbl = str(row[0]).strip()[:12]
                val_str = str(row[1]).strip()[:12]
                m = num_pat.search(val_str)
                if m:
                    raw_pairs.append((lbl, val_str, abs(float(m.group(1)))))
    if len(raw_pairs) < 2 and spec.kpis:
        raw_pairs = []
        for kp in spec.kpis[:max_bars]:
            lbl = (kp.label if hasattr(kp, "label") else kp["label"])[:12]
            val_str = (kp.value if hasattr(kp, "value") else kp["value"])[:12]
            m = num_pat.search(val_str)
            if m:
                raw_pairs.append((lbl, val_str, abs(float(m.group(1)))))
    if len(raw_pairs) < 2:
        return []
    mx = max((v for _, _, v in raw_pairs), default=1.0) or 1.0
    for lbl, val_str, num_v in raw_pairs[:max_bars]:
        items.append((lbl, val_str, max(0.16, min(1.0, num_v / mx))))
    return items


def split_card_head_body(raw: str, fallback_head: str) -> Tuple[str, str]:
    txt = (raw or "").strip()
    for sep in ("：", ":"):
        if sep in txt:
            h, b = txt.split(sep, 1)
            if 2 <= len(h.strip()) <= 16 and b.strip():
                return h.strip()[:14], b.strip()
    return fallback_head, txt


def add_rounded_box(
    slide,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    fill_hex: Optional[str] = "#FFFFFF",
    border_hex: Optional[str] = "#D6E0EC",
    border_pt: float = 0.75,
    dashed: bool = False,
    radius: float = 0.08,
    shadow: bool = False,
    name: Optional[str] = None,
):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in),
    )
    if name:
        shp.name = name
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    if fill_hex:
        shp.fill.solid()
        shp.fill.fore_color.rgb = _rgb(fill_hex)
    else:
        shp.fill.background()

    if border_hex and border_pt > 0:
        shp.line.color.rgb = _rgb(border_hex)
        shp.line.width = Pt(border_pt)
        if dashed:
            ln = shp.line._get_or_add_ln()
            etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    else:
        shp.line.fill.background()

    if shadow and fill_hex:
        apply_soft_card_shadow(shp)
    return shp


def add_rect(
    slide,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    fill_hex: Optional[str] = "#FFFFFF",
    border_hex: Optional[str] = None,
    border_pt: float = 0.75,
    name: Optional[str] = None,
):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in),
    )
    if name:
        shp.name = name
    if fill_hex:
        shp.fill.solid()
        shp.fill.fore_color.rgb = _rgb(fill_hex)
    else:
        shp.fill.background()
    if border_hex and border_pt > 0:
        shp.line.color.rgb = _rgb(border_hex)
        shp.line.width = Pt(border_pt)
    else:
        shp.line.fill.background()
    return shp


def add_box_text(
    slide,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    text: str,
    size_pt: float = 14.0,
    bold: bool = False,
    color_hex: str = "#162032",
    highlight_phrase: Optional[str] = None,
    highlight_color_hex: Optional[str] = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
    line_spacing: float = 1.15,
    name: Optional[str] = None,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
):
    tb = slide.shapes.add_textbox(Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in))
    if name:
        tb.name = name
    configure_zero_fill_textbox(tb, word_wrap=True, anchor=anchor)
    p = tb.text_frame.paragraphs[0]
    populate_paragraph(
        p,
        text=text,
        size_pt=size_pt,
        bold=bold,
        color_hex=color_hex,
        highlight_phrase=highlight_phrase,
        highlight_color_hex=highlight_color_hex,
        align=align,
        line_spacing=line_spacing,
        ea_font=ea_font,
        latin_font=latin_font,
    )
    return tb


def add_chamfered_header_tab(
    slide,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    text: str,
    fill_hex: str,
    text_color: str = "#FFFFFF",
    radius: float = 0.18,
    size_pt: float = 14.0,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
    name: Optional[str] = None,
) -> None:
    """Render a sleek compact chamfered-feel capsule tab with crisp top hairline highlight."""
    tab = add_rounded_box(
        slide, left_in, top_in, width_in, height_in,
        fill_hex=fill_hex, border_hex=None, radius=radius, name=name,
    )
    apply_soft_card_shadow(tab, blur_pt=3.0, dist_pt=1.0, alpha_pct=10)
    hi_hex = blend_with_white(fill_hex, 0.55)
    add_line(slide, left_in + 0.16, top_in + 0.03, left_in + width_in - 0.16, top_in + 0.03, color_hex=hi_hex, width_pt=0.65)
    add_box_text(
        slide, left_in + 0.06, top_in, width_in - 0.12, height_in,
        text=text, size_pt=size_pt, bold=True, color_hex=text_color,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
        ea_font=ea_font, latin_font=latin_font,
    )


def add_line(
    slide,
    x1_in: float,
    y1_in: float,
    x2_in: float,
    y2_in: float,
    color_hex: str,
    width_pt: float = 1.0,
    dashed: bool = False,
    arrow_end: bool = False,
):
    conn = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1_in), Inches(y1_in),
        Inches(x2_in), Inches(y2_in),
    )
    conn.line.color.rgb = _rgb(color_hex)
    conn.line.width = Pt(width_pt)
    ln = conn.line._get_or_add_ln()
    if dashed:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    if arrow_end:
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    return conn


def _add_faint_hex(slide, l_in: float, t_in: float, w_in: float, h_in: float, name: str) -> None:
    hx = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(l_in), Inches(t_in), Inches(w_in), Inches(h_in))
    hx.fill.background()
    hx.line.color.rgb = _rgb("#FFFFFF")
    hx.line.width = Pt(1.2)
    ln = hx.line._get_or_add_ln()
    sf = ln.find(qn("a:solidFill"))
    if sf is not None:
        srgb = sf.find(qn("a:srgbClr"))
        if srgb is not None:
            etree.SubElement(srgb, qn("a:alpha")).set("val", "14000")
    hx.name = name


# ---------------------------------------------------------------------------
# Dedicated Split-Panel 目录 (TOC) Slide
# ---------------------------------------------------------------------------

def build_v5_toc_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    """Build split-panel 目录 slide modeled on reference PPTX Slide 3: left theme sidebar + offset layered tiles."""
    ea_f, lat_f = _fonts(deck)
    sub_tint = blend_with_white(pal.s4, 0.56)
    shadow_tile = blend_with_white(pal.s1, 0.78)
    rule_tint = blend_with_white(pal.s1, 0.35)

    # Left full-height theme vertical block (w=3.50") + subtle geometric hexagons
    add_rect(slide, 0.0, 0.0, 3.50, 7.50, fill_hex=pal.s1, name="L2_toc_left_bg")
    _add_faint_hex(slide, 0.12, 0.22, 1.38, 1.22, "L2_toc_hex_1")
    _add_faint_hex(slide, 1.02, 0.72, 0.86, 0.76, "L2_toc_hex_2")
    _add_faint_hex(slide, 1.98, 5.84, 1.42, 1.24, "L2_toc_hex_3")

    add_box_text(slide, 0.34, 0.36, 2.82, 0.30, "LITERATURE SEMINAR", size_pt=10.5, bold=True, color_hex=sub_tint, align=PP_ALIGN.LEFT, name="L3_toc_tag", ea_font=ea_f, latin_font=lat_f)

    # Stacked giant "目\n录" + 90-degree clockwise vertical "CONTENTS" side-by-side
    add_box_text(
        slide, 0.58, 1.88, 1.10, 2.95,
        "目\n录", size_pt=72.0, bold=True, color_hex="#FFFFFF",
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.02,
        name="L3_toc_hero", ea_font=ea_f, latin_font=lat_f,
    )
    tb_en = add_box_text(
        slide, 1.78, 3.12, 1.60, 0.44,
        "CONTENTS", size_pt=16.5, bold=True, color_hex=sub_tint,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
        name="L3_toc_en_hero", ea_font=ea_f, latin_font=lat_f,
    )
    tb_en.rotation = 90.0

    # Wrapped deck title + subtitle at bottom-left
    add_box_text(slide, 0.34, 6.02, 2.86, 0.68, deck.meta.deck_title, size_pt=11.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.BOTTOM, line_spacing=1.15, name="L3_footer_left", ea_font=ea_f, latin_font=lat_f)
    if deck.meta.deck_subtitle:
        add_box_text(slide, 0.34, 6.76, 2.86, 0.38, deck.meta.deck_subtitle, size_pt=9.5, bold=False, color_hex=sub_tint, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.1, name="L3_footer_sub", ea_font=ea_f, latin_font=lat_f)

    # Top-right affiliation micro-header
    add_box_text(slide, 8.60, 0.30, 4.30, 0.32, deck.meta.affiliation, size_pt=11.5, bold=True, color_hex=pal.s1, align=PP_ALIGN.RIGHT, name="L3_footer_right", ea_font=ea_f, latin_font=lat_f)

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

        # Offset double-layer rounded number tile (shadow tile + primary tile)
        add_rounded_box(slide, 4.74, ry + 0.06, tile_s, tile_s, fill_hex=shadow_tile, border_hex=None, radius=0.18, name=f"L2_toc_tile_bg_{idx}")
        add_rounded_box(slide, 4.66, ry, tile_s, tile_s, fill_hex=pal.s1, border_hex=None, radius=0.18, name=f"L2_toc_num_{idx}")
        add_box_text(slide, 4.66, ry, tile_s, tile_s, f"{idx+1:02d}", size_pt=24.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_toc_num_{idx}", ea_font=ea_f, latin_font=lat_f)

        # Clean unboxed section title + bilingual subtitle + right page ref + crisp underline
        add_box_text(slide, 5.74, ry + 0.04, 5.80, 0.42, cn_clean, size_pt=22.0, bold=True, color_hex=pal.ink, anchor=MSO_ANCHOR.MIDDLE, name=f"L3_toc_cn_{idx}", ea_font=ea_f, latin_font=lat_f)
        if en:
            add_box_text(slide, 5.74, ry + 0.46, 5.60, 0.24, en, size_pt=11.5, bold=False, color_hex="#64748B", name=f"L3_toc_sub_{idx}", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 11.62, ry + 0.12, 0.82, 0.32, f"P.{idx+2:02d}", size_pt=11.5, bold=True, color_hex=pal.s3, align=PP_ALIGN.RIGHT, name=f"L3_toc_page_{idx}", ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 5.74, ry + tile_s - 0.02, 12.44, ry + tile_s - 0.02, color_hex=rule_tint, width_pt=1.35)


# ---------------------------------------------------------------------------
# Deep-Navy Cutout-Trapezoid Bilingual Header + Pure-White Inline Takeaway
# ---------------------------------------------------------------------------

def add_v5_header(
    slide,
    spec: SlideSpec,
    deck: DeckSpec,
    pal: ScientificPalette,
    total_slides: int,
) -> float:
    """Render reference-grade deep-navy cutout header bar + Row 2 vector chevrons & elevated white takeaway card."""
    ea_f, lat_f = _fonts(deck)
    variant = spec.header_variant or "nav_tabs"

    if variant == "editorial":
        add_rect(slide, 0.42, 0.20, 1.35, 0.05, fill_hex=pal.s1, name="L2_editorial_rule")
        add_box_text(slide, 0.42, 0.28, 11.20, 0.46, spec.title, size_pt=20.5, bold=True, color_hex=pal.ink, line_spacing=1.08, name="L3_title", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 11.75, 0.34, 1.16, 0.32, f"{spec.slide_no:02d} / {total_slides:02d}", size_pt=12.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.RIGHT, name="L3_page_num", ea_font=ea_f, latin_font=lat_f)
        add_box_text(
            slide, 0.42, 0.78, 12.48, 0.42,
            spec.takeaway, size_pt=14.0, bold=False, color_hex=pal.muted,
            highlight_phrase=spec.takeaway_highlight, highlight_color_hex=pal.s1,
            line_spacing=1.12, name="L3_takeaway", ea_font=ea_f, latin_font=lat_f,
        )
        add_line(slide, 0.42, 1.26, 12.91, 1.26, color_hex=pal.line, width_pt=0.85)
        return 1.38

    # Full-width deep-navy top bar + subtle bottom hairline BEFORE trapezoid cutout
    add_rect(slide, 0.0, 0.0, 13.333, 0.70, fill_hex=pal.s1, name="L2_nav_bg")
    add_line(slide, 0.0, 0.70, 13.333, 0.70, color_hex="#E2E8F0", width_pt=0.75)

    # Left circular crest with white outer oval + hexagonal inner motif + Rx monogram
    ring_out = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.24), Inches(0.10), Inches(0.50), Inches(0.50))
    ring_out.fill.background()
    ring_out.line.color.rgb = _rgb("#FFFFFF")
    ring_out.line.width = Pt(1.4)
    ring_out.name = "L2_nav_crest_outer"
    hex_in = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(0.32), Inches(0.18), Inches(0.34), Inches(0.34))
    hex_in.fill.background()
    hex_in.line.color.rgb = _rgb("#FFFFFF")
    hex_in.line.width = Pt(0.9)
    hex_in.name = "L2_nav_crest_inner"
    add_box_text(slide, 0.24, 0.10, 0.50, 0.50, "Rx", size_pt=10.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, name="L3_nav_crest", ea_font=ea_f, latin_font=lat_f)

    tabs_raw = (spec.nav_sections or [s.section_name for s in deck.slides if s.section_name] or ["01 背景演进", "02 构象机理", "03 药代转化"])[:6]
    nav_start_x = 0.96
    nav_total_w = 12.08
    tab_w = nav_total_w / max(len(tabs_raw), 1)
    active_idx = max(0, min(spec.active_nav_idx, len(tabs_raw) - 1))

    for t_i, raw_tab in enumerate(tabs_raw):
        tx = nav_start_x + t_i * tab_w
        cn_lbl, en_lbl = _split_bilingual(raw_tab, t_i)
        if t_i == active_idx:
            trap = slide.shapes.add_shape(
                MSO_SHAPE.TRAPEZOID,
                Inches(tx + 0.04), Inches(0.06), Inches(tab_w - 0.08), Inches(0.66),
            )
            trap.fill.solid()
            trap.fill.fore_color.rgb = _rgb("#FFFFFF")
            trap.line.fill.background()
            try:
                trap.adjustments[0] = 0.055
            except Exception:
                pass
            trap.name = f"L2_nav_active_{t_i}"
            add_box_text(slide, tx + 0.14, 0.09, tab_w - 0.28, 0.30, cn_lbl, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, name=f"L3_nav_tab_{t_i}", ea_font=ea_f, latin_font=lat_f)
            add_box_text(slide, tx + 0.14, 0.39, tab_w - 0.28, 0.24, en_lbl, size_pt=9.5, bold=False, color_hex="#64748B", align=PP_ALIGN.CENTER, name=f"L3_nav_tab_en_{t_i}", ea_font=ea_f, latin_font=lat_f)
        else:
            sub_tint = blend_with_white(pal.s4, 0.56)
            add_box_text(slide, tx + 0.10, 0.09, tab_w - 0.20, 0.30, cn_lbl, size_pt=13.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, name=f"L3_nav_tab_{t_i}", ea_font=ea_f, latin_font=lat_f)
            add_box_text(slide, tx + 0.10, 0.39, tab_w - 0.20, 0.24, en_lbl, size_pt=9.5, bold=False, color_hex=sub_tint, align=PP_ALIGN.CENTER, name=f"L3_nav_tab_en_{t_i}", ea_font=ea_f, latin_font=lat_f)
            if t_i < len(tabs_raw) - 1 and t_i + 1 != active_idx:
                add_line(slide, tx + tab_w, 0.16, tx + tab_w, 0.54, color_hex=pal.s3, width_pt=0.75)

    # Row 2 (T:0.84..1.28): Crisp double vector chevrons + Section Heading + Elevated Pure-White Inline Takeaway Card
    sec_heading = _clean_section_heading(spec)
    ch1 = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(0.40), Inches(0.94), Inches(0.18), Inches(0.24))
    ch1.fill.solid()
    ch1.fill.fore_color.rgb = _rgb(pal.s1)
    ch1.line.fill.background()
    ch1.name = "L2_sec_chevron_1"
    ch2 = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(0.53), Inches(0.96), Inches(0.14), Inches(0.20))
    ch2.fill.solid()
    ch2.fill.fore_color.rgb = _rgb(pal.s3)
    ch2.line.fill.background()
    ch2.name = "L2_sec_chevron_2"

    add_box_text(slide, 0.74, 0.84, 2.82, 0.44, sec_heading, size_pt=19.5, bold=True, color_hex=pal.s1, line_spacing=1.05, name="L3_title", ea_font=ea_f, latin_font=lat_f)

    add_rounded_box(slide, 3.62, 0.84, 9.31, 0.44, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.14, shadow=True, name="L2_takeaway_box")
    add_rect(slide, 3.70, 0.92, 0.06, 0.28, fill_hex=pal.s1, name="L2_takeaway_accent")
    add_box_text(
        slide, 3.84, 0.85, 8.96, 0.42,
        spec.takeaway, size_pt=14.0, bold=False, color_hex=pal.ink,
        highlight_phrase=spec.takeaway_highlight, highlight_color_hex=pal.s1,
        align=PP_ALIGN.LEFT, line_spacing=1.08, name="L3_takeaway", ea_font=ea_f, latin_font=lat_f,
    )
    return 1.42


def add_v5_bottom_banner(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    """Render elevated pure-white bottom synthesis bar & refined footer."""
    ea_f, lat_f = _fonts(deck)
    banner = spec.bottom_banner or {}
    mode = banner.get("mode", "bar")
    y, h = 6.26, 0.48
    total = len(deck.slides)

    if mode == "triple_pill":
        t_left = banner.get("left", "高选择性构象预组织")
        t_mid = banner.get("center", spec.takeaway[:26] or "核心机理突破")
        t_right = banner.get("right", "可逆共价低脱靶风险")
        add_rounded_box(slide, 0.40, y, 3.65, h, fill_hex="#FFFFFF", border_hex=pal.s4, border_pt=0.85, radius=0.45, shadow=True)
        add_box_text(slide, 0.50, y, 3.45, h, t_left, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

        add_rounded_box(slide, 4.46, y - 0.02, 4.41, h + 0.04, fill_hex="#FFFFFF", border_hex=pal.s1, border_pt=1.0, radius=0.45, shadow=True)
        add_box_text(slide, 4.58, y - 0.02, 4.17, h + 0.04, t_mid, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

        add_rounded_box(slide, 9.28, y, 3.65, h, fill_hex="#FFFFFF", border_hex=pal.s4, border_pt=0.85, radius=0.45, shadow=True)
        add_box_text(slide, 9.38, y, 3.45, h, t_right, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

        add_line(slide, 4.09, y + h / 2, 4.42, y + h / 2, color_hex=pal.s2, width_pt=1.5, arrow_end=True)
        add_line(slide, 8.91, y + h / 2, 9.24, y + h / 2, color_hex=pal.s2, width_pt=1.5, arrow_end=True)
    elif mode == "solid_bar":
        add_rounded_box(slide, 0.40, y, 12.53, h, fill_hex=pal.s1, border_hex=None, radius=0.18, shadow=True, name="L2_bottom_bar")
        badge = banner.get("badge", "突破")
        add_rounded_box(slide, 0.48, y + 0.07, 1.38, h - 0.14, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
        add_box_text(slide, 0.48, y + 0.07, 1.38, h - 0.14, badge, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 2.02, y, 10.76, h, banner.get("text", spec.takeaway), size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.LEFT, ea_font=ea_f, latin_font=lat_f)
    else:
        border_c = "#FECACA" if mode == "rose_quote" else "#D6E0EC"
        badge_c = "#B91C1C" if mode == "rose_quote" else pal.s1
        add_rounded_box(slide, 0.40, y, 12.53, h, fill_hex="#FFFFFF", border_hex=border_c, border_pt=0.75, radius=0.16, shadow=True, name="L2_bottom_bar")
        badge = banner.get("badge", "核心总结")
        add_rounded_box(slide, 0.48, y + 0.07, 1.44, h - 0.14, fill_hex=badge_c, border_hex=None, radius=0.18)
        add_box_text(slide, 0.48, y + 0.07, 1.44, h - 0.14, badge, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 2.08, y, 10.72, h, banner.get("text", spec.takeaway), size_pt=14.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.LEFT, ea_font=ea_f, latin_font=lat_f)

    # Subtle bottom rule + citation + page counter footer (11.0 pt)
    add_box_text(slide, 0.40, 6.90, 9.20, 0.32, spec.footer_left, size_pt=11.0, bold=False, color_hex="#64748B", name="L3_footer_left", ea_font=ea_f, latin_font=lat_f)
    add_box_text(slide, 9.80, 6.90, 3.13, 0.32, f"{deck.meta.affiliation} · {spec.slide_no:02d}/{total:02d}", size_pt=11.0, bold=False, color_hex="#64748B", align=PP_ALIGN.RIGHT, name="L3_footer_right", ea_font=ea_f, latin_font=lat_f)


# ---------------------------------------------------------------------------
# 8 v5.0 Pure-White Elevated Modular Layouts
# ---------------------------------------------------------------------------

def _build_lit_overview_dual_card(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    add_rounded_box(slide, 0.40, 1.48, 8.44, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, name="L2_left_dashed_box")

    panel_title = (spec.figure_bottom_note or "药物化学结构演进与构效关系").split("|")[0]
    add_chamfered_header_tab(slide, 1.72, 1.35, 5.80, 0.30, panel_title, fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f, name="L2_fig_pill")

    assets_n = len(spec.figure_spec.assets) if spec.figure_spec else 0
    if assets_n <= 1:
        add_rounded_box(slide, 0.52, 1.84, 8.20, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_subframe_main")
    else:
        add_rounded_box(slide, 0.52, 1.84, 3.42, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_subframe_left")
        add_rounded_box(slide, 5.28, 1.84, 3.42, 2.96, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_subframe_right")

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.lit_overview_dual_card), ea_font=ea_f, latin_font=lat_f)
        tag_xs = (0.62, 5.38)
        for idx, asset in enumerate(spec.figure_spec.assets[:2]):
            if asset.sublabel:
                tx = tag_xs[idx]
                add_rounded_box(slide, tx, 1.92, 1.54, 0.24, fill_hex="#FFFFFF", border_hex=pal.s4, border_pt=0.7, radius=0.45, name=f"L2_mol_tag_{idx}")
                add_box_text(slide, tx + 0.04, 1.92, 1.46, 0.24, asset.sublabel, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0, name=f"L3_mol_tag_{idx}", ea_font=ea_f, latin_font=lat_f)

    hdr_tint = blend_with_white(pal.s1, 0.90)
    for idx, ins in enumerate(spec.insights[:2]):
        cx = 0.52 + idx * 4.16
        add_rounded_box(slide, cx, 4.92, 4.02, 1.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.08, shadow=True, name=f"L2_left_ins_{idx}")
        add_rect(slide, cx + 0.02, 4.94, 3.98, 0.34, fill_hex=hdr_tint)
        add_rounded_box(slide, cx + 0.10, 4.97, 0.40, 0.28, fill_hex=pal.s1 if idx == 0 else pal.s2, border_hex=None, radius=0.22)
        add_box_text(slide, cx + 0.10, 4.97, 0.40, 0.28, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.56, 4.95, 3.38, 0.32, ins.heading, size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.14, 5.31, 3.74, 0.65, ins.body, size_pt=14.0, bold=False, color_hex=pal.ink, highlight_phrase=ins.highlight, highlight_color_hex=pal.s1, line_spacing=1.10, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)

    # Right Pure-White Elevated Dossier Card
    prof = spec.profile_card or {}
    add_rounded_box(slide, 8.98, 1.48, 3.95, 3.26, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_profile_card")
    badge_j = prof.get("journal_badge", "SCIENCE 2021 · 文献档案")
    add_chamfered_header_tab(slide, 9.38, 1.35, 3.15, 0.30, badge_j, fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    p_title = prof.get("paper_title", deck.meta.deck_title[:48])
    add_box_text(slide, 9.12, 1.80, 3.67, 0.70, p_title, size_pt=14.0, bold=True, color_hex=pal.s1, line_spacing=1.12, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
    p_auth = prof.get("authors", spec.footer_left)
    add_box_text(slide, 9.12, 2.52, 3.67, 0.30, p_auth, size_pt=11.5, bold=False, color_hex="#64748B", line_spacing=1.05, anchor=MSO_ANCHOR.TOP, name="L3_dossier_auth", ea_font=ea_f, latin_font=lat_f)

    add_line(slide, 9.12, 2.88, 12.79, 2.88, color_hex="#D6E0EC", width_pt=0.8)

    metrics = prof.get("metrics") or [(k.label, k.value) for k in spec.kpis[:3]] or [("Ki", "3.11 nM"), ("EC50", "74.5 nM")]
    my = 2.96
    for m_lbl, m_val in metrics[:4]:
        add_box_text(slide, 9.12, my, 1.42, 0.38, m_lbl, size_pt=14.0, bold=False, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 10.56, my, 2.23, 0.38, m_val, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.RIGHT, ea_font=ea_f, latin_font=lat_f)
        add_line(slide, 9.12, my + 0.40, 12.79, my + 0.40, color_hex="#E2E8F0", width_pt=0.6)
        my += 0.43

    # Bottom right pure-white elevated focus card
    add_rounded_box(slide, 8.98, 4.88, 3.95, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_focus_box")
    add_chamfered_header_tab(slide, 9.95, 4.74, 2.01, 0.30, "设计核心", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    focus_txt = prof.get("focus_text", spec.takeaway)
    add_box_text(slide, 9.12, 5.14, 3.67, 0.90, focus_txt, size_pt=14.0, bold=False, color_hex=pal.ink, line_spacing=1.12, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)


def _build_mechanism_3col_flow(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    """3 clean elevated pure-white columns connected by refined arrows & anchor-dotted leader callouts."""
    ea_f, lat_f = _fonts(deck)

    # Left Column
    add_rounded_box(slide, 0.40, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 0.88, 1.39, 2.30, 0.30, "关键药效团解析", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    l_cards = spec.left_cards or [{"heading": i.heading, "body": i.body} for i in spec.insights[:3]]
    soft_tint = blend_with_white(pal.s1, 0.92)
    for idx, lc in enumerate(l_cards[:3]):
        cy = 1.84 + idx * 1.42
        add_rounded_box(slide, 0.54, cy, 2.97, 1.16, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rect(slide, 0.56, cy + 0.02, 2.93, 0.34, fill_hex=soft_tint)
        add_rect(slide, 0.54, cy + 0.06, 0.06, 1.04, fill_hex=pal.s1)
        add_box_text(slide, 0.68, cy + 0.03, 2.78, 0.32, lc.get("heading", ""), size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.68, cy + 0.38, 2.78, 0.74, lc.get("body", ""), size_pt=14.0, bold=False, color_hex=pal.ink, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        if idx < min(len(l_cards), 3) - 1:
            plus_ov = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.90), Inches(cy + 1.18), Inches(0.24), Inches(0.22))
            plus_ov.fill.solid()
            plus_ov.fill.fore_color.rgb = _rgb(pal.s2)
            plus_ov.line.fill.background()
            add_box_text(slide, 1.90, cy + 1.17, 0.24, 0.24, "+", size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, ea_font=ea_f, latin_font=lat_f)

    # Refined Connector Arrow Left -> Center
    arr_l = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(3.71), Inches(3.70), Inches(0.18), Inches(0.24))
    arr_l.fill.solid()
    arr_l.fill.fore_color.rgb = _rgb(pal.s1)
    arr_l.line.fill.background()

    # Center Column (pure-white dashed frame + 3D figure + anchor-dotted callout pills)
    add_rounded_box(slide, 3.95, 1.50, 5.44, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.05, dashed=True, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 5.02, 1.36, 3.30, 0.30, "三维构象与口袋结合模式", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.mechanism_3col_flow), ea_font=ea_f, latin_font=lat_f)

    for idx, cb in enumerate(spec.callout_badges[:4]):
        bx = float(cb.get("x_in", 4.05))
        by = float(cb.get("y_in", 1.78))
        bw = max(1.68, float(cb.get("w_in", 1.82)))
        bh = 0.34
        c_hex = pal.token(cb.get("color_token", "s1"))
        if "target_x_in" in cb and "target_y_in" in cb:
            tx_t = float(cb["target_x_in"])
            ty_t = float(cb["target_y_in"])
            start_y = (by + bh) if ty_t > (by + bh * 0.5) else by
            add_line(slide, bx + bw * 0.5, start_y, tx_t, ty_t, color_hex=c_hex, width_pt=1.15, dashed=True)
            dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(tx_t - 0.045), Inches(ty_t - 0.045), Inches(0.09), Inches(0.09))
            dot.fill.solid()
            dot.fill.fore_color.rgb = _rgb(c_hex)
            dot.line.color.rgb = _rgb("#FFFFFF")
            dot.line.width = Pt(1.0)
            dot.name = f"L2_callout_dot_{idx}"
        add_rounded_box(slide, bx, by, bw, bh, fill_hex="#FFFFFF", border_hex=c_hex, border_pt=1.0, radius=0.45, shadow=True, name=f"L2_callout_{idx}")
        add_box_text(slide, bx + 0.04, by, bw - 0.08, bh, str(cb.get("text", "")), size_pt=14.0, bold=True, color_hex=c_hex, align=PP_ALIGN.CENTER, name=f"L3_callout_{idx}", ea_font=ea_f, latin_font=lat_f)

    # Refined Connector Arrow Center -> Right
    arr_r = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(9.45), Inches(3.70), Inches(0.18), Inches(0.24))
    arr_r.fill.solid()
    arr_r.fill.fore_color.rgb = _rgb(pal.s1)
    arr_r.line.fill.background()

    # Right Column
    add_rounded_box(slide, 9.69, 1.54, 3.25, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 10.17, 1.39, 2.30, 0.30, "关键结构优势", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    r_chain = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] + [{"title": "高选择性", "body": "低脱靶与口服稳定"}]
    for idx, rc in enumerate(r_chain[:3]):
        ry = 1.90 + idx * 1.40
        add_rounded_box(slide, 9.83, ry, 2.97, 1.06, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.08, shadow=True)
        add_rect(slide, 9.85, ry + 0.02, 2.93, 0.06, fill_hex=pal.s1 if idx == 0 else pal.s2)
        add_box_text(slide, 9.93, ry + 0.12, 2.77, 0.34, rc.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.93, ry + 0.46, 2.77, 0.54, rc.get("body", ""), size_pt=14.0, bold=False, color_hex=pal.ink, align=PP_ALIGN.CENTER, line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)
        if idx < 2:
            d_arr = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(11.19), Inches(ry + 1.10), Inches(0.24), Inches(0.24))
            d_arr.fill.solid()
            d_arr.fill.fore_color.rgb = _rgb(pal.s2)
            d_arr.line.fill.background()


def _build_data_dashboard_table(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    add_rounded_box(slide, 0.40, 1.50, 7.58, 4.64, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_left_dashboard")
    add_chamfered_header_tab(slide, 2.10, 1.36, 4.18, 0.30, "定量指标可视化看板与结构对照", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    kpis = spec.kpis[:3] or [
        {"value": "34–50%", "label": "大鼠口服生物利用度", "color_token": "s1"},
        {"value": "35×", "label": "较先导暴露提升", "color_token": "s2"},
        {"value": "5.1 h", "label": "大鼠半衰期 t1/2", "color_token": "s1"},
    ]
    tile_w = 2.34
    for idx, kp in enumerate(kpis[:3]):
        val = kp.value if hasattr(kp, "value") else kp["value"]
        lbl = kp.label if hasattr(kp, "label") else kp["label"]
        ctok = kp.color_token if hasattr(kp, "color_token") else kp.get("color_token", "s1")
        tx = 0.54 + idx * 2.48
        add_rounded_box(slide, tx, 1.84, tile_w, 0.88, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.08, shadow=True)
        add_rect(slide, tx + 0.02, 1.84, tile_w - 0.04, 0.07, fill_hex=pal.token(ctok), name=f"L2_kpi_bar_{idx}")
        add_box_text(slide, tx + 0.12, 1.93, tile_w - 0.24, 0.40, val, size_pt=21.0, bold=True, color_hex=pal.token(ctok), align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, tx + 0.12, 2.34, tile_w - 0.24, 0.34, lbl, size_pt=14.0, bold=False, color_hex=pal.muted, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    bars = extract_visual_metric_bars(spec, max_bars=4)
    if bars:
        fig_box = FigureBoxIn(left=0.54, top=2.86, width=4.02, height=3.16)
        add_rounded_box(slide, 0.54, 2.86, 4.02, 3.16, fill_hex="#FFFFFF", border_hex="#E2E8F0", border_pt=0.75, radius=0.06)
        add_rounded_box(slide, 4.68, 2.86, 3.16, 3.16, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True, name="L2_metric_bars_panel")
        add_rect(slide, 4.70, 2.88, 3.12, 0.34, fill_hex=blend_with_white(pal.s1, 0.90))
        add_box_text(slide, 4.78, 2.88, 2.96, 0.34, "关键指标柱状对比", size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        for b_i, (b_lbl, b_val, b_frac) in enumerate(bars):
            by = 3.30 + b_i * 0.66
            col_b = pal.s1 if b_i % 2 == 0 else pal.s2
            add_box_text(slide, 4.78, by, 1.78, 0.28, b_lbl, size_pt=14.0, bold=False, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
            add_box_text(slide, 6.58, by, 1.16, 0.28, b_val, size_pt=14.0, bold=True, color_hex=col_b, align=PP_ALIGN.RIGHT, ea_font=ea_f, latin_font=lat_f)
            add_rounded_box(slide, 4.78, by + 0.32, 2.96, 0.16, fill_hex="#EDF2F7", border_hex=None, radius=0.45)
            add_rounded_box(slide, 4.78, by + 0.32, max(0.32, 2.96 * b_frac), 0.16, fill_hex=col_b, border_hex=None, radius=0.45)
    else:
        fig_box = get_v5_figure_box(LayoutId.data_dashboard_table)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=fig_box, ea_font=ea_f, latin_font=lat_f)

    td = spec.table_data
    table_bottom = 3.92
    if td and td.headers:
        rows_count = len(td.rows) + 1
        cols_count = len(td.headers)
        row_h = min(0.46, 2.38 / max(rows_count, 2))
        t_shape = slide.shapes.add_table(rows_count, cols_count, Inches(8.12), Inches(1.50), Inches(4.81), Inches(row_h * rows_count))
        tbl = t_shape.table
        apply_zebra_table_borders(tbl, header_bg_hex=pal.s1, stripe_bg_hex="#FFFFFF", border_hex="#E2E8F0")
        for c_i, hdr in enumerate(td.headers):
            cell = tbl.cell(0, c_i)
            cell.text_frame.word_wrap = True
            p = cell.text_frame.paragraphs[0]
            populate_paragraph(p, hdr, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT, line_spacing=1.05, ea_font=ea_f, latin_font=lat_f)
        for r_i, row in enumerate(td.rows):
            for c_i, val in enumerate(row[:cols_count]):
                cell = tbl.cell(r_i + 1, c_i)
                cell.text_frame.word_wrap = True
                p = cell.text_frame.paragraphs[0]
                populate_paragraph(p, val, size_pt=14.0, bold=(c_i == cols_count - 1), color_hex=pal.s1 if c_i == cols_count - 1 else pal.ink, align=PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT, line_spacing=1.05, ea_font=ea_f, latin_font=lat_f)
        table_bottom = 1.50 + row_h * rows_count

    scards = spec.strategy_cards or [
        {"badge": "代谢瓶颈", "badge_color": "s1" if idx == 0 else "s2", "title": ins.heading, "body": ins.body}
        for idx, ins in enumerate(spec.insights[:2])
    ]
    cur_y = table_bottom + 0.14
    avail_h = max(0.88, (6.14 - cur_y - 0.10 * max(len(scards) - 1, 0)) / max(len(scards), 1))
    for idx, sc in enumerate(scards[:2]):
        sy = cur_y + idx * (avail_h + 0.10)
        raw_bcol = str(sc.get("badge_color") or "").strip()
        if not raw_bcol or raw_bcol in ("s1", "#00468B", "#D97706"):
            bcol = pal.s1 if idx == 0 else pal.s2
        elif raw_bcol in ("s2", "s3", "s4", "s5", "s6", "alert", "ink", "muted"):
            bcol = pal.token(raw_bcol)
        else:
            bcol = raw_bcol
        add_rounded_box(slide, 8.12, sy, 4.81, avail_h, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rect(slide, 8.20, sy + 0.12, 0.06, avail_h - 0.24, fill_hex=bcol)
        add_rounded_box(slide, 8.34, sy + 0.10, 1.14, 0.28, fill_hex=bcol, border_hex=None, radius=0.14)
        add_box_text(slide, 8.34, sy + 0.10, 1.14, 0.28, sc.get("badge", "策略"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.56, sy + 0.08, 3.26, 0.32, sc.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 8.34, sy + 0.44, 4.46, avail_h - 0.50, sc.get("body", ""), size_pt=14.0, bold=False, color_hex=pal.muted, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)


def _build_bg_top_summary_3box(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    top_tint = blend_with_white(pal.s6, 0.35)
    add_rounded_box(slide, 0.40, 1.48, 12.53, 0.96, fill_hex=top_tint, border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_rounded_box(slide, 0.48, 1.56, 1.28, 0.80, fill_hex=pal.s1, border_hex=None, radius=0.10)
    add_box_text(slide, 0.48, 1.56, 1.28, 0.80, "核心目标", size_pt=14.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    lines = spec.pain_points[:3] or [f"{ins.heading}：{ins.body}" for ins in spec.insights[:3]]
    cols_n = max(1, min(3, len(lines)))
    col_w = 10.90 / cols_n
    for idx, ln in enumerate(lines[:cols_n]):
        lx = 1.88 + idx * col_w
        add_box_text(slide, lx + 0.06, 1.54, col_w - 0.12, 0.84, ln, size_pt=14.0, bold=False, color_hex=pal.ink, line_spacing=1.08, anchor=MSO_ANCHOR.MIDDLE, ea_font=ea_f, latin_font=lat_f)
        if idx < cols_n - 1:
            add_line(slide, lx + col_w, 1.62, lx + col_w, 2.30, color_hex="#CBD5E1", width_pt=0.8)

    boxes = [
        (0.40, 3.82, spec.left_cards[0].get("heading", "01 核心痛点") if spec.left_cards else "01 核心痛点"),
        (4.50, 4.30, "02 分子设计与机理"),
        (9.08, 3.85, spec.right_chain[0].get("title", "03 预期突破") if spec.right_chain else "03 预期突破"),
    ]
    for bx, bw, btitle in boxes:
        add_rounded_box(slide, bx, 2.64, bw, 3.46, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, shadow=True)
        add_chamfered_header_tab(slide, bx + 0.45, 2.52, bw - 0.90, 0.30, btitle, fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    for ax in (4.24, 8.82):
        arr = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(ax), Inches(4.24), Inches(0.22), Inches(0.28))
        arr.fill.solid()
        arr.fill.fore_color.rgb = _rgb(pal.s1)
        arr.line.fill.background()

    for idx, ins in enumerate(spec.insights[:2]):
        cy = 3.04 + idx * 1.48
        add_rounded_box(slide, 0.56, cy, 3.50, 1.32, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        num_c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.68), Inches(cy + 0.12), Inches(0.30), Inches(0.30))
        num_c.fill.solid()
        num_c.fill.fore_color.rgb = _rgb(pal.s1 if idx == 0 else pal.s2)
        num_c.line.fill.background()
        add_box_text(slide, 0.68, cy + 0.12, 0.30, 0.30, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 1.06, cy + 0.10, 2.88, 0.34, ins.heading, size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.68, cy + 0.48, 3.26, 0.76, ins.body, size_pt=14.0, color_hex=pal.ink, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)

    r_items = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] or [{"title": spec.takeaway[:14], "body": spec.section_name}]
    for idx, rc in enumerate(r_items[:2]):
        cy = 3.04 + idx * 1.48
        add_rounded_box(slide, 9.24, cy, 3.53, 1.32, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rect(slide, 9.26, cy + 0.02, 3.49, 0.08, fill_hex=pal.s1 if idx == 0 else pal.s2)
        add_box_text(slide, 9.38, cy + 0.16, 3.25, 0.36, rc.get("title", ""), size_pt=15.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.38, cy + 0.54, 3.25, 0.70, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, align=PP_ALIGN.CENTER, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.bg_top_summary_3box), ea_font=ea_f, latin_font=lat_f)
        eng = spec.figure_spec.assets[0].engine.value if spec.figure_spec.assets else ""
        tag_l = "3D 空间构象" if eng == "cylview_3d" else "2D 化学结构"
        tag_r = f"{spec.kpis[0].label}: {spec.kpis[0].value}"[:18] if spec.kpis else "核心药效骨架"
        add_rounded_box(slide, 4.64, 5.64, 1.88, 0.34, fill_hex=top_tint, border_hex=pal.s4, border_pt=0.75, radius=0.28)
        add_box_text(slide, 4.66, 5.64, 1.84, 0.34, tag_l, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_rounded_box(slide, 6.62, 5.64, 2.04, 0.34, fill_hex=top_tint, border_hex=pal.s4, border_pt=0.75, radius=0.28)
        add_box_text(slide, 6.64, 5.64, 2.00, 0.34, tag_r, size_pt=14.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)


def _build_pain_points_left_arrows(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    pts = spec.pain_points or [f"{ins.heading}：{ins.body}" for ins in spec.insights[:3]]
    n = min(3, max(2, len(pts)))
    row_h = min(1.42, (4.58 - 0.14 * (n - 1)) / n)
    for idx, pt in enumerate(pts[:n]):
        ry = 1.54 + idx * (row_h + 0.14)
        c_head, c_body = split_card_head_body(pt, f"关键痛点 0{idx + 1}")
        add_rounded_box(slide, 0.40, ry, 5.06, row_h, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rounded_box(slide, 0.40, ry, 5.06, 0.34, fill_hex=pal.s1 if idx % 2 == 0 else pal.s2, border_hex=None, radius=0.06)
        add_box_text(slide, 0.54, ry, 4.78, 0.34, c_head, size_pt=14.0, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.54, ry + 0.38, 4.34, row_h - 0.44, c_body, size_pt=14.0, color_hex=pal.ink, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        cy_arr = ry + 0.34 + (row_h - 0.34) * 0.5 - 0.16
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(4.98), Inches(cy_arr), Inches(0.34), Inches(0.34))
        circ.fill.solid()
        circ.fill.fore_color.rgb = _rgb(pal.s1)
        circ.line.fill.background()
        add_box_text(slide, 4.98, cy_arr, 0.34, 0.34, "→", size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    add_rounded_box(slide, 5.66, 1.54, 7.27, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, shadow=True)
    add_chamfered_header_tab(slide, 7.46, 1.42, 3.68, 0.30, "关键科学问题与微界面机制", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    # Top dashed problem callout strip inside right frame
    add_rounded_box(slide, 5.82, 1.78, 6.94, 0.42, fill_hex=blend_with_white(pal.s6, 0.35), border_hex=pal.s3, border_pt=0.75, dashed=True, radius=0.10)
    add_box_text(slide, 5.92, 1.78, 6.74, 0.42, f"核心瓶颈：{spec.takeaway[:36]}", size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.pain_points_left_arrows), ea_font=ea_f, latin_font=lat_f)

    chips = spec.figure_chips or ["限域调控", "低能垒", "高选择性", "定量互证"]
    cw = 6.94 / max(len(chips[:4]), 1)
    for idx, ch in enumerate(chips[:4]):
        cx = 5.82 + idx * cw
        add_rounded_box(slide, cx + 0.04, 5.18, cw - 0.08, 0.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.14, shadow=True)
        add_rect(slide, cx + 0.12, 5.26, 0.06, 0.22, fill_hex=pal.s1 if idx % 2 == 0 else pal.s2)
        add_box_text(slide, cx + 0.18, 5.18, cw - 0.24, 0.38, ch, size_pt=14.0, bold=True, color_hex=pal.ink, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    note = spec.figure_bottom_note or spec.takeaway
    add_box_text(slide, 5.82, 5.64, 6.94, 0.40, note, size_pt=14.0, bold=True, color_hex=pal.alert, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)


def _build_fig_left_3step_chain(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    add_rounded_box(slide, 0.40, 1.54, 7.76, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.05, shadow=True)
    add_chamfered_header_tab(slide, 2.28, 1.41, 4.00, 0.30, spec.section_name[:16] or "多尺度表征与实验验证", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.fig_left_3step_chain), ea_font=ea_f, latin_font=lat_f)

    chain = spec.right_chain or [{"title": ins.heading, "body": ins.body} for ins in spec.insights[:3]]
    soft_tint = blend_with_white(pal.s1, 0.90)
    for idx, item in enumerate(chain[:3]):
        ry = 1.56 + idx * 1.56
        add_rounded_box(slide, 8.34, ry, 1.24, 1.24, fill_hex=pal.s1 if idx % 2 == 0 else pal.s2, border_hex=None, radius=0.08)
        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.78), Inches(ry + 0.12), Inches(0.36), Inches(0.34))
        badge.fill.solid()
        badge.fill.fore_color.rgb = _rgb("#FFFFFF")
        badge.line.fill.background()
        add_box_text(slide, 8.78, ry + 0.12, 0.36, 0.34, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 8.38, ry + 0.50, 1.16, 0.68, item.get("title", f"阶段 {idx+1}"), size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

        add_rounded_box(slide, 9.66, ry, 3.27, 1.24, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.08, shadow=True)
        add_rect(slide, 9.66, ry + 0.10, 0.06, 1.04, fill_hex=soft_tint)
        add_box_text(slide, 9.78, ry + 0.08, 3.04, 1.08, item.get("body", ""), size_pt=14.0, color_hex=pal.ink, line_spacing=1.08, ea_font=ea_f, latin_font=lat_f)
        if idx < 2:
            arr = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(10.50), Inches(ry + 1.27), Inches(0.32), Inches(0.26))
            arr.fill.solid()
            arr.fill.fore_color.rgb = _rgb(pal.s2)
            arr.line.fill.background()


def _build_vs_center_wing(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    l_cards = spec.left_cards or [{"heading": ins.heading or "传统路径", "body": ins.body} for ins in spec.insights[:2]]
    r_cards = spec.right_chain or [{"title": k.label, "body": k.value} for k in spec.kpis[:2]] or [{"title": "核心优势", "body": spec.takeaway}]

    for idx, lc in enumerate(l_cards[:2]):
        cy = 1.58 + idx * 2.26
        add_rounded_box(slide, 0.40, cy, 3.12, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rounded_box(slide, 0.40, cy, 3.12, 0.36, fill_hex=pal.s2, border_hex=None, radius=0.06)
        add_box_text(slide, 0.48, cy, 2.96, 0.36, lc.get("heading", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.54, cy + 0.44, 2.84, 1.54, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, line_spacing=1.10, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        arr_l = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(3.55), Inches(cy + 0.90), Inches(0.18), Inches(0.26))
        arr_l.fill.solid()
        arr_l.fill.fore_color.rgb = _rgb(pal.s2)
        arr_l.line.fill.background()

    add_rounded_box(slide, 3.76, 1.54, 5.80, 4.58, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 4.96, 1.40, 3.40, 0.30, "核心结构与机制对比", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.vs_center_wing), ea_font=ea_f, latin_font=lat_f)
    add_rounded_box(slide, 4.06, 5.62, 5.20, 0.38, fill_hex=blend_with_white(pal.s6, 0.35), border_hex=pal.s4, border_pt=0.75, radius=0.24)
    add_box_text(slide, 4.16, 5.62, 5.00, 0.38, "⇄  结构演进与定量性能双向印证", size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    for idx, rc in enumerate(r_cards[:2]):
        cy = 1.58 + idx * 2.26
        add_rounded_box(slide, 9.81, cy, 3.12, 2.08, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rounded_box(slide, 9.81, cy, 3.12, 0.36, fill_hex=pal.s1, border_hex=None, radius=0.06)
        add_box_text(slide, 9.89, cy, 2.96, 0.36, rc.get("title", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.95, cy + 0.44, 2.84, 1.54, rc.get("body", ""), size_pt=14.0, color_hex=pal.ink, line_spacing=1.10, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        arr_r = slide.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(9.59), Inches(cy + 0.90), Inches(0.18), Inches(0.26))
        arr_r.fill.solid()
        arr_r.fill.fore_color.rgb = _rgb(pal.s1)
        arr_r.line.fill.background()


def _build_roadmap_layered_matrix(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    rows_geom = [
        (1.52, 1.30, "研究目标"),
        (2.94, 1.82, "技术路线"),
        (4.88, 1.24, "核心指标"),
    ]
    for ry, rh, tag in rows_geom:
        add_rounded_box(slide, 0.40, ry, 0.82, rh, fill_hex=pal.s1, border_hex=None, radius=0.08)
        add_box_text(slide, 0.42, ry, 0.78, rh, tag, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_rounded_box(slide, 1.30, ry, 7.58, rh, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)

    # Row 1: 3 Horizontal Process Cards
    row1_items = spec.insights[:3] or [InsightItem(index="01", heading="目标聚焦", body=spec.takeaway[:24])]
    for idx, ins in enumerate(row1_items):
        cx = 1.42 + idx * 2.48
        add_rounded_box(slide, cx, 1.62, 2.26, 1.10, fill_hex=blend_with_white(pal.s6, 0.40), border_hex="#D6E0EC", border_pt=0.75, radius=0.06)
        add_rounded_box(slide, cx + 0.08, 1.68, 2.10, 0.30, fill_hex=pal.s1 if idx == 0 else pal.s2, border_hex=None, radius=0.10)
        add_box_text(slide, cx + 0.12, 1.68, 2.02, 0.30, f"{ins.index} {ins.heading[:8]}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.08, 2.02, 2.10, 0.64, ins.body[:26], size_pt=14.0, color_hex=pal.ink, line_spacing=1.05, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        if idx < len(row1_items) - 1:
            arr = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(cx + 2.29), Inches(2.06), Inches(0.16), Inches(0.22))
            arr.fill.solid()
            arr.fill.fore_color.rgb = _rgb(pal.s1)
            arr.line.fill.background()

    # Row 2: Left structure box + Right 2-step experimental flow blocks
    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.roadmap_layered_matrix), ea_font=ea_f, latin_font=lat_f)
    wf_steps = [
        ("设计合成与骨架修饰", spec.insights[0].body[:22] if spec.insights else "构建代表分子与路线"),
        ("表征验证与性能评估", spec.insights[-1].body[:22] if spec.insights else "活性、选择性与构象"),
    ]
    for idx, (wt, wb) in enumerate(wf_steps):
        wy = 3.04 + idx * 0.94
        add_rounded_box(slide, 5.22, wy, 3.52, 0.68, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=0.85, radius=0.08)
        add_rect(slide, 5.28, wy + 0.08, 0.06, 0.52, fill_hex=pal.s1 if idx == 0 else pal.s2)
        add_box_text(slide, 5.42, wy + 0.04, 3.24, 0.30, wt, size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 5.42, wy + 0.34, 3.24, 0.30, wb, size_pt=14.0, color_hex=pal.muted, ea_font=ea_f, latin_font=lat_f)
        if idx == 0:
            da = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(6.88), Inches(wy + 0.71), Inches(0.22), Inches(0.20))
            da.fill.solid()
            da.fill.fore_color.rgb = _rgb(pal.s2)
            da.line.fill.background()

    # Row 3: 3 Metric / Deliverable Badges
    row3_kpis = (
        [(k.value, k.label, pal.token(k.color_token)) for k in spec.kpis[:3]]
        if spec.kpis
        else [(ins.highlight or ins.heading[:8], ins.heading[:12], pal.s1 if i % 2 == 0 else pal.s2) for i, ins in enumerate(spec.insights[:3])]
    )
    if not row3_kpis:
        row3_kpis = [("目标达成", "阶段验证", pal.s1)]
    r3_w = 7.34 / max(len(row3_kpis), 1) - 0.10
    for idx, (mv, ml, mc) in enumerate(row3_kpis[:3]):
        mx = 1.42 + idx * (r3_w + 0.14)
        add_rounded_box(slide, mx, 4.98, r3_w, 1.04, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06)
        add_rect(slide, mx + 0.02, 5.00, r3_w - 0.04, 0.06, fill_hex=mc)
        add_box_text(slide, mx + 0.08, 5.10, r3_w - 0.16, 0.44, str(mv)[:12], size_pt=18.0, bold=True, color_hex=mc, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, mx + 0.08, 5.56, r3_w - 0.16, 0.36, str(ml)[:14], size_pt=14.0, color_hex=pal.ink, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    # Right vertical milestone flow
    add_rounded_box(slide, 9.06, 1.54, 3.87, 4.58, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 9.72, 1.39, 2.55, 0.30, "闭环实施与转化路径", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    nodes = spec.right_chain or [{"title": ins.heading, "body": ""} for ins in spec.insights[:3]] + [{"title": "定量成果产出", "body": ""}]
    for idx, nd in enumerate(nodes[:4]):
        ny = 1.94 + idx * 1.04
        is_last = idx == min(len(nodes[:4]), 4) - 1
        add_rounded_box(slide, 9.26, ny, 3.47, 0.72, fill_hex=pal.s1 if is_last else "#FFFFFF", border_hex=pal.s1 if is_last else "#D6E0EC", border_pt=0.85, radius=0.45, shadow=True)
        num_bg = "#FFFFFF" if is_last else pal.s1
        num_fg = pal.s1 if is_last else "#FFFFFF"
        nc = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.38), Inches(ny + 0.17), Inches(0.38), Inches(0.38))
        nc.fill.solid()
        nc.fill.fore_color.rgb = _rgb(num_bg)
        nc.line.fill.background()
        add_box_text(slide, 9.38, ny + 0.17, 0.38, 0.38, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=num_fg, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.84, ny, 2.76, 0.72, nd.get("title", ""), size_pt=14.0, bold=True, color_hex="#FFFFFF" if is_last else pal.ink, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        if not is_last:
            da_r = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(10.88), Inches(ny + 0.75), Inches(0.24), Inches(0.24))
            da_r.fill.solid()
            da_r.fill.fore_color.rgb = _rgb(pal.s2)
            da_r.line.fill.background()


def _build_timeline_chevron_flow(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    steps = (spec.chevron_steps[:4] if spec.chevron_steps else [
        f"{ins.index} {ins.heading[:10]}" for ins in spec.insights[:4]
    ]) or ["01 问题提出", "02 分子设计", "03 机理验证", "04 定量突破"]
    while len(steps) < 4:
        steps.append(f"0{len(steps) + 1} 阶段推进")

    stage_colors = [pal.s1, pal.s2, pal.s3, pal.s1]
    for idx, st in enumerate(steps[:4]):
        sx = 0.40 + idx * 3.17
        ch = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(sx), Inches(1.46), Inches(3.02), Inches(0.56))
        ch.fill.solid()
        ch.fill.fore_color.rgb = _rgb(stage_colors[idx])
        ch.line.fill.background()
        ch.name = f"L2_timeline_stage_{idx}"
        add_box_text(
            slide, sx + 0.22, 1.48, 2.58, 0.52, st[:14],
            size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER,
            ea_font=ea_f, latin_font=lat_f, name=f"L3_timeline_stage_{idx}",
        )

    add_rounded_box(slide, 0.40, 2.24, 6.82, 3.88, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, shadow=True)
    add_chamfered_header_tab(slide, 1.91, 2.12, 3.80, 0.30, "核心结构与阶段流程", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.timeline_chevron_flow), ea_font=ea_f, latin_font=lat_f)

    right_items = spec.insights[:3] or [InsightItem(index="01", heading="阶段目标", body=spec.takeaway)]
    for idx, ins in enumerate(right_items[:3]):
        cy = 2.24 + idx * 1.34
        add_rounded_box(slide, 7.42, cy, 5.51, 1.20, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rect(slide, 7.48, cy + 0.12, 0.06, 0.96, fill_hex=pal.s1 if idx != 1 else pal.s2)
        badge_c = pal.s1 if idx != 1 else pal.s2
        nc = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(7.66), Inches(cy + 0.12), Inches(0.34), Inches(0.34))
        nc.fill.solid()
        nc.fill.fore_color.rgb = _rgb(badge_c)
        nc.line.fill.background()
        add_box_text(slide, 7.66, cy + 0.12, 0.34, 0.34, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 8.10, cy + 0.10, 4.68, 0.36, ins.heading, size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 7.66, cy + 0.50, 5.12, 0.62, ins.body, size_pt=14.0, color_hex=pal.ink, line_spacing=1.08, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)


def _build_quadrant_2x2_matrix(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    cards = (spec.left_cards[:4] if len(spec.left_cards) >= 4 else [
        {"heading": ins.heading, "body": ins.body} for ins in spec.insights[:4]
    ])
    defaults = [
        {"heading": "科学假说与立题", "body": spec.takeaway[:36] or "聚焦关键科学痛点与分子切入点。"},
        {"heading": "先导结构优化", "body": "精准调控药效团取代基与理化性质平衡。"},
        {"heading": "作用机制与互证", "body": "结合动力学与结构表征验证结合模式。"},
        {"heading": "定量性能评估", "body": "系统评测活性、选择性与成药性窗口。"},
    ]
    while len(cards) < 4:
        cards.append(defaults[len(cards)])

    for idx, cd in enumerate(cards[:4]):
        col = idx % 2
        row = idx // 2
        cx = 0.40 + col * 3.96
        cy = 1.48 + row * 2.42
        hdr_c = pal.s1 if (row + col) % 2 == 0 else pal.s2
        add_rounded_box(slide, cx, cy, 3.78, 2.22, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rounded_box(slide, cx, cy, 3.78, 0.40, fill_hex=hdr_c, border_hex=None, radius=0.06)
        add_rounded_box(slide, cx + 0.10, cy + 0.06, 0.42, 0.28, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
        add_box_text(slide, cx + 0.10, cy + 0.06, 0.42, 0.28, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex=hdr_c, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.60, cy + 0.02, 3.08, 0.36, cd.get("heading", ""), size_pt=14.5, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.14, cy + 0.48, 3.50, 1.64, cd.get("body", ""), size_pt=14.0, color_hex=pal.ink, line_spacing=1.12, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)

    add_rounded_box(slide, 8.34, 1.48, 4.59, 4.64, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, shadow=True)
    add_chamfered_header_tab(slide, 9.14, 1.35, 3.00, 0.30, "代表分子与定量指标", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.quadrant_2x2_matrix), ea_font=ea_f, latin_font=lat_f)

    kpis = spec.kpis[:2] or [
        {"value": spec.insights[0].highlight or "关键聚焦", "label": spec.insights[0].heading[:10] if spec.insights else "核心指标", "color_token": "s1"},
        {"value": spec.insights[-1].highlight or "定量验证", "label": spec.insights[-1].heading[:10] if spec.insights else "研究优势", "color_token": "s2"},
    ]
    for idx, kp in enumerate(kpis[:2]):
        val = kp.value if hasattr(kp, "value") else kp["value"]
        lbl = kp.label if hasattr(kp, "label") else kp["label"]
        ctok = kp.color_token if hasattr(kp, "color_token") else kp.get("color_token", "s1")
        kx = 8.48 + idx * 2.23
        add_rounded_box(slide, kx, 4.92, 2.08, 1.08, fill_hex=blend_with_white(pal.s6, 0.30), border_hex="#D6E0EC", border_pt=0.75, radius=0.08)
        add_rect(slide, kx + 0.04, 4.94, 2.00, 0.05, fill_hex=pal.token(ctok))
        add_box_text(slide, kx + 0.08, 5.02, 1.92, 0.44, str(val)[:14], size_pt=17.0, bold=True, color_hex=pal.token(ctok), align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, kx + 0.08, 5.48, 1.92, 0.44, str(lbl)[:14], size_pt=14.0, color_hex=pal.ink, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)


def _build_hub_spoke_radial(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    add_rounded_box(slide, 0.40, 1.48, 4.88, 4.64, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 1.54, 1.35, 2.60, 0.30, "核心体系构筑", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    outer = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.76), Inches(1.72), Inches(4.16), Inches(4.16))
    outer.fill.solid()
    outer.fill.fore_color.rgb = _rgb(blend_with_white(pal.s6, 0.35))
    outer.line.color.rgb = _rgb(pal.s4)
    outer.line.width = Pt(1.0)

    mid = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.06), Inches(2.02), Inches(3.56), Inches(3.56))
    mid.fill.solid()
    mid.fill.fore_color.rgb = _rgb("#FFFFFF")
    mid.line.color.rgb = _rgb(pal.s2)
    mid.line.width = Pt(1.5)

    inner = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.35), Inches(2.31), Inches(2.98), Inches(2.98))
    inner.fill.solid()
    inner.fill.fore_color.rgb = _rgb("#FFFFFF")
    inner.line.color.rgb = _rgb(pal.s1)
    inner.line.width = Pt(1.0)
    etree.SubElement(inner.line._get_or_add_ln(), qn("a:prstDash")).set("val", "dash")

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.hub_spoke_radial), ea_font=ea_f, latin_font=lat_f)

    spoke_items = spec.insights[:3] or [InsightItem(index="01", heading="体系协同", body=spec.takeaway)]
    for idx, ins in enumerate(spoke_items[:3]):
        cy = 1.54 + idx * 1.56
        mid_y = cy + 0.69
        add_line(slide, 4.92, mid_y, 5.52, mid_y, color_hex=pal.s2, width_pt=1.4, dashed=True, arrow_end=True)
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(4.84), Inches(mid_y - 0.08), Inches(0.16), Inches(0.16))
        dot.fill.solid()
        dot.fill.fore_color.rgb = _rgb(pal.s1 if idx != 1 else pal.s2)
        dot.line.color.rgb = _rgb("#FFFFFF")
        dot.line.width = Pt(1.2)

        hdr_c = pal.s1 if idx != 1 else pal.s2
        add_rounded_box(slide, 5.52, cy, 7.41, 1.38, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rounded_box(slide, 5.52, cy, 7.41, 0.38, fill_hex=hdr_c, border_hex=None, radius=0.06)
        add_rounded_box(slide, 5.62, cy + 0.05, 0.42, 0.28, fill_hex="#FFFFFF", border_hex=None, radius=0.22)
        add_box_text(slide, 5.62, cy + 0.05, 0.42, 0.28, ins.index, size_pt=14.0, bold=True, color_hex=hdr_c, align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 6.14, cy + 0.02, 6.66, 0.34, ins.heading, size_pt=14.5, bold=True, color_hex="#FFFFFF", ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 5.66, cy + 0.44, 7.12, 0.86, ins.body, size_pt=14.0, color_hex=pal.ink, line_spacing=1.10, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)


def _build_dual_compare_cards(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
    add_rounded_box(slide, 0.40, 1.46, 12.53, 0.56, fill_hex=blend_with_white(pal.s6, 0.35), border_hex="#D6E0EC", border_pt=0.75, radius=0.08, shadow=True)
    add_rect(slide, 0.48, 1.54, 0.08, 0.40, fill_hex=pal.s1)
    add_box_text(slide, 0.66, 1.48, 12.14, 0.52, spec.takeaway or spec.title, size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)

    # Left Column: Conventional / Bottlenecks
    add_rounded_box(slide, 0.40, 2.18, 5.82, 3.94, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_rounded_box(slide, 0.40, 2.18, 5.82, 0.42, fill_hex=pal.s2, border_hex=None, radius=0.06)
    add_box_text(slide, 0.52, 2.20, 5.58, 0.38, "现有方案与研究瓶颈", size_pt=14.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    l_cards = spec.left_cards or [{"heading": i.heading, "body": i.body} for i in spec.insights[:3]]
    for idx, lc in enumerate(l_cards[:3]):
        sy = 2.72 + idx * 1.10
        add_rounded_box(slide, 0.56, sy, 5.50, 0.98, fill_hex=blend_with_white(pal.s6, 0.50), border_hex="#E2E8F0", border_pt=0.75, radius=0.06)
        nc = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.68), Inches(sy + 0.12), Inches(0.30), Inches(0.30))
        nc.fill.solid()
        nc.fill.fore_color.rgb = _rgb(pal.s2)
        nc.line.fill.background()
        add_box_text(slide, 0.68, sy + 0.12, 0.30, 0.30, f"0{idx + 1}", size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 1.06, sy + 0.10, 4.86, 0.34, lc.get("heading", ""), size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 0.68, sy + 0.46, 5.24, 0.46, lc.get("body", ""), size_pt=14.0, color_hex=pal.ink, line_spacing=1.05, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)

    # Center VS Badge + Connectors
    add_line(slide, 6.22, 4.16, 6.35, 4.16, color_hex=pal.s3, width_pt=2.0)
    add_line(slide, 6.98, 4.16, 7.11, 4.16, color_hex=pal.s1, width_pt=2.0)
    vs_circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(6.345), Inches(3.84), Inches(0.64), Inches(0.64))
    vs_circle.fill.solid()
    vs_circle.fill.fore_color.rgb = _rgb(pal.s1)
    vs_circle.line.color.rgb = _rgb("#FFFFFF")
    vs_circle.line.width = Pt(2.0)
    apply_soft_card_shadow(vs_circle)
    add_box_text(slide, 6.345, 3.84, 0.64, 0.64, "VS", size_pt=16.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)

    # Right Column: Our Innovation + Figure + Quantitative Strips
    add_rounded_box(slide, 7.11, 2.18, 5.82, 3.94, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=0.95, radius=0.06, shadow=True)
    add_rounded_box(slide, 7.11, 2.18, 5.82, 0.42, fill_hex=pal.s1, border_hex=None, radius=0.06)
    add_box_text(slide, 7.23, 2.20, 5.58, 0.38, "本研究突破与分子验证", size_pt=14.5, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
    add_rounded_box(slide, 7.27, 2.74, 5.50, 2.28, fill_hex="#FFFFFF", border_hex="#E2E8F0", border_pt=0.75, radius=0.05)

    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.dual_compare_cards), ea_font=ea_f, latin_font=lat_f)

    r_cards = spec.right_chain or [{"title": k.value, "body": k.label} for k in spec.kpis[:2]] or [
        {"title": spec.insights[-1].highlight or "关键突破", "body": spec.insights[-1].heading if spec.insights else "选择性提升"}
    ]
    for idx, rc in enumerate(r_cards[:2]):
        rx = 7.27 + idx * 2.84
        add_rounded_box(slide, rx, 5.12, 2.66, 0.88, fill_hex=blend_with_white(pal.s6, 0.30), border_hex="#D6E0EC", border_pt=0.75, radius=0.06)
        add_rect(slide, rx + 0.06, 5.20, 0.06, 0.72, fill_hex=pal.s1 if idx == 0 else pal.s2)
        add_box_text(slide, rx + 0.18, 5.16, 2.38, 0.38, str(rc.get("title", ""))[:14], size_pt=15.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, rx + 0.18, 5.54, 2.38, 0.38, str(rc.get("body", ""))[:18], size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)


def _build_tri_column_showcase(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, figure_renderer: Callable) -> None:
    ea_f, lat_f = _fonts(deck)
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
        accent = pal.s1 if idx != 1 else pal.s2
        add_rounded_box(slide, cx, 1.48, 3.96, 1.62, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
        add_rect(slide, cx + 0.02, 1.50, 3.92, 0.07, fill_hex=accent)
        nc = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx + 0.14), Inches(1.64), Inches(0.32), Inches(0.32))
        nc.fill.solid()
        nc.fill.fore_color.rgb = _rgb(accent)
        nc.line.fill.background()
        add_box_text(slide, cx + 0.14, 1.64, 0.32, 0.32, ins.index, size_pt=14.0, bold=True, color_hex="#FFFFFF", align=PP_ALIGN.CENTER, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.54, 1.62, 3.28, 0.36, ins.heading, size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, cx + 0.14, 2.04, 3.68, 0.98, ins.body, size_pt=14.0, color_hex=pal.ink, line_spacing=1.10, anchor=MSO_ANCHOR.TOP, ea_font=ea_f, latin_font=lat_f)
        if idx < 2:
            ch = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(cx + 4.02), Inches(2.15), Inches(0.21), Inches(0.28))
            ch.fill.solid()
            ch.fill.fore_color.rgb = _rgb(pal.s2)
            ch.line.fill.background()

    add_rounded_box(slide, 0.40, 3.34, 8.22, 2.78, fill_hex="#FFFFFF", border_hex=pal.s3, border_pt=1.0, dashed=True, radius=0.05, shadow=True)
    add_chamfered_header_tab(slide, 2.71, 3.21, 3.60, 0.30, "分子结构与机制示意", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)
    if spec.figure_spec:
        figure_renderer(slide, spec.figure_spec, pal, override_box=get_v5_figure_box(LayoutId.tri_column_showcase), ea_font=ea_f, latin_font=lat_f)

    add_rounded_box(slide, 8.82, 3.34, 4.11, 2.78, fill_hex="#FFFFFF", border_hex="#D6E0EC", border_pt=0.75, radius=0.06, shadow=True)
    add_chamfered_header_tab(slide, 9.58, 3.21, 2.60, 0.30, "核心结论与指标", fill_hex=pal.s1, ea_font=ea_f, latin_font=lat_f)

    right_rows = (
        [{"title": k.value, "body": k.label} for k in spec.kpis[:2]]
        if spec.kpis
        else [{"title": ins.highlight or ins.heading[:10], "body": ins.heading[:14]} for ins in spec.insights[:2]]
    )
    for idx, rr in enumerate(right_rows[:2]):
        ky = 3.64 + idx * 1.24
        col = pal.s1 if idx == 0 else pal.s2
        add_rounded_box(slide, 8.98, ky, 3.79, 1.10, fill_hex=blend_with_white(pal.s6, 0.38), border_hex="#D6E0EC", border_pt=0.75, radius=0.06)
        add_rect(slide, 9.04, ky + 0.12, 0.06, 0.86, fill_hex=col)
        add_box_text(slide, 9.18, ky + 0.10, 3.48, 0.42, str(rr.get("title", ""))[:16], size_pt=16.5, bold=True, color_hex=col, ea_font=ea_f, latin_font=lat_f)
        add_box_text(slide, 9.18, ky + 0.54, 3.48, 0.48, str(rr.get("body", ""))[:20], size_pt=14.0, color_hex=pal.ink, ea_font=ea_f, latin_font=lat_f)


_V5_DISPATCH = {
    LayoutId.lit_overview_dual_card: _build_lit_overview_dual_card,
    LayoutId.mechanism_3col_flow: _build_mechanism_3col_flow,
    LayoutId.data_dashboard_table: _build_data_dashboard_table,
    LayoutId.bg_top_summary_3box: _build_bg_top_summary_3box,
    LayoutId.pain_points_left_arrows: _build_pain_points_left_arrows,
    LayoutId.fig_left_3step_chain: _build_fig_left_3step_chain,
    LayoutId.vs_center_wing: _build_vs_center_wing,
    LayoutId.roadmap_layered_matrix: _build_roadmap_layered_matrix,
    LayoutId.timeline_chevron_flow: _build_timeline_chevron_flow,
    LayoutId.quadrant_2x2_matrix: _build_quadrant_2x2_matrix,
    LayoutId.hub_spoke_radial: _build_hub_spoke_radial,
    LayoutId.dual_compare_cards: _build_dual_compare_cards,
    LayoutId.tri_column_showcase: _build_tri_column_showcase,
}


def build_v5_content_slide(
    slide,
    spec: SlideSpec,
    deck: DeckSpec,
    pal: ScientificPalette,
    total_slides: int,
    figure_renderer: Callable,
) -> bool:
    """Build any of the 8 v5.0 pure-white elevated layouts cleanly. Returns True if handled."""
    builder = _V5_DISPATCH.get(spec.layout_id)
    if builder is None:
        return False
    add_v5_header(slide, spec, deck, pal, total_slides)
    builder(slide, spec, deck, pal, figure_renderer)
    add_v5_bottom_banner(slide, spec, deck, pal)
    return True
