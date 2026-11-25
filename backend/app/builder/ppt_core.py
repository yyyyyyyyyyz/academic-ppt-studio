"""Native python-pptx Compiler (v4.0) — 100% Atomic 3-Layer Editable Output.

Compiles DeckSpec JSON + rendered Layer 1 publication figures into native editable .pptx:
- Layer 1: Independent transparent PNGs (600 DPI)
- Layer 2: Native AutoShapes / Connectors / Bitangent Zoom-Lens Lines / 3pt Accent Bars
- Layer 3: Native TextBoxes & Three-Line Tables (XML dual-font + baseline sub/sup + >=18pt body)
- Speaker notes offloaded cleanly to slide.notes_slide
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree

from ..figure_factory.palettes import ScientificPalette, get_palette, hex_to_rgb
from ..figure_factory.vector_mech import compute_external_bitangents
from ..schemas.deck_spec import (
    DeckSpec,
    DesignStyle,
    EngineType,
    FigureAsset,
    FigureBoxIn,
    FigureSpec,
    LayoutId,
    NativeOverlay,
    SlideSpec,
    SlideType,
)
from .native_visuals import (
    add_native_chemdraw_group,
    add_native_cylview3d_group,
    add_native_origin_chart,
    add_native_vector_mech_group,
    compute_shared_chemdraw_scale,
)
from .xml_utils import (
    apply_three_line_table_borders,
    bind_xml_dual_font,
    configure_zero_fill_textbox,
    populate_paragraph,
)
from .v5_covers import build_v5_closing_slide, build_v5_cover_slide, build_v5_part_divider_slide
from .v5_layouts import build_v5_content_slide, build_v5_toc_slide


def _rgb(hex_str: str) -> RGBColor:
    r, g, b = hex_to_rgb(hex_str)
    return RGBColor(r, g, b)


def _set_white_slide_background(slide) -> None:
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(255, 255, 255)


def _add_native_line(
    slide,
    x1_in: float,
    y1_in: float,
    x2_in: float,
    y2_in: float,
    color_hex: str,
    width_pt: float = 0.75,
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
        prst = etree.SubElement(ln, qn("a:prstDash"))
        prst.set("val", "dash")
    if arrow_end:
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    return conn


def _add_native_textbox(
    slide,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    text: str,
    size_pt: float = 18.0,
    bold: bool = False,
    color_hex: str = "#162032",
    highlight_phrase: Optional[str] = None,
    highlight_color_hex: Optional[str] = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    line_spacing: float = 1.5,
    anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
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


def _add_picture_fit(
    slide,
    png_path: Path,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    locked_phys_w_in: Optional[float] = None,
    locked_phys_h_in: Optional[float] = None,
    name: Optional[str] = None,
) -> None:
    if not png_path.exists():
        return
    with Image.open(png_path) as im:
        pw, ph = im.size
    if pw <= 0 or ph <= 0:
        return

    aspect = pw / ph
    if locked_phys_w_in and locked_phys_h_in and locked_phys_w_in <= width_in and locked_phys_h_in <= height_in:
        draw_w = locked_phys_w_in
        draw_h = locked_phys_h_in
    else:
        if width_in / max(height_in, 1e-4) > aspect:
            draw_h = height_in
            draw_w = draw_h * aspect
        else:
            draw_w = width_in
            draw_h = draw_w / aspect

    cx = left_in + 0.5 * (width_in - draw_w)
    cy = top_in + 0.5 * (height_in - draw_h)
    pic = slide.shapes.add_picture(str(png_path), Inches(cx), Inches(cy), width=Inches(draw_w), height=Inches(draw_h))
    if name:
        pic.name = name


def _remap_pt(pt: List[float], src: FigureBoxIn, dst: FigureBoxIn) -> List[float]:
    if len(pt) < 2:
        return pt
    nx = (pt[0] - src.left) / max(src.width, 1e-4)
    ny = (pt[1] - src.top) / max(src.height, 1e-4)
    return [dst.left + nx * dst.width, dst.top + ny * dst.height]


def _render_figure_layer(
    slide,
    fig_spec: FigureSpec,
    pal: ScientificPalette,
    override_box: Optional[FigureBoxIn] = None,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> None:
    src_box = fig_spec.box_in
    box = override_box or src_box
    scale_x = box.width / max(src_box.width, 1e-4)
    scale_y = box.height / max(src_box.height, 1e-4)
    lbl_pt = 14.0
    shared_mol_scale = compute_shared_chemdraw_scale(fig_spec.assets, box)

    # Layer 1: 100% Native Editable Figures / Charts / Molecule Groups (+ transparent uploaded/3D photo assets)
    for asset in fig_spec.assets:
        nb = asset.norm_box if len(asset.norm_box) == 4 else [0.0, 0.0, 1.0, 1.0]
        a_left = box.left + nb[0] * box.width
        a_top = box.top + nb[1] * box.height
        a_w = nb[2] * box.width
        a_h = nb[3] * box.height
        fig_h = (a_h - 0.36) if (asset.label and (nb[1] + nb[3] > 0.90) and a_h > 1.0) else a_h

        if asset.engine == EngineType.origin_plot:
            add_native_origin_chart(
                slide, asset, a_left, a_top, a_w, fig_h, pal,
                latin_font=latin_font, ea_font=ea_font,
            )
        elif asset.engine == EngineType.chemdraw_rdkit:
            add_native_chemdraw_group(
                slide, asset, a_left, a_top, a_w, fig_h, pal,
                latin_font=latin_font, ea_font=ea_font, scale_in_per_unit=shared_mol_scale,
            )
        elif asset.engine == EngineType.cylview_3d:
            if asset.png_path and Path(asset.png_path).is_file():
                _add_picture_fit(
                    slide,
                    Path(asset.png_path),
                    left_in=a_left,
                    top_in=a_top,
                    width_in=a_w,
                    height_in=fig_h,
                    name=f"L1_{asset.asset_id}",
                )
            else:
                add_native_cylview3d_group(slide, asset, a_left, a_top, a_w, fig_h, pal)
        elif asset.engine == EngineType.vector_mech:
            add_native_vector_mech_group(
                slide, asset, a_left, a_top, a_w, fig_h, pal,
                latin_font=latin_font, ea_font=ea_font,
            )
        else:
            if not asset.png_path:
                continue
            p = Path(asset.png_path)
            if not p.exists():
                continue
            _add_picture_fit(
                slide,
                p,
                left_in=a_left,
                top_in=a_top,
                width_in=a_w,
                height_in=fig_h,
                name=f"L1_{asset.asset_id}",
            )

        if asset.label:
            lbl_top = (a_top + a_h + 0.02) if (nb[1] + nb[3] <= 0.90) else (a_top + a_h - 0.34)
            _add_native_textbox(
                slide,
                left_in=a_left,
                top_in=lbl_top,
                width_in=a_w,
                height_in=0.34,
                text=asset.label,
                size_pt=lbl_pt,
                bold=True,
                color_hex=pal.ink,
                align=PP_ALIGN.CENTER,
                line_spacing=1.10,
                name=f"L3_asset_lbl_{asset.asset_id}",
                ea_font=ea_font,
                latin_font=latin_font,
            )

    # Layer 2: Native editable vector overlays (zoom lens bitangents, arrows, badges)
    for idx, ov in enumerate(fig_spec.native_overlays):
        col = pal.token(ov.color_token)
        if ov.type == "zoom_lens_frame" and ov.source_circle_in and ov.target_circle_in:
            s_xy = _remap_pt(ov.source_circle_in[:2], src_box, box)
            t_xy = _remap_pt(ov.target_circle_in[:2], src_box, box)
            r_scale = min(scale_x, scale_y)
            s_cx, s_cy, s_r = s_xy[0], s_xy[1], ov.source_circle_in[2] * r_scale
            t_cx, t_cy, t_r = t_xy[0], t_xy[1], ov.target_circle_in[2] * r_scale

            # Dashed source circle
            c_src = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(s_cx - s_r), Inches(s_cy - s_r), Inches(2 * s_r), Inches(2 * s_r),
            )
            c_src.fill.background()
            c_src.line.color.rgb = _rgb(col)
            c_src.line.width = Pt(1.5)
            ln_s = c_src.line._get_or_add_ln()
            etree.SubElement(ln_s, qn("a:prstDash")).set("val", "dash")
            c_src.name = f"L2_zoom_src_{idx}"

            # Crisp enlarged target lens frame
            c_tgt = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(t_cx - t_r), Inches(t_cy - t_r), Inches(2 * t_r), Inches(2 * t_r),
            )
            c_tgt.fill.background()
            c_tgt.line.color.rgb = _rgb(col)
            c_tgt.line.width = Pt(2.0)
            c_tgt.name = f"L2_zoom_tgt_{idx}"

            # Exact external bitangents
            for p1, p2 in compute_external_bitangents((s_cx, s_cy, s_r), (t_cx, t_cy, t_r)):
                _add_native_line(slide, p1[0], p1[1], p2[0], p2[1], color_hex=col, width_pt=1.25, dashed=True)

        elif ov.type in ("arrow", "dashed_connector", "reaction_arrow") and ov.from_in and ov.to_in:
            f_pt = _remap_pt(ov.from_in, src_box, box)
            t_pt = _remap_pt(ov.to_in, src_box, box)
            _add_native_line(
                slide,
                f_pt[0], f_pt[1], t_pt[0], t_pt[1],
                color_hex=col,
                width_pt=2.2 if ov.type == "reaction_arrow" else 1.5,
                dashed=(ov.type == "dashed_connector" or "dashed" in ov.style),
                arrow_end=(ov.type != "divider"),
            )
            if ov.label:
                if ov.type == "reaction_arrow":
                    parts = [p.strip() for p in ov.label.split("|", 1)]
                    top_lbl = parts[0]
                    bot_lbl = parts[1] if len(parts) > 1 else ""
                    span_w = abs(t_pt[0] - f_pt[0])
                    pill_w = min(1.30, max(1.04, span_w + 0.28))
                    cx_a = 0.5 * (f_pt[0] + t_pt[0])
                    cy_a = 0.5 * (f_pt[1] + t_pt[1])
                    pill = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(cx_a - pill_w * 0.5), Inches(cy_a - 0.36), Inches(pill_w), Inches(0.28),
                    )
                    pill.name = f"L2_overlay_pill_{idx}"
                    try:
                        pill.adjustments[0] = 0.45
                    except Exception:
                        pass
                    pill.fill.solid()
                    pill.fill.fore_color.rgb = _rgb("#FFFFFF")
                    pill.line.color.rgb = _rgb(col)
                    pill.line.width = Pt(0.85)
                    _add_native_textbox(
                        slide, cx_a - pill_w * 0.5, cy_a - 0.36, pill_w, 0.28,
                        text=top_lbl, size_pt=14.0, bold=True, color_hex=col,
                        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
                        name=f"L3_overlay_lbl_{idx}", ea_font=ea_font, latin_font=latin_font,
                    )
                    if bot_lbl:
                        _add_native_textbox(
                            slide, cx_a - pill_w * 0.5, cy_a + 0.10, pill_w, 0.26,
                            text=bot_lbl, size_pt=14.0, bold=True, color_hex=pal.s2,
                            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
                            name=f"L3_overlay_sub_{idx}", ea_font=ea_font, latin_font=latin_font,
                        )
                else:
                    mx = 0.5 * (f_pt[0] + t_pt[0]) - 0.95
                    my = min(f_pt[1], t_pt[1]) - 0.38
                    _add_native_textbox(
                        slide, mx, my, 1.90, 0.32,
                        text=ov.label, size_pt=14.0, bold=True, color_hex=col,
                        align=PP_ALIGN.CENTER, line_spacing=1.1, name=f"L3_overlay_lbl_{idx}",
                        ea_font=ea_font, latin_font=latin_font,
                    )

        elif ov.type == "pocket_subsite":
            if ov.source_circle_in:
                s_xy = _remap_pt(ov.source_circle_in[:2], src_box, box)
                r_scale = min(scale_x, scale_y)
                sr = ov.source_circle_in[2] * r_scale
                arc = slide.shapes.add_shape(
                    MSO_SHAPE.OVAL,
                    Inches(s_xy[0] - sr), Inches(s_xy[1] - sr), Inches(2 * sr), Inches(2 * sr),
                )
                arc.fill.background()
                arc.line.color.rgb = _rgb(col)
                arc.line.width = Pt(1.0)
                ln_p = arc.line._get_or_add_ln()
                etree.SubElement(ln_p, qn("a:prstDash")).set("val", "dash")
                arc.name = f"L2_pocket_{idx}"
                if ov.label:
                    _add_native_textbox(
                        slide, s_xy[0] - 0.52, s_xy[1] - sr - 0.22, 1.04, 0.22,
                        text=ov.label, size_pt=10.5, bold=True, color_hex=col,
                        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
                        name=f"L3_pocket_lbl_{idx}", ea_font=ea_font, latin_font=latin_font,
                    )
            if ov.from_in and ov.to_in:
                f_pt = _remap_pt(ov.from_in, src_box, box)
                t_pt = _remap_pt(ov.to_in, src_box, box)
                _add_native_line(slide, f_pt[0], f_pt[1], t_pt[0], t_pt[1], color_hex=col, width_pt=1.35, dashed=True, arrow_end=True)
                dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(f_pt[0] - 0.045), Inches(f_pt[1] - 0.045), Inches(0.09), Inches(0.09))
                dot.fill.solid()
                dot.fill.fore_color.rgb = _rgb(col)
                dot.line.color.rgb = _rgb("#FFFFFF")
                dot.line.width = Pt(0.8)
                dot.name = f"L2_pocket_dot_{idx}"
                if ov.sublabel:
                    _add_native_textbox(
                        slide, f_pt[0] - 0.65, f_pt[1] - 0.26, 1.30, 0.22,
                        text=ov.sublabel, size_pt=10.5, bold=True, color_hex=col,
                        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0,
                        name=f"L3_pocket_lbl_{idx}", ea_font=ea_font, latin_font=latin_font,
                    )

        elif ov.type == "badge_label" and ov.pos_in and ov.label:
            p_pt = _remap_pt(ov.pos_in, src_box, box)
            _add_native_textbox(
                slide, p_pt[0], p_pt[1], 1.7, 0.34,
                text=ov.label, size_pt=14.0, bold=True, color_hex=col,
                align=PP_ALIGN.CENTER, line_spacing=1.1, name=f"L3_overlay_lbl_{idx}",
                ea_font=ea_font, latin_font=latin_font,
            )

        elif ov.type == "contrast_check" and ov.pos_in:
            p_pt = _remap_pt(ov.pos_in, src_box, box)
            mark = "✓" if ov.status == "pass" else "×"
            mark_col = pal.s1 if ov.status == "pass" else pal.alert
            txt = f"{mark} {ov.label or ''}".strip()
            _add_native_textbox(
                slide, p_pt[0], p_pt[1], 2.5, 0.36,
                text=txt, size_pt=14.5, bold=True, color_hex=mark_col, line_spacing=1.15,
                name=f"L3_overlay_lbl_{idx}",
                ea_font=ea_font, latin_font=latin_font,
            )


def _add_content_header_and_footer(
    slide,
    spec: SlideSpec,
    deck: DeckSpec,
    pal: ScientificPalette,
    total_slides: int,
) -> None:
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    # Optional top progress segments for medium/long decks (>=11 slides)
    if total_slides >= 11:
        seg_w = 12.40 / total_slides
        for idx in range(total_slides):
            bar = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(0.46 + idx * seg_w), Inches(0.08),
                Inches(max(0.04, seg_w - 0.03)), Inches(0.045),
            )
            bar.line.fill.background()
            bar.fill.solid()
            bar.fill.fore_color.rgb = _rgb(pal.s1 if idx + 1 == spec.slide_no else (pal.s4 if idx + 1 < spec.slide_no else pal.line))

    # Eyebrow + Page Number (Spec Section 2.2)
    _add_native_textbox(
        slide, 0.46, 0.23, 8.50, 0.26,
        text=spec.eyebrow, size_pt=14.25, bold=True, color_hex=pal.s3, line_spacing=1.0, name="L3_eyebrow",
        ea_font=ea_font, latin_font=latin_font,
    )
    _add_native_textbox(
        slide, 11.60, 0.23, 1.27, 0.26,
        text=f"{spec.slide_no:02d} / {total_slides:02d}", size_pt=14.25, bold=True, color_hex=pal.muted,
        align=PP_ALIGN.RIGHT, line_spacing=1.0, name="L3_page_num",
        ea_font=ea_font, latin_font=latin_font,
    )
    # Main Title (24-26pt 微软雅黑 Bold)
    _add_native_textbox(
        slide, 0.46, 0.52, 12.40, 0.46,
        text=spec.title, size_pt=24.0, bold=True, color_hex=pal.s1, line_spacing=1.1, name="L3_title",
        ea_font=ea_font, latin_font=latin_font,
    )
    # Takeaway (18pt 微软雅黑)
    if spec.takeaway:
        _add_native_textbox(
            slide, 0.46, 1.03, 12.40, 0.38,
            text=spec.takeaway, size_pt=18.0, bold=False, color_hex="#334155", line_spacing=1.2, name="L3_takeaway",
            ea_font=ea_font, latin_font=latin_font,
        )
    # Dual-thickness minimal header line (T=1.48)
    _add_native_line(slide, 0.46, 1.48, 1.71, 1.48, color_hex=pal.s1, width_pt=2.5)
    _add_native_line(slide, 1.71, 1.48, 12.86, 1.48, color_hex=pal.line, width_pt=0.75)

    # Bottom minimal footer (T=6.94 line + T=7.02 text)
    _add_native_line(slide, 0.46, 6.94, 12.86, 6.94, color_hex=pal.line, width_pt=0.75)
    _add_native_textbox(
        slide, 0.46, 7.02, 8.20, 0.32,
        text=spec.footer_left, size_pt=14.0, bold=False, color_hex=pal.muted, line_spacing=1.0, name="L3_footer_left",
        ea_font=ea_font, latin_font=latin_font,
    )
    _add_native_textbox(
        slide, 9.10, 7.02, 3.76, 0.32,
        text=f"{deck.meta.affiliation} · {pal.id.upper()}", size_pt=14.0, bold=False, color_hex=pal.muted,
        align=PP_ALIGN.RIGHT, line_spacing=1.0, name="L3_footer_right",
        ea_font=ea_font, latin_font=latin_font,
    )


def _render_insights_column(
    slide,
    spec: SlideSpec,
    pal: ScientificPalette,
    left_in: float = 8.68,
    top_in: float = 1.70,
    width_in: float = 4.18,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> None:
    cur_y = top_in

    # Frameless dual KPIs (38pt + hairline divider, ZERO box)
    if spec.kpis:
        kpis = spec.kpis[:2]
        slot_w = width_in / len(kpis)
        for idx, kp in enumerate(kpis):
            kx = left_in + idx * slot_w
            _add_native_textbox(
                slide, kx, cur_y, slot_w - 0.10, 0.56,
                text=kp.value, size_pt=36.0, bold=True, color_hex=pal.token(kp.color_token), line_spacing=1.05,
                name=f"L3_kpi_val_{idx}", ea_font=ea_font, latin_font=latin_font,
            )
            _add_native_textbox(
                slide, kx, cur_y + 0.58, slot_w - 0.10, 0.32,
                text=kp.label, size_pt=14.0, bold=False, color_hex=pal.muted, line_spacing=1.1,
                name=f"L3_kpi_lbl_{idx}", ea_font=ea_font, latin_font=latin_font,
            )
            if idx == 0 and len(kpis) == 2:
                _add_native_line(slide, left_in + slot_w - 0.12, cur_y + 0.08, left_in + slot_w - 0.12, cur_y + 0.88, color_hex=pal.line, width_pt=0.75)
        cur_y += 1.08
        _add_native_line(slide, left_in, cur_y - 0.08, left_in + width_in, cur_y - 0.08, color_hex=pal.line, width_pt=0.75)
        cur_y += 0.10

    # Max 3 frameless insights with 3pt left vertical accent bar + 18pt body text (1.5x line spacing)
    insights = spec.insights[:3]
    for idx, ins in enumerate(insights):
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(left_in), Inches(cur_y + 0.06), Inches(0.042), Inches(0.32),  # ~3 pt bar
        )
        bar.line.fill.background()
        bar.fill.solid()
        bar.fill.fore_color.rgb = _rgb(pal.s1)
        bar.name = f"L2_insight_bar_{idx}"

        _add_native_textbox(
            slide, left_in + 0.14, cur_y, width_in - 0.14, 0.36,
            text=f"{ins.index}  {ins.heading}", size_pt=18.0, bold=True, color_hex=pal.ink, line_spacing=1.2,
            name=f"L3_insight_h_{idx}", ea_font=ea_font, latin_font=latin_font,
        )
        _add_native_textbox(
            slide, left_in + 0.14, cur_y + 0.38, width_in - 0.14, 0.82,
            text=ins.body, size_pt=18.0, bold=False, color_hex=pal.ink,
            highlight_phrase=ins.highlight, highlight_color_hex=pal.s1, line_spacing=1.5,
            name=f"L3_insight_b_{idx}", ea_font=ea_font, latin_font=latin_font,
        )
        cur_y += 1.32


def _build_cover_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    if build_v5_cover_slide(slide, spec, deck, pal):
        return
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    # Top accent bar + left typography + right dedicated 3D hero visual (ZERO solid boxes)
    _add_native_line(slide, 0.65, 1.35, 2.25, 1.35, color_hex=pal.s1, width_pt=3.5)
    _add_native_textbox(slide, 0.65, 0.92, 6.40, 0.34, text=spec.eyebrow, size_pt=14.5, bold=True, color_hex=pal.s3, line_spacing=1.1, ea_font=ea_font, latin_font=latin_font)
    _add_native_textbox(slide, 0.65, 1.56, 6.50, 1.65, text=deck.meta.deck_title, size_pt=30.0, bold=True, color_hex=pal.s1, line_spacing=1.25, ea_font=ea_font, latin_font=latin_font)
    _add_native_textbox(slide, 0.65, 3.32, 6.40, 0.85, text=deck.meta.deck_subtitle, size_pt=18.0, bold=False, color_hex=pal.muted, line_spacing=1.45, ea_font=ea_font, latin_font=latin_font)

    _add_native_line(slide, 0.65, 5.10, 6.80, 5.10, color_hex=pal.line, width_pt=0.75)
    _add_native_textbox(slide, 0.65, 5.26, 6.40, 0.42, text=f"汇报人：{deck.meta.author}", size_pt=18.0, bold=True, color_hex=pal.ink, line_spacing=1.2, ea_font=ea_font, latin_font=latin_font)
    _add_native_textbox(slide, 0.65, 5.74, 6.40, 0.42, text=deck.meta.affiliation, size_pt=18.0, bold=False, color_hex=pal.muted, line_spacing=1.2, ea_font=ea_font, latin_font=latin_font)

    if spec.figure_spec:
        _render_figure_layer(slide, spec.figure_spec, pal, ea_font=ea_font, latin_font=latin_font)


def _build_toc_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, total_slides: int) -> None:
    if deck.meta.design_style != DesignStyle.zero_fill_frameless:
        build_v5_toc_slide(slide, spec, deck, pal)
        return
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    _add_content_header_and_footer(slide, spec, deck, pal, total_slides)
    items = spec.toc_items or [f"Part 0{i+1}" for i in range(4)]
    start_y = 2.05
    for idx, item in enumerate(items[:6]):
        y = start_y + idx * 0.78
        _add_native_textbox(slide, 0.85, y, 0.85, 0.48, text=f"0{idx+1}", size_pt=24.0, bold=True, color_hex=pal.s1, line_spacing=1.1, ea_font=ea_font, latin_font=latin_font)
        _add_native_line(slide, 1.72, y + 0.08, 1.72, y + 0.42, color_hex=pal.s2, width_pt=2.5)
        _add_native_textbox(slide, 1.98, y + 0.02, 10.2, 0.48, text=item, size_pt=20.0, bold=False, color_hex=pal.ink, line_spacing=1.2, ea_font=ea_font, latin_font=latin_font)
        _add_native_line(slide, 0.85, y + 0.58, 12.2, y + 0.58, color_hex=pal.line, width_pt=0.75)


def _build_part_divider_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    if build_v5_part_divider_slide(slide, spec, deck, pal):
        return
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    _add_native_line(slide, 1.1, 2.25, 2.8, 2.25, color_hex=pal.s1, width_pt=4.0)
    _add_native_textbox(slide, 1.1, 2.45, 11.0, 0.42, text=spec.eyebrow, size_pt=15.0, bold=True, color_hex=pal.s3, line_spacing=1.1, ea_font=ea_font, latin_font=latin_font)
    _add_native_textbox(slide, 1.1, 3.05, 11.0, 0.90, text=spec.title, size_pt=32.0, bold=True, color_hex=pal.s1, line_spacing=1.2, ea_font=ea_font, latin_font=latin_font)
    if spec.takeaway:
        _add_native_textbox(slide, 1.1, 4.15, 10.5, 0.65, text=spec.takeaway, size_pt=18.0, bold=False, color_hex=pal.muted, line_spacing=1.45, ea_font=ea_font, latin_font=latin_font)


def _build_closing_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette) -> None:
    if build_v5_closing_slide(slide, spec, deck, pal):
        return
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    _add_native_line(slide, 4.8, 2.30, 8.53, 2.30, color_hex=pal.s1, width_pt=3.0)
    _add_native_textbox(slide, 1.5, 2.60, 10.333, 0.90, text=spec.title or "敬请各位专家批评指正", size_pt=34.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER, line_spacing=1.2, ea_font=ea_font, latin_font=latin_font)
    _add_native_textbox(slide, 1.8, 3.70, 9.733, 0.60, text=spec.takeaway or f"{deck.meta.author} · {deck.meta.affiliation}", size_pt=18.0, bold=False, color_hex=pal.muted, align=PP_ALIGN.CENTER, line_spacing=1.4, ea_font=ea_font, latin_font=latin_font)
    _add_native_line(slide, 5.4, 4.60, 7.93, 4.60, color_hex=pal.line, width_pt=0.75)


def _build_content_slide(slide, spec: SlideSpec, deck: DeckSpec, pal: ScientificPalette, total_slides: int) -> None:
    ea_font = deck.locked_standards.fonts.get("ea", "微软雅黑")
    latin_font = deck.locked_standards.fonts.get("latin", "Arial")
    if build_v5_content_slide(slide, spec, deck, pal, total_slides, _render_figure_layer):
        return
    _add_content_header_and_footer(slide, spec, deck, pal, total_slides)

    # Render Hero Figure (Layer 1 + Layer 2)
    if spec.figure_spec:
        _render_figure_layer(slide, spec.figure_spec, pal, ea_font=ea_font, latin_font=latin_font)
        box = spec.figure_spec.box_in
        cap_top = max(box.top + box.height + 0.12, 6.22 if spec.layout_id == LayoutId.frameless_63_37 else box.top + box.height + 0.10)
        cap_top = min(cap_top, 6.30)
        _add_native_textbox(
            slide,
            box.left, cap_top, box.width, 0.56,
            text=spec.figure_spec.caption,
            size_pt=14.0, bold=False, color_hex=pal.muted,
            highlight_phrase=spec.figure_spec.caption.split("  ")[0] if "  " in spec.figure_spec.caption else None,
            highlight_color_hex=pal.s1,
            line_spacing=1.18,
            name="L3_caption",
            ea_font=ea_font, latin_font=latin_font,
        )

    # Optional frameless three-line table
    if spec.table_data and spec.table_data.headers:
        td = spec.table_data
        t_left, t_top, t_w = 8.68, 1.72, 4.18
        if spec.layout_id == LayoutId.three_line_table and not spec.figure_spec:
            t_left, t_top, t_w = 0.65, 1.80, 12.00
        rows_count = len(td.rows) + 1
        cols_count = len(td.headers)
        t_shape = slide.shapes.add_table(rows_count, cols_count, Inches(t_left), Inches(t_top), Inches(t_w), Inches(0.46 * rows_count))
        tbl = t_shape.table
        apply_three_line_table_borders(tbl, line_hex=pal.ink)
        for c_i, hdr in enumerate(td.headers):
            cell = tbl.cell(0, c_i)
            p = cell.text_frame.paragraphs[0]
            populate_paragraph(p, hdr, size_pt=14.0, bold=True, color_hex=pal.s1, align=PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT, line_spacing=1.15, ea_font=ea_font, latin_font=latin_font)
        for r_i, row in enumerate(td.rows):
            for c_i, val in enumerate(row[:cols_count]):
                cell = tbl.cell(r_i + 1, c_i)
                p = cell.text_frame.paragraphs[0]
                populate_paragraph(p, val, size_pt=14.0, bold=False, color_hex=pal.ink, align=PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT, line_spacing=1.15, ea_font=ea_font, latin_font=latin_font)

        if spec.layout_id == LayoutId.frameless_63_37 and spec.figure_spec:
            _add_native_line(slide, 8.42, 1.72, 8.42, 6.72, color_hex=pal.line, width_pt=0.75)
        if spec.insights:
            _render_insights_column(slide, spec, pal, left_in=8.68, top_in=t_top + 0.46 * rows_count + 0.25, width_in=4.18, ea_font=ea_font, latin_font=latin_font)
        return

    # Layout-specific skeleton coordinates
    if spec.layout_id == LayoutId.full_roadmap:
        # Full-width roadmap with bottom takeaway summary strip (no right axis)
        if spec.insights:
            n_ins = min(3, len(spec.insights))
            col_w = 12.2 / max(n_ins, 1)
            for idx, ins in enumerate(spec.insights[:3]):
                x = 0.56 + idx * col_w
                _add_native_textbox(slide, x, 5.95, col_w - 0.25, 0.34, text=f"{ins.index}  {ins.heading}", size_pt=18.0, bold=True, color_hex=pal.s1, line_spacing=1.1, ea_font=ea_font, latin_font=latin_font)
                _add_native_textbox(slide, x, 6.32, col_w - 0.25, 0.52, text=ins.body, size_pt=18.0, bold=False, color_hex=pal.ink, highlight_phrase=ins.highlight, highlight_color_hex=pal.s1, line_spacing=1.25, ea_font=ea_font, latin_font=latin_font)
    elif spec.layout_id == LayoutId.split_50_50:
        _add_native_line(slide, 6.72, 1.72, 6.72, 6.72, color_hex=pal.line, width_pt=0.75)
        _render_insights_column(slide, spec, pal, left_in=6.98, top_in=1.70, width_in=5.88, ea_font=ea_font, latin_font=latin_font)
    elif spec.layout_id == LayoutId.dual_wing_28_38_28:
        _add_native_line(slide, 4.10, 1.72, 4.10, 6.72, color_hex=pal.line, width_pt=0.75)
        _add_native_line(slide, 9.22, 1.72, 9.22, 6.72, color_hex=pal.line, width_pt=0.75)
        if spec.insights:
            _render_insights_column(slide, SlideSpec(**{**spec.model_dump(), "insights": spec.insights[:1], "kpis": []}), pal, left_in=0.46, top_in=1.78, width_in=3.45, ea_font=ea_font, latin_font=latin_font)
            _render_insights_column(slide, SlideSpec(**{**spec.model_dump(), "insights": spec.insights[1:3]}), pal, left_in=9.42, top_in=1.78, width_in=3.44, ea_font=ea_font, latin_font=latin_font)
    else:
        # Default canonical 63:37 asymmetric grid (Spec Section 2.2)
        _add_native_line(slide, 8.42, 1.72, 8.42, 6.72, color_hex=pal.line, width_pt=0.75)
        _render_insights_column(slide, spec, pal, left_in=8.68, top_in=1.70, width_in=4.18, ea_font=ea_font, latin_font=latin_font)


def compile_deck_to_pptx(deck: DeckSpec, output_pptx: Path | str) -> Path:
    """Compile a validated DeckSpec v4.0 JSON into a 100% native editable .pptx file."""
    prs = Presentation()
    prs.slide_width = Inches(deck.locked_standards.canvas_in[0])
    prs.slide_height = Inches(deck.locked_standards.canvas_in[1])
    blank_layout = prs.slide_layouts[6]

    pal = get_palette(deck.meta.palette_id)
    total_slides = len(deck.slides)

    for spec in deck.slides:
        slide = prs.slides.add_slide(blank_layout)
        _set_white_slide_background(slide)

        if spec.slide_type == SlideType.cover or spec.layout_id == LayoutId.cover:
            _build_cover_slide(slide, spec, deck, pal)
        elif spec.slide_type == SlideType.toc or spec.layout_id == LayoutId.toc:
            _build_toc_slide(slide, spec, deck, pal, total_slides)
        elif spec.slide_type == SlideType.part_divider or spec.layout_id == LayoutId.part_divider:
            _build_part_divider_slide(slide, spec, deck, pal)
        elif spec.slide_type == SlideType.closing or spec.layout_id == LayoutId.closing:
            _build_closing_slide(slide, spec, deck, pal)
        else:
            _build_content_slide(slide, spec, deck, pal, total_slides)

        # Offload full speaker notes & experimental details
        if spec.speaker_notes:
            notes_slide = slide.notes_slide
            notes_tf = notes_slide.notes_text_frame
            notes_tf.text = spec.speaker_notes

    out_p = Path(output_pptx)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_p))
    return out_p
