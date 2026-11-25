import React, { useState } from "react";
import { COVER_TEMPLATE_OPTIONS } from "../types/deckSpec";
import type { CoverTemplateId, DeckSpec, LayoutId, SlideSpec } from "../types/deckSpec";

const LAYOUT_OPTIONS: Array<{ id: LayoutId; label: string }> = [
  { id: "lit_overview_dual_card", label: "双分子卡片" },
  { id: "mechanism_3col_flow", label: "三栏构象" },
  { id: "data_dashboard_table", label: "数据看板" },
  { id: "bg_top_summary_3box", label: "三框对比" },
  { id: "pain_points_left_arrows", label: "痛点列表" },
  { id: "fig_left_3step_chain", label: "左图右链" },
  { id: "vs_center_wing", label: "双翼对比" },
  { id: "roadmap_layered_matrix", label: "路线矩阵" },
  { id: "timeline_chevron_flow", label: "五阶流程轴" },
  { id: "quadrant_2x2_matrix", label: "四象限矩阵" },
  { id: "hub_spoke_radial", label: "中心环辐射" },
  { id: "dual_compare_cards", label: "双栏 VS 对照" },
  { id: "tri_column_showcase", label: "三栏立柱展" },
  { id: "frameless_63_37", label: "极简 63:37" },
  { id: "split_50_50", label: "极简 50:50" },
  { id: "full_roadmap", label: "全幅路线" },
];

const FONT_PRESETS = [
  { id: "arial_msyh", label: "Arial + 微软雅黑", latin: "Arial", ea: "微软雅黑" },
  { id: "times_simsun", label: "Times + 宋体", latin: "Times New Roman", ea: "宋体" },
  { id: "times_msyh", label: "Times + 微软雅黑", latin: "Times New Roman", ea: "微软雅黑" },
];

interface SlideCanvasPreviewProps {
  deck: DeckSpec;
  slide: SlideSpec;
  previewUrl?: string;
  accentColor?: string;
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
  accentColor = "var(--rule-strong)",
  activeLayers,
  onToggleLayer,
  onUpdateSlide,
  onUpdateFonts,
  onUpdateCoverTemplate,
}) => {
  const [showNotes, setShowNotes] = useState(false);
  const [zoomOpen, setZoomOpen] = useState(false);
  const curLatin = deck.locked_standards?.fonts?.latin || "Arial";
  const curEa = deck.locked_standards?.fonts?.ea || "微软雅黑";
  const curFontId = FONT_PRESETS.find((f) => f.latin === curLatin && f.ea === curEa)?.id || "arial_msyh";

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        padding: "18px 22px",
        gap: 14,
        overflowY: "auto",
        background: "var(--paper-bg)",
      }}
    >
      {/* Clean Top Controls Bar */}
      <div
        style={{
          width: "100%",
          maxWidth: 1120,
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          padding: "9px 14px",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid var(--rule-hairline)",
          borderTop: `2px solid ${accentColor}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
          {onUpdateFonts && (
            <select
              className="editorial-select"
              value={curFontId}
              onChange={(e) => {
                const found = FONT_PRESETS.find((f) => f.id === e.target.value);
                if (found) onUpdateFonts(found.ea, found.latin);
              }}
              style={{ width: "auto", fontSize: 12, padding: "4px 8px", background: "var(--paper-bg)" }}
            >
              {FONT_PRESETS.map((fp) => (
                <option key={fp.id} value={fp.id}>
                  {fp.label}
                </option>
              ))}
            </select>
          )}

          {(slide.slide_type === "cover" || slide.slide_type === "closing") && onUpdateCoverTemplate && (
            <select
              className="editorial-select"
              value={deck.meta.cover_template || "hero_band_bottom_bar"}
              onChange={(e) => onUpdateCoverTemplate(e.target.value as CoverTemplateId)}
              style={{ width: "auto", fontSize: 12, padding: "4px 8px", background: "var(--paper-bg)" }}
            >
              {COVER_TEMPLATE_OPTIONS.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </select>
          )}

          {slide.slide_type === "content" && (
            <select
              className="editorial-select"
              value={slide.layout_id}
              onChange={(e) => onUpdateSlide({ ...slide, layout_id: e.target.value as LayoutId })}
              style={{ width: "auto", fontSize: 12, padding: "4px 8px", background: "var(--paper-bg)" }}
            >
              {LAYOUT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {previewUrl && (
            <button
              type="button"
              className="btn-editorial-ghost"
              onClick={() => setZoomOpen(true)}
              style={{ fontSize: 11.5, padding: "4px 10px" }}
            >
              高清放大
            </button>
          )}
          <div style={{ display: "inline-flex", border: "1px solid #D5D1C8", borderRadius: 2, overflow: "hidden" }}>
          {[
            { id: "L1", label: "L1 图" },
            { id: "L2", label: "L2 框" },
            { id: "L3", label: "L3 文" },
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
                }}
              >
                {ly.label}
              </button>
            );
          })}
        </div>
        </div>
      </div>

      {/* 16:9 Slide Preview */}
      <div style={{ width: "100%", maxWidth: 1120, margin: "0 auto", flexShrink: 0 }}>
        <div
          onClick={() => previewUrl && setZoomOpen(true)}
          title={previewUrl ? "点击高清全屏查看" : undefined}
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
            cursor: previewUrl ? "zoom-in" : "default",
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
            <div style={{ color: "var(--ink-muted)", fontSize: 13 }}>正在渲染预览...</div>
          )}
        </div>
      </div>

      {/* Concise Text Editor */}
      <div
        style={{
          width: "100%",
          maxWidth: 1120,
          margin: "0 auto",
          flexShrink: 0,
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid var(--rule-hairline)",
          padding: 14,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label style={{ fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>标题</div>
            <input
              className="editorial-input"
              value={slide.title}
              onChange={(e) => onUpdateSlide({ ...slide, title: e.target.value })}
            />
          </label>
          <label style={{ fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>核心结论</div>
            <input
              className="editorial-input"
              value={slide.takeaway}
              onChange={(e) => onUpdateSlide({ ...slide, takeaway: e.target.value })}
            />
          </label>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="button"
            className="btn-editorial-ghost"
            onClick={() => setShowNotes(!showNotes)}
            style={{ padding: "4px 10px", fontSize: 11.5 }}
          >
            {showNotes ? "收起备注" : "演讲备注"}
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

      {zoomOpen && previewUrl && (
        <div
          onClick={() => setZoomOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.85)",
            zIndex: 80,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            cursor: "zoom-out",
          }}
        >
          <img
            src={previewUrl}
            alt={`Slide ${slide.slide_no} HD`}
            style={{
              maxWidth: "94vw",
              maxHeight: "88vh",
              objectFit: "contain",
              background: "#FFFFFF",
              boxShadow: "0 24px 64px rgba(0, 0, 0, 0.55)",
            }}
          />
          <div className="font-mono" style={{ color: "#E2E8F0", fontSize: 12, marginTop: 10 }}>
            1920 × 1080 FULL HD · 点击任意空白处关闭
          </div>
        </div>
      )}
    </main>
  );
};
