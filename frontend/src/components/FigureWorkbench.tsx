import React, { useRef, useState } from "react";
import { Wand2, RefreshCw, Upload, Check, Sparkles, Download } from "lucide-react";
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
    chem_style_override?: string;
  }) => Promise<void>;
  onUploadReplacement: (file: File, assetId: string) => Promise<void>;
}

const CHEM_STYLES = [
  { id: "acs1996", label: "ACS 1996 经典出版风" },
  { id: "nature_burgundy", label: "Nature 绛红手绘风" },
  { id: "shaded_scaffold", label: "药效团环填色风" },
  { id: "jacs_terracotta", label: "JACS 砖红发表风" },
  { id: "reactive_spot", label: "反应位点蓝斑高亮" },
  { id: "minimal_mono", label: "极简纯黑线稿风" },
];

const ORIGIN_PRESETS = [
  { id: "nature_grouped_bar", label: "Nature 分组柱图 + Tukey 字母 / P 值" },
  { id: "nature_step_drop_zoom", label: "Nature 阶梯下降瀑布 + 局部放大" },
  { id: "nature_horizontal_ranked", label: "Nature 横向排序柱图 + 显著性星号" },
  { id: "kinetics_spline", label: "动力学平滑样条 + 直标" },
  { id: "paired_gain_bar", label: "斜线对照柱图 + 增幅胶囊" },
  { id: "electrochem_suite", label: "电化学 LSV / Tafel / 稳定性 4 联" },
  { id: "xps_deconv", label: "XPS 半透明分峰 + 价态表" },
  { id: "dft_energy_profile", label: "DFT 自由能阶梯曲线" },
  { id: "dft_slab_bader_link", label: "DFT 晶面吸附 + Bader 联动" },
  { id: "ml_parity_kde", label: "ML 奇偶散点 + 边缘 KDE" },
  { id: "benchmark_scatter", label: "文献性能基准散点 + ★椭圆" },
];

