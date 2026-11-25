import React, { useEffect, useRef, useState } from "react";
import type {
  ArchetypeId,
  ArchetypeInfo,
  AssetUrlBundle,
  FigureSpec,
  SlideSpec,
} from "../types/deckSpec";

interface FigureWorkbenchProps {
  deckId: string;
  paletteId: string;
  accentColor?: string;
  slide: SlideSpec;
  archetypes: ArchetypeInfo[];
  assetUrls: Record<string, AssetUrlBundle>;
  busy: boolean;
  onRegenerate: () => Promise<void>;
  onRefineOrSwitch: (params: {
    asset_id?: string;
    selected_candidate_idx?: number;
    refinement_instruction?: string;
    archetype_override?: ArchetypeId;
    smiles_override?: string;
    fixed_bond_length_px?: number;
    origin_preset?: string;
    render_mode?: string;
    mech_mode_override?: string;
    chem_style_override?: string;
    style_3d_override?: string;
    rotation_deg_override?: number[];
    show_nonpolar_h_override?: boolean;
  }) => Promise<void>;
  onUploadReplacement: (file: File, assetId: string) => Promise<void>;
}

interface StyleCardOption {
  id: string;
  group: string;
  label: string;
  swatchA: string;
  swatchB: string;
}

const CHEM_STYLES_2D: StyleCardOption[] = [
  { id: "acs1996", group: "标准线稿", label: "杂原子着色", swatchA: "#1E293B", swatchB: "#00468B" },
  { id: "minimal_mono", group: "标准线稿", label: "纯黑极简", swatchA: "#111827", swatchB: "#6B7280" },
  { id: "nature_burgundy", group: "期刊单色", label: "绛红手绘", swatchA: "#7C1D35", swatchB: "#B91C1C" },
  { id: "jacs_terracotta", group: "期刊单色", label: "砖红印刷", swatchA: "#9A3412", swatchB: "#C2410C" },
  { id: "shaded_scaffold", group: "重点标注", label: "环骨架填色", swatchA: "#1E293B", swatchB: "#93C5FD" },
  { id: "reactive_spot", group: "重点标注", label: "反应位点高亮", swatchA: "#1E293B", swatchB: "#2563EB" },
];

const STYLES_3D: StyleCardOption[] = [
  { id: "ball_stick", group: "球棍建模", label: "经典灰碳", swatchA: "#687482", swatchB: "#D42430" },
  { id: "pymol_neon_green", group: "球棍建模", label: "PyMOL 亮绿", swatchA: "#3AE048", swatchB: "#446CFF" },
  { id: "metallic_studio", group: "球棍建模", label: "高光金属", swatchA: "#A4ACB8", swatchB: "#1E3A8A" },
  { id: "stick_clean", group: "棒状模型", label: "纯化学键", swatchA: "#5292A6", swatchB: "#D42430" },
  { id: "spacefill_cpk", group: "空间填充", label: "范德华球", swatchA: "#5C6068", swatchB: "#305CD4" },
];

const VIEW_PRESETS_3D: Array<{ label: string; deg: number[] }> = [
  { label: "正面", deg: [0, 0, 0] },
  { label: "俯视", deg: [35, 0, 0] },
  { label: "侧视", deg: [10, 55, 0] },
  { label: "翻转", deg: [0, 90, 0] },
];

