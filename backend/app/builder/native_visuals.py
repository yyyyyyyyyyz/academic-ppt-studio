"""Native Editable PowerPoint Visual Builders (Zero-Raster Vector & Chart Output).

Compiles FigureSpec assets directly into 100% natively editable PowerPoint shapes:
- OriginPlotEngine presets -> Native OOXML Excel-backed Chart shapes (`add_chart`)
- ChemDrawEngine molecules -> Native GroupShape of connectors, halos & >=14pt atom TextBoxes
- CYLview3DEngine 3D ball-and-stick -> Z-sorted GroupShape of shaded Ovals & rounded Connectors
- VectorMechanismEngine & scientific icons -> Native GroupShape of AutoShapes, arrows & TextBoxes
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from lxml import etree
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_MARK
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from rdkit import Chem

from ..figure_factory.chemdraw_engine import _prepare_molecule
from ..figure_factory.cylview3d_engine import _ATOM_RADII_A, _atom_color, _embed_and_align, _visible_atom_mask
from ..figure_factory.palettes import ScientificPalette, blend_with_white, hex_to_rgb
from ..schemas.deck_spec import EngineType, FigureAsset, FigureBoxIn
from .xml_utils import bind_chart_txpr, configure_zero_fill_textbox, insert_chart_child_ordered, populate_paragraph

EMU_PER_INCH = 914400


def _rgb(hex_str: str) -> RGBColor:
    r, g, b = hex_to_rgb(hex_str)
    return RGBColor(r, g, b)


def _hex6(hex_str: str) -> str:
    r, g, b = hex_to_rgb(hex_str)
    return f"{r:02X}{g:02X}{b:02X}"


def _set_group_bounds(grp, left_in: float, top_in: float, width_in: float, height_in: float) -> None:
    """Set identity xfrm (off==chOff, ext==chExt) so child inches map 1:1 to slide coordinates."""
    grpPr = grp._element.grpSpPr
    xfrm = grpPr.find(qn("a:xfrm"))
    if xfrm is None:
        xfrm = etree.SubElement(grpPr, qn("a:xfrm"))
    lx, ty = int(round(left_in * EMU_PER_INCH)), int(round(top_in * EMU_PER_INCH))
    cx, cy = max(1, int(round(width_in * EMU_PER_INCH))), max(1, int(round(height_in * EMU_PER_INCH)))

    for tag, x_attr, y_attr, x_val, y_val in (
        ("a:off", "x", "y", lx, ty),
        ("a:ext", "cx", "cy", cx, cy),
        ("a:chOff", "x", "y", lx, ty),
        ("a:chExt", "cx", "cy", cx, cy),
    ):
        el = xfrm.find(qn(tag))
        if el is None:
            el = etree.SubElement(xfrm, qn(tag))
        el.set(x_attr, str(x_val))
        el.set(y_attr, str(y_val))


def _add_group_line(
    grp_shapes,
    x1_in: float,
    y1_in: float,
    x2_in: float,
    y2_in: float,
    color_rgb: Tuple[int, int, int] | str,
    width_pt: float = 1.6,
    dashed: bool = False,
    arrow_end: bool = False,
    round_cap: bool = False,
):
    conn = grp_shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1_in), Inches(y1_in),
        Inches(x2_in), Inches(y2_in),
    )
    if isinstance(color_rgb, str):
        r, g, b = hex_to_rgb(color_rgb)
    else:
        r, g, b = int(color_rgb[0]), int(color_rgb[1]), int(color_rgb[2])
    conn.line.color.rgb = RGBColor(r, g, b)
    conn.line.width = Pt(width_pt)
    ln = conn.line._get_or_add_ln()
    if round_cap:
        ln.set("cap", "rnd")
    if dashed:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    if arrow_end:
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    return conn


def _add_group_textbox(
    grp_shapes,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    text: str,
    size_pt: float = 14.0,
    bold: bool = False,
    color_hex: str = "#162032",
    align: PP_ALIGN = PP_ALIGN.CENTER,
    anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
    line_spacing: float = 1.05,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
):
    tb = grp_shapes.add_textbox(Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in))
    configure_zero_fill_textbox(tb, word_wrap=False, anchor=anchor)
    p = tb.text_frame.paragraphs[0]
    populate_paragraph(
        p,
        text=text,
        size_pt=max(14.0, size_pt),
        bold=bold,
        color_hex=color_hex,
        align=align,
        line_spacing=line_spacing,
        ea_font=ea_font,
        latin_font=latin_font,
    )
    return tb


# ---------------------------------------------------------------------------
# 1. Native Editable PowerPoint OriginPro-Styled Charts (Excel-backed OOXML)
# ---------------------------------------------------------------------------

_SPPR_FOLLOWERS = {
    "chartSpace": {"txPr", "externalData", "printSettings", "userShapes", "extLst"},
    "plotArea": {"extLst"},
    "ser": {"invertIfNegative", "pictureOptions", "dPt", "dLbls", "trendline", "errBars", "cat", "val", "xVal", "yVal", "smooth", "shape", "extLst"},
}


def _ensure_chart_sppr(parent_el, fill_hex: Optional[str], border_hex: Optional[str], border_pt: float = 1.0) -> None:
    spPr = parent_el.find(qn("c:spPr"))
    if spPr is None:
        spPr = etree.Element(qn("c:spPr"))
        local = etree.QName(parent_el).localname
        insert_chart_child_ordered(parent_el, spPr, _SPPR_FOLLOWERS.get(local, {"extLst"}))
    for child_tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:pattFill", "a:ln"):
        old = spPr.find(qn(child_tag))
        if old is not None:
            spPr.remove(old)
    if fill_hex:
        sf = etree.SubElement(spPr, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", _hex6(fill_hex))
    else:
        etree.SubElement(spPr, qn("a:noFill"))
    if border_hex and border_pt > 0:
        ln = etree.SubElement(spPr, qn("a:ln"))
        ln.set("w", str(int(round(border_pt * 12700))))
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", _hex6(border_hex))
    else:
        ln = etree.SubElement(spPr, qn("a:ln"))
        etree.SubElement(ln, qn("a:noFill"))


def _apply_series_hatch(series, fg_hex: str, bg_hex: str, border_hex: str, border_pt: float = 1.0) -> None:
    spPr = series._element.find(qn("c:spPr"))
    if spPr is None:
        spPr = etree.Element(qn("c:spPr"))
        insert_chart_child_ordered(series._element, spPr, _SPPR_FOLLOWERS["ser"])
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:pattFill", "a:ln"):
        old = spPr.find(qn(tag))
        if old is not None:
            spPr.remove(old)
    pf = etree.SubElement(spPr, qn("a:pattFill"))
    pf.set("prst", "wdUpDiag")
    fg = etree.SubElement(pf, qn("a:fgClr"))
    etree.SubElement(fg, qn("a:srgbClr")).set("val", _hex6(fg_hex))
    bg = etree.SubElement(pf, qn("a:bgClr"))
    etree.SubElement(bg, qn("a:srgbClr")).set("val", _hex6(bg_hex))

    ln = etree.SubElement(spPr, qn("a:ln"))
    ln.set("w", str(int(round(border_pt * 12700))))
    sf = etree.SubElement(ln, qn("a:solidFill"))
    etree.SubElement(sf, qn("a:srgbClr")).set("val", _hex6(border_hex))


def _style_chart_origin_xml(
    chart,
    pal: ScientificPalette,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
    has_legend: bool = True,
    ylabel: Optional[str] = None,
    xlabel: Optional[str] = None,
    modern_bar_style: bool = False,
) -> None:
    chart.has_title = False
    # Pure white outer chartSpace (borderless) + schema-ordered default chart font (>= 14 pt)
    _ensure_chart_sppr(chart._chartSpace, fill_hex="#FFFFFF", border_hex=None, border_pt=0.0)
    bind_chart_txpr(chart._chartSpace, latin_font=latin_font, ea_font=ea_font, size_pt=14.0, color_hex=pal.ink)

    # White plot area with crisp Origin or modern subtle border
    plot_area = chart._chartSpace.chart.plotArea
    _ensure_chart_sppr(
        plot_area,
        fill_hex="#FFFFFF",
        border_hex="#CBD5E1" if modern_bar_style else pal.ink,
        border_pt=0.6 if modern_bar_style else 1.0,
    )

    if has_legend:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        ov_el = chart.legend._element.find(qn("c:overlay"))
        if ov_el is None:
            ov_el = etree.Element(qn("c:overlay"))
            insert_chart_child_ordered(chart.legend._element, ov_el, {"spPr", "txPr", "extLst"})
        ov_el.set("val", "0")
        chart.legend.font.name = latin_font
        chart.legend.font.size = Pt(14.0)
        chart.legend.font.color.rgb = _rgb(pal.ink)
        bind_chart_txpr(chart.legend._element, latin_font=latin_font, ea_font=ea_font, size_pt=14.0, bold=False, color_hex=pal.ink)
    else:
        chart.has_legend = False

    for ax_name in ("category_axis", "value_axis"):
        ax = getattr(chart, ax_name, None)
        if ax is None:
            continue
        if modern_bar_style and ax_name == "value_axis":
            ax.has_major_gridlines = True
            try:
                ax.major_gridlines.format.line.color.rgb = _rgb("#E8EEF5")
                ax.major_gridlines.format.line.width = Pt(0.6)
            except Exception:
                pass
            ax.major_tick_mark = XL_TICK_MARK.OUTSIDE
            ax.minor_tick_mark = XL_TICK_MARK.NONE
        elif modern_bar_style and ax_name == "category_axis":
            ax.has_major_gridlines = False
            ax.major_tick_mark = XL_TICK_MARK.OUTSIDE
        else:
            ax.has_major_gridlines = False
            ax.has_minor_gridlines = False
            ax.major_tick_mark = XL_TICK_MARK.INSIDE
            if ax_name == "value_axis":
                ax.minor_tick_mark = XL_TICK_MARK.INSIDE
        if modern_bar_style:
            try:
                ax.format.line.color.rgb = _rgb("#334155")
                ax.format.line.width = Pt(1.0)
            except Exception:
                pass
        ax.tick_labels.font.name = latin_font
        ax.tick_labels.font.size = Pt(14.0)
        ax.tick_labels.font.color.rgb = _rgb(pal.ink)
        bind_chart_txpr(ax._element, latin_font=latin_font, ea_font=ea_font, size_pt=14.0, color_hex=pal.ink)

    if ylabel and hasattr(chart, "value_axis"):
        chart.value_axis.has_title = True
        p = chart.value_axis.axis_title.text_frame.paragraphs[0]
        populate_paragraph(p, ylabel, size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font, align=PP_ALIGN.CENTER, line_spacing=1.1)
    if xlabel and hasattr(chart, "category_axis"):
        chart.category_axis.has_title = True
        p = chart.category_axis.axis_title.text_frame.paragraphs[0]
        populate_paragraph(p, xlabel, size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font, align=PP_ALIGN.CENTER, line_spacing=1.1)


def add_native_origin_chart(
    slide,
    asset: FigureAsset,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    pal: ScientificPalette,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
) -> None:
    """Render an OriginPro-styled figure as a 100% natively editable Excel-backed PowerPoint Chart."""
    preset = (asset.preset or "kinetics_spline").strip().lower()
    data = asset.plot_data or {}

    if preset in ("paired_gain_bar", "dft_slab_bader_link"):
        categories = data.get("categories") or data.get("sites") or ["Aryl-Cl", "Aryl-Br", "Heteroaryl", "Alkyl"]
        ctrl_vals = [float(v) for v in (data.get("control") or [42.0, 62.4, 48.5, 51.0])]
        work_vals = [float(v) for v in (data.get("this_work") or data.get("e_ads") or [87.5, 91.2, 86.0, 84.5])]
        if preset == "dft_slab_bader_link":
            work_vals = [abs(v) for v in work_vals]
            cd = CategoryChartData()
            cd.categories = categories
            cd.add_series(data.get("work_label", "|E_ads| (eV)"), work_vals)
            shp = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in), cd)
            shp.name = f"L1_{asset.asset_id}_chart"
            chart = shp.chart
            plot = chart.plots[0]
            plot.gap_width = 75
            plot.has_data_labels = True
            plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
            plot.data_labels.font.name = latin_font
            plot.data_labels.font.size = Pt(14.0)
            plot.series[0].format.fill.solid()
            plot.series[0].format.fill.fore_color.rgb = _rgb(pal.s1)
            dlbls = plot._element.find(qn("c:dLbls"))
            if dlbls is not None:
                bind_chart_txpr(dlbls, latin_font=latin_font, ea_font=ea_font, size_pt=14.0, bold=True, color_hex=pal.s1)
            _style_chart_origin_xml(chart, pal, latin_font=latin_font, ea_font=ea_font, has_legend=False, ylabel=data.get("ylabel", "|E_ads| (eV)"))
            return

        cd = CategoryChartData()
        cd.categories = categories
        cd.add_series(data.get("control_label", "Conventional"), ctrl_vals)
        cd.add_series(data.get("work_label", "This Work"), work_vals)

        shp = slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in),
            cd,
        )
        shp.name = f"L1_{asset.asset_id}_chart"
        chart = shp.chart
        plot = chart.plots[0]
        plot.gap_width = 85
        plot.overlap = -15
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.show_value = True
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.name = latin_font
        dl.font.size = Pt(14.0)
        dl.font.color.rgb = _rgb(pal.ink)

        dlbls_el = plot._element.find(qn("c:dLbls"))
        if dlbls_el is not None:
            bind_chart_txpr(dlbls_el, latin_font=latin_font, ea_font=ea_font, size_pt=14.0, bold=True, color_hex=pal.ink)

        # Series 0: Cool Steel-Blue Fine Hatch Control; Series 1: Solid Oxford Primary
        _apply_series_hatch(plot.series[0], fg_hex="#4A7BB0", bg_hex="#CFE0F5", border_hex="#4A7BB0", border_pt=1.0)
        plot.series[1].format.fill.solid()
        plot.series[1].format.fill.fore_color.rgb = _rgb(pal.s1)
        plot.series[1].format.line.color.rgb = _rgb("#002F61")
        plot.series[1].format.line.width = Pt(0.9)

        max_v = max(max(ctrl_vals), max(work_vals), 1.0)
        chart.value_axis.minimum_scale = 0.0
        chart.value_axis.maximum_scale = round(max_v * 1.44, 0)

        _style_chart_origin_xml(
            chart, pal,
            latin_font=latin_font, ea_font=ea_font,
            has_legend=True,
            ylabel=data.get("ylabel", "Isolated Yield (%)"),
            modern_bar_style=True,
        )

        # Add native editable relative gain delta pill badges above bar pairs
        deltas = data.get("deltas")
        if not deltas:
            deltas = [f"{'+' if (w - c) >= 0 else ''}{w - c:.1f}%" for c, w in zip(ctrl_vals, work_vals)]
        n_cat = max(len(categories), 1)
        plot_l = left_in + 0.92
        plot_w = max(width_in - 1.10, 1.0)
        plot_top = top_in + 0.50
        plot_bot = top_in + height_in - 0.42
        plot_h = max(plot_bot - plot_top, 0.6)
        max_sc = float(chart.value_axis.maximum_scale)
        for idx, d_txt in enumerate(deltas[:n_cat]):
            if not d_txt:
                continue
            top_bar_v = max(ctrl_vals[idx], work_vals[idx])
            y_bar = plot_bot - (top_bar_v / max_sc) * plot_h
            badge_y = max(plot_top + 0.04, y_bar - 0.62)
            cx = plot_l + (idx + 0.5) * (plot_w / n_cat)
            pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx - 0.46), Inches(badge_y), Inches(0.92), Inches(0.30))
            pill.name = f"L2_{asset.asset_id}_delta_bg_{idx}"
            try:
                pill.adjustments[0] = 0.45
            except Exception:
                pass
            pill.fill.solid()
            pill.fill.fore_color.rgb = _rgb("#FFFFFF")
            pill.line.color.rgb = _rgb(pal.s1)
            pill.line.width = Pt(0.85)
            tb = slide.shapes.add_textbox(Inches(cx - 0.46), Inches(badge_y), Inches(0.92), Inches(0.30))
            tb.name = f"L3_{asset.asset_id}_delta_{idx}"
            configure_zero_fill_textbox(tb, word_wrap=False, anchor=MSO_ANCHOR.MIDDLE)
            populate_paragraph(
                tb.text_frame.paragraphs[0],
                text=str(d_txt),
                size_pt=14.0,
                bold=True,
                color_hex=pal.s1,
                align=PP_ALIGN.CENTER,
                line_spacing=1.0,
                ea_font=ea_font,
                latin_font=latin_font,
            )
        return

    if preset in ("benchmark_scatter", "ml_parity_kde"):
        xy = XyChartData()
        if preset == "benchmark_scatter":
            s_lit = xy.add_series("Literature")
            lit_x = data.get("lit_x", [110, 120, 95, 130, 85, 100, 75])
            lit_y = data.get("lit_y", [58, 66, 72, 79, 61, 82, 54])
            for vx, vy in zip(lit_x, lit_y):
                s_lit.add_data_point(float(vx), float(vy))
            s_work = xy.add_series("This Work")
            s_work.add_data_point(float(data.get("this_x", 45.0)), float(data.get("this_y", 94.5)))
            ylabel = data.get("ylabel", "Target Yield (%)")
            xlabel = data.get("xlabel", "Reaction Temperature (°C)")
        else:
            rng = np.random.default_rng(21)
            y_true = np.asarray(data.get("y_true", rng.uniform(15, 96, 36)), dtype=np.float64)
            y_pred = np.asarray(data.get("y_pred", np.clip(y_true + rng.normal(0, 4.1, size=len(y_true)), 8, 99)), dtype=np.float64)
            s_pts = xy.add_series("Predictions")
            for vx, vy in zip(y_true, y_pred):
                s_pts.add_data_point(float(vx), float(vy))
            s_diag = xy.add_series("y = x")
            s_diag.add_data_point(10.0, 10.0)
            s_diag.add_data_point(100.0, 100.0)
            ylabel = "ML Predicted Yield (%)"
            xlabel = "Experimental Yield (%)"

        shp = slide.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in), xy)
        shp.name = f"L1_{asset.asset_id}_chart"
        chart = shp.chart
        _style_chart_origin_xml(chart, pal, latin_font=latin_font, ea_font=ea_font, has_legend=True, ylabel=ylabel, xlabel=xlabel)
        return

    if preset == "dft_energy_profile":
        states = data.get("states", ["IS", "IM1", "TS1", "IM2", "FS"])
        e_ctrl = [float(v) for v in data.get("control", [0.00, -0.22, 1.18, -0.35, -0.68])]
        e_work = [float(v) for v in data.get("this_work", [0.00, -0.34, 0.42, -0.58, -0.92])]
        cd = CategoryChartData()
        cd.categories = states
        cd.add_series(data.get("control_label", "Unassisted"), e_ctrl)
        cd.add_series(data.get("work_label", "Catalyst Synergy"), e_work)
        shp = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in), cd)
        shp.name = f"L1_{asset.asset_id}_chart"
        chart = shp.chart
        plot = chart.plots[0]
        plot.series[0].format.line.color.rgb = _rgb(pal.muted)
        plot.series[0].format.line.width = Pt(2.0)
        plot.series[1].format.line.color.rgb = _rgb(pal.s1)
        plot.series[1].format.line.width = Pt(2.8)
        _style_chart_origin_xml(chart, pal, latin_font=latin_font, ea_font=ea_font, has_legend=True, ylabel="Delta G (eV)")
        return

    # Default: kinetics_spline / electrochem_suite / xps_deconv -> Native XY smooth line chart
    xy = XyChartData()
    x_vals = [float(v) for v in data.get("x", [0, 10, 20, 30, 45, 60, 90, 120])]
    series_list = data.get("series", [
        {"name": "Catalyst A", "y": [0, 28, 56, 76, 89, 94, 96, 96], "color": pal.s1},
        {"name": "Bulk Control", "y": [0, 14, 29, 41, 52, 60, 66, 68], "color": pal.s3},
        {"name": "Blank", "y": [0, 4, 8, 12, 16, 19, 22, 24], "color": pal.muted},
    ])
    for idx, s in enumerate(series_list):
        xs = s.get("x", x_vals)
        ys = s.get("y", [])
        ser = xy.add_series(s.get("name", f"Series {idx+1}"))
        for vx, vy in zip(xs, ys):
            ser.add_data_point(float(vx), float(vy))

    shp = slide.shapes.add_chart(
        XL_CHART_TYPE.XY_SCATTER_SMOOTH,
        Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in),
        xy,
    )
    shp.name = f"L1_{asset.asset_id}_chart"
    chart = shp.chart
    for idx, ser in enumerate(chart.plots[0].series):
        col = series_list[idx].get("color") if idx < len(series_list) else None
        col_hex = col or ([pal.s1, pal.s3, pal.muted, pal.alert][idx % 4])
        ser.format.line.color.rgb = _rgb(col_hex)
        ser.format.line.width = Pt(2.4 if idx == 0 else 1.8)
    _style_chart_origin_xml(
        chart, pal,
        latin_font=latin_font, ea_font=ea_font,
        has_legend=True,
        ylabel=data.get("ylabel", "Yield (%)"),
        xlabel=data.get("xlabel", "Reaction Time (min)"),
    )


# ---------------------------------------------------------------------------
# 2. Native Editable 2D ChemDraw GroupShape Builder
# ---------------------------------------------------------------------------

def _atom_style_hex(
    atomic_num: int,
    pal: ScientificPalette,
    heteroatom_theme_sync: bool,
    drug_burgundy: bool,
    chem_style: str = "acs1996",
) -> str:
    style = (chem_style or ("nature_burgundy" if drug_burgundy else "acs1996")).strip().lower()
    if style == "acs1996" and drug_burgundy:
        style = "nature_burgundy"

    if style == "minimal_mono":
        return "#1E1E1E"
    if style == "nature_burgundy":
        if atomic_num in (0, 1, 6):
            return "#7F1D1D"
        if atomic_num == 7:
            return "#1F4E78"
        if atomic_num in (8, 9, 17, 35, 53):
            return "#B5121B"
        if atomic_num in (15, 16):
            return "#9A6B16"
        return "#1F4E78"
    if style == "jacs_terracotta":
        if atomic_num in (0, 1, 6):
            return "#9A3412"
        if atomic_num == 7:
            return "#1F4E78"
        if atomic_num in (8, 9, 17, 35, 53):
            return "#B91C1C"
        if atomic_num in (15, 16):
            return "#9A6B16"
        return "#1F4E78"

    carbon_hex = "#141E2B"
    if atomic_num in (0, 1, 6):
        return carbon_hex
    if heteroatom_theme_sync:
        n_hex, alert_hex, s_hex = pal.s1, pal.alert, pal.s2
    else:
        n_hex, alert_hex, s_hex = "#00468B", "#AD002A", "#B07300"
    if atomic_num == 7:
        return n_hex
    if atomic_num in (8, 9, 17, 35, 53):
        return alert_hex
    if atomic_num in (15, 16):
        return s_hex
    return n_hex


def compute_shared_chemdraw_scale(assets: Sequence[FigureAsset], box: FigureBoxIn) -> Optional[float]:
    """Compute uniform inches-per-RDKit-unit across all 2D molecules on a slide."""
    scales: List[float] = []
    for asset in assets:
        if asset.engine != EngineType.chemdraw_rdkit:
            continue
        try:
            mol = _prepare_molecule(asset.smiles or "c1ccccc1")
        except Exception:
            continue
        conf = mol.GetConformer()
        xs = [conf.GetAtomPosition(i).x for i in range(mol.GetNumAtoms())]
        ys = [conf.GetAtomPosition(i).y for i in range(mol.GetNumAtoms())]
        if not xs:
            continue
        nb = asset.norm_box if len(asset.norm_box) == 4 else [0.0, 0.0, 1.0, 1.0]
        aw = max(0.8, nb[2] * box.width - 0.18)
        ah = max(0.8, nb[3] * box.height - 0.18)
        span_x = max(max(xs) - min(xs) + 1.05, 1.6)
        span_y = max(max(ys) - min(ys) + 1.05, 1.6)
        bond_cap_in = (float(asset.fixed_bond_length_px or 20) / 100.0) if asset.fixed_bond_length_px else 0.24
        max_scale = max(0.14, min(0.24, bond_cap_in)) / 1.5
        scales.append(min(aw / span_x, ah / span_y, max_scale))
    return min(scales) if scales else None


def add_native_chemdraw_group(
    slide,
    asset: FigureAsset,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    pal: ScientificPalette,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
    scale_in_per_unit: Optional[float] = None,
) -> None:
    """Build a 100% natively editable 2D chemical structure inside a single PowerPoint GroupShape."""
    smiles = asset.smiles or "c1ccc(CNc2ccccc2)cc1"
    mol = _prepare_molecule(smiles)
    conf = mol.GetConformer()
    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return

    coords = np.array([[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y] for i in range(n_atoms)], dtype=np.float64)
    min_xy = coords.min(axis=0)
    max_xy = coords.max(axis=0)
    mid_xy = 0.5 * (min_xy + max_xy)
    span_x = max(float(max_xy[0] - min_xy[0]) + 1.05, 1.6)
    span_y = max(float(max_xy[1] - min_xy[1]) + 1.05, 1.6)

    avail_w = max(0.6, width_in - 0.16)
    avail_h = max(0.6, height_in - 0.16)
    local_scale = min(avail_w / span_x, avail_h / span_y)
    scale = min(local_scale, scale_in_per_unit) if scale_in_per_unit else min(local_scale, 0.24 / 1.5)

    cx_box = left_in + 0.5 * width_in
    cy_box = top_in + 0.5 * height_in

    # Map RDKit 2D (+Y up) -> Slide (+Y down)
    pts_in: List[Tuple[float, float]] = [
        (cx_box + (coords[i, 0] - mid_xy[0]) * scale, cy_box - (coords[i, 1] - mid_xy[1]) * scale)
        for i in range(n_atoms)
    ]

    grp = slide.shapes.add_group_shape()
    grp.name = f"L1_{asset.asset_id}_mol2d"
    _set_group_bounds(grp, left_in, top_in, width_in, height_in)
    g_shapes = grp.shapes

    # 1. Translucent Highlight Halos + Crisp Dashed Pharmacophore Rings / Shaded Polygons
    chem_style = (getattr(asset, "chem_style", "acs1996") or ("nature_burgundy" if asset.drug_burgundy else "acs1996")).strip().lower()
    if chem_style == "acs1996" and asset.drug_burgundy:
        chem_style = "nature_burgundy"

    def _halo_pair(tok: str) -> Tuple[str, str]:
        base = pal.token(tok)
        h_hex = blend_with_white(pal.s4, 0.25) if tok == "s6" else blend_with_white(base, 0.22)
        r_hex = pal.s1 if tok == "s6" else base
        return h_hex, r_hex

    groups_spec: List[Tuple[List[Tuple[float, float]], str, str]] = []
    group_atom_sets: List[Tuple[set[int], str, str]] = []
    if asset.highlight_groups:
        for hg in asset.highlight_groups:
            idxs = [idx for idx in (hg.get("atoms") or []) if 0 <= idx < n_atoms]
            if not idxs:
                continue
            tok = str(hg.get("color_token", asset.highlight_halo_token or "s6"))
            h_hex, r_hex = _halo_pair(tok)
            groups_spec.append(([pts_in[idx] for idx in idxs], h_hex, r_hex))
            group_atom_sets.append((set(idxs), h_hex, r_hex))
    else:
        halo_atoms = [idx for idx in (asset.highlight_atoms or []) if 0 <= idx < n_atoms]
        if not halo_atoms and asset.highlight_rings:
            atom_rings_tmp = mol.GetRingInfo().AtomRings()
            if atom_rings_tmp:
                halo_atoms = list(atom_rings_tmp[0])
        halo_centers: List[Tuple[float, float]] = [pts_in[idx] for idx in halo_atoms]
        for b_idx in (asset.highlight_bonds or []):
            if 0 <= b_idx < mol.GetNumBonds():
                b = mol.GetBondWithIdx(b_idx)
                p1, p2 = pts_in[b.GetBeginAtomIdx()], pts_in[b.GetEndAtomIdx()]
                halo_centers.append((0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1])))
        if halo_centers:
            h_hex, r_hex = _halo_pair(asset.highlight_halo_token or "s6")
            groups_spec.append((halo_centers, h_hex, r_hex))
            if halo_atoms:
                group_atom_sets.append((set(halo_atoms), h_hex, r_hex))

    atom_rings = mol.GetRingInfo().AtomRings()
    if chem_style == "shaded_scaffold" and atom_rings and group_atom_sets:
        for ring in atom_rings:
            r_set = set(ring)
            matched_ring_hex: Optional[str] = None
            for aset, _, r_hex in group_atom_sets:
                if r_set & aset:
                    matched_ring_hex = r_hex
                    break
            if matched_ring_hex and len(ring) >= 3:
                poly_pts = [pts_in[a] for a in ring]
                fb = g_shapes.build_freeform(Inches(poly_pts[0][0]), Inches(poly_pts[0][1]))
                fb.add_line_segments([(Inches(px), Inches(py)) for px, py in poly_pts[1:]], close=True)
                poly_shp = fb.convert_to_shape()
                poly_shp.fill.solid()
                poly_shp.fill.fore_color.rgb = _rgb(matched_ring_hex)
                sf_p = poly_shp._element.spPr.find(qn("a:solidFill"))
                if sf_p is not None:
                    srgb_p = sf_p.find(qn("a:srgbClr"))
                    if srgb_p is not None:
                        etree.SubElement(srgb_p, qn("a:alpha")).set("val", "20000")
                poly_shp.line.fill.background()

    halo_r = max(0.14, 0.92 * scale)
    for centers, halo_hex, ring_hex in groups_spec:
        if chem_style not in ("minimal_mono", "shaded_scaffold"):
            for hx, hy in centers:
                ov = g_shapes.add_shape(MSO_SHAPE.OVAL, Inches(hx - halo_r), Inches(hy - halo_r), Inches(2 * halo_r), Inches(2 * halo_r))
                ov.fill.solid()
                ov.fill.fore_color.rgb = _rgb(halo_hex)
                sf = ov._element.spPr.find(qn("a:solidFill"))
                if sf is not None:
                    srgb = sf.find(qn("a:srgbClr"))
                    if srgb is not None:
                        etree.SubElement(srgb, qn("a:alpha")).set("val", "20000")
                ov.line.fill.background()
        if len(centers) >= 2:
            xs_c = [p[0] for p in centers]
            ys_c = [p[1] for p in centers]
            pad_r = max(0.16, 1.05 * scale)
            rx0, ry0 = min(xs_c) - pad_r, min(ys_c) - pad_r
            rx1, ry1 = max(xs_c) + pad_r, max(ys_c) + pad_r
            ring_ov = g_shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(rx0), Inches(ry0), Inches(max(0.24, rx1 - rx0)), Inches(max(0.24, ry1 - ry0)),
            )
            ring_ov.fill.background()
            ring_ov.line.color.rgb = _rgb(ring_hex)
            ring_ov.line.width = Pt(0.85)
            ln_r = ring_ov.line._get_or_add_ln()
            etree.SubElement(ln_r, qn("a:prstDash")).set("val", "dash")

    ring_centroids = [
        (
            sum(pts_in[a][0] for a in ring) / len(ring),
            sum(pts_in[a][1] for a in ring) / len(ring),
        )
        for ring in atom_rings
        if len(ring) >= 3
    ]

    # 2. Native Chemical Bonds (including chiral solid wedges & hashed wedges + 4 chem styles)
    accent_atoms: set[int] = set()
    for aset, _, _ in group_atom_sets:
        accent_atoms |= aset
    atom_cols = []
    for i in range(n_atoms):
        col = _atom_style_hex(
            mol.GetAtomWithIdx(i).GetAtomicNum(), pal, asset.heteroatom_theme_sync, asset.drug_burgundy, chem_style=chem_style
        )
        if chem_style == "minimal_mono" and i in accent_atoms:
            col = pal.s1
        atom_cols.append(col)

    is_label_atom = [mol.GetAtomWithIdx(i).GetAtomicNum() != 6 for i in range(n_atoms)]
    trim_r = 0.088
    base_bond_w = max(1.5, min(2.2, scale * 11.5))
    if chem_style == "nature_burgundy":
        bond_w = base_bond_w * 1.15
    elif chem_style == "minimal_mono":
        bond_w = base_bond_w * 0.80
    else:
        bond_w = base_bond_w

    def _draw_split_seg(p1: Tuple[float, float], p2: Tuple[float, float], col1: str, col2: str, w_pt: float) -> None:
        if col1 == col2:
            _add_group_line(g_shapes, p1[0], p1[1], p2[0], p2[1], col1, width_pt=w_pt, round_cap=True)
        else:
            mx, my = 0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1])
            _add_group_line(g_shapes, p1[0], p1[1], mx, my, col1, width_pt=w_pt, round_cap=True)
            _add_group_line(g_shapes, mx, my, p2[0], p2[1], col2, width_pt=w_pt, round_cap=True)

    for bond in mol.GetBonds():
        i1, i2 = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        x1, y1 = pts_in[i1]
        x2, y2 = pts_in[i2]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 1e-4:
            continue
        ux, uy = dx / dist, dy / dist
        sx1 = x1 + (trim_r if is_label_atom[i1] else 0.0) * ux
        sy1 = y1 + (trim_r if is_label_atom[i1] else 0.0) * uy
        sx2 = x2 - (trim_r if is_label_atom[i2] else 0.0) * ux
        sy2 = y2 - (trim_r if is_label_atom[i2] else 0.0) * uy
        if math.hypot(sx2 - sx1, sy2 - sy1) < 0.02:
            sx1, sy1, sx2, sy2 = x1, y1, x2, y2

        c1, c2 = atom_cols[i1], atom_cols[i2]
        nx, ny = -uy, ux
        btype = bond.GetBondType()
        bdir = bond.GetBondDir()

        if bdir == Chem.BondDir.BEGINWEDGE:
            hw = 0.036
            fb = g_shapes.build_freeform(Inches(sx1), Inches(sy1))
            fb.add_line_segments(
                [
                    (Inches(sx2 + nx * hw), Inches(sy2 + ny * hw)),
                    (Inches(sx2 - nx * hw), Inches(sy2 - ny * hw)),
                ],
                close=True,
            )
            w_shp = fb.convert_to_shape()
            w_shp.fill.solid()
            w_shp.fill.fore_color.rgb = _rgb(c1)
            w_shp.line.fill.background()
        elif bdir == Chem.BondDir.BEGINDASH:
            for t in (0.18, 0.36, 0.54, 0.72, 0.90):
                px_h = sx1 + (sx2 - sx1) * t
                py_h = sy1 + (sy2 - sy1) * t
                hw = 0.012 + (0.036 - 0.012) * t
                col_h = c1 if t < 0.5 else c2
                _add_group_line(g_shapes, px_h - nx * hw, py_h - ny * hw, px_h + nx * hw, py_h + ny * hw, col_h, width_pt=max(1.1, bond_w * 0.72), round_cap=True)
        elif btype == Chem.BondType.DOUBLE:
            if bond.IsInRing() and atom_rings:
                mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
                in_nx, in_ny = nx, ny
                for r_idx, ring in enumerate(atom_rings):
                    if i1 in ring and i2 in ring:
                        rcx, rcy = ring_centroids[r_idx]
                        if (rcx - mx) * nx + (rcy - my) * ny < 0:
                            in_nx, in_ny = -nx, -ny
                        break
                off = 0.044
                _draw_split_seg((sx1, sy1), (sx2, sy2), c1, c2, bond_w)
                ix1 = sx1 + (sx2 - sx1) * 0.12 + in_nx * off
                iy1 = sy1 + (sy2 - sy1) * 0.12 + in_ny * off
                ix2 = sx2 - (sx2 - sx1) * 0.12 + in_nx * off
                iy2 = sy2 - (sy2 - sy1) * 0.12 + in_ny * off
                _draw_split_seg((ix1, iy1), (ix2, iy2), c1, c2, bond_w * 0.88)
            else:
                off = 0.022
                _draw_split_seg((sx1 + nx * off, sy1 + ny * off), (sx2 + nx * off, sy2 + ny * off), c1, c2, bond_w * 0.90)
                _draw_split_seg((sx1 - nx * off, sy1 - ny * off), (sx2 - nx * off, sy2 - ny * off), c1, c2, bond_w * 0.90)
        elif btype == Chem.BondType.TRIPLE:
            off = 0.036
            _draw_split_seg((sx1, sy1), (sx2, sy2), c1, c2, bond_w)
            _draw_split_seg((sx1 + nx * off, sy1 + ny * off), (sx2 + nx * off, sy2 + ny * off), c1, c2, bond_w * 0.80)
            _draw_split_seg((sx1 - nx * off, sy1 - ny * off), (sx2 - nx * off, sy2 - ny * off), c1, c2, bond_w * 0.80)
        else:
            _draw_split_seg((sx1, sy1), (sx2, sy2), c1, c2, bond_w)

    # 3. Pure-White Knockout Ovals + Native Editable Atom Labels (>= 14 pt Arial + XML subscript)
    for i in range(n_atoms):
        atom = mol.GetAtomWithIdx(i)
        anum = atom.GetAtomicNum()
        if anum == 6:
            continue
        sym = atom.GetSymbol()
        nh = atom.GetTotalNumHs()
        ax, ay = pts_in[i]
        if nh == 0:
            lbl = sym
        elif nh == 1:
            nbr_xs = [pts_in[nb.GetIdx()][0] for nb in atom.GetNeighbors()]
            lbl = f"H{sym}" if (nbr_xs and ax < (sum(nbr_xs) / len(nbr_xs)) - 0.04) else f"{sym}H"
        else:
            lbl = f"{sym}H{nh}"

        ko_w = 0.16 + 0.075 * max(0, len(lbl) - 1)
        ko_h = 0.17
        ko = g_shapes.add_shape(MSO_SHAPE.OVAL, Inches(ax - ko_w * 0.5), Inches(ay - ko_h * 0.5), Inches(ko_w), Inches(ko_h))
        ko.fill.solid()
        ko.fill.fore_color.rgb = _rgb("#FFFFFF")
        ko.line.fill.background()

        tb_w = 0.28 + 0.11 * max(0, len(lbl) - 1)
        tb_h = 0.24
        _add_group_textbox(
            g_shapes,
            ax - tb_w * 0.5, ay - tb_h * 0.5, tb_w, tb_h,
            text=lbl,
            size_pt=14.0,
            bold=True,
            color_hex=atom_cols[i],
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            line_spacing=1.0,
            ea_font=ea_font,
            latin_font=latin_font,
        )


# ---------------------------------------------------------------------------
# 3. Native Editable 3D CYLview Ball-and-Stick GroupShape Builder
# ---------------------------------------------------------------------------

def _apply_sphere_radial_grad(
    oval_shape,
    base_rgb: Tuple[int, int, int],
    outline_hex: str = "#3D4652",
    depth_t: float = 1.0,
) -> None:
    r, g, b = int(base_rgb[0]), int(base_rgb[1]), int(base_rgb[2])
    fog = max(0.0, min(0.12, (1.0 - depth_t) * 0.12))
    r = int(round(r * (1.0 - fog) + 255.0 * fog))
    g = int(round(g * (1.0 - fog) + 255.0 * fog))
    b = int(round(b * (1.0 - fog) + 255.0 * fog))

    hi_r = min(255, int(r * 0.30 + 255 * 0.70))
    hi_g = min(255, int(g * 0.30 + 255 * 0.70))
    hi_b = min(255, int(b * 0.30 + 255 * 0.70))
    sh_r = max(0, int(r * 0.56))
    sh_g = max(0, int(g * 0.56))
    sh_b = max(0, int(b * 0.56))

    spPr = oval_shape._element.spPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill"):
        old = spPr.find(qn(tag))
        if old is not None:
            spPr.remove(old)

    gf = etree.SubElement(spPr, qn("a:gradFill"))
    gf.set("flip", "none")
    gf.set("rotWithShape", "1")
    gs_lst = etree.SubElement(gf, qn("a:gsLst"))

    for pos, (cr, cg, cb) in ((0, (hi_r, hi_g, hi_b)), (48000, (r, g, b)), (100000, (sh_r, sh_g, sh_b))):
        gs = etree.SubElement(gs_lst, qn("a:gs"))
        gs.set("pos", str(pos))
        srgb = etree.SubElement(gs, qn("a:srgbClr"))
        srgb.set("val", f"{cr:02X}{cg:02X}{cb:02X}")

    path_el = etree.SubElement(gf, qn("a:path"))
    path_el.set("path", "circle")
    ft = etree.SubElement(path_el, qn("a:fillToRect"))
    ft.set("l", "26000")
    ft.set("t", "24000")
    ft.set("r", "74000")
    ft.set("b", "76000")

    oval_shape.line.color.rgb = _rgb(outline_hex)
    oval_shape.line.width = Pt(0.75)


def add_native_cylview3d_group(
    slide,
    asset: FigureAsset,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    pal: ScientificPalette,
) -> None:
    """Build a 100% natively editable Z-sorted 3D conformer GroupShape matching all 5 3D styles."""
    smiles = asset.smiles or "c1ccnc(c1)c2ccccn2"
    style = (asset.style_3d or "ball_stick").lower()
    style_cfg = {
        "ball_stick": {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True},
        "stick_clean": {"sphere_mult": 0.40, "bond_mult": 1.35, "draw_bonds": True},
        "spacefill_cpk": {"sphere_mult": 2.25, "bond_mult": 0.0, "draw_bonds": False},
        "pymol_neon_green": {"sphere_mult": 1.04, "bond_mult": 1.05, "draw_bonds": True},
        "metallic_studio": {"sphere_mult": 1.02, "bond_mult": 1.02, "draw_bonds": True},
    }.get(style, {"sphere_mult": 1.0, "bond_mult": 1.0, "draw_bonds": True})

    mol, coords = _embed_and_align(smiles, rotation_deg=asset.rotation_deg)
    vis = _visible_atom_mask(mol, asset.show_nonpolar_h)
    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0 or not np.any(vis):
        return

    radii_a = np.array([_ATOM_RADII_A.get(a.GetAtomicNum(), 0.36) for a in mol.GetAtoms()], dtype=np.float32) * float(style_cfg["sphere_mult"])
    colors = [_atom_color(a.GetAtomicNum(), pal, style_3d=style) for a in mol.GetAtoms()]

    vis_coords = coords[vis]
    vis_radii = radii_a[vis]
    min_xy = (vis_coords[:, :2] - vis_radii[:, None]).min(axis=0)
    max_xy = (vis_coords[:, :2] + vis_radii[:, None]).max(axis=0)
    span_xy = np.maximum(max_xy - min_xy, 1.8)
    avail_w = max(0.6, width_in - 0.16)
    avail_h = max(0.6, height_in - 0.16)
    scale = min(avail_w / float(span_xy[0]), avail_h / float(span_xy[1]))

    mid_xy = 0.5 * (min_xy + max_xy)
    cx_box = left_in + 0.5 * width_in
    cy_box = top_in + 0.5 * height_in

    pts_x = cx_box + (coords[:, 0] - mid_xy[0]) * scale
    pts_y = cy_box + (coords[:, 1] - mid_xy[1]) * scale
    pts_z = coords[:, 2]
    radii_in = radii_a * scale * 0.86

    grp = slide.shapes.add_group_shape()
    grp.name = f"L1_{asset.asset_id}_mol3d"
    _set_group_bounds(grp, left_in, top_in, width_in, height_in)
    g_shapes = grp.shapes

    # Whisper-soft contact shadow ellipse underneath molecule
    vis_x = pts_x[vis]
    vis_y = pts_y[vis]
    sh_cx = float(0.5 * (vis_x.min() + vis_x.max()))
    sh_cy = float(vis_y.max() + radii_in[vis].max() * 0.55)
    sh_w = max(0.9, float(0.76 * (vis_x.max() - vis_x.min())))
    sh_h = 0.14
    sh_ov = g_shapes.add_shape(MSO_SHAPE.OVAL, Inches(sh_cx - sh_w * 0.5), Inches(sh_cy - sh_h * 0.5), Inches(sh_w), Inches(sh_h))
    sh_ov.fill.solid()
    sh_ov.fill.fore_color.rgb = _rgb("#0F172A")
    sf_sh = sh_ov._element.spPr.find(qn("a:solidFill"))
    if sf_sh is not None:
        srgb_sh = sf_sh.find(qn("a:srgbClr"))
        if srgb_sh is not None:
            etree.SubElement(srgb_sh, qn("a:alpha")).set("val", "7000")
    sh_ov.line.fill.background()

    outline_hex = "#1E262E" if style == "pymol_neon_green" else (asset.outline_stroke if asset.outline_stroke and asset.outline_stroke != "#4A4A4A" else "#3D4652")
    vis_z = pts_z[vis]
    z_min = float(vis_z.min()) if len(vis_z) else -1.0
    z_max = float(vis_z.max()) if len(vis_z) else 1.0
    z_span = max(z_max - z_min, 1e-4)

    draw_items: List[Tuple[float, str, Any]] = []
    for bond in (mol.GetBonds() if style_cfg["draw_bonds"] else []):
        i1, i2 = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if not (vis[i1] and vis[i2]):
            continue
        mx = 0.5 * (pts_x[i1] + pts_x[i2])
        my = 0.5 * (pts_y[i1] + pts_y[i2])
        mz = 0.5 * (pts_z[i1] + pts_z[i2])
        z1_mid = 0.5 * (pts_z[i1] + mz)
        z2_mid = 0.5 * (mz + pts_z[i2])
        draw_items.append((float(z1_mid) - 0.02, "bond", (pts_x[i1], pts_y[i1], mx, my, colors[i1], z1_mid)))
        draw_items.append((float(z2_mid) - 0.02, "bond", (mx, my, pts_x[i2], pts_y[i2], colors[i2], z2_mid)))

    for idx in range(n_atoms):
        if not vis[idx]:
            continue
        dt = (float(pts_z[idx]) - z_min) / z_span
        draw_items.append((float(pts_z[idx]), "atom", (float(pts_x[idx]), float(pts_y[idx]), float(radii_in[idx]), colors[idx], dt)))

    draw_items.sort(key=lambda item: item[0])
    bond_w_pt = max(2.6, min(6.2, 0.12 * float(style_cfg["bond_mult"]) * scale * 72.0 * 1.9))

    for _, kind, payload in draw_items:
        if kind == "bond":
            x1, y1, x2, y2, col_arr, zb = payload
            depth_fac = 0.72 + 0.28 * ((float(zb) - z_min) / z_span)
            cr = min(255, int(col_arr[0] * depth_fac))
            cg = min(255, int(col_arr[1] * depth_fac))
            cb = min(255, int(col_arr[2] * depth_fac))
            _add_group_line(g_shapes, x1, y1, x2, y2, outline_hex, width_pt=bond_w_pt + 1.2, round_cap=True)
            _add_group_line(g_shapes, x1, y1, x2, y2, (cr, cg, cb), width_pt=bond_w_pt, round_cap=True)
        else:
            ax, ay, ar, col_arr, dt = payload
            ov = g_shapes.add_shape(MSO_SHAPE.OVAL, Inches(ax - ar), Inches(ay - ar), Inches(2 * ar), Inches(2 * ar))
            _apply_sphere_radial_grad(ov, (int(col_arr[0]), int(col_arr[1]), int(col_arr[2])), outline_hex=outline_hex, depth_t=dt)


# ---------------------------------------------------------------------------
# 4. Native Editable Vector Mechanism & Scientific Icon Builders
# ---------------------------------------------------------------------------

def add_native_icon_group(parent_shapes, icon_name: str, left_in: float, top_in: float, size_in: float, pal: ScientificPalette) -> None:
    """Draw a clean vector scientific icon directly using native PowerPoint AutoShapes inside parent_shapes."""
    s = size_in
    soft = blend_with_white(pal.s4, 0.35)
    lw = max(1.4, s * 2.2)

    def _box(sh_type, lx, ty, w, h, fill=soft, stroke=pal.s1):
        sh = parent_shapes.add_shape(sh_type, Inches(left_in + lx * s), Inches(top_in + ty * s), Inches(max(0.03, w * s)), Inches(max(0.03, h * s)))
        if fill:
            sh.fill.solid()
            sh.fill.fore_color.rgb = _rgb(fill)
        else:
            sh.fill.background()
        if stroke:
            sh.line.color.rgb = _rgb(stroke)
            sh.line.width = Pt(lw)
        else:
            sh.line.fill.background()
        return sh

    if icon_name in ("flask", "prohibited_flask"):
        _box(MSO_SHAPE.RECTANGLE, 0.40, 0.14, 0.20, 0.24, fill="#FFFFFF")
        _box(MSO_SHAPE.ISOSCELES_TRIANGLE, 0.20, 0.36, 0.60, 0.50, fill=soft)
        if icon_name == "prohibited_flask":
            _box(MSO_SHAPE.OVAL, 0.10, 0.10, 0.80, 0.80, fill=None, stroke=pal.alert)
            _add_group_line(parent_shapes, left_in + 0.22 * s, top_in + 0.22 * s, left_in + 0.78 * s, top_in + 0.78 * s, pal.alert, width_pt=lw + 0.5)
    elif icon_name == "ball_mill":
        _box(MSO_SHAPE.ROUNDED_RECTANGLE, 0.14, 0.26, 0.72, 0.48, fill=soft)
        for bx, by, br in ((0.30, 0.48, 0.12), (0.50, 0.52, 0.14), (0.68, 0.44, 0.12)):
            _box(MSO_SHAPE.OVAL, bx - br * 0.5, by - br * 0.5, br, br, fill=pal.s1, stroke="#FFFFFF")
    elif icon_name == "porous_hex":
        for hx, hy in ((0.32, 0.22), (0.20, 0.44), (0.44, 0.44)):
            _box(MSO_SHAPE.HEXAGON, hx, hy, 0.32, 0.30, fill=soft)
    elif icon_name == "nmr_spectrum":
        _add_group_line(parent_shapes, left_in + 0.12 * s, top_in + 0.78 * s, left_in + 0.88 * s, top_in + 0.78 * s, pal.s1, width_pt=lw)
        for px, py in ((0.32, 0.34), (0.50, 0.52), (0.68, 0.20)):
            _add_group_line(parent_shapes, left_in + px * s, top_in + 0.78 * s, left_in + px * s, top_in + py * s, pal.s1, width_pt=lw)
    elif icon_name == "crystal_cube":
        _box(MSO_SHAPE.CUBE, 0.18, 0.18, 0.64, 0.64, fill=soft)
    else:
        _box(MSO_SHAPE.LIGHTNING_BOLT if icon_name == "lightning" else MSO_SHAPE.OVAL, 0.18, 0.18, 0.64, 0.64, fill=soft)


def add_native_vector_mech_group(
    slide,
    asset: FigureAsset,
    left_in: float,
    top_in: float,
    width_in: float,
    height_in: float,
    pal: ScientificPalette,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
) -> None:
    """Compile VectorMechanismEngine modes into 100% natively editable GroupShapes."""
    mode = (asset.mech_mode or "dual_cycle").strip().lower()
    data = asset.mech_data or {}

    grp = slide.shapes.add_group_shape()
    grp.name = f"L1_{asset.asset_id}_mech"
    _set_group_bounds(grp, left_in, top_in, width_in, height_in)
    gs = grp.shapes

    def _add_card(lx, ty, w, h, fill="#F8FAFC", border=pal.s1, radius=0.10):
        sh = gs.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(lx), Inches(ty), Inches(w), Inches(h))
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
        if fill:
            sh.fill.solid()
            sh.fill.fore_color.rgb = _rgb(fill)
        else:
            sh.fill.background()
        if border:
            sh.line.color.rgb = _rgb(border)
            sh.line.width = Pt(1.4)
        else:
            sh.line.fill.background()
        return sh

    if mode == "roadmap_4stage":
        stages = data.get("stages", [
            {"num": "01", "title": "Pain Point", "sub": "Solvent-free goal", "icon": "prohibited_flask"},
            {"num": "02", "title": "Mechanochem.", "sub": "High-energy shear", "icon": "ball_mill"},
            {"num": "03", "title": "Confinement", "sub": "Porous synergy", "icon": "porous_hex"},
            {"num": "04", "title": "Validation", "sub": "NMR & kinetics", "icon": "nmr_spectrum"},
        ])
        n = min(4, len(stages))
        slot_w = width_in / max(n, 1)
        icon_s = min(0.85, height_in * 0.28)
        for idx, st in enumerate(stages[:4]):
            cx = left_in + (idx + 0.5) * slot_w
            _add_card(cx - 0.34, top_in + 0.14, 0.68, 0.34, fill=pal.s1, border=None, radius=0.35)
            _add_group_textbox(gs, cx - 0.34, top_in + 0.14, 0.68, 0.34, st.get("num", f"0{idx+1}"), size_pt=14.0, bold=True, color_hex="#FFFFFF", ea_font=ea_font, latin_font=latin_font)
            add_native_icon_group(gs, st.get("icon", "flask"), cx - icon_s * 0.5, top_in + 0.62, icon_s, pal)
            _add_group_line(gs, cx - slot_w * 0.38, top_in + 0.68 + icon_s + 0.10, cx + slot_w * 0.38, top_in + 0.68 + icon_s + 0.10, pal.s1, width_pt=1.8)
            _add_group_textbox(gs, cx - slot_w * 0.45, top_in + 0.84 + icon_s, slot_w * 0.90, 0.36, st.get("title", ""), size_pt=14.5, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)
            _add_group_textbox(gs, cx - slot_w * 0.45, top_in + 1.22 + icon_s, slot_w * 0.90, 0.34, st.get("sub", ""), size_pt=14.0, color_hex=pal.muted, ea_font=ea_font, latin_font=latin_font)
            if idx < n - 1:
                _add_group_line(gs, cx + slot_w * 0.32, top_in + 0.62 + icon_s * 0.5, cx + slot_w * 0.68, top_in + 0.62 + icon_s * 0.5, pal.s2, width_pt=2.0, arrow_end=True)
        return

    if mode == "gap_quadrant":
        x0, y0 = left_in + 0.45, top_in + 0.18
        pw, ph = max(1.2, width_in - 0.70), max(1.0, height_in - 0.65)
        zone = _add_card(x0 + pw * 0.52, y0 + 0.06, pw * 0.46, ph * 0.44, fill=pal.s6, border=pal.s3, radius=0.08)
        _add_group_line(gs, x0, y0 + ph * 0.5, x0 + pw, y0 + ph * 0.5, pal.line, width_pt=1.2, dashed=True)
        _add_group_line(gs, x0 + pw * 0.5, y0, x0 + pw * 0.5, y0 + ph, pal.line, width_pt=1.2, dashed=True)
        _add_group_line(gs, x0, y0 + ph, x0 + pw, y0 + ph, pal.ink, width_pt=1.8, arrow_end=True)
        _add_group_line(gs, x0, y0 + ph, x0, y0, pal.ink, width_pt=1.8, arrow_end=True)
        tx, ty = x0 + pw * 0.75, y0 + ph * 0.25
        for rad, col in ((0.30, pal.s5), (0.19, pal.s3), (0.10, pal.s1)):
            c = gs.add_shape(MSO_SHAPE.OVAL, Inches(tx - rad), Inches(ty - rad), Inches(2 * rad), Inches(2 * rad))
            c.fill.solid()
            c.fill.fore_color.rgb = _rgb(col)
            c.line.fill.background()
        _add_group_textbox(gs, tx - 0.9, ty + 0.30, 1.8, 0.34, data.get("target_label", "Target Zone"), size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)
        _add_group_textbox(gs, x0, y0 + ph + 0.06, pw, 0.32, data.get("xlabel", "Process Greenness & Atom Economy"), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)
        return

    if mode == "sunburst_pathway":
        cats = data.get("categories", [
            {"title": "Photocatalysis", "sub": "Visible light"},
            {"title": "Mechanochem.", "sub": "Solvent-free"},
            {"title": "Porous Cage", "sub": "Zeolite / MOF"},
            {"title": "Operando NMR", "sub": "Real-time"},
        ])
        cx, cy = left_in + width_in * 0.5, top_in + height_in * 0.5
        cw, ch = min(2.1, width_in * 0.34), min(0.84, height_in * 0.24)
        offsets = [(-width_in * 0.28, -height_in * 0.26), (width_in * 0.28, -height_in * 0.26), (-width_in * 0.28, height_in * 0.26), (width_in * 0.28, height_in * 0.26)]
        for idx, (cat, (ox, oy)) in enumerate(zip(cats[:4], offsets)):
            nx, ny = cx + ox, cy + oy
            _add_group_line(gs, cx, cy, nx, ny, pal.s2, width_pt=2.0, arrow_end=True)
            _add_card(nx - cw * 0.5, ny - ch * 0.5, cw, ch, fill=blend_with_white(pal.series[idx % len(pal.series)], 0.65), border=pal.s1, radius=0.14)
            _add_group_textbox(gs, nx - cw * 0.46, ny - ch * 0.38, cw * 0.92, ch * 0.42, cat.get("title", ""), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)
            _add_group_textbox(gs, nx - cw * 0.46, ny + ch * 0.04, cw * 0.92, ch * 0.36, cat.get("sub", ""), size_pt=14.0, color_hex=pal.muted, ea_font=ea_font, latin_font=latin_font)
        hub_r = min(0.68, min(width_in, height_in) * 0.18)
        hub = gs.add_shape(MSO_SHAPE.OVAL, Inches(cx - hub_r), Inches(cy - hub_r), Inches(2 * hub_r), Inches(2 * hub_r))
        hub.fill.solid()
        hub.fill.fore_color.rgb = _rgb("#FFFFFF")
        hub.line.color.rgb = _rgb(pal.s1)
        hub.line.width = Pt(2.4)
        _add_group_textbox(gs, cx - hub_r * 0.9, cy - 0.36, hub_r * 1.8, 0.72, data.get("center_title", "Core Hub"), size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)
        return

    if mode == "pd_coupling_cycle":
        cx, cy = left_in + width_in * 0.5, top_in + height_in * 0.48
        rad = min(width_in * 0.24, height_in * 0.30)
        ring = gs.add_shape(MSO_SHAPE.OVAL, Inches(cx - rad), Inches(cy - rad), Inches(2 * rad), Inches(2 * rad))
        ring.fill.background()
        ring.line.color.rgb = _rgb(pal.s1)
        ring.line.width = Pt(2.4)

        _add_card(cx - 0.72, cy - rad - 0.22, 1.44, 0.42, fill="#FFFFFF", border=pal.s1, radius=0.22)
        _add_group_textbox(gs, cx - 0.70, cy - rad - 0.22, 1.40, 0.42, data.get("top_species", "Pd(0)Ln"), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)

        _add_card(cx + rad * 0.56, cy + rad * 0.36, 1.66, 0.42, fill="#FFFFFF", border=pal.alert, radius=0.22)
        _add_group_textbox(gs, cx + rad * 0.58, cy + rad * 0.36, 1.62, 0.42, data.get("right_species", "Ar–Pd(II)–X"), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)

        _add_card(cx - rad * 0.56 - 1.72, cy + rad * 0.36, 1.72, 0.42, fill="#FFFFFF", border=pal.s1, radius=0.22)
        _add_group_textbox(gs, cx - rad * 0.54 - 1.72, cy + rad * 0.36, 1.68, 0.42, data.get("left_species", "Ar–Pd(II)–NHR"), size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)

        _add_group_textbox(gs, cx - 0.78, cy - 0.28, 1.56, 0.30, "Pd(0) / Pd(II)", size_pt=14.5, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)
        _add_group_textbox(gs, cx - 0.78, cy + 0.02, 1.56, 0.28, "C–N 催化循环", size_pt=14.0, color_hex=pal.muted, ea_font=ea_font, latin_font=latin_font)

        # Entry / Exit reaction arrows & labels
        _add_group_line(gs, cx + rad + 0.62, cy - rad + 0.04, cx + rad * 0.85, cy - rad * 0.35, pal.alert, width_pt=2.0, arrow_end=True)
        _add_group_textbox(gs, cx + rad + 0.16, cy - rad - 0.24, 1.24, 0.30, "Ar–X 氧化加成", size_pt=14.0, bold=True, color_hex=pal.alert, ea_font=ea_font, latin_font=latin_font)

        _add_group_line(gs, cx - rad * 0.85, cy - rad * 0.35, cx - rad - 0.62, cy - rad + 0.04, pal.s1, width_pt=2.2, arrow_end=True)
        _add_card(cx - rad - 1.26, cy - rad - 0.26, 1.28, 0.34, fill="#FFFFFF", border=pal.s1, radius=0.25)
        _add_group_textbox(gs, cx - rad - 1.24, cy - rad - 0.26, 1.24, 0.34, "Ar–NHR 产物", size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)

        _add_group_textbox(gs, cx - 1.35, top_in + height_in - 0.42, 2.70, 0.34, "R–NH2 + Base → Base·HX", size_pt=14.0, bold=True, color_hex=pal.ink, ea_font=ea_font, latin_font=latin_font)
        return

    # Default: dual_cycle or delta_g_concept native vector loops
    cx, cy = left_in + width_in * 0.5, top_in + height_in * 0.5
    rad = min(width_in * 0.21, height_in * 0.36)
    for ox, col, title in ((-rad * 1.25, pal.s2, "Cycle I\nActivation"), (rad * 1.25, pal.s1, "Cycle II\nCoupling")):
        ring = gs.add_shape(MSO_SHAPE.OVAL, Inches(cx + ox - rad), Inches(cy - rad), Inches(2 * rad), Inches(2 * rad))
        ring.fill.background()
        ring.line.color.rgb = _rgb(col)
        ring.line.width = Pt(2.4)
        _add_group_textbox(gs, cx + ox - rad * 0.8, cy - 0.34, rad * 1.6, 0.68, title, size_pt=14.0, bold=True, color_hex=col, ea_font=ea_font, latin_font=latin_font)
    _add_card(cx - 0.75, cy - 0.30, 1.50, 0.60, fill=pal.s6, border=pal.s1, radius=0.22)
    _add_group_textbox(gs, cx - 0.72, cy - 0.28, 1.44, 0.56, data.get("center_species", "[M-Ln] Int."), size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)
    _add_group_textbox(gs, cx - rad * 2.0, top_in + 0.08, rad * 1.5, 0.34, data.get("top_left", "SET / HAA"), size_pt=14.0, bold=True, color_hex=pal.s2, ea_font=ea_font, latin_font=latin_font)
    _add_group_textbox(gs, cx + rad * 0.5, top_in + 0.08, rad * 1.5, 0.34, data.get("top_right", "Red. Elim."), size_pt=14.0, bold=True, color_hex=pal.s1, ea_font=ea_font, latin_font=latin_font)
