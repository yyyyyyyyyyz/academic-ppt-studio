"""XML Utilities for python-pptx: Dual-Font Binding, Native Baseline Sub/Superscript & 3-Line Tables."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

from ..figure_factory.palettes import hex_to_rgb


UNICODE_SUB_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")
UNICODE_SUP_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
UNICODE_SUB_CHARS = set("₀₁₂₃₄₅₆₇₈₉₊₋")
UNICODE_SUP_CHARS = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def sanitize_unicode_sub_sup_to_markup(text: str) -> str:
    """Convert raw Unicode sub/superscripts into explicit _{...} / ^{...} markup before XML run splitting."""
    if not text:
        return ""
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in UNICODE_SUB_CHARS:
            buf = []
            while i < n and text[i] in UNICODE_SUB_CHARS:
                buf.append(text[i].translate(UNICODE_SUB_MAP))
                i += 1
            out.append("_{" + "".join(buf) + "}")
        elif ch in UNICODE_SUP_CHARS:
            buf = []
            while i < n and text[i] in UNICODE_SUP_CHARS:
                buf.append(text[i].translate(UNICODE_SUP_MAP))
                i += 1
            out.append("^{" + "".join(buf) + "}")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# Common chemical / unit / PK auto-markup patterns (when not already inside _{...} or ^{...})
_ION_SUP_RE = re.compile(r"\b(Ni|Fe|Co|Cu|Pd|Pt|Ru|Ir|Mn|Zn|Li|Na|K|Ca|Mg|Al)([1-4][+-]|[+-])(?![A-Za-z0-9_{^])")
_UNIT_SUP_RE = re.compile(r"\b(cm|mL|L|dec|mol|g|s|min|h)-([1-3])\b")
_PK_SUB_RE = re.compile(r"(?<![A-Za-z0-9_{^])(EC|IC|CC|LD|GI)(50|90)(?![A-Za-z0-9_{^])")
_THALF_RE = re.compile(r"(?<![A-Za-z0-9_{^])t(1/2)(?![A-Za-z0-9_{^])")
_CHEM_FORMULA_RE = re.compile(
    r"(?<![A-Za-z0-9_{^])("
    r"H2O|CO2|CO|N2|H2|O2|NH3|NH2|CH4|CH3|CH2OH|CF3|C2H4|NO2|SO2|H2O2|SiO2|Al2O3|TiO2|Fe3O4|Cu2O"
    r")(?![A-Za-z0-9_^{+-])"
)
_ORG_FORMULA_RE = re.compile(r"\b((?:[CHNOFSP]|Cl|Br)\d+(?:(?:[CHNOFSP]|Cl|Br)\d+)+)\b")
_MPRO_RE = re.compile(r"(?<![A-Za-z0-9_{^])M(pro)(?![A-Za-z0-9_{^])")
_KI_RE = re.compile(r"(?<![A-Za-z0-9_{^])K(i)(?![A-Za-z0-9_{^])")
_FAFG_RE = re.compile(r"(?<![A-Za-z0-9_{^])F(a)([×*])F(g)(?![A-Za-z0-9_{^])")
_SPAN_TOKEN_RE = re.compile(r"(_\{[^}]+\}|\^\{[^}]+\})")


def _normalize_plain_chunk(chunk: str) -> str:
    s = _ION_SUP_RE.sub(lambda m: f"{m.group(1)}^{{{m.group(2)}}}", chunk)
    s = _UNIT_SUP_RE.sub(lambda m: f"{m.group(1)}^{{-{m.group(2)}}}", s)
    s = _PK_SUB_RE.sub(lambda m: f"{m.group(1)}_{{{m.group(2)}}}", s)
    s = _THALF_RE.sub(lambda m: f"t_{{{m.group(1)}}}", s)
    s = _MPRO_RE.sub(lambda m: f"M^{{{m.group(1)}}}", s)
    s = _KI_RE.sub(lambda m: f"K_{{{m.group(1)}}}", s)
    s = _FAFG_RE.sub(lambda m: f"F_{{{m.group(1)}}}{m.group(2)}F_{{{m.group(3)}}}", s)
    s = _ORG_FORMULA_RE.sub(lambda m: re.sub(r"(\d+)", r"_{\1}", m.group(1)), s)
    s = _CHEM_FORMULA_RE.sub(lambda m: re.sub(r"(\d+)", r"_{\1}", m.group(1)), s)
    return s


def normalize_scientific_markup(text: str) -> str:
    """Convert raw Unicode sub/sup and common formulas/units into explicit _{...} / ^{...} spans."""
    s = sanitize_unicode_sub_sup_to_markup(text)
    if not s:
        return s
    parts: List[str] = []
    pos = 0
    for m in _SPAN_TOKEN_RE.finditer(s):
        if m.start() > pos:
            parts.append(_normalize_plain_chunk(s[pos:m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    if pos < len(s):
        parts.append(_normalize_plain_chunk(s[pos:]))
    return "".join(parts)


def parse_markup_segments(text: str) -> List[Tuple[str, Optional[str]]]:
    """Parse text with _{sub} and ^{sup} into [(segment_text, None|'sub'|'sup')]."""
    norm = normalize_scientific_markup(text)
    pattern = re.compile(r"(_\{[^}]+\}|\^\{[^}]+\})")
    parts: List[Tuple[str, Optional[str]]] = []
    pos = 0
    for m in pattern.finditer(norm):
        if m.start() > pos:
            parts.append((norm[pos:m.start()], None))
        tok = m.group(0)
        if tok.startswith("_{"):
            parts.append((tok[2:-1], "sub"))
        elif tok.startswith("^{"):
            parts.append((tok[2:-1], "sup"))
        pos = m.end()
    if pos < len(norm):
        parts.append((norm[pos:], None))
    return parts or [("", None)]


def bind_xml_dual_font(
    run,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
    size_pt: float = 18.0,
    bold: bool = False,
    italic: bool = False,
    color_hex: str = "#162032",
    baseline_kind: Optional[str] = None,
) -> None:
    """Bind XML <a:latin>, <a:ea>, <a:cs> fonts and optional native baseline sub/superscript."""
    r, g, b = hex_to_rgb(color_hex)
    font = run.font
    font.name = latin_font
    font.size = Pt(size_pt)
    font.bold = bold
    font.italic = italic
    font.color.rgb = RGBColor(r, g, b)

    rPr = run._r.get_or_add_rPr()
    if baseline_kind == "sub":
        rPr.set("baseline", "-25000")
    elif baseline_kind == "sup":
        rPr.set("baseline", "30000")
    else:
        if "baseline" in rPr.attrib:
            del rPr.attrib["baseline"]

    # Remove old font tags to avoid duplicates
    for tag in ("a:latin", "a:ea", "a:cs"):
        existing = rPr.find(qn(tag))
        if existing is not None:
            rPr.remove(existing)

    latin_el = etree.SubElement(rPr, qn("a:latin"))
    latin_el.set("typeface", latin_font)
    ea_el = etree.SubElement(rPr, qn("a:ea"))
    ea_el.set("typeface", ea_font)
    cs_el = etree.SubElement(rPr, qn("a:cs"))
    cs_el.set("typeface", latin_font)


def populate_paragraph(
    paragraph,
    text: str,
    size_pt: float = 18.0,
    bold: bool = False,
    color_hex: str = "#162032",
    highlight_phrase: Optional[str] = None,
    highlight_color_hex: Optional[str] = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    line_spacing: float = 1.5,
    ea_font: str = "微软雅黑",
    latin_font: str = "Arial",
) -> None:
    """Populate a python-pptx paragraph with dual XML fonts, native sub/superscript, and optional single keyword highlight."""
    paragraph.clear()
    paragraph.alignment = align
    if line_spacing and line_spacing > 0:
        paragraph.line_spacing = line_spacing

    # Split optional highlight phrase (bold + theme color) before sub/sup parsing
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

    for chunk_txt, is_hi in chunks:
        for seg_txt, base_kind in parse_markup_segments(chunk_txt):
            if not seg_txt:
                continue
            run = paragraph.add_run()
            run.text = seg_txt
            bind_xml_dual_font(
                run=run,
                ea_font=ea_font,
                latin_font=latin_font,
                size_pt=size_pt,
                bold=bold or is_hi,
                color_hex=(highlight_color_hex or color_hex) if is_hi else color_hex,
                baseline_kind=base_kind,
            )


_TXPR_FOLLOWERS = {
    "chartSpace": {"externalData", "printSettings", "userShapes", "extLst"},
    "catAx": {"crossAx", "crosses", "crossesAt", "auto", "lblAlgn", "lblOffset", "tickLblSkip", "tickMarkSkip", "noMultiLvlLbl", "crossBetween", "majorUnit", "minorUnit", "dispUnits", "extLst"},
    "valAx": {"crossAx", "crosses", "crossesAt", "auto", "lblAlgn", "lblOffset", "tickLblSkip", "tickMarkSkip", "noMultiLvlLbl", "crossBetween", "majorUnit", "minorUnit", "dispUnits", "extLst"},
    "dateAx": {"crossAx", "crosses", "crossesAt", "auto", "lblAlgn", "lblOffset", "tickLblSkip", "tickMarkSkip", "noMultiLvlLbl", "crossBetween", "majorUnit", "minorUnit", "dispUnits", "extLst"},
    "serAx": {"crossAx", "crosses", "crossesAt", "auto", "lblAlgn", "lblOffset", "tickLblSkip", "tickMarkSkip", "noMultiLvlLbl", "crossBetween", "majorUnit", "minorUnit", "dispUnits", "extLst"},
    "dLbls": {"dLblPos", "showLegendKey", "showVal", "showCatName", "showSerName", "showPercent", "showBubbleSize", "separator", "showLeaderLines", "leaderLines", "extLst"},
    "legend": {"extLst"},
}


def insert_chart_child_ordered(parent_el, new_el, follower_localnames: set[str]) -> None:
    """Insert new_el before the first child whose localname is in follower_localnames (OOXML XSD order)."""
    for idx, child in enumerate(list(parent_el)):
        if etree.QName(child).localname in follower_localnames:
            parent_el.insert(idx, new_el)
            return
    parent_el.append(new_el)


def bind_chart_txpr(
    parent_el,
    latin_font: str = "Arial",
    ea_font: str = "微软雅黑",
    size_pt: float = 14.0,
    bold: bool = False,
    color_hex: str = "#162032",
) -> None:
    """Attach explicit schema-ordered XML <c:txPr> dual fonts and >=14pt size on a PowerPoint Chart XML element."""
    old_txpr = parent_el.find(qn("c:txPr"))
    if old_txpr is not None:
        parent_el.remove(old_txpr)

    r, g, b = hex_to_rgb(color_hex)
    hex_val = f"{r:02X}{g:02X}{b:02X}"

    txpr = etree.Element(qn("c:txPr"))
    etree.SubElement(txpr, qn("a:bodyPr"))
    etree.SubElement(txpr, qn("a:lstStyle"))
    p_el = etree.SubElement(txpr, qn("a:p"))
    ppr = etree.SubElement(p_el, qn("a:pPr"))
    def_rpr = etree.SubElement(ppr, qn("a:defRPr"))
    def_rpr.set("sz", str(int(round(max(14.0, size_pt) * 100))))
    def_rpr.set("b", "1" if bold else "0")

    sf = etree.SubElement(def_rpr, qn("a:solidFill"))
    srgb = etree.SubElement(sf, qn("a:srgbClr"))
    srgb.set("val", hex_val)

    etree.SubElement(def_rpr, qn("a:latin")).set("typeface", latin_font)
    etree.SubElement(def_rpr, qn("a:ea")).set("typeface", ea_font)
    etree.SubElement(def_rpr, qn("a:cs")).set("typeface", latin_font)

    end_rpr = etree.SubElement(p_el, qn("a:endParaRPr"))
    end_rpr.set("lang", "en-US")

    parent_local = etree.QName(parent_el).localname
    followers = _TXPR_FOLLOWERS.get(parent_local, {"extLst"})
    insert_chart_child_ordered(parent_el, txpr, followers)


def configure_zero_fill_textbox(shape, word_wrap: bool = True, anchor: MSO_ANCHOR = MSO_ANCHOR.TOP) -> None:
    """Ensure a textbox strictly has zero background fill and zero outline."""
    shape.fill.background()
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = word_wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(0)
    tf.margin_right = Pt(0)
    tf.margin_top = Pt(0)
    tf.margin_bottom = Pt(0)


def apply_soft_card_shadow(
    shape,
    blur_pt: float = 5.0,
    dist_pt: float = 1.5,
    alpha_pct: int = 8,
    color_hex: str = "#0F172A",
) -> None:
    """Attach a crisp native OOXML outer drop shadow onto a card AutoShape (keeps pure #FFFFFF fill)."""
    spPr = shape._element.spPr
    for old in list(spPr.findall(qn("a:effectLst"))):
        spPr.remove(old)

    eff_lst = etree.Element(qn("a:effectLst"))
    shdw = etree.SubElement(eff_lst, qn("a:outerShdw"))
    shdw.set("blurRad", str(int(round(blur_pt * 12700))))
    shdw.set("dist", str(int(round(dist_pt * 12700))))
    shdw.set("dir", "5400000")
    shdw.set("algn", "tl")
    shdw.set("rotWithShape", "0")
    srgb = etree.SubElement(shdw, qn("a:srgbClr"))
    srgb.set("val", color_hex.lstrip("#").upper())
    etree.SubElement(srgb, qn("a:alpha")).set("val", str(int(alpha_pct) * 1000))

    followers = {"scene3d", "sp3d", "extLst"}
    inserted = False
    for idx, child in enumerate(list(spPr)):
        if etree.QName(child).localname in followers:
            spPr.insert(idx, eff_lst)
            inserted = True
            break
    if not inserted:
        spPr.append(eff_lst)


def apply_three_line_table_borders(table, line_hex: str = "#162032") -> None:
    """Style a python-pptx table as a zero-fill academic three-line table (top 1.5pt, header 0.75pt, bottom 1.5pt)."""
    n_rows = len(table.rows)
    n_cols = len(table.columns)
    rgb_hex = line_hex.lstrip("#").upper()

    def _set_border(tcPr, edge: str, width_pt: Optional[float]) -> None:
        tag = qn(f"a:{edge}")
        old = tcPr.find(tag)
        if old is not None:
            tcPr.remove(old)
        el = etree.SubElement(tcPr, tag)
        if width_pt is None or width_pt <= 0:
            el.set("w", "0")
            etree.SubElement(el, qn("a:noFill"))
        else:
            el.set("w", str(int(round(width_pt * 12700))))
            el.set("cap", "flat")
            el.set("cmpd", "sng")
            el.set("algn", "ctr")
            sf = etree.SubElement(el, qn("a:solidFill"))
            srgb = etree.SubElement(sf, qn("a:srgbClr"))
            srgb.set("val", rgb_hex)

    for r_idx in range(n_rows):
        for c_idx in range(n_cols):
            cell = table.cell(r_idx, c_idx)
            cell.fill.background()
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tcPr = cell._tc.get_or_add_tcPr()
            _set_border(tcPr, "lnL", None)
            _set_border(tcPr, "lnR", None)
            _set_border(tcPr, "lnT", 1.5 if r_idx == 0 else None)
            if r_idx == 0:
                _set_border(tcPr, "lnB", 0.75)
            elif r_idx == n_rows - 1:
                _set_border(tcPr, "lnB", 1.5)
            else:
                _set_border(tcPr, "lnB", None)


def apply_zebra_table_borders(
    table,
    header_bg_hex: str = "#00468B",
    stripe_bg_hex: str = "#F5F8FC",
    border_hex: str = "#D8E2EC",
) -> None:
    """Style a python-pptx table with solid theme header and clean zebra-striped rows."""
    n_rows = len(table.rows)
    n_cols = len(table.columns)
    hr, hg, hb = hex_to_rgb(header_bg_hex)
    sr, sg, sb = hex_to_rgb(stripe_bg_hex)
    b_hex = border_hex.lstrip("#").upper()

    def _set_thin_border(tcPr, edge: str, width_pt: Optional[float]) -> None:
        tag = qn(f"a:{edge}")
        old = tcPr.find(tag)
        if old is not None:
            tcPr.remove(old)
        el = etree.SubElement(tcPr, tag)
        if width_pt is None or width_pt <= 0:
            el.set("w", "0")
            etree.SubElement(el, qn("a:noFill"))
        else:
            el.set("w", str(int(round(width_pt * 12700))))
            sf = etree.SubElement(el, qn("a:solidFill"))
            srgb = etree.SubElement(sf, qn("a:srgbClr"))
            srgb.set("val", b_hex)

    for r_idx in range(n_rows):
        for c_idx in range(n_cols):
            cell = table.cell(r_idx, c_idx)
            cell.fill.solid()
            if r_idx == 0:
                cell.fill.fore_color.rgb = RGBColor(hr, hg, hb)
            elif r_idx % 2 == 1:
                cell.fill.fore_color.rgb = RGBColor(255, 255, 255)
            else:
                cell.fill.fore_color.rgb = RGBColor(sr, sg, sb)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tcPr = cell._tc.get_or_add_tcPr()
            _set_thin_border(tcPr, "lnL", None)
            _set_thin_border(tcPr, "lnR", None)
            _set_thin_border(tcPr, "lnT", 0.5 if r_idx > 0 else None)
            _set_thin_border(tcPr, "lnB", 0.75 if r_idx == n_rows - 1 else 0.5)
