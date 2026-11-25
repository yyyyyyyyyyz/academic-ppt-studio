import React from "react";
import { Plus, Trash2, CheckCircle2, AlertTriangle } from "lucide-react";
import type { SlideSpec } from "../types/deckSpec";

interface DeckOutlinePanelProps {
  slides: SlideSpec[];
  selectedSlideNo: number;
  onSelectSlide: (slideNo: number) => void;
  onAddContentSlide: () => void;
  onDeleteSlide: (slideNo: number) => void;
}

export const DeckOutlinePanel: React.FC<DeckOutlinePanelProps> = ({
  slides,
  selectedSlideNo,
  onSelectSlide,
  onAddContentSlide,
  onDeleteSlide,
}) => {
  return (
    <aside
      style={{
        width: 276,
        background: "var(--surface-pure)",
        borderRight: "1px solid var(--rule-hairline)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Editorial Section Header */}
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid var(--rule-strong)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div>
          <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 2 }}>
            TABLE OF CONTENTS
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span className="font-serif" style={{ fontWeight: 700, fontSize: 16, color: "var(--ink-primary)" }}>
              分镜目录
            </span>
            <span className="font-mono" style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
              ({slides.length})
            </span>
          </div>
        </div>
        <button
          type="button"
          className="btn-editorial-ghost"
          onClick={onAddContentSlide}
          title="新增内容页"
          style={{ padding: "5px 10px", fontSize: 12 }}
        >
          <Plus size={13} /> 加页
        </button>
      </div>

      {/* Swiss Hairline Index Rows */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {slides.map((sl) => {
          const active = sl.slide_no === selectedSlideNo;
          const fig = sl.figure_spec;
          const archTag = fig ? fig.archetype.slice(0, 3) : sl.slide_type.toUpperCase();
          const qaScore = fig ? fig.overall_qa_score : null;
          const passed = fig ? fig.qa_passed : true;

          return (
            <div
              key={sl.slide_no}
              onClick={() => onSelectSlide(sl.slide_no)}
              style={{
                padding: "12px 14px 12px 13px",
                cursor: "pointer",
                borderBottom: "1px solid #ECEAE3",
                borderLeft: active ? "3px solid var(--nature-crimson)" : "3px solid transparent",
                background: active ? "var(--paper-bg)" : "var(--surface-pure)",
                transition: "background-color 140ms ease, border-color 140ms ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10.5,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    color: active ? "var(--nature-crimson)" : "var(--oxford-navy)",
                  }}
                >
                  #{String(sl.slide_no).padStart(2, "0")} · {archTag}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {qaScore !== null && (
                    <span
                      className="font-mono"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 3,
                        fontSize: 10.5,
                        fontWeight: 600,
                        color: passed ? "var(--audit-sage)" : "var(--nature-crimson)",
                      }}
                    >
                      {passed ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
                      QA {qaScore.toFixed(1)}
                    </span>
                  )}
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
                        color: "var(--ink-muted)",
                      }}
                      title="删除本页"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              </div>

              <div
                className="font-serif"
                style={{
                  fontSize: 13.5,
                  fontWeight: active ? 700 : 600,
                  color: "var(--ink-primary)",
                  lineHeight: 1.38,
                }}
              >
                {sl.title || sl.section_name}
              </div>

              {sl.takeaway && (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-muted)",
                    marginTop: 4,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {sl.takeaway}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
};
