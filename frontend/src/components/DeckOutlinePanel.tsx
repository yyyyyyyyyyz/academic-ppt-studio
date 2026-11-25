import React from "react";
import type { SlideSpec } from "../types/deckSpec";

interface DeckOutlinePanelProps {
  slides: SlideSpec[];
  selectedSlideNo: number;
  accentColor?: string;
  onSelectSlide: (slideNo: number) => void;
  onAddContentSlide: () => void;
  onDeleteSlide: (slideNo: number) => void;
}

export const DeckOutlinePanel: React.FC<DeckOutlinePanelProps> = ({
  slides,
  selectedSlideNo,
  accentColor = "var(--nature-crimson)",
  onSelectSlide,
  onAddContentSlide,
  onDeleteSlide,
}) => {
  return (
    <aside
      style={{
        width: 248,
        background: "var(--surface-pure)",
        borderRight: "1px solid var(--rule-hairline)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          padding: "13px 14px",
          borderBottom: "1px solid var(--rule-strong)",
          borderTop: `2px solid ${accentColor}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span className="font-serif" style={{ fontWeight: 700, fontSize: 15.5, color: "var(--ink-primary)" }}>
            页面目录
          </span>
          <span className="font-mono" style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
            ({slides.length})
          </span>
        </div>
        <button
          type="button"
          className="btn-editorial-ghost"
          onClick={onAddContentSlide}
          style={{ padding: "4px 10px", fontSize: 12 }}
        >
          + 加页
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {slides.map((sl) => {
          const active = sl.slide_no === selectedSlideNo;
          const fig = sl.figure_spec;
          const kindLabel =
            fig?.assets?.[0]?.engine === "cylview_3d"
              ? "3D"
              : fig?.assets?.[0]?.engine === "chemdraw_rdkit"
                ? "2D"
                : sl.slide_type === "cover"
                  ? "封面"
                  : sl.slide_type === "toc"
                    ? "目录"
                    : sl.slide_type === "closing"
                      ? "尾页"
                      : "";

          return (
            <div
              key={sl.slide_no}
              onClick={() => onSelectSlide(sl.slide_no)}
              style={{
                padding: "11px 14px 11px 12px",
                cursor: "pointer",
                borderBottom: "1px solid #ECEAE3",
                borderLeft: active ? `3px solid ${accentColor}` : "3px solid transparent",
                background: active ? "var(--paper-bg)" : "var(--surface-pure)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    color: active ? accentColor : "var(--ink-muted)",
                  }}
                >
                  #{String(sl.slide_no).padStart(2, "0")}
                  {kindLabel ? ` · ${kindLabel}` : ""}
                </span>
                {sl.slide_type === "content" && slides.length > 3 && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSlide(sl.slide_no);
                    }}
                    style={{
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      padding: 2,
                      fontSize: 11,
                      color: "var(--ink-muted)",
                    }}
                  >
                    删除
                  </button>
                )}
              </div>

              <div
                className="font-serif"
                style={{
                  fontSize: 13,
                  fontWeight: active ? 700 : 600,
                  color: "var(--ink-primary)",
                  lineHeight: 1.35,
                }}
              >
                {sl.title || sl.section_name}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
};