export const FigureWorkbench: React.FC<FigureWorkbenchProps> = ({
  accentColor = "var(--nature-crimson)",
  slide,
  assetUrls,
  busy,
  onRegenerate,
  onRefineOrSwitch,
  onUploadReplacement,
}) => {
  const fig: FigureSpec | null | undefined = slide.figure_spec;
  const [smilesInput, setSmilesInput] = useState("");
  const [bondLen, setBondLen] = useState<number>(28);
  const uploadRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setSmilesInput("");
    const bLen = slide.figure_spec?.assets?.[0]?.fixed_bond_length_px;
    if (typeof bLen === "number" && bLen >= 20 && bLen <= 42) {
      setBondLen(bLen);
    }
  }, [slide.slide_no, fig?.figure_id]);

  if (!fig) {
    return (
      <aside
        style={{
          width: 348,
          background: "var(--surface-pure)",
          borderLeft: "1px solid var(--rule-hairline)",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          color: "var(--ink-muted)",
          textAlign: "center",
          flexShrink: 0,
          fontSize: 13,
        }}
      >
        封面 / 目录 / 尾页
      </aside>
    );
  }

  const primaryAsset = fig.assets[0];
  const bundle = primaryAsset ? assetUrls[primaryAsset.asset_id] : undefined;
  const activeUrl = bundle?.png_url;
  const is2D = primaryAsset?.engine === "chemdraw_rdkit";
  const is3D = primaryAsset?.engine === "cylview_3d";
  const curRot = primaryAsset?.rotation_deg || [0, 0, 0];
  const cur2DStyle = primaryAsset?.chem_style || "acs1996";
  const cur3DStyle = primaryAsset?.style_3d || "ball_stick";

  return (
    <aside
      style={{
        width: 356,
        background: "var(--surface-pure)",
        borderLeft: "1px solid var(--rule-hairline)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflowY: "auto",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          padding: "13px 16px",
          borderBottom: "1px solid var(--rule-strong)",
          borderTop: `2px solid ${accentColor}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 99,
              background: accentColor,
              display: "inline-block",
            }}
          />
          <span className="font-serif" style={{ fontWeight: 700, fontSize: 15.5, color: "var(--ink-primary)" }}>
            分子结构工作台
          </span>
        </div>
        <button
          type="button"
          className="btn-editorial-primary"
          disabled={busy}
          onClick={onRegenerate}
          style={{ padding: "5px 12px", fontSize: 12, background: accentColor, borderColor: accentColor }}
        >
          重绘
        </button>
      </div>

      <div style={{ padding: 15, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Transparent Figure Preview */}
        <div>
          <div
            className="alpha-checkerboard"
            style={{
              width: "100%",
              height: 176,
              borderRadius: 2,
              border: "1px solid #D6D2C8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
              padding: 10,
            }}
          >
            {activeUrl ? (
              <img
                key={activeUrl}
                src={activeUrl}
                alt="Structure preview"
                style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
              />
            ) : (
              <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>暂无预览</span>
            )}
          </div>

          {(bundle?.cdxml_url || bundle?.svg_url || bundle?.sdf_url) && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {bundle.cdxml_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.cdxml_url} download>
                  .cdxml
                </a>
              )}
              {bundle.svg_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.svg_url} download>
                  .svg
                </a>
              )}
              {bundle.sdf_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.sdf_url} download>
                  .sdf
                </a>
              )}
            </div>
          )}
        </div>

        {/* 2D / 3D Switch */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            padding: 3,
            background: "var(--paper-bg)",
            border: "1px solid #D6D2C8",
            borderRadius: 3,
            gap: 3,
          }}
        >
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              onRefineOrSwitch({
                archetype_override: "A05_chemdraw_halo",
                smiles_override: smilesInput || primaryAsset?.smiles || undefined,
              })
            }
            style={{
              padding: "7px 8px",
              fontSize: 12.5,
              fontWeight: 700,
              borderRadius: 2,
              cursor: "pointer",
              border: "none",
              background: is2D ? accentColor : "transparent",
              color: is2D ? "#FFFFFF" : "var(--ink-secondary)",
            }}
          >
            2D ChemDraw
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              onRefineOrSwitch({
                archetype_override: "A04_cylview_3d",
                smiles_override: smilesInput || primaryAsset?.smiles || undefined,
              })
            }
            style={{
              padding: "7px 8px",
              fontSize: 12.5,
              fontWeight: 700,
              borderRadius: 2,
              cursor: "pointer",
              border: "none",
              background: is3D ? accentColor : "transparent",
              color: is3D ? "#FFFFFF" : "var(--ink-secondary)",
            }}
          >
            3D 建模构象
          </button>
        </div>

        {/* Molecule Input */}
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <span style={{ fontSize: 12, color: "var(--ink-secondary)", fontWeight: 600 }}>药名或 SMILES</span>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              className="editorial-input font-mono"
              placeholder={primaryAsset?.smiles || "Osimertinib / 青蒿素"}
              value={smilesInput}
              onChange={(e) => setSmilesInput(e.target.value)}
              style={{ flex: 1, fontSize: 11.5 }}
            />
            <button
              type="button"
              className="btn-editorial-navy"
              disabled={busy}
              onClick={() =>
                onRefineOrSwitch({
                  asset_id: primaryAsset?.asset_id,
                  smiles_override: smilesInput || primaryAsset?.smiles || undefined,
                  fixed_bond_length_px: is2D ? bondLen : undefined,
                })
              }
              style={{ padding: "6px 12px", fontSize: 12, flexShrink: 0 }}
            >
              生成
            </button>
          </div>
        </div>

        {/* 2D Visual Swatch Grid */}
        {primaryAsset && is2D && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 12, color: "var(--ink-secondary)", fontWeight: 600 }}>2D 绘制风格</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {CHEM_STYLES_2D.map((cs) => {
                const selected = cur2DStyle === cs.id;
                return (
                  <button
                    key={cs.id}
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      onRefineOrSwitch({
                        asset_id: primaryAsset.asset_id,
                        chem_style_override: cs.id,
                      })
                    }
                    style={{
                      textAlign: "left",
                      padding: "7px 9px",
                      borderRadius: 2,
                      cursor: "pointer",
                      border: selected ? `1.5px solid ${accentColor}` : "1px solid #DCD8CF",
                      background: selected ? "var(--paper-bg)" : "#FFFFFF",
                      boxShadow: selected ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        width: 14,
                        height: 24,
                        borderRadius: 2,
                        background: `linear-gradient(135deg, ${cs.swatchA} 50%, ${cs.swatchB} 50%)`,
                        flexShrink: 0,
                        border: "1px solid rgba(0,0,0,0.08)",
                      }}
                    />
                    <span style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 10.5, color: "var(--ink-muted)", lineHeight: 1.1 }}>{cs.group}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: selected ? accentColor : "var(--ink-primary)", marginTop: 2 }}>
                        {cs.label}
                      </div>
                    </span>
                  </button>
                );
              })}
            </div>
            <label style={{ fontSize: 12, paddingTop: 2 }}>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--ink-secondary)", fontWeight: 600 }}>
                <span>键长</span>
                <span className="font-mono">{bondLen} px</span>
              </div>
              <input
                type="range"
                min={20}
                max={42}
                value={bondLen}
                onChange={(e) => setBondLen(Number(e.target.value))}
                onMouseUp={() =>
                  onRefineOrSwitch({
                    asset_id: primaryAsset.asset_id,
                    fixed_bond_length_px: bondLen,
                  })
                }
                style={{ width: "100%", marginTop: 4, accentColor }}
              />
            </label>
          </div>
        )}

        {/* 3D Visual Swatch Grid */}
        {primaryAsset && is3D && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 12, color: "var(--ink-secondary)", fontWeight: 600 }}>3D 建模风格</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {STYLES_3D.map((st) => {
                const selected = cur3DStyle === st.id;
                return (
                  <button
                    key={st.id}
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      onRefineOrSwitch({
                        asset_id: primaryAsset.asset_id,
                        style_3d_override: st.id,
                      })
                    }
                    style={{
                      textAlign: "left",
                      padding: "7px 9px",
                      borderRadius: 2,
                      cursor: "pointer",
                      border: selected ? `1.5px solid ${accentColor}` : "1px solid #DCD8CF",
                      background: selected ? "var(--paper-bg)" : "#FFFFFF",
                      boxShadow: selected ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        width: 14,
                        height: 24,
                        borderRadius: 99,
                        background: `radial-gradient(circle at 35% 30%, #FFFFFF 0%, ${st.swatchA} 45%, ${st.swatchB} 100%)`,
                        flexShrink: 0,
                        border: "1px solid rgba(0,0,0,0.08)",
                      }}
                    />
                    <span style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 10.5, color: "var(--ink-muted)", lineHeight: 1.1 }}>{st.group}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: selected ? accentColor : "var(--ink-primary)", marginTop: 2 }}>
                        {st.label}
                      </div>
                    </span>
                  </button>
                );
              })}
            </div>

            <div>
              <div style={{ fontSize: 12, color: "var(--ink-secondary)", fontWeight: 600, marginBottom: 5 }}>视角</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4 }}>
                {VIEW_PRESETS_3D.map((vp) => {
                  const active = curRot[0] === vp.deg[0] && curRot[1] === vp.deg[1] && curRot[2] === vp.deg[2];
                  return (
                    <button
                      key={vp.label}
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        onRefineOrSwitch({
                          asset_id: primaryAsset.asset_id,
                          rotation_deg_override: vp.deg,
                        })
                      }
                      style={{
                        padding: "5px 4px",
                        fontSize: 11.5,
                        fontWeight: 600,
                        borderRadius: 2,
                        cursor: "pointer",
                        border: active ? `1px solid ${accentColor}` : "1px solid #D6D2C8",
                        background: active ? accentColor : "#FFFFFF",
                        color: active ? "#FFFFFF" : "var(--ink-secondary)",
                      }}
                    >
                      {vp.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--ink-secondary)", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={Boolean(primaryAsset.show_nonpolar_h)}
                disabled={busy}
                onChange={(e) =>
                  onRefineOrSwitch({
                    asset_id: primaryAsset.asset_id,
                    show_nonpolar_h_override: e.target.checked,
                  })
                }
                style={{ accentColor }}
              />
              <span>显示全部氢原子</span>
            </label>
          </div>
        )}

        {/* Custom Upload */}
        {primaryAsset && (
          <div style={{ paddingTop: 6, borderTop: "1px solid #ECEAE3" }}>
            <button
              type="button"
              disabled={busy}
              onClick={() => uploadRef.current?.click()}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 2,
                border: "1px dashed #A8A49B",
                background: "var(--paper-bg)",
                color: "var(--ink-secondary)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              上传图片替换
            </button>
            <input
              ref={uploadRef}
              type="file"
              accept=".png,.jpg,.jpeg,.svg"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUploadReplacement(f, primaryAsset.asset_id);
              }}
            />
          </div>
        )}
      </div>
    </aside>
  );
};
