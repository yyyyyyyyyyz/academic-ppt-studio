"""Run-Level Word Sync — Preserves Original XML Font/Color Formatting While Offloading Overflow."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from docx import Document
from pptx import Presentation

from .xml_utils import normalize_scientific_markup


def extract_docx_sections(docx_path: Path | str) -> Dict[str, str]:
    """Extract heading -> body paragraph text mapping from a Word (.docx) document."""
    doc = Document(str(docx_path))
    sections: Dict[str, List[str]] = {}
    current_heading = "Overview"
    sections[current_heading] = []

    for para in doc.paragraphs:
        txt = para.text.strip()
        if not txt:
            continue
        style_name = (para.style.name or "").lower() if para.style else ""
        if "heading" in style_name or txt.startswith(("1.", "2.", "3.", "4.", "一、", "二、", "三、", "四、")):
            current_heading = txt
            sections.setdefault(current_heading, [])
        else:
            sections[current_heading].append(txt)

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def _replace_paragraph_runs_preserving_style(paragraph, new_text: str) -> None:
    """Replace text inside existing XML runs without calling shape.text = ... (preserves fonts & colors)."""
    clean_text = normalize_scientific_markup(new_text).replace("_{", "").replace("^{", "").replace("}", "")
    if not paragraph.runs:
        r = paragraph.add_run()
        r.text = clean_text
        return
    paragraph.runs[0].text = clean_text
    for r in paragraph.runs[1:]:
        r.text = ""


def sync_word_into_pptx(
    docx_path: Path | str,
    input_pptx: Path | str,
    output_pptx: Path | str,
    max_slide_chars: int = 70,
) -> Dict[str, object]:
    """Synchronize updated Word prose into an existing .pptx while preserving run styles and offloading excess to notes."""
    sections = extract_docx_sections(docx_path)
    prs = Presentation(str(input_pptx))
    updated_slides: List[int] = []

    section_items = list(sections.items())
    for s_idx, slide in enumerate(prs.slides, start=1):
        # Match by slide title substring or fallback sequential section
        title_shape = None
        takeaway_shape = None
        for shp in slide.shapes:
            if not shp.has_text_frame:
                continue
            if getattr(shp, "name", "") == "L3_title":
                title_shape = shp
            elif getattr(shp, "name", "") == "L3_takeaway":
                takeaway_shape = shp

        matched_text: Optional[str] = None
        slide_title = title_shape.text_frame.text.strip() if title_shape else ""
        for heading, body in section_items:
            if slide_title and (slide_title[:4] in heading or heading[:4] in slide_title):
                matched_text = body
                break

        if not matched_text and section_items and takeaway_shape is not None:
            matched_text = section_items[min(s_idx - 1, len(section_items) - 1)][1]

        if matched_text and takeaway_shape is not None and takeaway_shape.text_frame.paragraphs:
            short_takeaway = matched_text.splitlines()[0][:max_slide_chars]
            if len(matched_text.splitlines()[0]) > max_slide_chars:
                short_takeaway = short_takeaway.rstrip("，。.; ") + "。"
            _replace_paragraph_runs_preserving_style(takeaway_shape.text_frame.paragraphs[0], short_takeaway)

            # Offload full detail cleanly to speaker notes
            notes_tf = slide.notes_slide.notes_text_frame
            existing_notes = notes_tf.text.strip()
            sync_block = f"\n[Word Sync Update]\n{matched_text}"
            notes_tf.text = (existing_notes + sync_block).strip()
            updated_slides.append(s_idx)

    out_p = Path(output_pptx)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_p))
    return {
        "updated_slides": updated_slides,
        "sections_parsed": len(sections),
        "output_pptx": str(out_p),
    }
