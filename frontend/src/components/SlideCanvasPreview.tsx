import React, { useState } from "react";
import { Layers, ShieldCheck, AlertCircle, FileText, LayoutTemplate } from "lucide-react";
import { COVER_TEMPLATE_OPTIONS } from "../types/deckSpec";
import type { CoverTemplateId, DeckSpec, LayoutId, SlideSpec } from "../types/deckSpec";

const LAYOUT_OPTIONS: Array<{ id: LayoutId; label: string }> = [
  { id: "lit_overview_dual_card", label: "v5.0 · 双分子/文献档案卡 (复旦/文献精读)" },
  { id: "mechanism_3col_flow", label: "v5.0 · 三栏机理流与3D构象 (浙大/中大)" },
  { id: "data_dashboard_table", label: "v5.0 · KPI看板 + 纯白数据表 (麦肯锡/答辩)" },
  { id: "bg_top_summary_3box", label: "v5.0 · 顶摘要 + 三虚线框演进 (上海大学)" },
  { id: "pain_points_left_arrows", label: "v5.0 · 左痛点箭头 + 右图微标签 (像素答辩)" },
  { id: "fig_left_3step_chain", label: "v5.0 · 左图 + 右三阶纵向链 (复旦/中南)" },
  { id: "vs_center_wing", label: "v5.0 · 居中图 + 左右对称VS双翼 (浙大)" },
  { id: "roadmap_layered_matrix", label: "v5.0 · 左分层竖标 + 右闭环矩阵 (重点研发)" },
  { id: "frameless_63_37", label: "v4.0 · 极简去框 63:37 黄金分割" },
  { id: "split_50_50", label: "v4.0 · 极简去框 50:50 对照" },
  { id: "full_roadmap", label: "v4.0 · 全幅去框技术路线" },
];

const FONT_PRESETS = [
  { id: "arial_msyh", label: "Arial + 微软雅黑 (默认)", latin: "Arial", ea: "微软雅黑" },
  { id: "times_simsun", label: "Times New Roman + 宋体", latin: "Times New Roman", ea: "宋体" },
  { id: "times_msyh", label: "Times New Roman + 微软雅黑", latin: "Times New Roman", ea: "微软雅黑" },
];

interface SlideCanvasPreviewProps {
  deck: DeckSpec;
  slide: SlideSpec;
  previewUrl?: string;
  activeLayers: string[];
  onToggleLayer: (layer: string) => void;
  onUpdateSlide: (updated: SlideSpec) => void;
  onUpdateFonts?: (ea: string, latin: string) => void;
  onUpdateCoverTemplate?: (tpl: CoverTemplateId) => void;
}

