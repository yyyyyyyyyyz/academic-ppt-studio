"""Slide Preview Renderer — LibreOffice soffice (when available) + Deterministic High-Res PIL Layer Renderer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..figure_factory.palettes import ScientificPalette, get_palette, hex_to_rgb
from ..figure_factory.vector_mech import compute_external_bitangents
from ..schemas.deck_spec import DeckSpec, DesignStyle, LayoutId, SlideSpec, SlideType, V5_LAYOUT_IDS
from .font_resolver import resolve_pil_font
from .v5_cover_renderer import (
    render_v5_closing_preview,
    render_v5_cover_preview,
    render_v5_part_divider_preview,
)
from .v5_renderer import render_v5_slide_preview, render_v5_toc_preview


SCALE_PX_PER_IN = 96.0  # 13.333 * 96 = 1280 x 720 crisp preview


def _load_font(size_pt: float, bold: bool = False, is_latin: bool = False) -> ImageFont.FreeTypeFont:
    px = max(12, int(round(size_pt * 1.3333)))
    return resolve_pil_font(px, is_cjk=not is_latin, bold=bold)


def _in_to_px(val: float) -> int:
    return int(round(val * SCALE_PX_PER_IN))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_w: int,
    font: ImageFont.FreeTypeFont,
    color: Tuple[int, int, int],
    line_spacing: float = 1.4,
    align: str = "left",
) -> None:
    clean = text.replace("_{", "").replace("^{", "").replace("}", "")
    if _has_cjk(clean):
        # Switch cleanly to Microsoft YaHei if caller requested Latin font on mixed CJK string
        font_sz = font.size if hasattr(font, "size") else 18
        bold_guess = "bd" in str(getattr(font, "path", "")).lower()
        font = _load_font(font_sz / 1.3333, bold=bold_guess, is_latin=False)
    lines: List[str] = []
    for raw_ln in clean.split("\n"):
        if not raw_ln:
            lines.append("")
            continue
        cur = ""
        # Tokenize by spaces for Latin word-preserving wrap, or character-by-character for CJK
        tokens = raw_ln.split(" ") if not _has_cjk(raw_ln) else list(raw_ln)
        sep = " " if not _has_cjk(raw_ln) else ""
        for tok in tokens:
            test = f"{cur}{sep}{tok}" if cur else tok
            bbox = draw.textbbox((0, 0), test, font=font)
            if (bbox[2] - bbox[0]) > max_w and cur:
                lines.append(cur)
                cur = tok
            else:
                cur = test
        if cur:
            lines.append(cur)

    line_h = int(round((font.size if hasattr(font, "size") else 18) * line_spacing))
    cy = y
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        lw = bbox[2] - bbox[0]
        tx = x
        if align == "center":
            tx = x + (max_w - lw) // 2
        elif align == "right":
            tx = x + max_w - lw
        draw.text((tx, cy), ln, font=font, fill=color)
        cy += line_h


def render_slide_preview_png(
    spec: SlideSpec,
    deck: DeckSpec,
    output_png: Path | str,
    layers: Sequence[str] = ("L1", "L2", "L3"),
) -> Path:
    """Render a high-res PNG preview of a SlideSpec with optional L1/L2/L3 layer toggling."""
    if spec.slide_type == SlideType.cover:
        cov_out = render_v5_cover_preview(spec, deck, output_png, layers=layers)
        if cov_out is not None:
            return cov_out
    if spec.slide_type == SlideType.part_divider:
        div_out = render_v5_part_divider_preview(spec, deck, output_png, layers=layers)
        if div_out is not None:
            return div_out
    if spec.slide_type == SlideType.closing:
        cls_out = render_v5_closing_preview(spec, deck, output_png, layers=layers)
        if cls_out is not None:
            return cls_out
    if spec.slide_type == SlideType.toc and deck.meta.design_style != DesignStyle.zero_fill_frameless:
        return render_v5_toc_preview(spec, deck, output_png, layers=layers)
    if spec.layout_id in V5_LAYOUT_IDS:
        v5_out = render_v5_slide_preview(spec, deck, output_png, layers=layers)
        if v5_out is not None:
            return v5_out
    w, h = 1280, 720
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    pal = get_palette(deck.meta.palette_id)
    total = len(deck.slides)

    show_l1 = "L1" in layers
    show_l2 = "L2" in layers
    show_l3 = "L3" in layers

    s1 = hex_to_rgb(pal.s1)
    s2 = hex_to_rgb(pal.s2)
    s3 = hex_to_rgb(pal.s3)
    ink = hex_to_rgb(pal.ink)
    muted = hex_to_rgb(pal.muted)
    line_c = hex_to_rgb(pal.line)
    alert_c = hex_to_rgb(pal.alert)

    # Layer 1: Scientific figure PNGs
    if show_l1 and spec.figure_spec:
        box = spec.figure_spec.box_in
        for asset in spec.figure_spec.assets:
            if not asset.png_path or not Path(asset.png_path).exists():
                continue
            nb = asset.norm_box if len(asset.norm_box) == 4 else [0.0, 0.0, 1.0, 1.0]
            ax = _in_to_px(box.left + nb[0] * box.width)
            ay = _in_to_px(box.top + nb[1] * box.height)
            aw = _in_to_px(nb[2] * box.width)
            ah = _in_to_px(nb[3] * box.height)
            with Image.open(asset.png_path) as im:
                rgba = im.convert("RGBA")
                if asset.engine.value == "chemdraw_rdkit" and asset.physical_width_in and asset.physical_height_in:
                    lock_w = _in_to_px(asset.physical_width_in)
                    lock_h = _in_to_px(asset.physical_height_in)
                    scale = min(1.0, aw / max(lock_w, 1), ah / max(lock_h, 1))
                    nw = max(1, int(round(lock_w * scale)))
                    nh = max(1, int(round(lock_h * scale)))
                else:
                    scale = min(aw / max(rgba.width, 1), ah / max(rgba.height, 1))
                    nw = max(1, int(round(rgba.width * scale)))
                    nh = max(1, int(round(rgba.height * scale)))
                resized = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                px = ax + (aw - nw) // 2
                py = ay + (ah - nh) // 2
                canvas.alpha_composite(resized, dest=(px, py))

    # Layer 2: Vector skeletons & overlays
    if show_l2:
        if spec.slide_type == SlideType.content:
            if total >= 11:
                seg_w = 12.40 / total
                for i in range(total):
                    col = s1 if i + 1 == spec.slide_no else (hex_to_rgb(pal.s4) if i + 1 < spec.slide_no else line_c)
                    draw.rectangle([_in_to_px(0.46 + i * seg_w), _in_to_px(0.08), _in_to_px(0.46 + (i + 1) * seg_w - 0.03), _in_to_px(0.125)], fill=col)

            draw.line([_in_to_px(0.46), _in_to_px(1.48), _in_to_px(1.71), _in_to_px(1.48)], fill=s1, width=3)
            draw.line([_in_to_px(1.71), _in_to_px(1.48), _in_to_px(12.86), _in_to_px(1.48)], fill=line_c, width=1)
            draw.line([_in_to_px(0.46), _in_to_px(6.94), _in_to_px(12.86), _in_to_px(6.94)], fill=line_c, width=1)

            if spec.layout_id == LayoutId.frameless_63_37:
                draw.line([_in_to_px(8.42), _in_to_px(1.72), _in_to_px(8.42), _in_to_px(6.72)], fill=line_c, width=1)
                if not (spec.table_data and spec.table_data.headers):
                    cur_y = 1.70 + (1.18 if spec.kpis else 0.0)
                    for _ in spec.insights[:3]:
                        draw.rectangle([_in_to_px(8.68), _in_to_px(cur_y + 0.06), _in_to_px(8.722), _in_to_px(cur_y + 0.38)], fill=s1)
                        cur_y += 1.32
        elif spec.slide_type == SlideType.cover:
            draw.line([_in_to_px(0.65), _in_to_px(1.35), _in_to_px(2.25), _in_to_px(1.35)], fill=s1, width=5)
            draw.line([_in_to_px(0.65), _in_to_px(5.10), _in_to_px(6.80), _in_to_px(5.10)], fill=line_c, width=1)

        if spec.figure_spec:
            for ov in spec.figure_spec.native_overlays:
                col = hex_to_rgb(pal.token(ov.color_token))
                if ov.type == "zoom_lens_frame" and ov.source_circle_in and ov.target_circle_in:
                    sx, sy, sr = ov.source_circle_in
                    tx, ty, tr = ov.target_circle_in
                    draw.ellipse([_in_to_px(sx - sr), _in_to_px(sy - sr), _in_to_px(sx + sr), _in_to_px(sy + sr)], outline=col, width=2)
                    draw.ellipse([_in_to_px(tx - tr), _in_to_px(ty - tr), _in_to_px(tx + tr), _in_to_px(ty + tr)], outline=col, width=3)
                    for p1, p2 in compute_external_bitangents((sx, sy, sr), (tx, ty, tr)):
                        draw.line([_in_to_px(p1[0]), _in_to_px(p1[1]), _in_to_px(p2[0]), _in_to_px(p2[1])], fill=col, width=2)
                elif ov.type in ("arrow", "dashed_connector", "reaction_arrow") and ov.from_in and ov.to_in:
                    x1, y1 = _in_to_px(ov.from_in[0]), _in_to_px(ov.from_in[1])
                    x2, y2 = _in_to_px(ov.to_in[0]), _in_to_px(ov.to_in[1])
                    draw.line([x1, y1, x2, y2], fill=col, width=3)
                    # Draw arrowhead at (x2, y2)
                    import math
                    ang = math.atan2(y2 - y1, x2 - x1)
                    ah_len = 12
                    p_left = (x2 - ah_len * math.cos(ang - 0.45), y2 - ah_len * math.sin(ang - 0.45))
                    p_right = (x2 - ah_len * math.cos(ang + 0.45), y2 - ah_len * math.sin(ang + 0.45))
                    draw.polygon([(x2, y2), p_left, p_right], fill=col)
                    if ov.label and show_l3:
                        mx = _in_to_px(0.5 * (ov.from_in[0] + ov.to_in[0]) - 0.85)
                        my = _in_to_px(min(ov.from_in[1], ov.to_in[1]) - 0.36)
                        _draw_wrapped_text(draw, ov.label, mx, my, _in_to_px(1.70), _load_font(14.0, True, True), col, 1.1, align="center")

    # Layer 3: Native typography
    if show_l3:
        if spec.slide_type == SlideType.cover:
            _draw_wrapped_text(draw, spec.eyebrow, _in_to_px(0.65), _in_to_px(0.92), _in_to_px(6.4), _load_font(14.5, True, True), s3)
            _draw_wrapped_text(draw, deck.meta.deck_title, _in_to_px(0.65), _in_to_px(1.56), _in_to_px(6.5), _load_font(28.0, True), s1, 1.25)
            _draw_wrapped_text(draw, deck.meta.deck_subtitle, _in_to_px(0.65), _in_to_px(3.32), _in_to_px(6.4), _load_font(18.0), muted, 1.4)
            _draw_wrapped_text(draw, f"汇报人：{deck.meta.author}   |   {deck.meta.affiliation}", _in_to_px(0.65), _in_to_px(5.26), _in_to_px(6.4), _load_font(18.0, True), ink)
        elif spec.slide_type == SlideType.closing:
            _draw_wrapped_text(draw, spec.title or "敬请各位专家批评指正", _in_to_px(1.5), _in_to_px(2.60), _in_to_px(10.33), _load_font(32.0, True), s1, align="center")
            _draw_wrapped_text(draw, spec.takeaway or f"{deck.meta.author} · {deck.meta.affiliation}", _in_to_px(1.8), _in_to_px(3.70), _in_to_px(9.73), _load_font(18.0), muted, align="center")
        elif spec.slide_type == SlideType.part_divider:
            _draw_wrapped_text(draw, spec.eyebrow, _in_to_px(1.1), _in_to_px(2.45), _in_to_px(11.0), _load_font(15.0, True, True), s3)
            _draw_wrapped_text(draw, spec.title, _in_to_px(1.1), _in_to_px(3.05), _in_to_px(11.0), _load_font(30.0, True), s1)
        else:
            _draw_wrapped_text(draw, spec.eyebrow, _in_to_px(0.46), _in_to_px(0.23), _in_to_px(8.50), _load_font(14.25, True, True), s3)
            _draw_wrapped_text(draw, f"{spec.slide_no:02d} / {total:02d}", _in_to_px(11.60), _in_to_px(0.23), _in_to_px(1.27), _load_font(14.25, True, True), muted, align="right")
            _draw_wrapped_text(draw, spec.title, _in_to_px(0.46), _in_to_px(0.52), _in_to_px(12.40), _load_font(24.0, True), s1, 1.1)
            if spec.takeaway:
                _draw_wrapped_text(draw, spec.takeaway, _in_to_px(0.46), _in_to_px(1.03), _in_to_px(12.40), _load_font(18.0), (51, 65, 85), 1.2)
            if spec.figure_spec:
                box = spec.figure_spec.box_in
                if show_l3:
                    for asset in spec.figure_spec.assets:
                        if asset.label:
                            nb = asset.norm_box if len(asset.norm_box) == 4 else [0.0, 0.0, 1.0, 1.0]
                            a_left = box.left + nb[0] * box.width
                            a_top = box.top + nb[1] * box.height
                            a_w = nb[2] * box.width
                            a_h = nb[3] * box.height
                            lbl_top = (a_top + a_h + 0.04) if (nb[1] + nb[3] <= 0.90) else (a_top + a_h - 0.34)
                            _draw_wrapped_text(
                                draw, asset.label,
                                _in_to_px(a_left), _in_to_px(lbl_top),
                                _in_to_px(a_w), _load_font(14.0, True, True), ink, 1.15, align="center",
                            )
                cap_top = min(max(box.top + box.height + 0.12, 6.22 if spec.layout_id == LayoutId.frameless_63_37 else box.top + box.height + 0.10), 6.30)
                _draw_wrapped_text(draw, spec.figure_spec.caption, _in_to_px(box.left), _in_to_px(cap_top), _in_to_px(box.width), _load_font(14.0, False, True), muted, 1.15)
            _draw_wrapped_text(draw, spec.footer_left, _in_to_px(0.46), _in_to_px(7.02), _in_to_px(8.2), _load_font(14.0, False, True), muted)
            _draw_wrapped_text(draw, f"{deck.meta.affiliation} · {pal.id.upper()}", _in_to_px(9.10), _in_to_px(7.02), _in_to_px(3.76), _load_font(14.0, False, True), muted, align="right")

            if spec.slide_type == SlideType.toc:
                for idx, item in enumerate((spec.toc_items or [])[:6]):
                    y = 2.05 + idx * 0.78
                    _draw_wrapped_text(draw, f"0{idx+1}   {item}", _in_to_px(0.85), _in_to_px(y), _in_to_px(11.2), _load_font(20.0, True), ink)
            elif spec.table_data and spec.table_data.headers:
                td = spec.table_data
                t_left, t_top, t_w = 8.68, 1.72, 4.18
                row_h = 0.46
                rows_count = len(td.rows) + 1
                cols_count = len(td.headers)
                col_w = t_w / max(cols_count, 1)
                # 3-line academic borders (top 1.5pt, header bottom 0.75pt, bottom 1.5pt)
                draw.line([_in_to_px(t_left), _in_to_px(t_top), _in_to_px(t_left + t_w), _in_to_px(t_top)], fill=ink, width=2)
                draw.line([_in_to_px(t_left), _in_to_px(t_top + row_h), _in_to_px(t_left + t_w), _in_to_px(t_top + row_h)], fill=ink, width=1)
                draw.line([_in_to_px(t_left), _in_to_px(t_top + row_h * rows_count), _in_to_px(t_left + t_w), _in_to_px(t_top + row_h * rows_count)], fill=ink, width=2)
                for c_i, hdr in enumerate(td.headers):
                    _draw_wrapped_text(
                        draw, hdr,
                        _in_to_px(t_left + c_i * col_w + 0.04), _in_to_px(t_top + 0.11),
                        _in_to_px(col_w - 0.08), _load_font(14.0, True, True), s1, 1.1,
                        align="center" if c_i > 0 else "left",
                    )
                for r_i, row in enumerate(td.rows):
                    ry = t_top + (r_i + 1) * row_h + 0.11
                    for c_i, val in enumerate(row[:cols_count]):
                        _draw_wrapped_text(
                            draw, val,
                            _in_to_px(t_left + c_i * col_w + 0.04), _in_to_px(ry),
                            _in_to_px(col_w - 0.08), _load_font(14.0, False, True), ink, 1.1,
                            align="center" if c_i > 0 else "left",
                        )
                cur_y = t_top + row_h * rows_count + 0.25
                for ins in spec.insights[:2]:
                    if show_l2:
                        draw.rectangle([_in_to_px(8.68), _in_to_px(cur_y + 0.06), _in_to_px(8.722), _in_to_px(cur_y + 0.38)], fill=s1)
                    _draw_wrapped_text(draw, f"{ins.index}  {ins.heading}", _in_to_px(8.82), _in_to_px(cur_y), _in_to_px(4.04), _load_font(18.0, True), ink, 1.15)
                    _draw_wrapped_text(draw, ins.body, _in_to_px(8.82), _in_to_px(cur_y + 0.38), _in_to_px(4.04), _load_font(18.0), ink, 1.38)
                    cur_y += 1.32
            elif spec.layout_id != LayoutId.full_roadmap:
                cur_y = 1.70
                if spec.kpis:
                    slot_w = 4.18 / len(spec.kpis[:2])
                    for idx, kp in enumerate(spec.kpis[:2]):
                        kx = 8.68 + idx * slot_w
                        _draw_wrapped_text(draw, kp.value, _in_to_px(kx), _in_to_px(cur_y), _in_to_px(slot_w - 0.1), _load_font(34.0, True, True), hex_to_rgb(pal.token(kp.color_token)))
                        _draw_wrapped_text(draw, kp.label, _in_to_px(kx), _in_to_px(cur_y + 0.58), _in_to_px(slot_w - 0.1), _load_font(14.0), muted)
                    cur_y += 1.18
                for ins in spec.insights[:3]:
                    _draw_wrapped_text(draw, f"{ins.index}  {ins.heading}", _in_to_px(8.82), _in_to_px(cur_y), _in_to_px(4.04), _load_font(18.0, True), ink, 1.15)
                    _draw_wrapped_text(draw, ins.body, _in_to_px(8.82), _in_to_px(cur_y + 0.38), _in_to_px(4.04), _load_font(18.0), ink, 1.38)
                    cur_y += 1.32

    out_p = Path(output_png)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(str(out_p), format="PNG")
    return out_p


def render_deck_previews(deck: DeckSpec, output_dir: Path | str, pptx_path: Optional[Path | str] = None) -> List[Path]:
    """Render all slides to PNG previews (using LibreOffice if installed, else deterministic PIL renderer)."""
    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)

    soffice = shutil.which("soffice")
    if soffice and pptx_path and Path(pptx_path).exists():
        try:
            pdf_dir = out_d / "_lo_pdf"
            pdf_dir.mkdir(exist_ok=True)
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(pptx_path)], check=True, timeout=60)
        except Exception:
            pass

    paths: List[Path] = []
    for spec in deck.slides:
        out_p = out_d / f"slide_{spec.slide_no:02d}.png"
        render_slide_preview_png(spec, deck, out_p)
        paths.append(out_p)
    return paths
