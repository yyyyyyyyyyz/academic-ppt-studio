import React, { useRef } from "react";
import { Download, CheckCircle2, AlertTriangle, FileJson, FileText, X } from "lucide-react";
import type { AuditReport, DeckSpec } from "../types/deckSpec";

interface ExportPanelProps {
  open: boolean;
  deck: DeckSpec;
  buildResult: {
    pptx_url: string;
    deck_spec_url: string;
    preview_urls: string[];
    audit_report: AuditReport;
  } | null;
  syncedUrl: string | null;
  busy: boolean;
  onClose: () => void;
  onBuildPptx: () => Promise<void>;
  onSyncWord: (file: File) => Promise<void>;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({
  open,
  deck,
  buildResult,
  syncedUrl,
  busy,
  onClose,
  onBuildPptx,
  onSyncWord,
}) => {
  const docxRef = useRef<HTMLInputElement | null>(null);
  if (!open) return null;

  const downloadDeckJson = () => {
    const blob = new Blob([JSON.stringify(deck, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${deck.meta.deck_id}_spec_v5.json`;
    a.click();
    URL.revokeObjectURL(url);
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
          maxWidth: 700,
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid #D6D2C8",
          borderTop: "3px solid var(--nature-crimson)",
          boxShadow: "0 24px 60px rgba(23, 23, 23, 0.22)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "16px 24px",
            borderBottom: "1px solid var(--rule-strong)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "var(--surface-pure)",
          }}
        >
          <div>
            <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 3 }}>
              PRE-PRESS AUDIT & DELIVERY
            </div>
            <div className="font-serif" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-primary)" }}>
              原生编译、合规审计与交付 (.pptx / JSON / Word Sync)
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", padding: 4 }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              className="btn-editorial-primary"
              disabled={busy}
              onClick={onBuildPptx}
              style={{ flex: 1, padding: "11px 18px" }}
            >
              {busy ? "正在编译并执行 audit_pptx..." : "编译 100% 原生可编辑 .pptx + 执行合规审计"}
            </button>
            <button type="button" className="btn-editorial-ghost" onClick={downloadDeckJson}>
              <FileJson size={14} /> 下载 DeckSpec JSON
            </button>
          </div>

          {buildResult && (
            <div
              style={{
                borderRadius: 2,
                border: buildResult.audit_report.passed ? "1px solid #9EC5B2" : "1px solid #E5B4B4",
                background: buildResult.audit_report.passed ? "#F3F9F6" : "#FDF2F2",
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingBottom: 10,
                  marginBottom: 12,
                  borderBottom: "1px solid var(--rule-hairline)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {buildResult.audit_report.passed ? (
                    <CheckCircle2 size={18} color="var(--audit-sage)" />
                  ) : (
                    <AlertTriangle size={18} color="var(--nature-crimson)" />
                  )}
                  <span
                    className="font-serif"
                    style={{
                      fontWeight: 700,
                      fontSize: 15,
                      color: buildResult.audit_report.passed ? "var(--audit-sage)" : "var(--nature-crimson)",
                    }}
                  >
                    audit_pptx 印前门禁：{buildResult.audit_report.passed ? "通过检验 (0 项违规)" : "存在告警"}
                  </span>
                </div>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    color: buildResult.audit_report.passed ? "var(--audit-sage)" : "var(--nature-crimson)",
                  }}
                >
                  {buildResult.audit_report.passed ? "100% PASSED" : "ACTION NEEDED"}
                </span>
              </div>

              {/* Swiss 2-Column Metric Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  background: "var(--surface-pure)",
                  border: "1px solid var(--rule-hairline)",
                  fontSize: 12,
                }}
              >
                {[
                  ["总页数 / 正文页", `${buildResult.audit_report.total_slides} / ${buildResult.audit_report.content_slides} 页`],
                  ["填色正文文本框", `${buildResult.audit_report.filled_body_boxes}`],
                  ["最小正文字号", `${buildResult.audit_report.min_body_pt_observed} pt`],
                  ["最小元素字号", `${buildResult.audit_report.min_any_pt_observed} pt`],
                  ["Unicode 假上下标", `${buildResult.audit_report.unicode_sub_sup_count}`],
                  ["XML 双字体缺失", `${buildResult.audit_report.missing_xml_font_runs}`],
                ].map(([label, val], idx) => (
                  <div
                    key={label}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "7px 12px",
                      borderBottom: idx < 4 ? "1px solid var(--rule-hairline)" : "none",
                      borderRight: idx % 2 === 0 ? "1px solid var(--rule-hairline)" : "none",
                    }}
                  >
                    <span style={{ color: "var(--ink-secondary)" }}>{label}</span>
                    <span className="font-mono" style={{ fontWeight: 600, color: "var(--ink-primary)" }}>
                      {val}
                    </span>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 10 }}>
                <a
                  href={buildResult.pptx_url}
                  download
                  className="btn-editorial-navy"
                  style={{ textDecoration: "none" }}
                >
                  <Download size={14} /> 一键下载 .pptx 原生可编辑文件
                </a>

                <button
                  type="button"
                  className="btn-editorial-ghost"
                  disabled={busy}
                  onClick={() => docxRef.current?.click()}
                  style={{ borderColor: "var(--ink-primary)" }}
                >
                  <FileText size={14} /> Word (.docx) Run 级样式保留同步
                </button>
                <input
                  ref={docxRef}
                  type="file"
                  accept=".docx"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) onSyncWord(f);
                  }}
                />
              </div>

              {syncedUrl && (
                <div style={{ marginTop: 10 }}>
                  <a
                    href={syncedUrl}
                    download
                    style={{ fontSize: 13, color: "var(--oxford-navy)", fontWeight: 600 }}
                  >
                    下载 Word 同步后的 .pptx →
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
