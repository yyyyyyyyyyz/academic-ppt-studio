"""Planner Agent — Parses Documents into DeckSpec v4.0 with Free Slide Count, Notes Offloading & Faithfull Zero-LLM Mode."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..figure_factory.chem_grounding import extract_compounds_from_text, resolve_compound_smiles
from ..providers.llm_image_provider import ModelProvider
from ..schemas.deck_spec import (
    CoverTemplateId,
    DeckMeta,
    DeckSpec,
    DesignStyle,
    InsightItem,
    KpiItem,
    LayoutId,
    ScenarioType,
    SlideSpec,
    SlideType,
    TableData,
)
from .art_director_agent import ArtDirectorAgent
from .doc_parser import (
    ParsedDocument,
    ParsedSection,
    clean_prose_without_smiles,
    extract_chart_data_from_table,
    parse_scientific_text,
)


_CANONICAL_TOPICS = [
    ("研究背景与立题痛点", "BACKGROUND & RATIONALE", "梳理领域关键科学瓶颈与临床/工艺痛点，明确立题依据。"),
    ("国内外研究进展与空白", "STATE OF ART & GAP", "对比既有文献体系边界，确立本课题核心突破方向。"),
    ("总体技术路线与实验设计", "RESEARCH ROADMAP", "构建多阶段递进式实验设计与表征验证闭环。"),
    ("分子设计与构效关系优化", "MOLECULAR DESIGN", "围绕靶点结合模式与成药性指标完成先导结构迭代。"),
    ("作用机理与表征互证", "MECHANISTIC INSIGHTS", "结合结构表征与动力学分析阐明核心反应与结合机制。"),
    ("定量性能与综合评价", "QUANTITATIVE PERFORMANCE", "系统汇总活性、选择性及稳定性定量对照数据。"),
    ("总结、创新点与未来展望", "SUMMARY & OUTLOOK", "凝练核心学术创新点并规划下一阶段深化验证路径。"),
]

_LEAD_FILLER_PAT = re.compile(r"^(?:因此|进一步|随后|此外|同时|相较(?:于)?|基于此|研究表明|结果表明|实验显示)[，,\s]*")
_HEADING_BREAK_PAT = re.compile(r"[：:，,]|\s*(?:表明|显示|采用|建立|实现|达到|证实|提出|发现|揭示|保持|诱导)\s*")


def _split_clean_sentences(sec: ParsedSection) -> List[str]:
    """Split a ParsedSection into clean, SMILES-stripped informative sentences."""
    raw_paras = sec.paragraphs if sec.paragraphs else sec.content.splitlines()
    sentences: List[str] = []
    for para in raw_paras:
        cleaned = clean_prose_without_smiles(para)
        if not cleaned:
            continue
        parts = re.split(r"[。！？；;\n]+", cleaned)
        for part in parts:
            s = part.strip(" ，,;；:：")
            if len(s) >= 8:
                sentences.append(s)
    return sentences


def _derive_heading_from_sentence(sentence: str, fallback_idx: int) -> str:
    """Extract a concise 4–12 char Chinese/English heading directly from the sentence."""
    stripped = _LEAD_FILLER_PAT.sub("", sentence.strip())
    chunks = _HEADING_BREAK_PAT.split(stripped, maxsplit=1)
    head = chunks[0].strip() if chunks else stripped
    if len(head) > 13:
        head = head[:12].rstrip("的与和及 ")
    if len(head) < 3:
        head = f"要点 {fallback_idx:02d}"
    return head


def _derive_highlight_from_sentence(sentence: str, metrics: List[Tuple[str, str]]) -> Optional[str]:
    """Pick a high-signal numeric metric or concise clause directly present in the sentence."""
    for val, _ in metrics:
        if val and val in sentence:
            return val[:12]
    m_num = re.search(r"(-?\d+(?:\.\d+)?\s*(?:%|倍|nM|μM|h|mol%|ppm|kcal/mol|mg/kg|ns))", sentence)
    if m_num:
        return m_num.group(1).strip()[:12]
    m_eng = re.search(r"([A-Za-z][A-Za-z0-9\-/]{2,11})", sentence)
    if m_eng:
        return m_eng.group(1)
    return sentence[:8] if len(sentence) >= 6 else None


def _truncate_clean(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for sep in ("，", "、", "：", ",", ";", " "):
        pos = cut.rfind(sep)
        if pos >= max_len // 2:
            return cut[:pos].rstrip("，、：,; ") + "。"
    return cut.rstrip("，、：,; ") + "…"


def _build_deterministic_slide_fields(
    sec: ParsedSection,
    c_idx: int,
) -> Tuple[str, List[KpiItem], List[InsightItem], Optional[TableData]]:
    """Build faithful slide takeaway, real KPIs, real insights, and Word table with zero hardcoded fake data."""
    sentences = _split_clean_sentences(sec)
    metrics = sec.metrics

    # 1. Takeaway: prefer sentence containing numeric evidence or conclusion verbs
    best_sent = sentences[0] if sentences else clean_prose_without_smiles(sec.heading)
    for sent in sentences:
        if any(k in sent for k in ("表明", "实现", "达到", "降低", "提升", "发现", "亟需", "IC50", "%", "倍")):
            best_sent = sent
            break
    takeaway = _truncate_clean(best_sent, 48)
    if takeaway and not takeaway.endswith(("。", "…", ".", "!", "？")):
        takeaway += "。"

    # 2. KPIs strictly from extracted numbers in this section (never fabricate)
    kpis: List[KpiItem] = []
    kpi_tokens = ("s1", "s2", "alert")
    for idx, (val, lbl) in enumerate(metrics[:3]):
        kpis.append(KpiItem(value=val, label=lbl, color_token=kpi_tokens[idx % len(kpi_tokens)]))

    # 3. Insights strictly from real sentences of this section
    insights: List[InsightItem] = []
    for i, sent in enumerate(sentences[:3]):
        heading = _derive_heading_from_sentence(sent, i + 1)
        body = _truncate_clean(sent, 44)
        if not body.endswith(("。", "…", ".")):
            body += "。"
        insights.append(
            InsightItem(
                index=f"0{i + 1}",
                heading=heading,
                body=body,
                highlight=_derive_highlight_from_sentence(sent, metrics),
            )
        )
    if not insights:
        clean_title = clean_prose_without_smiles(sec.heading)
        insights.append(
            InsightItem(
                index="01",
                heading=clean_title[:12] or f"板块 {c_idx + 1:02d}",
                body=takeaway or f"围绕{clean_title}开展系统分析与表征验证。",
                highlight=clean_title[:8] if clean_title else None,
            )
        )

    # 4. Real Word table if attached to this section
    table_data: Optional[TableData] = None
    if sec.tables:
        tbl = sec.tables[0]
        table_data = TableData(
            headers=[h[:18] for h in tbl.headers[:5]],
            rows=[[c[:22] for c in r[:5]] for r in tbl.rows[:6]],
        )

    return takeaway, kpis, insights, table_data


def _expand_sections_to_count(sections: List[ParsedSection], target_count: int) -> List[ParsedSection]:
    """If requested content slides exceed section count, sub-split longest real sections before padding."""
    expanded = list(sections)
    if not expanded or len(expanded) >= target_count:
        return expanded

    while len(expanded) < target_count:
        # Pick longest section with >= 2 paragraphs or sentences
        best_idx = -1
        best_len = 0
        for i, sec in enumerate(expanded):
            sents = _split_clean_sentences(sec)
            if len(sents) >= 2 and len(sec.content) > best_len:
                best_len = len(sec.content)
                best_idx = i
        if best_idx < 0:
            break
        src = expanded[best_idx]
        sents = _split_clean_sentences(src)
        mid = max(1, len(sents) // 2)
        first_sents = sents[:mid]
        second_sents = sents[mid:]
        first_text = "。".join(first_sents) + "。"
        second_text = "。".join(second_sents) + "。"
        sec_a = ParsedSection(
            heading=src.heading,
            content=first_text,
            paragraphs=first_sents,
            tables=[],
            image_paths=list(src.image_paths[:1]),
            smiles=list(src.smiles[:1]),
            metrics=src.metrics[:2],
        )
        sec_b = ParsedSection(
            heading=f"{src.heading[:16]}（续）",
            content=second_text,
            paragraphs=second_sents,
            tables=list(src.tables),
            image_paths=list(src.image_paths[1:] if len(src.image_paths) > 1 else []),
            smiles=list(src.smiles[1:] if len(src.smiles) > 1 else src.smiles),
            metrics=src.metrics[2:] or src.metrics[:2],
        )
        expanded[best_idx : best_idx + 1] = [sec_a, sec_b]
    return expanded


class PlannerAgent:
    """Transforms any scientific document or prompt into a complete DeckSpec v4.0."""

    def __init__(self, provider: Optional[ModelProvider] = None) -> None:
        self.provider = provider or ModelProvider()
        self.art_director = ArtDirectorAgent(provider=self.provider)

    def _compute_structure_plan(
        self,
        target_slide_count: int,
        include_toc: bool = True,
        include_dividers: Optional[bool] = None,
    ) -> List[str]:
        """Determine exact sequence of slide types including Cover, TOC, Part Dividers, Content, and Closing."""
        n = max(3, min(40, int(target_slide_count)))
        if n <= 3:
            return ["cover"] + ["content"] * (n - 2) + ["closing"]

        use_dividers = include_dividers if include_dividers is not None else (n >= 10)
        if not use_dividers:
            if include_toc:
                return ["cover", "toc"] + ["content"] * (n - 3) + ["closing"]
            return ["cover"] + ["content"] * (n - 2) + ["closing"]

        if n == 4:
            return ["cover", "toc", "content", "closing"] if include_toc else ["cover", "part_1", "content", "closing"]
        if n == 5:
            return ["cover", "toc", "part_1", "content", "closing"]

        part_count = 2 if n < 13 else (3 if n < 24 else 4)
        overhead = 3 if include_toc else 2  # cover + (toc) + closing
        remaining_content = n - overhead - part_count
        if remaining_content < part_count:
            part_count = max(1, remaining_content)
            remaining_content = n - overhead - part_count
        seq = ["cover", "toc"] if include_toc else ["cover"]
        per_part = max(1, remaining_content // part_count)
        extra = remaining_content - per_part * part_count
        for p in range(part_count):
            seq.append(f"part_{p + 1}")
            c_cnt = per_part + (1 if p < extra else 0)
            seq.extend(["content"] * c_cnt)
        seq.append("closing")
        return seq[:n]

    def _try_llm_content_outline(
        self,
        doc: ParsedDocument,
        num_content: int,
        scenario: ScenarioType,
        is_proposal: bool,
    ) -> Optional[List[Dict[str, Any]]]:
        if self.provider.active_text_backend() == "local":
            return None

        table_summaries: List[str] = []
        for idx, sec in enumerate(doc.sections):
            for tbl in sec.tables[:2]:
                rows_txt = "; ".join([" | ".join(r[:5]) for r in ([tbl.headers] + tbl.rows[:4])])
                table_summaries.append(f"[Sec {idx + 1} Table]: {rows_txt}")
        compound_list = extract_compounds_from_text(doc.raw_text)[:12]
        compound_summary = ", ".join(f"{lbl}={smi}" for lbl, smi in compound_list) if compound_list else "None detected"

        from ..schemas.deck_spec import V5_LAYOUT_IDS
        from .outline_agent import load_word_outline_skill

        skill_guidance = load_word_outline_skill()
        layout_enum_str = "|".join(f'"{lid.value}"' for lid in sorted(V5_LAYOUT_IDS, key=lambda x: x.value))
        sys_p = (
            f"{skill_guidance}\n\n"
            "Now map the manuscript into strict SlideSpec JSON with layout choice AND visual drawing instructions per slide:\n"
            '{"slides": [{"section_name": str, "eyebrow": str, '
            f'"layout_id": {layout_enum_str}, '
            '"title": str (<=22 chars), "takeaway": str (<=40 chars, 1 sentence), '
            '"kpis": [{"value": str, "label": str, "color_token": "s1"|"s2"|"s3"|"alert"}], '
            '"insights": [{"index": "01", "heading": str, "body": str (<=30 chars), "highlight": str (2-10 chars)}], '
            '"visual_plan": {"mode": "chemdraw_2d"|"pymol_3d"|"origin_real_data"|"mechanism_3d_pathway"|"blender_3d_ai"|"vector_mech", '
            '"compound_name": str, "smiles": str, "chem_style": "nature_burgundy"|"shaded_scaffold"|"jacs_terracotta"|"reactive_spot"|"minimal_mono"|"acs1996", '
            '"origin_preset": "nature_grouped_bar"|"nature_step_drop_zoom"|"nature_horizontal_ranked"|"kinetics_spline"|"dft_energy_profile", '
            '"chart_data": {"categories": [str], "series": [{"name": str, "values": [float]}], "ylabel": str, "p_value": str}, '
            '"pathway_spec": {"title_top": str, "blocked_label": str, "sub_box_label": str, "nodes": [{"smiles": str, "label": str}], "step_labels": [str]}, '
            '"scene_description": str}, '
            '"speaker_notes": str}]}\n'
            f"Produce EXACTLY {num_content} items in slides. Vary layout_id cleanly across adjacent slides. "
            "Never invent numbers in chart_data—only extract real measurements from text/tables. "
            "Keep slide body text ultra-concise and put experimental details in speaker_notes. "
            + ("This is a research PROPOSAL: do NOT fabricate experimental yields or curves." if is_proposal else "")
        )
        extra_context = ""
        if table_summaries:
            extra_context += "\n\nExtracted Word Tables:\n" + "\n".join(table_summaries[:6])
        extra_context += f"\n\nDetected Compounds/SMILES:\n{compound_summary}"
        usr_p = f"Title: {doc.title}\nScenario: {scenario.value}\nDocument:\n{doc.raw_text[:14000]}{extra_context}"
        res = self.provider.generate_json(sys_p, usr_p, timeout=55.0)
        if isinstance(res, dict) and isinstance(res.get("slides"), list) and len(res["slides"]) >= 1:
            for item in res["slides"]:
                if isinstance(item, dict) and isinstance(item.get("visual_plan"), dict):
                    vp = item["visual_plan"]
                    raw_smi = str(vp.get("smiles") or vp.get("compound_name") or "").strip()
                    if raw_smi:
                        resolved = resolve_compound_smiles(raw_smi, allow_pubchem=True)
                        if resolved:
                            vp["smiles"] = resolved
            return res["slides"]
        return None

    def plan_deck(
        self,
        source_text: str,
        deck_title: Optional[str] = None,
        author: str = "Researcher",
        affiliation: str = "School of Pharmaceutical Sciences",
        scenario: ScenarioType = ScenarioType.defense,
        target_slide_count: int = 10,
        palette_id: str = "lancet",
        is_proposal: Optional[bool] = None,
        deck_id: str = "deck_active",
        design_style: DesignStyle = DesignStyle.defense_modular,
        cover_template: Optional[CoverTemplateId] = None,
        advisor: str = "",
        date_str: str = "",
        parsed_doc: Optional[ParsedDocument] = None,
        include_dividers: Optional[bool] = None,
    ) -> DeckSpec:
        doc = parsed_doc or parse_scientific_text(source_text, default_title=deck_title or "绿色催化与分子精准合成研究汇报")
        final_title = deck_title.strip() if deck_title and deck_title.strip() else doc.title
        proposal_flag = doc.is_proposal_hint if is_proposal is None else is_proposal

        include_toc = (design_style != DesignStyle.zero_fill_frameless) or (target_slide_count >= 11)
        seq = self._compute_structure_plan(
            target_slide_count,
            include_toc=include_toc,
            include_dividers=include_dividers,
        )
        num_content = sum(1 for item in seq if item == "content")

        llm_slides = self._try_llm_content_outline(doc, num_content, scenario, proposal_flag)
        planned_sections = _expand_sections_to_count(doc.sections, num_content) if not llm_slides else doc.sections

        slides: List[SlideSpec] = []
        content_cursor = 0
        toc_titles: List[str] = []

        for idx in range(min(4, max(3, len(doc.sections)))):
            if idx < len(doc.sections):
                toc_titles.append(doc.sections[idx].heading)
            else:
                toc_titles.append(_CANONICAL_TOPICS[idx][0])

        part_names = [sec.heading[:16] for sec in doc.sections[:4]] or ["研究背景与立题依据", "研究方案与技术路线", "机理与核心进展", "总结与未来规划"]

        for s_no, slot in enumerate(seq, start=1):
            if slot == "cover":
                cover_spec = SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.cover,
                    layout_id=LayoutId.cover,
                    eyebrow=f"{scenario.value.upper().replace('_', ' ')} · ACADEMIC PRESENTATION",
                    title=final_title,
                    takeaway="原子级图/文全分离可编辑学术报告",
                    speaker_notes=f"开场致谢并介绍课题总体背景：{final_title}。",
                )
                slides.append(
                    self.art_director.direct_slide(
                        cover_spec,
                        palette_id=palette_id,
                        is_proposal=proposal_flag,
                        detected_smiles=doc.detected_smiles,
                    )
                )
            elif slot == "toc":
                slides.append(
                    SlideSpec(
                        slide_no=s_no,
                        slide_type=SlideType.toc,
                        layout_id=LayoutId.toc,
                        eyebrow="CONTENTS · REPORT OUTLINE",
                        title="汇报提纲与逻辑框架",
                        takeaway="围绕科学痛点、机制假说、定量互证与转化前景展开系统汇报。",
                        toc_items=toc_titles,
                        speaker_notes="简要概览本次汇报的核心板块与时间分配。",
                    )
                )
            elif slot.startswith("part_"):
                p_idx = int(slot.split("_")[1]) - 1
                p_title = part_names[p_idx % len(part_names)]
                p_subs = [
                    "Background, Literature Gap, and Research Significance",
                    "Experimental Strategy, Synthetic Route, and Workflow",
                    "Catalytic Mechanism, Characterization, and Quantitative Results",
                    "Conclusions, Innovation Highlights, and Future Outlook",
                ]
                p_chips = [
                    ["选题背景", "科学痛点", "立题依据"],
                    ["总体设计", "合成路线", "表征方案"],
                    ["催化机理", "定量互证", "结构解析"],
                    ["核心结论", "创新亮点", "转化前景"],
                ]
                slides.append(
                    SlideSpec(
                        slide_no=s_no,
                        slide_type=SlideType.part_divider,
                        layout_id=LayoutId.part_divider,
                        eyebrow=f"PART 0{p_idx + 1}",
                        title=p_title,
                        takeaway=p_subs[p_idx % len(p_subs)],
                        figure_chips=p_chips[p_idx % len(p_chips)],
                    )
                )
            elif slot == "closing":
                slides.append(
                    SlideSpec(
                        slide_no=s_no,
                        slide_type=SlideType.closing,
                        layout_id=LayoutId.closing,
                        eyebrow="THANK YOU",
                        title="敬请各位专家批评指正",
                        takeaway=f"{author} · {affiliation}",
                        speaker_notes="感谢各位评审专家聆听，欢迎就反应机理与实验方案提问交流。",
                    )
                )
            else:
                c_idx = content_cursor
                content_cursor += 1
                sec = planned_sections[c_idx] if c_idx < len(planned_sections) else None
                sec_table: Optional[TableData] = None
                sec_smiles = sec.smiles if sec else None
                sec_images = sec.image_paths if sec else None
                visual_plan: Optional[Dict[str, Any]] = None
                table_chart_data: Optional[Dict[str, Any]] = None
                if sec and sec.tables and not proposal_flag:
                    table_chart_data = extract_chart_data_from_table(sec.tables[0], heading=sec.heading)

                if llm_slides and c_idx < len(llm_slides):
                    raw_s = llm_slides[c_idx]
                    sec_name = raw_s.get("section_name", sec.heading if sec else f"专题 {c_idx + 1}")
                    eyebrow = raw_s.get("eyebrow", f"SECTION {c_idx + 1:02d}")
                    title = raw_s.get("title", sec_name)[:28]
                    takeaway = raw_s.get("takeaway", "")[:46]
                    if isinstance(raw_s.get("visual_plan"), dict):
                        visual_plan = dict(raw_s["visual_plan"])
                        if raw_s.get("layout_id"):
                            visual_plan["layout_id"] = raw_s["layout_id"]
                    elif raw_s.get("layout_id"):
                        visual_plan = {"layout_id": raw_s["layout_id"]}
                    kpis = [
                        KpiItem(
                            value=k.get("value", "—"),
                            label=k.get("label", "核心指标"),
                            color_token="s1" if i == 0 else "alert",
                        )
                        for i, k in enumerate(raw_s.get("kpis", [])[:2])
                    ]
                    insights = [
                        InsightItem(
                            index=ins.get("index", f"0{i + 1}"),
                            heading=ins.get("heading", "核心发现")[:14],
                            body=ins.get("body", "简洁阐述核心科学依据。")[:40],
                            highlight=ins.get("highlight"),
                        )
                        for i, ins in enumerate(raw_s.get("insights", [])[:3])
                    ]
                    notes = raw_s.get("speaker_notes", "")
                    if sec and sec.tables:
                        tbl = sec.tables[0]
                        sec_table = TableData(headers=[h[:18] for h in tbl.headers[:5]], rows=[[c[:22] for c in r[:5]] for r in tbl.rows[:6]])
                elif sec is not None:
                    sec_name = sec.heading
                    canon_eye = _CANONICAL_TOPICS[c_idx % len(_CANONICAL_TOPICS)][1]
                    eyebrow = f"SECTION {c_idx + 1:02d} · {canon_eye}"
                    title = sec_name[:26]
                    takeaway, kpis, insights, sec_table = _build_deterministic_slide_fields(sec, c_idx)
                    notes = clean_prose_without_smiles(sec.content) or f"详细讲解{title}。"
                else:
                    canon_title, canon_eye, canon_take = _CANONICAL_TOPICS[c_idx % len(_CANONICAL_TOPICS)]
                    sec_name = canon_title
                    eyebrow = f"SECTION {c_idx + 1:02d} · {canon_eye}"
                    title = canon_title
                    takeaway = canon_take
                    kpis = []
                    insights = [
                        InsightItem(index="01", heading=canon_title[:10], body=canon_take, highlight=canon_title[:6]),
                    ]
                    notes = f"详细讲解{title}的实验条件、对照设计及文献溯源。"

                slide = SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.content,
                    layout_id=LayoutId.frameless_63_37,
                    section_name=sec_name,
                    eyebrow=eyebrow,
                    title=title,
                    takeaway=takeaway,
                    kpis=kpis if (kpis and (c_idx % 2 == 0 or sec_table is not None)) else kpis[:1],
                    insights=insights,
                    table_data=sec_table,
                    footer_left=f"{final_title[:28]} · {scenario.value}",
                    speaker_notes=notes,
                )
                slides.append(
                    self.art_director.direct_slide(
                        slide,
                        palette_id=palette_id,
                        is_proposal=proposal_flag,
                        detected_smiles=doc.detected_smiles,
                        content_index=c_idx,
                        design_style=design_style,
                        section_smiles=sec_smiles,
                        section_images=sec_images,
                        visual_plan=visual_plan,
                        table_chart_data=table_chart_data,
                    )
                )

        # Populate consistent bilingual nav_sections and TOC items across v5.0 slides
        _en_subs = [
            "Background & Rationale",
            "Research Design & Flow",
            "Mechanism & Conformation",
            "Quantitative Insights",
            "Prospects & Summary",
        ]
        content_slides = [sl for sl in slides if sl.slide_type == SlideType.content]
        if content_slides:
            nav_tabs = [f"{sl.section_name[:8]}|{_en_subs[idx % len(_en_subs)]}" for idx, sl in enumerate(content_slides[:5])]
            for c_pos, sl in enumerate(content_slides):
                sl.nav_sections = nav_tabs
                sl.active_nav_idx = min(c_pos, len(nav_tabs) - 1)
            for sl in slides:
                if sl.slide_type == SlideType.toc:
                    sl.toc_items = [
                        f"{csl.section_name[:18]}|{_en_subs[idx % len(_en_subs)]}"
                        for idx, csl in enumerate(content_slides[:6])
                    ]

        resolved_cover = cover_template
        if resolved_cover is None and design_style != DesignStyle.zero_fill_frameless:
            resolved_cover = CoverTemplateId.hero_band_bottom_bar

        return DeckSpec(
            meta=DeckMeta(
                deck_id=deck_id,
                deck_title=final_title,
                deck_subtitle=f"{scenario.value.replace('_', ' ').title()} · 顶刊美编级原子可编辑学术汇报",
                author=author,
                affiliation=affiliation,
                advisor=advisor,
                date_str=date_str,
                scenario=scenario,
                target_slide_count=len(slides),
                palette_id=palette_id,
                is_proposal=proposal_flag,
                design_style=design_style,
                cover_template=resolved_cover,
            ),
            slides=slides,
        )
