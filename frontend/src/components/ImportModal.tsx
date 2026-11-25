import React, { useRef, useState } from "react";
import { fetchWordOutlineSkill, summarizeOutlineFromFile } from "../api/client";
import type { WordOutlineResult } from "../api/client";
import { COVER_TEMPLATE_OPTIONS } from "../types/deckSpec";
import type { CoverTemplateId, DesignStyle, PaletteInfo, ScenarioType } from "../types/deckSpec";

interface ImportModalProps {
  open: boolean;
  palettes: PaletteInfo[];
  loading: boolean;
  onClose: () => void;
  onPlanText: (payload: {
    source_text: string;
    deck_title?: string;
    author: string;
    affiliation: string;
    advisor?: string;
    date_str?: string;
    scenario: ScenarioType;
    target_slide_count: number;
    palette_id: string;
    is_proposal: boolean;
    design_style: DesignStyle;
    cover_template: CoverTemplateId;
    include_dividers: boolean;
  }) => Promise<void>;
  onPlanFile: (formData: FormData) => Promise<void>;
}

const CoverMiniPreview: React.FC<{ id: CoverTemplateId; color: string; tint: string }> = ({ id, color, tint }) => {
  if (id === "hero_band_bottom_bar") {
    return (
      <svg viewBox="0 0 80 45" style={{ width: "100%", height: 38, display: "block", border: "1px solid #E2E0D8", background: "#FFFFFF" }}>
        <rect x="0" y="0" width="80" height="33" fill={color} />
        <rect x="0" y="33" width="80" height="2" fill={tint} />
        <rect x="16" y="13" width="48" height="4" rx="1" fill="#FFFFFF" />
        <rect x="24" y="20" width="32" height="2" rx="1" fill="#FFFFFF" opacity="0.7" />
        <circle cx="20" cy="40" r="2" fill={color} />
        <circle cx="40" cy="40" r="2" fill={color} />
        <circle cx="60" cy="40" r="2" fill={color} />
      </svg>
    );
  }
  if (id === "top_bottom_bands_framed") {
    return (
      <svg viewBox="0 0 80 45" style={{ width: "100%", height: 38, display: "block", border: "1px solid #E2E0D8", background: "#FFFFFF" }}>
        <rect x="0" y="0" width="80" height="8" fill={color} />
        <rect x="0" y="37" width="80" height="8" fill={color} />
        <rect x="18" y="16" width="44" height="4" rx="1" fill={color} />
        <rect x="26" y="22" width="28" height="1.8" rx="0.9" fill="#64748B" />
      </svg>
    );
  }
  if (id === "floating_rounded_hero_card") {
    return (
      <svg viewBox="0 0 80 45" style={{ width: "100%", height: 38, display: "block", border: "1px solid #E2E0D8", background: "#FFFFFF" }}>
        <rect x="5" y="33" width="70" height="3.5" rx="1.5" fill={tint} />
        <rect x="3" y="3" width="74" height="31.5" rx="3" fill={color} />
        <rect x="7" y="14" width="44" height="4" rx="1" fill="#FFFFFF" />
        <rect x="7" y="20" width="32" height="2" rx="1" fill="#FFFFFF" opacity="0.7" />
      </svg>
    );
  }
  if (id === "left_aligned_rounded_panel") {
    return (
      <svg viewBox="0 0 80 45" style={{ width: "100%", height: 38, display: "block", border: "1px solid #E2E0D8", background: "#FFFFFF" }}>
        <rect x="2" y="2" width="76" height="33" rx="2.5" fill={color} />
        <rect x="6" y="15" width="44" height="4" rx="1" fill="#FFFFFF" />
        <rect x="6" y="21" width="34" height="2" rx="1" fill="#FFFFFF" opacity="0.7" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 80 45" style={{ width: "100%", height: 38, display: "block", border: "1px solid #E2E0D8", background: "#FFFFFF" }}>
      <polygon points="0,0 80,0 80,30 40,35 0,30" fill={color} />
      <rect x="18" y="10" width="44" height="4" rx="1" fill="#FFFFFF" />
      <rect x="26" y="16" width="28" height="2" rx="1" fill="#FFFFFF" opacity="0.75" />
    </svg>
  );
};

const SAMPLE_OUTLINE = `# EGFR C797S 变构抑制剂设计与成药性研究
## 1. 研究背景与耐药痛点
第三代共价抑制剂诱发 C797S 耐药突变，亟需新型非共价变构抑制剂。
SMILES: COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34
## 2. 先导结构优化（2D 结构）
引入吗啉极性侧链优化脂水分配系数（cLogP = 3.1），满足 Lipinski 规则。
SMILES: COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4
## 3. 3D 构象与结合模式（3D 球棍）
吲哚核心与铰链区形成双齿氢键，吗啉尾链深入溶剂区。
SMILES: Cc1nc(Nc2ncc(s2)C(=O)Nc3c(C)cccc3Cl)cc(n1)N4CCN(CCO)CC4
## 4. 总结与展望
明确后续安全性筛选与成药优化方向。`;

export const ImportModal: React.FC<ImportModalProps> = ({
  open,
  palettes,
  loading,
  onClose,
  onPlanText,
  onPlanFile,
}) => {
  const [deckTitle, setDeckTitle] = useState("EGFR 抑制剂先导化合物研究汇报");
  const [author, setAuthor] = useState("汇报人");
  const [affiliation, setAffiliation] = useState("药学院实验室");
  const [advisor, setAdvisor] = useState("");
  const [dateStr, setDateStr] = useState("2026 年 11 月");
  const [scenario, setScenario] = useState<ScenarioType>("defense");
  const [slideCount, setSlideCount] = useState<number>(10);
  const [paletteId, setPaletteId] = useState<string>("lancet");
  const [designStyle, setDesignStyle] = useState<DesignStyle>("defense_modular");
  const [coverTemplate, setCoverTemplate] = useState<CoverTemplateId>("hero_band_bottom_bar");
  const [isProposal, setIsProposal] = useState<boolean>(false);
  const [includeDividers, setIncludeDividers] = useState<boolean>(true);
  const [sourceText, setSourceText] = useState<string>(SAMPLE_OUTLINE);

  const [outlining, setOutlining] = useState(false);
  const [outlineData, setOutlineData] = useState<WordOutlineResult | null>(null);
  const [outlineView, setOutlineView] = useState<"cards" | "raw">("cards");
  const [skillOpen, setSkillOpen] = useState(false);
  const [skillContent, setSkillContent] = useState<string>("");
  const [outlineErr, setOutlineErr] = useState<string | null>(null);

  const outlineFileRef = useRef<HTMLInputElement | null>(null);
  const directFileRef = useRef<HTMLInputElement | null>(null);

  if (!open) return null;

  const activePal = palettes.find((p) => p.id === paletteId);
  const previewPrimary = activePal?.tokens?.s1 || "#00468B";
  const previewTint = activePal?.tokens?.s4 || "#72A6D5";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onPlanText({
      source_text: sourceText,
      deck_title: deckTitle,
      author,
      affiliation,
      advisor,
      date_str: dateStr,
      scenario,
      target_slide_count: slideCount,
      palette_id: paletteId,
      is_proposal: isProposal,
      design_style: designStyle,
      cover_template: coverTemplate,
      include_dividers: includeDividers,
    });
  };

  const handleOutlineFromFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setOutlining(true);
    setOutlineErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("target_slide_count", String(slideCount));
      fd.append("scenario", scenario);
      fd.append("is_proposal", String(isProposal));
      const res = await summarizeOutlineFromFile(fd);
      setOutlineData(res);
      setDeckTitle(res.title || deckTitle);
      setSourceText(res.outline_markdown || sourceText);
      setOutlineView("cards");
    } catch (err) {
      setOutlineErr(String(err));
    } finally {
      setOutlining(false);
    }
  };

  const handleDirectFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("deck_title", deckTitle);
    fd.append("author", author);
    fd.append("affiliation", affiliation);
    fd.append("advisor", advisor);
    fd.append("date_str", dateStr);
    fd.append("scenario", scenario);
    fd.append("target_slide_count", String(slideCount));
    fd.append("palette_id", paletteId);
    fd.append("is_proposal", String(isProposal));
    fd.append("design_style", designStyle);
    fd.append("cover_template", coverTemplate);
    fd.append("include_dividers", String(includeDividers));
    await onPlanFile(fd);
  };

  const toggleSkillPreview = async () => {
    if (!skillOpen && !skillContent) {
      try {
        const res = await fetchWordOutlineSkill();
        setSkillContent(res.content);
      } catch (err) {
        setOutlineErr(String(err));
      }
    }
    setSkillOpen((v) => !v);
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(23, 23, 23, 0.48)",
        backdropFilter: "blur(4px)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        className="editorial-fade-in"
        style={{
          width: "100%",
          maxWidth: 860,
          maxHeight: "92vh",
          overflowY: "auto",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid #D6D2C8",
          borderTop: `3px solid ${previewPrimary}`,
          boxShadow: "0 24px 60px rgba(23, 23, 23, 0.22)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 20px",
            borderBottom: "1px solid var(--rule-strong)",
            background: "var(--surface-pure)",
          }}
        >
          <div className="font-serif" style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-primary)" }}>
            导入 Word / 规划大纲
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", fontSize: 20, lineHeight: 1, padding: 4 }}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.3fr 0.75fr 0.9fr 0.7fr 0.65fr", gap: 10 }}>
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>标题</div>
              <input className="editorial-input" value={deckTitle} onChange={(e) => setDeckTitle(e.target.value)} />
            </label>
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>汇报人</div>
              <input className="editorial-input" value={author} onChange={(e) => setAuthor(e.target.value)} />
            </label>
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>单位</div>
              <input className="editorial-input" value={affiliation} onChange={(e) => setAffiliation(e.target.value)} />
            </label>
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>导师</div>
              <input className="editorial-input" value={advisor} onChange={(e) => setAdvisor(e.target.value)} placeholder="选填" />
            </label>
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>日期</div>
              <input className="editorial-input" value={dateStr} onChange={(e) => setDateStr(e.target.value)} />
            </label>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr 1fr",
              gap: 10,
              alignItems: "center",
              padding: 12,
              background: "var(--paper-bg)",
              border: "1px solid var(--rule-hairline)",
              borderRadius: 2,
            }}
          >
            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>场景</div>
              <select className="editorial-select" value={scenario} onChange={(e) => setScenario(e.target.value as ScenarioType)}>
                <option value="defense">答辩</option>
                <option value="midterm">中期</option>
                <option value="group_meeting">组会</option>
                <option value="literature_review">文献综述</option>
              </select>
            </label>

            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)", display: "flex", justifyContent: "space-between" }}>
                <span>页数</span>
                <span className="font-mono" style={{ color: previewPrimary, fontWeight: 700 }}>{slideCount}</span>
              </div>
              <input
                type="range"
                min={3}
                max={30}
                value={slideCount}
                onChange={(e) => setSlideCount(Number(e.target.value))}
                style={{ width: "100%", accentColor: previewPrimary }}
              />
            </label>

            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>配色</div>
              <select
                key={`pal_${palettes.length}`}
                className="editorial-select"
                value={paletteId}
                onChange={(e) => setPaletteId(e.target.value)}
              >
                {palettes.length === 0 ? (
                  <option value="lancet">Lancet 深蓝</option>
                ) : (
                  palettes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))
                )}
              </select>
            </label>

            <label style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>版式</div>
              <select className="editorial-select" value={designStyle} onChange={(e) => setDesignStyle(e.target.value as DesignStyle)}>
                <option value="defense_modular">答辩卡片风</option>
                <option value="consulting_editorial">看板风</option>
                <option value="zero_fill_frameless">极简去框</option>
              </select>
            </label>
          </div>

          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-secondary)", marginBottom: 6 }}>封面样式</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
              {COVER_TEMPLATE_OPTIONS.map((tpl) => {
                const selected = coverTemplate === tpl.id;
                return (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => setCoverTemplate(tpl.id)}
                    style={{
                      textAlign: "left",
                      padding: 6,
                      background: selected ? "#FDF8F8" : "var(--surface-pure)",
                      border: selected ? `1.5px solid ${previewPrimary}` : "1px solid var(--rule-hairline)",
                      borderRadius: 2,
                      cursor: "pointer",
                    }}
                  >
                    <CoverMiniPreview id={tpl.id} color={previewPrimary} tint={previewTint} />
                    <div style={{ fontSize: 11, fontWeight: 700, color: selected ? previewPrimary : "var(--ink-primary)", marginTop: 4 }}>
                      {tpl.name}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Skill-Driven Word -> Outline Bar */}
          <div
            style={{
              padding: 12,
              background: "var(--paper-bg)",
              border: "1px solid var(--rule-hairline)",
              borderRadius: 2,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-primary)" }}>PPT 大纲与内容</span>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "var(--ink-secondary)", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={includeDividers}
                    onChange={(e) => setIncludeDividers(e.target.checked)}
                    style={{ accentColor: previewPrimary }}
                  />
                  <span>含章节过渡页</span>
                </label>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "var(--ink-secondary)", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={isProposal}
                    onChange={(e) => setIsProposal(e.target.checked)}
                    style={{ accentColor: previewPrimary }}
                  />
                  <span>开题报告</span>
                </label>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn-editorial-ghost"
                  onClick={toggleSkillPreview}
                  style={{ padding: "4px 9px", fontSize: 11.5 }}
                >
                  {skillOpen ? "收起 Skill 规则" : "大纲 Skill 规则"}
                </button>
                <button
                  type="button"
                  className="btn-editorial-navy"
                  disabled={outlining || loading}
                  onClick={() => outlineFileRef.current?.click()}
                  style={{ padding: "5px 11px", fontSize: 11.5 }}
                >
                  {outlining ? "正在总结大纲..." : "上传 Word 总结大纲"}
                </button>
                <button
                  type="button"
                  className="btn-editorial-ghost"
                  disabled={outlining || loading}
                  onClick={() => directFileRef.current?.click()}
                  style={{ padding: "4px 10px", fontSize: 11.5, borderColor: previewPrimary, color: previewPrimary }}
                >
                  直接导入 Word 生成
                </button>
                <input ref={outlineFileRef} type="file" accept=".docx,.pdf,.txt,.md" hidden onChange={handleOutlineFromFile} />
                <input ref={directFileRef} type="file" accept=".docx,.pdf,.txt,.md" hidden onChange={handleDirectFileUpload} />
              </div>
            </div>

            {outlineErr && (
              <div style={{ fontSize: 12, color: "var(--nature-crimson)", background: "#FDF2F2", padding: "6px 10px", border: "1px solid #E5B4B4" }}>
                {outlineErr}
              </div>
            )}

            {skillOpen && (
              <pre
                className="font-mono"
                style={{
                  margin: 0,
                  maxHeight: 160,
                  overflowY: "auto",
                  padding: 10,
                  fontSize: 11,
                  lineHeight: 1.5,
                  background: "#FFFFFF",
                  border: "1px solid #DCD8CF",
                  whiteSpace: "pre-wrap",
                }}
              >
                {skillContent || "正在加载..."}
              </pre>
            )}

            {outlineData && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11.5, color: "var(--ink-secondary)" }}>
                <span>
                  已总结 <strong>{outlineData.content_slide_count}</strong> 页内容 · 分子 {outlineData.detected_compounds.length} 个 · 表格 {outlineData.table_count} 张 · 引擎{" "}
                  <span className="font-mono" style={{ color: previewPrimary }}>{outlineData.engine_used}</span>
                </span>
                <div style={{ display: "inline-flex", border: "1px solid #D5D1C8", borderRadius: 2, overflow: "hidden" }}>
                  <button
                    type="button"
                    onClick={() => setOutlineView("cards")}
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      border: "none",
                      cursor: "pointer",
                      background: outlineView === "cards" ? "var(--ink-primary)" : "#FFFFFF",
                      color: outlineView === "cards" ? "#FFFFFF" : "var(--ink-secondary)",
                    }}
                  >
                    大纲卡片
                  </button>
                  <button
                    type="button"
                    onClick={() => setOutlineView("raw")}
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      border: "none",
                      borderLeft: "1px solid #D5D1C8",
                      cursor: "pointer",
                      background: outlineView === "raw" ? "var(--ink-primary)" : "#FFFFFF",
                      color: outlineView === "raw" ? "#FFFFFF" : "var(--ink-secondary)",
                    }}
                  >
                    编辑文本
                  </button>
                </div>
              </div>
            )}

            {outlineData && outlineView === "cards" ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, maxHeight: 220, overflowY: "auto" }}>
                {outlineData.slides.map((sl, i) => (
                  <div
                    key={`${sl.title}_${i}`}
                    style={{
                      padding: "9px 11px",
                      background: "#FFFFFF",
                      border: "1px solid #DCD8CF",
                      borderLeft: `3px solid ${previewPrimary}`,
                      borderRadius: 2,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span className="font-mono" style={{ fontSize: 10.5, fontWeight: 700, color: previewPrimary }}>
                        {String(i + 1).padStart(2, "0")} · {sl.visual_mode.toUpperCase()} ({sl.visual_style})
                      </span>
                      {sl.compound_name && (
                        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink-muted)" }}>
                          {sl.compound_name}
                        </span>
                      )}
                    </div>
                    <div className="font-serif" style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-primary)", marginBottom: 3 }}>
                      {sl.title}
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-secondary)", lineHeight: 1.4 }}>{sl.takeaway}</div>
                  </div>
                ))}
              </div>
            ) : (
              <textarea
                rows={6}
                className="editorial-textarea"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                style={{ lineHeight: 1.55 }}
              />
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, paddingTop: 4, borderTop: "1px solid var(--rule-hairline)" }}>
            <button type="button" className="btn-editorial-ghost" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn-editorial-primary" disabled={loading || outlining} style={{ background: previewPrimary, borderColor: previewPrimary }}>
              {loading ? "生成中..." : "生成 PPT"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
