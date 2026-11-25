"""Automated PPTX Audit Gatekeeper (audit_pptx.py).

Enforces all non-negotiable engineering rules before delivery:
1. Zero filled body textboxes in zero_fill_frameless mode
2. Strict >= 14.0 pt minimum font size across all body textboxes, tables, charts, and native molecular groups
   (while allowing refined 9.0–12.0 pt micro-chrome on nav English subtitles, footers, TOC English subtitles)
3. Explicit XML <a:ea> & <a:latin> dual-font binding on every text run, table cell, group atom label, and chart <c:txPr>
4. Valid OOXML XSD element ordering on chart <c:txPr>, <c:spPr>, and non-overlapping <c:overlay val="0"/>
5. Zero raw Unicode sub/superscript glyphs (₀-₉, ⁰-⁹)
6. Every content slide possesses >= 1 valid publication-grade figure (Native Chart, L1_ Native Group, or Picture, QA >= 8.5)
7. Zero full-slide baked images (> 85% of slide area), zero out-of-bounds or overlapping text shapes
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from ..schemas.deck_spec import AuditReport, AuditViolation, DeckSpec, DesignStyle, SlideType, V5_LAYOUT_IDS


UNICODE_FORBIDDEN = set("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
EMU_PER_INCH = 914400.0
_MICRO_CHROME_PREFIXES = (
    "L3_nav_tab_en_",
    "L3_nav_crest",
    "L3_footer_",
    "L3_page_num",
    "L3_toc_sub_",
    "L3_toc_page_",
    "L3_toc_tag",
    "L3_dossier_auth",
    "L3_mol_tag_",
    "L3_pocket_lbl_",
)


def _has_solid_fill(shape) -> bool:
    try:
        spPr = shape._element.spPr
        if spPr is None:
            return False
        if spPr.find(qn("a:solidFill")) is not None:
            return True
    except Exception:
        pass
    return False


def _rects_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], tol: float = 0.08) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix = min(ax2, bx2) - max(ax1, bx1)
    iy = min(ay2, by2) - max(ay1, by1)
    return ix > tol and iy > tol


def _child_idx(parent, localname: str) -> Optional[int]:
    for i, ch in enumerate(list(parent)):
        if etree.QName(ch).localname == localname:
            return i
    return None


def audit_pptx(pptx_path: Path | str, deck_spec: Optional[DeckSpec] = None) -> AuditReport:
    """Run full programmatic quality, editability, OOXML schema, & font audit on a generated .pptx file."""
    p = Path(pptx_path)
    prs = Presentation(str(p))

    canvas_w = prs.slide_width / EMU_PER_INCH
    canvas_h = prs.slide_height / EMU_PER_INCH
    slide_area = canvas_w * canvas_h

    expected_latin = "Arial"
    expected_ea = "微软雅黑"
    if deck_spec and deck_spec.locked_standards and deck_spec.locked_standards.fonts:
        expected_latin = deck_spec.locked_standards.fonts.get("latin", "Arial")
        expected_ea = deck_spec.locked_standards.fonts.get("ea", "微软雅黑")

    violations: List[AuditViolation] = []
    filled_body_boxes = 0
    min_body_pt = 999.0
    min_any_pt = 999.0
    unicode_sub_sup_count = 0
    missing_xml_font_runs = 0
    slides_missing_figure: List[int] = []
    slides_below_qa: List[int] = []
    full_slide_baked: List[int] = []
    overlap_count = 0
    oob_count = 0
    content_slides = 0

    def _floor_for_shape(shp_name: str, is_v5_slide: bool) -> float:
        if any(shp_name.startswith(pref) for pref in _MICRO_CHROME_PREFIXES):
            return 9.0 if is_v5_slide else 14.0
        if shp_name.startswith("L3_nav_tab_"):
            return 13.0
        return 14.0

    def _audit_text_runs(s_idx: int, shp_name: str, paragraphs, *, check_body_18: bool = False, min_floor: float = 14.0) -> None:
        nonlocal min_body_pt, min_any_pt, unicode_sub_sup_count, missing_xml_font_runs
        is_micro = any(shp_name.startswith(pref) for pref in _MICRO_CHROME_PREFIXES)
        for para in paragraphs:
            for run in para.runs:
                txt = run.text or ""
                if not txt.strip():
                    continue
                bad_u = sum(1 for c in txt if c in UNICODE_FORBIDDEN)
                if bad_u > 0:
                    unicode_sub_sup_count += bad_u
                    violations.append(AuditViolation(slide_no=s_idx, rule="native_xml_sub_sup", message=f"Raw Unicode sub/sup glyph found in '{txt[:20]}'."))

                pt_val = run.font.size.pt if run.font.size else 18.0
                if not is_micro:
                    min_any_pt = min(min_any_pt, pt_val)
                if pt_val < min_floor - 0.05:
                    violations.append(AuditViolation(slide_no=s_idx, rule="min_any_pt", message=f"Text run below {min_floor:.1f}pt ({pt_val:.1f}pt) in {shp_name or 'shape'}: '{txt[:20]}'"))
                if check_body_18:
                    min_body_pt = min(min_body_pt, pt_val)
                    if pt_val < 18.0 - 0.05:
                        violations.append(AuditViolation(slide_no=s_idx, rule="min_body_pt", message=f"Body run below 18pt ({pt_val:.1f}pt): '{txt[:20]}'"))

                rPr = run._r.find(qn("a:rPr"))
                if rPr is None:
                    missing_xml_font_runs += 1
                    violations.append(AuditViolation(slide_no=s_idx, rule="xml_dual_font", message=f"Run '{txt[:15]}' missing <a:rPr>."))
                else:
                    latin_el = rPr.find(qn("a:latin"))
                    ea_el = rPr.find(qn("a:ea"))
                    if latin_el is None or latin_el.get("typeface") != expected_latin or ea_el is None or ea_el.get("typeface") != expected_ea:
                        missing_xml_font_runs += 1
                        violations.append(AuditViolation(slide_no=s_idx, rule="xml_dual_font", message=f"Run '{txt[:15]}' missing explicit {expected_latin} + {expected_ea} XML binding."))

    def _audit_chart_fonts(s_idx: int, shp) -> None:
        nonlocal min_any_pt, missing_xml_font_runs
        cs = shp.chart._chartSpace
        txprs = cs.findall(f".//{qn('c:txPr')}")
        if not txprs:
            missing_xml_font_runs += 1
            violations.append(AuditViolation(slide_no=s_idx, rule="chart_font", message=f"Chart {getattr(shp, 'name', '')} missing <c:txPr> typography specification."))
            return
        for tp in txprs:
            for def_rpr in tp.findall(f".//{qn('a:defRPr')}"):
                sz_str = def_rpr.get("sz")
                if sz_str and sz_str.isdigit():
                    pt_val = int(sz_str) / 100.0
                    min_any_pt = min(min_any_pt, pt_val)
                    if pt_val < 14.0 - 0.05:
                        violations.append(AuditViolation(slide_no=s_idx, rule="chart_font", message=f"Chart text below 14.0pt ({pt_val:.1f}pt)."))
                lat = def_rpr.find(qn("a:latin"))
                ea = def_rpr.find(qn("a:ea"))
                if lat is None or lat.get("typeface") != expected_latin or ea is None or ea.get("typeface") != expected_ea:
                    missing_xml_font_runs += 1
                    violations.append(AuditViolation(slide_no=s_idx, rule="chart_font", message=f"Chart <c:txPr> missing {expected_latin} + {expected_ea} binding."))

        # Strict OOXML element order validation (txPr / spPr / overlay)
        i_tx, i_ext = _child_idx(cs, "txPr"), _child_idx(cs, "externalData")
        if i_tx is not None and i_ext is not None and i_tx > i_ext:
            violations.append(AuditViolation(slide_no=s_idx, rule="chart_ooxml_order", message="chartSpace <c:txPr> appears after <c:externalData>."))

        for ax_tag in ("c:catAx", "c:valAx"):
            for ax_el in cs.findall(f".//{qn(ax_tag)}"):
                itx, icr = _child_idx(ax_el, "txPr"), _child_idx(ax_el, "crossAx")
                if itx is not None and icr is not None and itx > icr:
                    violations.append(AuditViolation(slide_no=s_idx, rule="chart_ooxml_order", message=f"{ax_tag} <c:txPr> appears after <c:crossAx>."))

        for ser_el in cs.findall(f".//{qn('c:ser')}"):
            isp, ival = _child_idx(ser_el, "spPr"), _child_idx(ser_el, "val")
            if ival is None:
                ival = _child_idx(ser_el, "yVal")
            if isp is not None and ival is not None and isp > ival:
                violations.append(AuditViolation(slide_no=s_idx, rule="chart_ooxml_order", message="Chart series <c:spPr> appears after <c:val>."))

        leg_el = cs.find(f".//{qn('c:legend')}")
        if leg_el is not None:
            ov = leg_el.find(qn("c:overlay"))
            if ov is not None and ov.get("val") == "1":
                violations.append(AuditViolation(slide_no=s_idx, rule="chart_legend_overlay", message="Chart legend has overlay=1 (may overlap plot area)."))

    def _walk_group_shapes(s_idx: int, grp, is_v5_slide: bool) -> None:
        for sub in grp.shapes:
            sub_name = getattr(sub, "name", "") or ""
            if sub.shape_type == MSO_SHAPE_TYPE.GROUP:
                _walk_group_shapes(s_idx, sub, is_v5_slide)
            elif sub.has_text_frame:
                _audit_text_runs(s_idx, sub_name, sub.text_frame.paragraphs, check_body_18=False, min_floor=_floor_for_shape(sub_name, is_v5_slide))

    for s_idx, slide in enumerate(prs.slides, start=1):
        spec_slide = deck_spec.slides[s_idx - 1] if (deck_spec and s_idx - 1 < len(deck_spec.slides)) else None
        is_structural = False
        if spec_slide:
            is_structural = spec_slide.slide_type in (SlideType.cover, SlideType.toc, SlideType.part_divider, SlideType.closing)
        else:
            has_content_header = any(getattr(sh, "name", "") == "L3_title" for sh in slide.shapes)
            is_structural = not has_content_header

        is_v5_slide = False
        if spec_slide and deck_spec:
            is_v5_slide = (spec_slide.layout_id in V5_LAYOUT_IDS) or (deck_spec.meta.design_style != DesignStyle.zero_fill_frameless)
        else:
            is_v5_slide = any(getattr(sh, "name", "") in ("L2_nav_bg", "L2_toc_left_bg", "L2_top_solid_bar", "L2_editorial_rule") for sh in slide.shapes)

        if not is_structural:
            content_slides += 1

        fig_count = 0
        text_boxes: List[Tuple[str, Tuple[float, float, float, float]]] = []

        for shp in slide.shapes:
            left_in = shp.left / EMU_PER_INCH
            top_in = shp.top / EMU_PER_INCH
            w_in = shp.width / EMU_PER_INCH
            h_in = shp.height / EMU_PER_INCH
            name = getattr(shp, "name", "") or ""

            if left_in < -0.10 or top_in < -0.10 or (left_in + w_in) > canvas_w + 0.12 or (top_in + h_in) > canvas_h + 0.12:
                oob_count += 1
                violations.append(AuditViolation(slide_no=s_idx, rule="bounds", message=f"Shape {name or shp.shape_type} exceeds canvas bounds."))

            if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
                fig_count += 1
                area_ratio = (w_in * h_in) / max(slide_area, 1.0)
                if area_ratio > 0.85:
                    full_slide_baked.append(s_idx)
                    violations.append(AuditViolation(slide_no=s_idx, rule="no_baked_slide", message=f"Picture occupies {area_ratio:.1%} of slide (>85% limit)."))

            if getattr(shp, "has_chart", False):
                fig_count += 1
                _audit_chart_fonts(s_idx, shp)

            if shp.shape_type == MSO_SHAPE_TYPE.GROUP:
                if name.startswith("L1_"):
                    fig_count += 1
                _walk_group_shapes(s_idx, shp, is_v5_slide)

            if shp.has_text_frame:
                if name.startswith("L3_") and not name.startswith("L3_asset_lbl_") and not name.startswith("L3_pk_bar_plot_delta_") and not name.startswith("L3_nav_tab_"):
                    text_boxes.append((name, (left_in, top_in, left_in + w_in, top_in + h_in)))

                is_thin_bar = w_in < 0.12 or h_in < 0.12
                has_text_content = bool(shp.text_frame.text.strip())
                if not is_v5_slide and not is_structural and not is_thin_bar and has_text_content and _has_solid_fill(shp):
                    filled_body_boxes += 1
                    violations.append(AuditViolation(slide_no=s_idx, rule="zero_fill_frameless", message=f"Filled text box detected on slide {s_idx}: {name}"))

                is_small_allowed = any(tag in name for tag in ("eyebrow", "page_num", "caption", "footer", "kpi_lbl", "asset_lbl", "overlay_lbl", "_delta_"))
                check_18 = (not is_v5_slide and not is_structural and not is_small_allowed)
                _audit_text_runs(s_idx, name, shp.text_frame.paragraphs, check_body_18=check_18, min_floor=_floor_for_shape(name, is_v5_slide))

                if is_v5_slide and name == "L3_title":
                    for para in shp.text_frame.paragraphs:
                        for run in para.runs:
                            if run.text.strip() and run.font.size and run.font.size.pt < 18.0:
                                violations.append(AuditViolation(slide_no=s_idx, rule="min_title_pt", message=f"v5.0 title below 18.0pt ({run.font.size.pt:.1f}pt)."))

            if shp.has_table:
                for row in shp.table.rows:
                    for cell in row.cells:
                        _audit_text_runs(s_idx, name or "table", cell.text_frame.paragraphs, check_body_18=False, min_floor=14.0)

        for i in range(len(text_boxes)):
            for j in range(i + 1, len(text_boxes)):
                n1, r1 = text_boxes[i]
                n2, r2 = text_boxes[j]
                if _rects_overlap(r1, r2, tol=0.10):
                    overlap_count += 1
                    violations.append(AuditViolation(slide_no=s_idx, rule="overlap", message=f"Text boxes {n1} and {n2} overlap."))

        if not is_structural and fig_count == 0:
            slides_missing_figure.append(s_idx)
            violations.append(AuditViolation(slide_no=s_idx, rule="every_content_slide_has_figure", message=f"Content slide {s_idx} has zero scientific figure assets."))

        if not is_structural and spec_slide and spec_slide.figure_spec:
            if spec_slide.figure_spec.overall_qa_score < 8.5 or not spec_slide.figure_spec.qa_passed:
                slides_below_qa.append(s_idx)
                violations.append(AuditViolation(slide_no=s_idx, rule="figure_qa_score", message=f"Slide {s_idx} figure QA score {spec_slide.figure_spec.overall_qa_score} < 8.5."))

    if min_body_pt > 900:
        min_body_pt = 18.0
    if min_any_pt > 900:
        min_any_pt = 14.0

    passed = (
        len([v for v in violations if v.severity == "error"]) == 0
        and filled_body_boxes == 0
        and unicode_sub_sup_count == 0
        and missing_xml_font_runs == 0
        and len(slides_missing_figure) == 0
        and len(slides_below_qa) == 0
        and len(full_slide_baked) == 0
        and overlap_count == 0
        and oob_count == 0
    )

    return AuditReport(
        passed=passed,
        pptx_path=str(p),
        total_slides=len(prs.slides),
        content_slides=content_slides,
        filled_body_boxes=filled_body_boxes,
        min_body_pt_observed=round(min_body_pt, 2),
        min_any_pt_observed=round(min_any_pt, 2),
        unicode_sub_sup_count=unicode_sub_sup_count,
        missing_xml_font_runs=missing_xml_font_runs,
        slides_missing_figure=slides_missing_figure,
        slides_below_qa_score=slides_below_qa,
        full_slide_baked_images=full_slide_baked,
        overlap_count=overlap_count,
        out_of_bounds_count=oob_count,
        violations=violations,
    )
