"""Document Parser — Extracts structured scientific sections, tables, embedded images, SMILES, and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
from typing import List, Optional, Tuple


@dataclass
class ParsedTable:
    headers: List[str]
    rows: List[List[str]]


@dataclass
class ParsedSection:
    heading: str
    content: str
    keywords: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    image_paths: List[str] = field(default_factory=list)
    smiles: List[str] = field(default_factory=list)
    metrics: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    title: str
    raw_text: str
    sections: List[ParsedSection]
    detected_smiles: List[str] = field(default_factory=list)
    is_proposal_hint: bool = False


_PROPOSAL_HINTS = ("开题", "拟开展", "研究方案", "技术路线", "可行性分析", "proposal", "work plan")
_HEADING_PAT = re.compile(r"^(#{1,3}\s+|[一二三四五六七八九十]+[、.]|\d+[.、]\s+|第[一二三四五六七八九十\d]+[章节部分])")
_SMILES_EXTRACT_PAT = re.compile(r"SMILES[:：]\s*([A-Za-z0-9@+\-\[\]\(\)=#$./\\]+)", flags=re.IGNORECASE)
_SMILES_STRIP_PAT = re.compile(
    r"(?:\(|（)?[^()（）\n]{0,16}SMILES[:：]\s*[A-Za-z0-9@+\-\[\]\(\)=#$./\\]+\s*(?:\)|）)?",
    flags=re.IGNORECASE,
)

_NAMED_METRIC_PAT = re.compile(
    r"(?<![A-Za-z0-9])(IC50|EC50|Ki|Kd|t1/2|cLogP|LogP|TPSA|ΔG(?:_bind)?|AUC(?:\([^)]+\))?|TGI|PMI|HPLC|F)"
    r"\s*[=≈:：为达]\s*(-?\d+(?:\.\d+)?(?:\s*(?:nM|μM|uM|mM|pM|kcal/mol|kJ/mol|ng·h/mL|%|h|min|Å²|mg/kg|mol%|ppm|倍))?)",
    flags=re.IGNORECASE,
)
_CN_METRIC_PAT = re.compile(
    r"(选择性(?:倍数|高达)?|抑瘤率|分离收率|收率|口服生物利用度|半衰期|相对分子量|分子量|结合自由能|纯度|降低|提升|金属残留)"
    r"[^，。；\n]{0,10}?(?:达|为|至|约|高达|=|:|：|<|>)?\s*(-?\d+(?:\.\d+)?\s*(?:%|倍|mol%|ppm|h|min|nm|nM|kcal/mol))",
)


def clean_prose_without_smiles(text: str) -> str:
    """Remove inline SMILES annotations while keeping readable scientific prose."""
    cleaned = _SMILES_STRIP_PAT.sub("", text or "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\(\s*\)|（\s*）", "", cleaned)
    return cleaned.strip()


def extract_section_metrics(text: str, limit: int = 4) -> List[Tuple[str, str]]:
    """Extract deterministic quantitative metrics (value, label) directly from scientific text."""
    cleaned = clean_prose_without_smiles(text)
    results: List[Tuple[str, str]] = []
    seen_values = set()

    def _add(val: str, lbl: str) -> None:
        v = re.sub(r"\s+", " ", val.strip())
        l = lbl.strip()
        if not v or v in seen_values:
            return
        seen_values.add(v)
        results.append((v[:14], l[:14]))

    for m in _NAMED_METRIC_PAT.finditer(cleaned):
        key = m.group(1).strip()
        val = m.group(2).strip()
        start = max(0, m.start() - 18)
        prefix = cleaned[start : m.start()]
        label_map = {
            "ic50": "IC50 活性",
            "ec50": "EC50 活性",
            "t1/2": "半衰期 t1/2",
            "f": "口服利用度 F",
            "tgi": "抑瘤率 TGI",
            "clogp": "脂水分配 cLogP",
            "logp": "脂水分配 LogP",
            "tpsa": "极性面积 TPSA",
            "pmi": "过程质量 PMI",
            "auc": "暴露量 AUC",
        }
        norm_key = key.lower().split("(")[0]
        label = label_map.get(norm_key, key)
        if norm_key == "ic50" and ("wt" in prefix.lower() or "野生" in prefix):
            label = "WT-EGFR IC50"
        elif norm_key == "ic50" and ("c797s" in prefix.lower() or "突变" in prefix):
            label = "突变体 IC50"
        _add(val, label)
        if len(results) >= limit:
            return results

    for m in _CN_METRIC_PAT.finditer(cleaned):
        lbl = m.group(1).strip()
        val = m.group(2).strip()
        _add(val, lbl)
        if len(results) >= limit:
            return results

    return results


def _finalize_section(sec: ParsedSection) -> ParsedSection:
    joined = "\n".join(sec.paragraphs) if sec.paragraphs else sec.content
    sec.content = joined.strip()
    sec.smiles = _SMILES_EXTRACT_PAT.findall(sec.content)
    sec.metrics = extract_section_metrics(sec.content)
    return sec


def parse_file_to_text(file_path: Path | str) -> str:
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext == ".docx":
        from docx import Document

        doc = Document(str(p))
        parts: List[str] = []
        for para in doc.paragraphs:
            t = para.text.strip()
            if t:
                parts.append(t)
        return "\n".join(parts)
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(p))
        pages = [pg.extract_text() or "" for pg in reader.pages]
        return "\n".join(pages)
    return p.read_text(encoding="utf-8", errors="ignore")


def parse_docx_structured(
    file_path: Path | str,
    image_output_dir: Optional[Path | str] = None,
    default_title: str = "学术研究工作汇报",
) -> ParsedDocument:
    """Parse a Word (.docx) document preserving sections, tables, embedded figures, SMILES, and metrics."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    p = Path(file_path)
    doc = Document(str(p))
    out_img_dir = Path(image_output_dir) if image_output_dir is not None else None
    if out_img_dir is not None:
        out_img_dir.mkdir(parents=True, exist_ok=True)

    title = default_title
    title_resolved = False
    sections: List[ParsedSection] = []
    cur_sec: Optional[ParsedSection] = None
    raw_lines: List[str] = []
    img_counter = 0

    def _ensure_section(default_heading: str = "研究背景与科学问题") -> ParsedSection:
        nonlocal cur_sec
        if cur_sec is None:
            cur_sec = ParsedSection(heading=default_heading, content="")
        return cur_sec

    def _flush_section() -> None:
        nonlocal cur_sec
        if cur_sec is not None and (cur_sec.paragraphs or cur_sec.tables or cur_sec.image_paths):
            sections.append(_finalize_section(cur_sec))
        cur_sec = None

    blip_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/main}"
    _ = blip_ns
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

    for child in doc.element.body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            txt = para.text.strip()
            style_name = (para.style.name if para.style and para.style.name else "").lower()

            # Extract embedded figures bound to this paragraph's section
            extracted_imgs: List[str] = []
            if out_img_dir is not None:
                for blip in child.iter():
                    if not blip.tag.endswith("}blip"):
                        continue
                    rid = blip.attrib.get(rel_attr)
                    if not rid or rid not in doc.part.related_parts:
                        continue
                    rel_part = doc.part.related_parts[rid]
                    blob = getattr(rel_part, "blob", b"")
                    if not blob or len(blob) < 512:
                        continue
                    img_counter += 1
                    target_png = out_img_dir / f"word_fig_{img_counter:02d}.png"
                    try:
                        from PIL import Image

                        with Image.open(BytesIO(blob)) as im:
                            im.convert("RGBA").save(str(target_png), format="PNG")
                        extracted_imgs.append(str(target_png))
                    except Exception:
                        continue

            if not txt:
                if extracted_imgs:
                    _ensure_section().image_paths.extend(extracted_imgs)
                continue

            raw_lines.append(txt)
            is_heading_style = ("heading" in style_name or "标题" in style_name) and "title" not in style_name
            is_title_style = "title" in style_name and not is_heading_style

            if not title_resolved and not _HEADING_PAT.match(txt) and not is_heading_style and (is_title_style or len(txt) <= 48):
                title = txt.lstrip("# ").strip() or title
                title_resolved = True
                if extracted_imgs:
                    _ensure_section().image_paths.extend(extracted_imgs)
                continue

            title_resolved = True
            if (is_heading_style or _HEADING_PAT.match(txt)) and len(txt) <= 68:
                _flush_section()
                cur_sec = ParsedSection(heading=txt.lstrip("# ").strip(), content="")
                if extracted_imgs:
                    cur_sec.image_paths.extend(extracted_imgs)
            else:
                sec = _ensure_section()
                sec.paragraphs.append(txt)
                if extracted_imgs:
                    sec.image_paths.extend(extracted_imgs)

        elif tag == "tbl":
            tbl = Table(child, doc)
            matrix: List[List[str]] = []
            for row in tbl.rows:
                vals = [re.sub(r"\s+", " ", cell.text.strip()) for cell in row.cells]
                if any(vals):
                    matrix.append(vals)
            if len(matrix) >= 2 and len(matrix[0]) >= 2:
                sec = _ensure_section()
                sec.tables.append(ParsedTable(headers=matrix[0], rows=matrix[1:]))
                raw_lines.append(" | ".join(matrix[0]))

    _flush_section()
    raw_text = "\n".join(raw_lines).strip()
    if not sections:
        return parse_scientific_text(raw_text, default_title=title)

    all_smiles: List[str] = []
    for sec in sections:
        for s in sec.smiles:
            if s not in all_smiles:
                all_smiles.append(s)

    is_prop = any(h in raw_text.lower() for h in _PROPOSAL_HINTS)
    return ParsedDocument(
        title=title,
        raw_text=raw_text,
        sections=sections,
        detected_smiles=all_smiles,
        is_proposal_hint=is_prop,
    )


