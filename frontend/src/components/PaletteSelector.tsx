import React from "react";
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
  if (!open) return null;

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
          maxWidth: 880,
          maxHeight: "84vh",
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
            padding: "14px 20px",
            borderBottom: "1px solid var(--rule-strong)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "var(--surface-pure)",
          }}
        >
          <div className="font-serif" style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-primary)" }}>
            配色方案
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", fontSize: 20, lineHeight: 1, padding: 4 }}
          >
            ×
          </button>
        </div>

        <div
          style={{
            padding: 18,
            overflowY: "auto",
            background: "var(--paper-bg)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
            gap: 12,
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
                }}
              >
                <div style={{ display: "flex", height: 12, width: "100%" }}>
                  {pal.series.slice(0, 5).map((hx) => (
                    <div key={hx} style={{ flex: 1, background: hx }} />
                  ))}
                </div>

                <div style={{ padding: "10px 12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="font-serif" style={{ fontSize: 14, fontWeight: 700, color: pal.tokens.s1 }}>
                    {pal.name}
                  </span>
                  {isSelected && (
                    <span className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: "var(--nature-crimson)" }}>
                      当前
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
