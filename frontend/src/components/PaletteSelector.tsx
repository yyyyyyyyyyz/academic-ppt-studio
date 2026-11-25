import React, { useState } from "react";
import { Check, Copy, X } from "lucide-react";
import type { PaletteInfo } from "../types/deckSpec";

interface PaletteSelectorProps {
  open: boolean;
  palettes: PaletteInfo[];
  activePaletteId: string;
  busy: boolean;
  onClose: () => void;
  onApplyPalette: (paletteId: string) => Promise<void>;
}

export const PaletteSelector: React.FC<PaletteSelectorProps> = ({
  open,
  palettes,
  activePaletteId,
  busy,
  onClose,
  onApplyPalette,
}) => {
  const [copiedHex, setCopiedHex] = useState<string | null>(null);

  if (!open) return null;

  const copyHex = (hex: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(hex);
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 1200);
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
          maxWidth: 960,
          maxHeight: "86vh",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid #D6D2C8",
          borderTop: "3px solid var(--nature-crimson)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 24px 60px rgba(23, 23, 23, 0.22)",
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
              COLOR SYSTEM · 15 JOURNAL PALETTES
            </div>
            <div className="font-serif" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-primary)" }}>
              顶刊科研色板图谱（点击即全套幻灯片与图表联动换肤）
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {copiedHex && (
              <span className="font-mono" style={{ fontSize: 11.5, color: "var(--audit-sage)", fontWeight: 600 }}>
                COPIED {copiedHex}
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", padding: 4 }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <div
          style={{
            padding: 20,
            overflowY: "auto",
            background: "var(--paper-bg)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 14,
          }}
        >
          {palettes.map((pal) => {
            const isSelected = pal.id === activePaletteId;
            return (
              <div
                key={pal.id}
                onClick={() => !busy && onApplyPalette(pal.id)}
                style={{
                  borderRadius: 2,
                  cursor: busy ? "wait" : "pointer",
                  border: isSelected ? "2px solid var(--nature-crimson)" : "1px solid #D6D2C8",
                  background: "var(--surface-pure)",
                  overflow: "hidden",
                  boxShadow: isSelected ? "0 8px 24px rgba(181, 18, 27, 0.08)" : "0 2px 6px rgba(23, 23, 23, 0.03)",
                  transition: "border-color 140ms ease, box-shadow 140ms ease",
                }}
              >
                {/* Continuous Pantone-Style 5-Strip Color Specimen Bar */}
                <div style={{ display: "flex", height: 10, width: "100%" }}>
                  {pal.series.slice(0, 5).map((hx) => (
                    <div key={hx} style={{ flex: 1, background: hx }} />
                  ))}
                </div>

                <div style={{ padding: 13 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                    <span className="font-serif" style={{ fontSize: 14.5, fontWeight: 700, color: pal.tokens.s1 }}>
                      {pal.name}
                    </span>
                    {isSelected && (
                      <span
                        className="font-mono"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 3,
                          fontSize: 10,
                          fontWeight: 700,
                          color: "var(--nature-crimson)",
                        }}
                      >
                        <Check size={12} /> ACTIVE
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: 11.5, color: "var(--ink-muted)", marginBottom: 10, lineHeight: 1.45 }}>
                    {pal.description}
                  </div>

                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {pal.series.map((hx) => (
                      <button
                        key={hx}
                        type="button"
                        onClick={(e) => copyHex(hx, e)}
                        title={`点击复制 ${hx}`}
                        className="font-mono"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "3px 6px",
                          borderRadius: 2,
                          border: "1px solid var(--rule-hairline)",
                          background: "var(--paper-bg)",
                          color: "var(--ink-secondary)",
                          cursor: "pointer",
                          fontSize: 10,
                        }}
                      >
                        <span
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: 1,
                            background: hx,
                            display: "inline-block",
                          }}
                        />
                        {hx}
                        <Copy size={9} color="var(--ink-muted)" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