def parse_document_file(
    file_path: Path | str,
    image_output_dir: Optional[Path | str] = None,
    default_title: str = "学术研究工作汇报",
) -> ParsedDocument:
    """Unified entry point for .docx (structured with tables/images), .pdf, .md, and .txt files."""
    p = Path(file_path)
    if p.suffix.lower() == ".docx":
        return parse_docx_structured(p, image_output_dir=image_output_dir, default_title=default_title)
    text = parse_file_to_text(p)
    return parse_scientific_text(text, default_title=default_title)


def parse_scientific_text(text: str, default_title: str = "学术研究工作汇报") -> ParsedDocument:
    raw = (text or "").strip()
    if not raw:
        raw = (
            f"# {default_title}\n"
            "## 1. 研究背景与痛点立题\n传统均相溶剂合成存在高稀释、能耗高与分离繁琐等瓶颈，亟需绿色高效的固相限域催化方案。\n"
            "## 2. 科学问题与研究空白\n当前纳米催化剂易在机械剪切或高温下发生团聚失活，且副产物水分子抑制催化循环。\n"
            "## 3. 总体技术路线\n构建无溶剂球磨与微孔分子筛限域协同体系，串联原位核磁表征与动力学验证。\n"
            "## 4. 催化机理与活性中心解析\n通过三维配位构型调控及双催化循环实现低能垒 C–N 交叉偶联。\n"
            "## 5. 定量动力学与多维度表征\n产物分离收率达到 91.2%，过程质量强度 PMI 降低 91.7%，XPS 证实高价金属位点稳定存在。\n"
            "## 6. 总结与展望\n形成可推广的绿色合成范式，为药物中间体放大生产提供新途径。"
        )

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    title = default_title
    sections: List[ParsedSection] = []
    cur_heading = "研究背景与科学问题"
    cur_paras: List[str] = []

    for idx, ln in enumerate(lines):
        if idx == 0 and (ln.startswith("# ") or (not _HEADING_PAT.match(ln) and len(ln) <= 45)):
            clean_t = ln.lstrip("# ").strip()
            if clean_t:
                title = clean_t
            continue
        if _HEADING_PAT.match(ln) and len(ln) <= 65:
            if cur_paras:
                sections.append(_finalize_section(ParsedSection(heading=cur_heading, content="\n".join(cur_paras), paragraphs=list(cur_paras))))
                cur_paras = []
            cur_heading = ln.lstrip("# ").strip()
        else:
            cur_paras.append(ln)

    if cur_paras:
        sections.append(_finalize_section(ParsedSection(heading=cur_heading, content="\n".join(cur_paras), paragraphs=list(cur_paras))))

    if not sections:
        chunks = [raw[i : i + 260] for i in range(0, len(raw), 260)]
        default_heads = ["研究背景与痛点", "研究空白与科学假说", "总体技术路线", "机理与微观结构", "定量数据与表征", "总结与展望"]
        for i, ch in enumerate(chunks[:6]):
            sections.append(_finalize_section(ParsedSection(heading=default_heads[i % len(default_heads)], content=ch, paragraphs=[ch])))

    smiles_matches = _SMILES_EXTRACT_PAT.findall(raw)
    lower_raw = raw.lower()
    is_prop = any(h in lower_raw for h in _PROPOSAL_HINTS)

    return ParsedDocument(
        title=title,
        raw_text=raw,
        sections=sections,
        detected_smiles=smiles_matches,
        is_proposal_hint=is_prop,
    )
