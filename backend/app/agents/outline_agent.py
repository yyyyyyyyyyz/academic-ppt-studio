"""Outline Agent — Skill-driven Word/PDF -> Structured PPT Outline Generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..figure_factory.chem_grounding import extract_compounds_from_text, resolve_compound_smiles
from ..providers.llm_image_provider import ModelProvider
from ..schemas.deck_spec import LayoutId, ScenarioType, V5_LAYOUT_IDS
from .doc_parser import ParsedDocument, clean_prose_without_smiles

_SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "word_to_outline_skill.md"

_ALLOWED_2D_STYLES = {
    "acs1996",
    "minimal_mono",
    "nature_burgundy",
    "jacs_terracotta",
    "shaded_scaffold",
    "reactive_spot",
}
_ALLOWED_3D_STYLES = {
    "ball_stick",
    "pymol_neon_green",
    "metallic_studio",
    "stick_clean",
    "spacefill_cpk",
}
_VALID_LAYOUT_IDS = {lid.value for lid in V5_LAYOUT_IDS}


def load_word_outline_skill() -> str:
    """Load the Skill Markdown guiding LLM Word->PPT outline summarization."""
    try:
        if _SKILL_PATH.is_file():
            txt = _SKILL_PATH.read_text(encoding="utf-8").strip()
            if txt:
                return txt
    except OSError:
        pass
    return (
        "你是药物化学科研 PPT 大纲架构师。请忠实提炼原文逻辑与真实数据，"
        "严格输出 JSON: {\"title\", \"summary\", \"slides\": [{\"section_name\", \"title\", "
        "\"takeaway\", \"bullets\", \"kpis\", \"compound_name\", \"smiles\", "
        "\"visual_mode\": \"2d\"|\"3d\", \"visual_style\", \"layout_id\"}]}。"
    )


def _format_outline_markdown(title: str, slides: List[Dict[str, Any]]) -> str:
    lines: List[str] = [f"# {title.strip() or '学术研究汇报'}"]
    for idx, sl in enumerate(slides, start=1):
        mode_tag = "3D" if str(sl.get("visual_mode", "")).lower() == "3d" else "2D"
        sl_title = str(sl.get("title") or sl.get("section_name") or f"第 {idx} 部分").strip()
        lines.append(f"## {idx}. {sl_title}（{mode_tag}）")
        takeaway = str(sl.get("takeaway") or "").strip()
        if takeaway:
            lines.append(takeaway)
        for b in sl.get("bullets") or []:
            bs = str(b).strip()
            if bs and bs != takeaway:
                lines.append(f"- {bs}")
        smi = str(sl.get("smiles") or "").strip()
        if smi:
            lines.append(f"SMILES: {smi}")
    return "\n".join(lines).strip()


class OutlineAgent:
    """Summarizes parsed Word/PDF documents into a structured PPT outline via Skill + ModelProvider."""

    def __init__(self, provider: Optional[ModelProvider] = None) -> None:
        self.provider = provider or ModelProvider()

    def _build_llm_outline(
        self,
        doc: ParsedDocument,
        num_content: int,
        scenario: ScenarioType,
        is_proposal: bool,
    ) -> Optional[Dict[str, Any]]:
        if self.provider.active_text_backend() == "local":
            return None

        skill_doc = load_word_outline_skill()
        table_summaries: List[str] = []
        for idx, sec in enumerate(doc.sections):
            for tbl in sec.tables[:2]:
                rows_txt = "; ".join([" | ".join(r[:5]) for r in ([tbl.headers] + tbl.rows[:4])])
                table_summaries.append(f"[Sec {idx + 1} Table]: {rows_txt}")
        compound_list = extract_compounds_from_text(doc.raw_text)[:15]
        compound_summary = (
            ", ".join(f"{lbl}={smi}" for lbl, smi in compound_list) if compound_list else "None detected"
        )
        section_headings = " / ".join(sec.heading for sec in doc.sections[:12]) or "N/A"

        sys_prompt = (
            f"{skill_doc}\n\n"
            f"本次任务要求：生成 EXACTLY {num_content} 个内容页条目（slides 数组长度必须为 {num_content}）。"
        )
        if is_proposal:
            sys_prompt += "\n【强制】本次为开题报告（is_proposal=true），严禁捏造未测实验结果、收率或数值曲线。"

        usr_prompt = (
            f"文档原标题：{doc.title}\n"
            f"汇报场景：{scenario.value}\n"
            f"是否开题报告：{is_proposal}\n"
            f"原文章节标题：{section_headings}\n"
            f"识别到的化合物与 SMILES：{compound_summary}\n"
            + (f"提取到的 Word 表格：\n" + "\n".join(table_summaries[:6]) + "\n" if table_summaries else "")
            + f"\n文档正文（截取前 14000 字）：\n{doc.raw_text[:14000]}"
        )

        res = self.provider.generate_json(sys_prompt, usr_prompt, timeout=50.0)
        if not isinstance(res, dict) or not isinstance(res.get("slides"), list) or not res["slides"]:
            return None

        norm_slides: List[Dict[str, Any]] = []
        for idx, raw in enumerate(res["slides"][:num_content]):
            if not isinstance(raw, dict):
                continue
            v_mode = "3d" if str(raw.get("visual_mode") or "").strip().lower() == "3d" else "2d"
            v_style = str(raw.get("visual_style") or "").strip()
            if v_mode == "3d" and v_style not in _ALLOWED_3D_STYLES:
                v_style = "ball_stick"
            if v_mode == "2d" and v_style not in _ALLOWED_2D_STYLES:
                v_style = "acs1996"
            lid = str(raw.get("layout_id") or "").strip()
            if lid not in _VALID_LAYOUT_IDS:
                lid = LayoutId.lit_overview_dual_card.value

            comp_name = str(raw.get("compound_name") or "").strip()
            smi_raw = str(raw.get("smiles") or "").strip()
            resolved_smi = (
                resolve_compound_smiles(smi_raw or comp_name, allow_pubchem=True)
                or (doc.detected_smiles[idx % len(doc.detected_smiles)] if doc.detected_smiles else "")
            )
            norm_slides.append(
                {
                    "section_name": str(raw.get("section_name") or raw.get("title") or f"章节 {idx + 1}")[:18],
                    "title": str(raw.get("title") or f"部分 {idx + 1}")[:24],
                    "takeaway": str(raw.get("takeaway") or "")[:50],
                    "bullets": [str(b).strip()[:36] for b in (raw.get("bullets") or [])[:3] if str(b).strip()],
                    "kpis": [
                        {"value": str(k.get("value", ""))[:14], "label": str(k.get("label", ""))[:14]}
                        for k in (raw.get("kpis") or [])[:2]
                        if isinstance(k, dict) and k.get("value")
                    ],
                    "compound_name": comp_name,
                    "smiles": resolved_smi,
                    "visual_mode": v_mode,
                    "visual_style": v_style,
                    "layout_id": lid,
                }
            )

        if not norm_slides:
            return None

        out_title = str(res.get("title") or doc.title).strip()[:36]
        out_summary = str(res.get("summary") or f"基于《{out_title}》提炼 {len(norm_slides)} 页结构化科研汇报大纲。").strip()[:60]
        return {"title": out_title, "summary": out_summary, "slides": norm_slides}

    def _build_local_outline(
        self,
        doc: ParsedDocument,
        num_content: int,
        is_proposal: bool,
    ) -> Dict[str, Any]:
        from .planner_agent import _build_deterministic_slide_fields, _expand_sections_to_count

        expanded = _expand_sections_to_count(doc.sections, num_content)
        styles_2d = ["acs1996", "shaded_scaffold", "nature_burgundy", "reactive_spot"]
        styles_3d = ["ball_stick", "pymol_neon_green", "metallic_studio", "stick_clean"]
        layouts = [
            LayoutId.bg_top_summary_3box.value,
            LayoutId.dual_compare_cards.value,
            LayoutId.hub_spoke_radial.value,
            LayoutId.timeline_chevron_flow.value,
            LayoutId.quadrant_2x2_matrix.value,
            LayoutId.tri_column_showcase.value,
            LayoutId.lit_overview_dual_card.value,
            LayoutId.mechanism_3col_flow.value,
            LayoutId.data_dashboard_table.value if not is_proposal else LayoutId.fig_left_3step_chain.value,
            LayoutId.roadmap_layered_matrix.value,
        ]

        slides: List[Dict[str, Any]] = []
        for idx in range(num_content):
            sec = expanded[idx] if idx < len(expanded) else doc.sections[idx % max(1, len(doc.sections))]
            takeaway, kpis, insights, table_data = _build_deterministic_slide_fields(sec, idx)
            txt_hint = f"{sec.heading} {takeaway}".lower()
            is_3d = any(k in txt_hint for k in ("3d", "立体", "构象", "对接", "口袋", "球棍", "结合")) or (idx % 2 == 1)
            v_mode = "3d" if is_3d else "2d"
            v_style = styles_3d[idx % len(styles_3d)] if is_3d else styles_2d[idx % len(styles_2d)]

            smi = (
                sec.smiles[0]
                if sec.smiles
                else (doc.detected_smiles[idx % len(doc.detected_smiles)] if doc.detected_smiles else "")
            )
            clean_title = clean_prose_without_smiles(sec.heading)[:22] or f"研究板块 {idx + 1:02d}"
            lid = LayoutId.data_dashboard_table.value if table_data is not None else layouts[idx % len(layouts)]

            slides.append(
                {
                    "section_name": clean_title[:16],
                    "title": clean_title,
                    "takeaway": takeaway,
                    "bullets": [f"{ins.heading}：{ins.body}" for ins in insights[:3]],
                    "kpis": [{"value": k.value, "label": k.label} for k in kpis[:2]],
                    "compound_name": "",
                    "smiles": smi,
                    "visual_mode": v_mode,
                    "visual_style": v_style,
                    "layout_id": lid,
                }
            )

        return {
            "title": doc.title[:36],
            "summary": f"已解析 {len(doc.sections)} 个原始章节，生成 {len(slides)} 页结构化汇报大纲。",
            "slides": slides,
        }

    def summarize_document_to_outline(
        self,
        doc: ParsedDocument,
        target_slide_count: int = 8,
        scenario: ScenarioType = ScenarioType.defense,
        is_proposal: Optional[bool] = None,
    ) -> Dict[str, Any]:
        proposal_flag = doc.is_proposal_hint if is_proposal is None else is_proposal
        n_total = max(3, min(40, int(target_slide_count)))
        num_content = max(1, n_total - (2 if n_total <= 3 else 3))

        llm_res = self._build_llm_outline(doc, num_content=num_content, scenario=scenario, is_proposal=proposal_flag)
        if llm_res is not None:
            engine_used = self.provider.active_text_backend()
            core = llm_res
        else:
            engine_used = "local"
            core = self._build_local_outline(doc, num_content=num_content, is_proposal=proposal_flag)

        slides = core["slides"]
        title = core["title"]
        compounds = extract_compounds_from_text(doc.raw_text)
        table_count = sum(len(s.tables) for s in doc.sections)
        image_count = sum(len(s.image_paths) for s in doc.sections)

        return {
            "title": title,
            "summary": core["summary"],
            "engine_used": engine_used,
            "skill_name": "word-to-ppt-outline/v2",
            "slide_count": n_total,
            "content_slide_count": len(slides),
            "detected_compounds": [{"name": lbl, "smiles": smi} for lbl, smi in compounds[:12]],
            "table_count": table_count,
            "image_count": image_count,
            "slides": slides,
            "outline_markdown": _format_outline_markdown(title, slides),
        }