export const SlideCanvasPreview: React.FC<SlideCanvasPreviewProps> = ({
  deck,
  slide,
  previewUrl,
  activeLayers,
  onToggleLayer,
  onUpdateSlide,
  onUpdateFonts,
  onUpdateCoverTemplate,
}) => {
  const [showNotes, setShowNotes] = useState(false);
  const fig = slide.figure_spec;
  const figOk =
    slide.slide_type !== "content" ||
    (fig !== null && fig !== undefined && fig.qa_passed && fig.overall_qa_score >= 8.5);
  const takeawayLen = slide.takeaway?.length || 0;
  const curLatin = deck.locked_standards?.fonts?.latin || "Arial";
  const curEa = deck.locked_standards?.fonts?.ea || "微软雅黑";
  const curFontId = FONT_PRESETS.find((f) => f.latin === curLatin && f.ea === curEa)?.id || "arial_msyh";

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        padding: "20px 24px",
        gap: 14,
        overflowY: "auto",
        background: "var(--paper-bg)",
      }}
    >
      {/* Editorial Compliance Telemetry Bar + 3-Layer Inspector */}
      <div
        style={{
          width: "100%",
          maxWidth: 960,
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          padding: "10px 14px",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid var(--rule-hairline)",
          borderTop: "2px solid var(--rule-strong)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 12 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              color: "var(--audit-sage)",
              fontWeight: 600,
            }}
          >
            <ShieldCheck size={14} />
            {deck.meta.design_style === "zero_fill_frameless" ? "0 填色正文框 (v4.0)" : "全原生可编辑 · ≥14pt"}
          </span>
          <span style={{ color: "var(--rule-hairline)" }}>|</span>
          <span
            className="font-mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              color: figOk ? "var(--audit-sage)" : "var(--nature-crimson)",
              fontWeight: 600,
              fontSize: 11.5,
            }}
          >
            {figOk ? <ShieldCheck size={13} /> : <AlertCircle size={13} />}
            QA {fig ? `${fig.overall_qa_score.toFixed(1)}/10` : "STRUCTURAL"}
          </span>

          {onUpdateFonts && (
            <>
              <span style={{ color: "var(--rule-hairline)" }}>|</span>
              <select
                className="editorial-select"
                value={curFontId}
                onChange={(e) => {
                  const found = FONT_PRESETS.find((f) => f.id === e.target.value);
                  if (found) onUpdateFonts(found.ea, found.latin);
                }}
                title="图表与全页双字体规范"
                style={{ width: "auto", fontSize: 11.5, padding: "4px 8px", background: "var(--paper-bg)" }}
              >
                {FONT_PRESETS.map((fp) => (
                  <option key={fp.id} value={fp.id}>
                    {fp.label}
                  </option>
                ))}
              </select>
            </>
          )}

          {(slide.slide_type === "cover" || slide.slide_type === "closing") && onUpdateCoverTemplate && (
            <>
              <span style={{ color: "var(--rule-hairline)" }}>|</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <LayoutTemplate size={14} color="var(--nature-crimson)" />
                <select
                  className="editorial-select"
                  value={deck.meta.cover_template || "hero_band_bottom_bar"}
                  onChange={(e) => onUpdateCoverTemplate(e.target.value as CoverTemplateId)}
                  title="切换封面与尾页配套模板（配色自动跟随科研色板）"
                  style={{ width: "auto", fontSize: 11.5, padding: "4px 8px", background: "var(--paper-bg)" }}
                >
                  {COVER_TEMPLATE_OPTIONS.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      首尾套系：{tpl.name}
                    </option>
                  ))}
                </select>
              </span>
            </>
          )}

          {slide.slide_type === "content" && (
            <>
              <span style={{ color: "var(--rule-hairline)" }}>|</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <LayoutTemplate size={14} color="var(--oxford-navy)" />
                <select
                  className="editorial-select"
                  value={slide.layout_id}
                  onChange={(e) => onUpdateSlide({ ...slide, layout_id: e.target.value as LayoutId })}
                  style={{ width: "auto", fontSize: 11.5, padding: "4px 8px", background: "var(--paper-bg)" }}
                >
                  {LAYOUT_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </span>
            </>
          )}

          {deck.meta.is_proposal && (
            <>
              <span style={{ color: "var(--rule-hairline)" }}>|</span>
              <span className="font-mono" style={{ color: "var(--oxford-navy)", fontWeight: 600, fontSize: 11 }}>
                PROPOSAL GUARD: ON
              </span>
            </>
          )}
        </div>

        {/* Minimalist 3-Layer Toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Layers size={13} color="var(--ink-muted)" />
          <span className="kicker" style={{ color: "var(--ink-muted)", marginRight: 2 }}>LAYERS</span>
          <div style={{ display: "inline-flex", border: "1px solid #D5D1C8", borderRadius: 2, overflow: "hidden" }}>
            {[
              { id: "L1", label: "L1 图元" },
              { id: "L2", label: "L2 矢量" },
              { id: "L3", label: "L3 文本" },
            ].map((ly, idx) => {
              const on = activeLayers.includes(ly.id);
              return (
                <button
                  key={ly.id}
                  type="button"
                  onClick={() => onToggleLayer(ly.id)}
                  style={{
                    fontSize: 11,
                    padding: "4px 9px",
                    cursor: "pointer",
                    fontWeight: 600,
                    border: "none",
                    borderLeft: idx > 0 ? "1px solid #D5D1C8" : "none",
                    background: on ? "var(--ink-primary)" : "var(--surface-pure)",
                    color: on ? "#ffffff" : "var(--ink-secondary)",
                    transition: "background-color 140ms ease, color 140ms ease",
                  }}
                >
                  {ly.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Museum-Framed 16:9 Rendered Slide Plate */}
      <div style={{ width: "100%", maxWidth: 960, margin: "0 auto", flexShrink: 0 }}>
        <div
          style={{
            width: "100%",
            aspectRatio: "16 / 9",
            background: "#ffffff",
            borderRadius: 2,
            border: "1px solid #D6D2C8",
            boxShadow: "0 18px 42px rgba(23, 23, 23, 0.08)",
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {previewUrl ? (
            <img
              key={previewUrl}
              src={previewUrl}
              alt={`Slide ${slide.slide_no}`}
              style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
            />
          ) : (
            <div style={{ color: "var(--ink-muted)", fontSize: 14 }}>正在渲染 16:9 幻灯片高清预览图版...</div>
          )}
        </div>

        {/* Printed Plate Telemetry Caption */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "7px 2px 0",
            fontSize: 10.5,
            color: "var(--ink-muted)",
          }}
        >
          <span className="font-mono" style={{ letterSpacing: "0.06em" }}>
            PLATE {String(slide.slide_no).padStart(2, "0")} / {String(deck.slides.length).padStart(2, "0")} · LAYOUT:{" "}
            {slide.layout_id.toUpperCase()} · 1920×1080 HIGH-DPI
          </span>
          <span className="font-serif" style={{ fontStyle: "italic" }}>
            {slide.eyebrow || slide.section_name}
          </span>
        </div>
      </div>

      {/* Manuscript Copy & Speaker Notes Desk */}
      <div
        style={{
          width: "100%",
          maxWidth: 960,
          margin: "0 auto",
          flexShrink: 0,
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid var(--rule-hairline)",
          borderTop: "2px solid var(--rule-strong)",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="kicker" style={{ color: "var(--nature-crimson)" }}>
            MANUSCRIPT COPY & SPEAKER NOTES
          </span>
          <span className="font-mono" style={{ fontSize: 11, color: "var(--ink-muted)" }}>
            INSIGHTS: {slide.insights.length}/3 · NATIVE XML RUNS
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <label style={{ fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)" }}>
              页面主标题 (24–26pt 微软雅黑)
            </div>
            <input
              className="editorial-input"
              value={slide.title}
              onChange={(e) => onUpdateSlide({ ...slide, title: e.target.value })}
            />
          </label>
          <label style={{ fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)", display: "flex", justifyContent: "space-between" }}>
              <span>Takeaway 单句核心结论</span>
              <span className="font-mono" style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                {takeawayLen}/40 字
              </span>
            </div>
            <input
              className="editorial-input"
              value={slide.takeaway}
              onChange={(e) => onUpdateSlide({ ...slide, takeaway: e.target.value })}
            />
          </label>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 4, borderTop: "1px solid #ECEAE3" }}>
          <span style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
            详细实验参数与口述讲稿自动分流至 PowerPoint 演讲者备注栏
          </span>
          <button
            type="button"
            className="btn-editorial-ghost"
            onClick={() => setShowNotes(!showNotes)}
            style={{ padding: "5px 10px", fontSize: 11.5 }}
          >
            <FileText size={12} /> {showNotes ? "收起演讲者备注" : "编辑演讲者备注 (Speaker Notes)"}
          </button>
        </div>

        {showNotes && (
          <textarea
            rows={3}
            className="editorial-textarea"
            value={slide.speaker_notes}
            onChange={(e) => onUpdateSlide({ ...slide, speaker_notes: e.target.value })}
            style={{ fontSize: 12.5, lineHeight: 1.55 }}
          />
        )}
      </div>
    </main>
  );
};
