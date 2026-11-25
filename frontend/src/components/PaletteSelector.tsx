import React, { useEffect, useState } from "react";
import { buildCustomHexRamp, resolvePaletteAccent } from "../types/deckSpec";
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
  const [customHex, setCustomHex] = useState<string>("#1B5E7A");
  const [hexInput, setHexInput] = useState<string>("#1B5E7A");

  useEffect(() => {
    if (activePaletteId.toLowerCase().startsWith("custom_")) {
      const part = activePaletteId.slice(7).split("_")[0] || "";
      if (/^[0-9A-Fa-f]{6}$/.test(part)) {
        const norm = `#${part.toUpperCase()}`;
        setCustomHex(norm);
        setHexInput(norm);
      }
    }
  }, [activePaletteId]);

  if (!open) return null;

  const isCustomActive = activePaletteId.toLowerCase().startsWith("custom_");
  const customRamp = buildCustomHexRamp(customHex);
  const topBorderColor = resolvePaletteAccent(activePaletteId, palettes);

  const handleHexInputChange = (val: string) => {
    setHexInput(val);
    const cleaned = val.trim().replace(/^#/, "");
    if (/^[0-9A-Fa-f]{6}$/.test(cleaned)) {
      setCustomHex(`#${cleaned.toUpperCase()}`);
    }
  };

  const applyCustom = () => {
    if (busy) return;
    const h = customHex.replace(/^#/, "").toUpperCase();
    onApplyPalette(`custom_${h}`);
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
          maxWidth: 920,
          maxHeight: "88vh",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid #D6D2C8",
          borderTop: `3px solid ${topBorderColor}`,
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
            配色方案与自定义色盘
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", fontSize: 20, lineHeight: 1, padding: 4 }}
          >
            ×
          </button>
        </div>

        <div style={{ padding: 18, overflowY: "auto", background: "var(--paper-bg)", display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Custom Color Picker Strip */}
          <div
            style={{
              background: "var(--surface-pure)",
              border: isCustomActive ? `2px solid ${customRamp[0]}` : "1px solid #D6D2C8",
              borderRadius: 2,
              padding: "12px 14px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="font-serif" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-primary)" }}>
                自定义颜色
              </span>
              <input
                type="color"
                value={customHex}
                onChange={(e) => {
                  const next = e.target.value.toUpperCase();
                  setCustomHex(next);
                  setHexInput(next);
                }}
                aria-label="选择自定义主色"
                style={{
                  width: 34,
                  height: 28,
                  padding: 1,
                  border: "1px solid #CBD5E1",
                  borderRadius: 2,
                  background: "#FFFFFF",
                  cursor: "pointer",
                }}
              />
              <input
                type="text"
                className="editorial-input font-mono"
                value={hexInput}
                onChange={(e) => handleHexInputChange(e.target.value)}
                maxLength={7}
                style={{ width: 94, fontSize: 12.5, padding: "4px 8px" }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 200 }}>
              <div style={{ display: "flex", flex: 1, height: 18, border: "1px solid #E2E8F0", borderRadius: 2, overflow: "hidden" }}>
                {customRamp.map((hx) => (
                  <div key={hx} style={{ flex: 1, background: hx }} title={hx} />
                ))}
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={applyCustom}
                className="btn-editorial-primary"
                style={{ background: customRamp[0], borderColor: customRamp[0], padding: "5px 14px", fontSize: 12, whiteSpace: "nowrap" }}
              >
                {busy ? "应用..." : isCustomActive ? "更新自定义色" : "应用自定义色"}
              </button>
            </div>
          </div>

          {/* 15 Unified Journal Presets */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(256px, 1fr))",
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
                    border: isSelected ? `2px solid ${pal.tokens.s1}` : "1px solid #D6D2C8",
                    background: "var(--surface-pure)",
                    overflow: "hidden",
                    boxShadow: isSelected ? "0 8px 20px rgba(23,23,23,0.10)" : "0 2px 6px rgba(23,23,23,0.03)",
                  }}
                >
                  <div style={{ display: "flex", height: 18, width: "100%" }}>
                    {pal.series.slice(0, 6).map((hx) => (
                      <div key={hx} style={{ flex: 1, background: hx }} />
                    ))}
                  </div>

                  <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="font-serif" style={{ fontSize: 14, fontWeight: 700, color: pal.tokens.s1 }}>
                        {pal.name}
                      </span>
                      {isSelected && (
                        <span
                          className="font-mono"
                          style={{
                            fontSize: 10.5,
                            fontWeight: 700,
                            color: "#FFFFFF",
                            background: pal.tokens.s1,
                            padding: "1px 6px",
                            borderRadius: 2,
                          }}
                        >
                          当前
                        </span>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
                      {pal.series.slice(0, 5).map((hx) => (
                        <span
                          key={hx}
                          className="font-mono"
                          style={{ fontSize: 9.5, color: "var(--ink-muted)" }}
                        >
                          {hx}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
