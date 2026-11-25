"""Planner Agent — Parses Documents into DeckSpec v4.0 with Free Slide Count & Notes Offloading."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

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
)
from .art_director_agent import ArtDirectorAgent
from .doc_parser import ParsedDocument, parse_scientific_text


_CANONICAL_TOPICS = [
    ("研究背景与立题痛点", "BACKGROUND & RATIONALE", "传统均相高稀释体系过程废液多且能耗高，亟需绿色高效的催化新策略。"),
    ("国内外研究进展与空白", "STATE OF ART & GAP", "现有报道难以兼顾高分散稳定性与低能垒活化，跨尺度协同调控仍是空白。"),
    ("总体技术路线与实验设计", "RESEARCH ROADMAP", "构建“材料限域设计—多场协同反应—原位机理互证—定量放大”四阶段闭环。"),
    ("多尺度装置与微观界⾯", "MULTI-SCALE INTERFACE", "宏观剪切传质与介孔限域微环境协同作用，高效富集底物并锁定副产分子。"),
    ("催化双循环与分子机理", "CATALYTIC MECHANISM", "双中心氧化还原耦合降低关键决速步活化能垒，避免传统高温副反应。"),
    ("催化剂分散性与抗团聚调控", "DISPERSION & STABILITY", "多孔骨架空间限域锚定单分散活性中心，显著抑制循环过程中的团聚失活。"),
    ("催化效率与绿色度定量对比", "QUANTITATIVE PERFORMANCE", "在温和条件下分离收率达 91.2%，过程质量强度 PMI 较对照工艺降低 91.7%。"),
    ("表征谱学与电子态解析", "SPECTROSCOPIC PROOF", "原位 XPS 与动力学同位素效应证实高价金属活性中间体稳定调控电荷转移。"),
    ("DFT 能垒与构效预测模型", "THEORETICAL INSIGHTS", "理论计算与机器学习模型揭示反应自由能降幅与电子结构描述符呈强线性相关。"),
    ("总结、创新点与未来展望", "SUMMARY & OUTLOOK", "形成可推广的绿色合成范式，下一步将拓展连续流工艺与临床前药物分子库验证。"),
]


class PlannerAgent:
    """Transforms any scientific document or prompt into a complete DeckSpec v4.0."""

    def __init__(self, provider: Optional[ModelProvider] = None) -> None:
        self.provider = provider or ModelProvider()
        self.art_director = ArtDirectorAgent(provider=self.provider)

    def _compute_structure_plan(self, target_slide_count: int, include_toc: bool = True) -> List[str]:
        """Determine exact sequence of slide types matching Spec Section 2.4 dynamic scaling."""
        n = max(3, min(40, int(target_slide_count)))
        if n <= 3:
            return ["cover"] + ["content"] * (n - 2) + ["closing"]
        if n <= 18:
            if include_toc:
                return ["cover", "toc"] + ["content"] * (n - 3) + ["closing"]
            return ["cover"] + ["content"] * (n - 2) + ["closing"]

        # Long defense deck (>=19): Cover + TOC + interleaved PART dividers + content + Closing
        part_count = 3 if n < 24 else 4
        remaining_content = n - 3 - part_count
        seq = ["cover", "toc"]
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

        sys_p = (
            "You are a top-tier Academic Presentation Planner (Nature/Science/Angewandte standard). "
            "Given a scientific source document, produce strict JSON: "
            '{"slides": [{"section_name": str, "eyebrow": str, "title": str (<=22 Chinese chars), '
            '"takeaway": str (<=36 chars, 1 sentence), "kpis": [{"value": str, "label": str}], '
            '"insights": [{"index": "01", "heading": str, "body": str (<=24 chars), "highlight": str (2-8 chars)}], '
            '"speaker_notes": str}]}. '
            f"Produce EXACTLY {num_content} items in slides. Keep slide body text ultra-concise (40-70 chars total) "
            "and offload all detailed experimental conditions and references into speaker_notes. "
            + ("This is a research PROPOSAL: do NOT fabricate experimental yields or curves." if is_proposal else "")
        )
        usr_p = f"Title: {doc.title}\nScenario: {scenario.value}\nDocument:\n{doc.raw_text[:6000]}"
        res = self.provider.generate_json(sys_p, usr_p, timeout=45.0)
        if isinstance(res, dict) and isinstance(res.get("slides"), list) and len(res["slides"]) >= 1:
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
    ) -> DeckSpec:
        doc = parse_scientific_text(source_text, default_title=deck_title or "绿色催化与分子精准合成研究汇报")
        final_title = deck_title.strip() if deck_title and deck_title.strip() else doc.title
        proposal_flag = doc.is_proposal_hint if is_proposal is None else is_proposal

        include_toc = (design_style != DesignStyle.zero_fill_frameless) or (target_slide_count >= 11)
        seq = self._compute_structure_plan(target_slide_count, include_toc=include_toc)
        num_content = sum(1 for item in seq if item == "content")

        llm_slides = self._try_llm_content_outline(doc, num_content, scenario, proposal_flag)

        slides: List[SlideSpec] = []
        content_cursor = 0
        toc_titles: List[str] = []

        # Pre-compute TOC titles from sections or canonical topics
        for idx in range(min(4, max(3, len(doc.sections)))):
            if idx < len(doc.sections):
                toc_titles.append(doc.sections[idx].heading)
            else:
                toc_titles.append(_CANONICAL_TOPICS[idx][0])

        part_names = ["研究背景与立题依据", "研究方案与技术路线", "机理与核心进展", "总结与未来规划"]

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
                slides.append(self.art_director.direct_slide(cover_spec, palette_id=palette_id, is_proposal=proposal_flag, detected_smiles=doc.detected_smiles))
            elif slot == "toc":
                slides.append(SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.toc,
                    layout_id=LayoutId.toc,
                    eyebrow="CONTENTS · REPORT OUTLINE",
                    title="汇报提纲与逻辑框架",
                    takeaway="围绕科学痛点、机制假说、定量互证与转化前景展开系统汇报。",
                    toc_items=toc_titles,
                    speaker_notes="简要概览本次汇报的四大核心板块与时间分配。",
                ))
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
                slides.append(SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.part_divider,
                    layout_id=LayoutId.part_divider,
                    eyebrow=f"PART 0{p_idx + 1}",
                    title=p_title,
                    takeaway=p_subs[p_idx % len(p_subs)],
                    figure_chips=p_chips[p_idx % len(p_chips)],
                ))
            elif slot == "closing":
                slides.append(SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.closing,
                    layout_id=LayoutId.closing,
                    eyebrow="THANK YOU",
                    title="敬请各位专家批评指正",
                    takeaway=f"{author} · {affiliation}",
                    speaker_notes="感谢各位评审专家聆听，欢迎就反应机理与实验方案提问交流。",
                ))
            else:
                c_idx = content_cursor
                content_cursor += 1
                if llm_slides and c_idx < len(llm_slides):
                    raw_s = llm_slides[c_idx]
                    sec_name = raw_s.get("section_name", f"专题 {c_idx + 1}")
                    eyebrow = raw_s.get("eyebrow", f"SECTION {c_idx + 1:02d}")
                    title = raw_s.get("title", sec_name)[:28]
                    takeaway = raw_s.get("takeaway", "")[:46]
                    kpis = [KpiItem(value=k.get("value", "90%"), label=k.get("label", "指标"), color_token="s1" if i == 0 else "alert") for i, k in enumerate(raw_s.get("kpis", [])[:2])]
                    insights = [
                        InsightItem(
                            index=ins.get("index", f"0{i + 1}"),
                            heading=ins.get("heading", "核心发现")[:14],
                            body=ins.get("body", "简洁阐述核心科学依据。")[:32],
                            highlight=ins.get("highlight"),
                        )
                        for i, ins in enumerate(raw_s.get("insights", [])[:3])
                    ]
                    notes = raw_s.get("speaker_notes", "")
                else:
                    sec = doc.sections[c_idx] if c_idx < len(doc.sections) else None
                    canon_title, canon_eye, canon_take = _CANONICAL_TOPICS[c_idx % len(_CANONICAL_TOPICS)]
                    sec_name = sec.heading if sec else canon_title
                    eyebrow = f"SECTION {c_idx + 1:02d} · {canon_eye}"
                    title = sec_name[:26] if sec and len(sec.heading) >= 4 else canon_title
                    clean_content = " ".join(ln for ln in sec.content.splitlines() if not ln.strip().upper().startswith("SMILES:")) if sec else ""
                    takeaway = (clean_content[:42].rstrip("，。 ") + "。") if len(clean_content) > 12 else canon_take
                    kpis = (
                        [KpiItem(value="SOP 4 步", label="无中途开罐", color_token="s1"), KpiItem(value="4 项", label="固态表征矩阵", color_token="s2")]
                        if proposal_flag
                        else [KpiItem(value="91.2%", label="目标产物收率", color_token="s1"), KpiItem(value="-91.7%", label="溶剂减废幅度", color_token="alert")]
                    )
                    insights = [
                        InsightItem(index="01", heading="科学机制锚点", body="微观限域微环境显著降低反应活化能垒。", highlight="降低反应活化能垒"),
                        InsightItem(index="02", heading="表征与定量互证", body="分子结构与动力学曲线在同色标下精准对齐。", highlight="同色标下精准对齐"),
                    ]
                    notes = sec.content if sec else f"详细讲解{title}的实验条件、对照设计及文献溯源。"

                slide = SlideSpec(
                    slide_no=s_no,
                    slide_type=SlideType.content,
                    layout_id=LayoutId.frameless_63_37,
                    section_name=sec_name,
                    eyebrow=eyebrow,
                    title=title,
                    takeaway=takeaway,
                    kpis=kpis if c_idx % 2 == 0 else [],
                    insights=insights,
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