export const FigureWorkbench: React.FC<FigureWorkbenchProps> = ({
  slide,
  archetypes,
  assetUrls,
  busy,
  onRegenerate,
  onRefineOrSwitch,
  onUploadReplacement,
}) => {
  const fig: FigureSpec | null | undefined = slide.figure_spec;
  const [refineText, setRefineText] = useState("");
  const [smilesInput, setSmilesInput] = useState("");
  const [bondLen, setBondLen] = useState<number>(28);
  const uploadRef = useRef<HTMLInputElement | null>(null);

  if (!fig) {
    return (
      <aside
        style={{
          width: 376,
          background: "var(--surface-pure)",
          borderLeft: "1px solid var(--rule-hairline)",
          padding: 28,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          color: "var(--ink-muted)",
          textAlign: "center",
          flexShrink: 0,
        }}
      >
        <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 8 }}>
          STRUCTURAL SECTION
        </div>
        <div className="font-serif" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink-primary)", marginBottom: 8 }}>
          结构过渡页
        </div>
        <div style={{ fontSize: 12.5, lineHeight: 1.65 }}>
          当前页为目录 / 封面 / 致谢过渡页。点击左侧任意正文页，即可启动单页科研绘图精修工作台。
        </div>
      </aside>
    );
  }

  const primaryAsset = fig.assets[0];
  const bundle = primaryAsset ? assetUrls[primaryAsset.asset_id] : undefined;
  const activeUrl = bundle?.png_url;
  const candidates = bundle?.candidates || [];

  return (
    <aside
      style={{
        width: 380,
        background: "var(--surface-pure)",
        borderLeft: "1px solid var(--rule-hairline)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflowY: "auto",
        flexShrink: 0,
      }}
    >
      {/* Editorial Art-Direction Header */}
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid var(--rule-strong)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div>
          <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 2 }}>
            ART DIRECTION · PLATE INSPECTOR
          </div>
          <div className="font-serif" style={{ fontWeight: 700, fontSize: 16, color: "var(--ink-primary)" }}>
            科研图元精修台
          </div>
          <div className="font-mono" style={{ fontSize: 10.5, color: "var(--ink-muted)", marginTop: 2 }}>
            SLIDE #{String(slide.slide_no).padStart(2, "0")} · QA {fig.overall_qa_score.toFixed(1)}/10 ·{" "}
            {fig.qa_passed ? "PASSED" : "NEEDS REVIEW"}
          </div>
        </div>
        <button
          type="button"
          className="btn-editorial-primary"
          disabled={busy}
          onClick={onRegenerate}
          style={{ padding: "7px 12px", fontSize: 12 }}
        >
          <RefreshCw size={13} /> 重绘
        </button>
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Layer 1 Transparent Asset Preview Bay */}
        <div>
          <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 7, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--ink-secondary)" }}>Layer 1 独立透明底科研图元</span>
            <span className="font-mono" style={{ fontSize: 10.5, color: "var(--audit-sage)", fontWeight: 600 }}>
              OCR TEXT: {primaryAsset?.qa_result?.ocr_text_count ?? 0}
            </span>
          </div>
          <div
            className="alpha-checkerboard"
            style={{
              width: "100%",
              height: 188,
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
              <img src={activeUrl} alt="Figure asset" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
            ) : (
              <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>暂无独立预览图元</span>
            )}
          </div>
          {(bundle?.cdxml_url || bundle?.sdf_url || bundle?.svg_url || bundle?.csv_url) && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {bundle.cdxml_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.cdxml_url} download>
                  <Download size={11} /> .cdxml
                </a>
              )}
              {bundle.sdf_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.sdf_url} download>
                  <Download size={11} /> .sdf (PyMOL)
                </a>
              )}
              {bundle.svg_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.svg_url} download>
                  <Download size={11} /> .svg
                </a>
              )}
              {bundle.csv_url && (
                <a className="btn-editorial-ghost font-mono" style={{ padding: "3px 8px", fontSize: 11, textDecoration: "none" }} href={bundle.csv_url} download>
                  <Download size={11} /> .csv (Origin)
                </a>
              )}
            </div>
          )}
        </div>

        {/* Archetype A01-A10 Selector */}
        <label style={{ fontSize: 12 }}>
          <div className="kicker" style={{ color: "var(--ink-muted)", marginBottom: 5 }}>
            FIGURE ARCHETYPE (A01–A10)
          </div>
          <select
            className="editorial-select"
            value={fig.archetype}
            disabled={busy}
            onChange={(e) => onRefineOrSwitch({ archetype_override: e.target.value as ArchetypeId })}
          >
            {archetypes.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>

        {/* Engine-Specific Parameter Panel */}
        {primaryAsset && (primaryAsset.engine === "chemdraw_rdkit" || primaryAsset.engine === "cylview_3d") && (
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
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
              <div className="kicker" style={{ color: "var(--oxford-navy)" }}>
                {primaryAsset.engine === "chemdraw_rdkit" ? "CHEMDRAW 2D · ACS 1996" : "PYMOL / CYLVIEW 3D"}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    onRefineOrSwitch({
                      archetype_override: "A05_chemdraw_halo",
                      smiles_override: smilesInput || primaryAsset.smiles || undefined,
                    })
                  }
                  style={{
                    padding: "2px 8px",
                    fontSize: 11,
                    fontWeight: 700,
                    borderRadius: 2,
                    cursor: "pointer",
                    border: "1px solid var(--nature-crimson)",
                    background: primaryAsset.engine === "chemdraw_rdkit" ? "var(--nature-crimson)" : "#FFFFFF",
                    color: primaryAsset.engine === "chemdraw_rdkit" ? "#FFFFFF" : "var(--nature-crimson)",
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
                      smiles_override: smilesInput || primaryAsset.smiles || undefined,
                    })
                  }
                  style={{
                    padding: "2px 8px",
                    fontSize: 11,
                    fontWeight: 700,
                    borderRadius: 2,
                    cursor: "pointer",
                    border: "1px solid var(--oxford-navy)",
                    background: primaryAsset.engine === "cylview_3d" ? "var(--oxford-navy)" : "#FFFFFF",
                    color: primaryAsset.engine === "cylview_3d" ? "#FFFFFF" : "var(--oxford-navy)",
                  }}
                >
                  3D 球棍
                </button>
              </div>
            </div>
            <label style={{ fontSize: 12 }}>
              <span style={{ color: "var(--ink-secondary)", fontWeight: 600 }}>药名 / SMILES（支持自动检索）</span>
              <input
                className="editorial-input font-mono"
                placeholder={primaryAsset.smiles || "如 Osimertinib / 青蒿素 或 SMILES"}
                value={smilesInput}
                onChange={(e) => setSmilesInput(e.target.value)}
                style={{ marginTop: 4, fontSize: 11.5 }}
              />
            </label>
            {primaryAsset.engine === "chemdraw_rdkit" && (
              <>
                <label style={{ fontSize: 12 }}>
                  <span style={{ color: "var(--ink-secondary)", fontWeight: 600 }}>ChemDraw 发表画风</span>
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
                    {CHEM_STYLES.map((cs) => (
                      <option key={cs.id} value={cs.id}>
                        {cs.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ fontSize: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", color: "var(--ink-secondary)", fontWeight: 600 }}>
                    <span>全局物理键长锁定</span>
                    <span className="font-mono" style={{ color: "var(--nature-crimson)" }}>{bondLen} px</span>
                  </div>
                  <input
                    type="range"
                    min={20}
                    max={42}
                    value={bondLen}
                    onChange={(e) => setBondLen(Number(e.target.value))}
                    style={{ width: "100%", marginTop: 4, accentColor: "var(--nature-crimson)" }}
                  />
                </label>
              </>
            )}
            <button
              type="button"
              className="btn-editorial-navy"
              disabled={busy}
              onClick={() =>
                onRefineOrSwitch({
                  asset_id: primaryAsset.asset_id,
                  smiles_override: smilesInput || primaryAsset.smiles || undefined,
                  fixed_bond_length_px: bondLen,
                })
              }
              style={{ padding: "7px 12px", fontSize: 12 }}
            >
              应用分子参数并重新计算
            </button>
          </div>
        )}

        {primaryAsset && primaryAsset.engine === "origin_plot" && (
          <div
            style={{
              padding: 12,
              borderRadius: 2,
              background: "var(--paper-bg)",
              border: "1px solid var(--rule-hairline)",
            }}
          >
            <div className="kicker" style={{ color: "var(--oxford-navy)", marginBottom: 6 }}>
              ORIGINPRO 600 DPI PRESET
            </div>
            <select
              className="editorial-select"
              value={primaryAsset.preset || "kinetics_spline"}
              disabled={busy}
              onChange={(e) => onRefineOrSwitch({ asset_id: primaryAsset.asset_id, origin_preset: e.target.value })}
            >
              {ORIGIN_PRESETS.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {primaryAsset && primaryAsset.engine === "sci3d_art" && (
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
            <div className="kicker" style={{ color: "var(--oxford-navy)" }}>
              3D RENDER MODE & ART DIRECTION
            </div>
            <select
              className="editorial-select"
              value={primaryAsset.render_mode}
              disabled={busy}
              onChange={(e) => onRefineOrSwitch({ asset_id: primaryAsset.asset_id, render_mode: e.target.value })}
            >
              <option value="c4d_octane_cutaway">C4D Octane 3D 剖切装置与多孔材质</option>
              <option value="editorial_flat_3d">Nature Reviews 2D 扁平微立体编辑风</option>
              <option value="vesta_polyhedra">VESTA 多面体晶体界面模式</option>
              <option value="nature_line_art">Nature Reviews 细线稿多尺度模式</option>
            </select>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                className="editorial-input"
                placeholder="如：放大孔道水分子、调浅载体蓝..."
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                style={{ flex: 1, fontSize: 12 }}
              />
              <button
                type="button"
                className="btn-editorial-primary"
                disabled={busy || !refineText.trim()}
                onClick={() => onRefineOrSwitch({ asset_id: primaryAsset.asset_id, refinement_instruction: refineText })}
                style={{ padding: "7px 11px", fontSize: 12, flexShrink: 0 }}
              >
                <Wand2 size={12} /> 微调
              </button>
            </div>
          </div>
        )}

        {/* Best-of-N Candidate Selector */}
        {candidates.length > 1 && primaryAsset && (
          <div>
            <div className="kicker" style={{ color: "var(--ink-secondary)", marginBottom: 7, display: "flex", alignItems: "center", gap: 5 }}>
              <Sparkles size={12} color="var(--nature-crimson)" /> BEST-OF-N CANDIDATE SELECTOR
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {candidates.map((cand, idx) => {
                const selected = idx === primaryAsset.selected_candidate_idx;
                return (
                  <div
                    key={cand.candidate_id}
                    onClick={() => onRefineOrSwitch({ asset_id: primaryAsset.asset_id, selected_candidate_idx: idx })}
                    style={{
                      border: selected ? "2px solid var(--nature-crimson)" : "1px solid #D6D2C8",
                      borderRadius: 2,
                      padding: 6,
                      cursor: "pointer",
                      background: selected ? "var(--paper-bg)" : "var(--surface-pure)",
                    }}
                  >
                    <div
                      className="alpha-checkerboard"
                      style={{ height: 74, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 2 }}
                    >
                      {cand.png_url && (
                        <img
                          src={cand.png_url}
                          alt={cand.candidate_id}
                          style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                        />
                      )}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginTop: 5 }}>
                      <span className="font-mono" style={{ color: "var(--ink-secondary)" }}>
                        SCORE {cand.vlm_aesthetic_score.toFixed(1)}
                      </span>
                      {selected && <Check size={13} color="var(--nature-crimson)" />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Local High-Res Asset Replacement */}
        {primaryAsset && (
          <div style={{ paddingTop: 4, borderTop: "1px solid #ECEAE3" }}>
            <button
              type="button"
              disabled={busy}
              onClick={() => uploadRef.current?.click()}
              style={{
                width: "100%",
                padding: "9px 12px",
                borderRadius: 2,
                border: "1px dashed #A8A49B",
                background: "var(--paper-bg)",
                color: "var(--ink-secondary)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
              }}
            >
              <Upload size={13} /> 上传本地 ChemDraw / Origin / C4D 原图替换
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
