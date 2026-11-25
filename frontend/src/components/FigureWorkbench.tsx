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

const CHEM_STYLES_2D = [
  { id: "acs1996", label: "ACS 1996 经典" },
  { id: "nature_burgundy", label: "Nature 绛红" },
  { id: "shaded_scaffold", label: "药效团填色" },
  { id: "jacs_terracotta", label: "JACS 砖红" },
  { id: "reactive_spot", label: "反应位点高亮" },
  { id: "minimal_mono", label: "极简黑线" },
];

const STYLES_3D = [
  { id: "ball_stick", label: "球棍模型 (Ball & Stick)" },
  { id: "stick_clean", label: "棒状模型 (Stick)" },
  { id: "spacefill_cpk", label: "空间填充 (CPK)" },
  { id: "pymol_neon_green", label: "PyMOL 亮绿碳" },
  { id: "metallic_studio", label: "金属质感 (Blender)" },
];

const VIEW_PRESETS_3D: Array<{ label: string; deg: number[] }> = [
  { label: "正面", deg: [0, 0, 0] },
  { label: "俯视", deg: [35, 0, 0] },
  { label: "侧视", deg: [10, 55, 0] },
  { label: "翻转", deg: [0, 90, 0] },
];

export const FigureWorkbench: React.FC<FigureWorkbenchProps> = ({
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
          width: 340,
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

  return (
    <aside
      style={{
        width: 348,
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
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div className="font-serif" style={{ fontWeight: 700, fontSize: 15.5, color: "var(--ink-primary)" }}>
          结构式
        </div>
        <button
          type="button"
          className="btn-editorial-primary"
          disabled={busy}
          onClick={onRegenerate}
          style={{ padding: "6px 12px", fontSize: 12 }}
        >
          重绘
        </button>
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Transparent Figure Preview */}
        <div>
          <div
            className="alpha-checkerboard"
            style={{
              width: "100%",
              height: 184,
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
              <img key={activeUrl} src={activeUrl} alt="Structure preview" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
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
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
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
              padding: "8px 10px",
              fontSize: 12.5,
              fontWeight: 700,
              borderRadius: 2,
              cursor: "pointer",
              border: "1px solid var(--nature-crimson)",
              background: is2D ? "var(--nature-crimson)" : "#FFFFFF",
              color: is2D ? "#FFFFFF" : "var(--nature-crimson)",
            }}
          >
            2D 结构式
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
              padding: "8px 10px",
              fontSize: 12.5,
              fontWeight: 700,
              borderRadius: 2,
              cursor: "pointer",
              border: "1px solid var(--oxford-navy)",
              background: is3D ? "var(--oxford-navy)" : "#FFFFFF",
              color: is3D ? "#FFFFFF" : "var(--oxford-navy)",
            }}
          >
            3D 结构式
          </button>
        </div>

        {/* Molecule Input */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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

        {/* 2D Styles */}
        {primaryAsset && is2D && (
          <div
            style={{
              padding: 12,
              borderRadius: 2,
              background: "var(--paper-bg)",
              border: "1px solid var(--rule-hairline)",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <label style={{ fontSize: 12 }}>
              <span style={{ color: "var(--ink-secondary)", fontWeight: 600 }}>2D 风格</span>
              <select
                className="editorial-select"
                value={primaryAsset.chem_style || "acs1996"}
                disabled={busy}
                onChange={(e) =>
                  onRefineOrSwitch({
                    asset_id: primaryAsset.asset_id,
                    chem_style_override: e.target.value,
                  })
                }
                style={{ marginTop: 4 }}
              >
                {CHEM_STYLES_2D.map((cs) => (
                  <option key={cs.id} value={cs.id}>
                    {cs.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
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
                style={{ width: "100%", marginTop: 4, accentColor: "var(--nature-crimson)" }}
              />
            </label>
          </div>
        )}

        {/* 3D Styles */}
        {primaryAsset && is3D && (
          <div
            style={{
              padding: 12,
              borderRadius: 2,
              background: "var(--paper-bg)",
              border: "1px solid var(--rule-hairline)",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <label style={{ fontSize: 12 }}>
              <span style={{ color: "var(--ink-secondary)", fontWeight: 600 }}>3D 风格</span>
              <select
                className="editorial-select"
                value={primaryAsset.style_3d || "ball_stick"}
                disabled={busy}
                onChange={(e) =>
                  onRefineOrSwitch({
                    asset_id: primaryAsset.asset_id,
                    style_3d_override: e.target.value,
                  })
                }
                style={{ marginTop: 4 }}
              >
                {STYLES_3D.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.label}
                  </option>
                ))}
              </select>
            </label>

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
                        border: active ? "1px solid var(--oxford-navy)" : "1px solid #D6D2C8",
                        background: active ? "var(--oxford-navy)" : "#FFFFFF",
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
                style={{ accentColor: "var(--oxford-navy)" }}
              />
              <span>显示全部氢原子</span>
            </label>
          </div>
        )}

        {/* Custom Upload */}
        {primaryAsset && (
          <div style={{ paddingTop: 4, borderTop: "1px solid #ECEAE3" }}>
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
