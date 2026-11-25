import React, { useEffect, useState } from "react";
import {
  applyPaletteToDeck,
  buildPptx,
  checkAccessCode,
  fetchArchetypes,
  fetchPalettes,
  planDeck,
  planDeckFromFile,
  regenerateFigure,
  renderSlideLayersPreview,
  selectOrRefineFigure,
  syncWordToPptx,
  uploadCustomFigure,
} from "./api/client";
import { formatPaletteLabel, resolvePaletteAccent } from "./types/deckSpec";
import type {
  ArchetypeId,
  ArchetypeInfo,
  AssetUrlBundle,
  AuditReport,
  CoverTemplateId,
  DeckSpec,
  DesignStyle,
  PaletteInfo,
  ScenarioType,
  SlideSpec,
} from "./types/deckSpec";
import { DeckOutlinePanel } from "./components/DeckOutlinePanel";
import { SlideCanvasPreview } from "./components/SlideCanvasPreview";
import { FigureWorkbench } from "./components/FigureWorkbench";
import { ImportModal } from "./components/ImportModal";
import { PaletteSelector } from "./components/PaletteSelector";
import { ExportPanel } from "./components/ExportPanel";
import { ModelSettingsModal } from "./components/ModelSettingsModal";
import { isCloudAiActive, isHostedAiActive, loadAiConfig, saveAiConfig } from "./types/aiConfig";
import type { AiConfig } from "./types/aiConfig";

const NIRMATRELVIR_DEMO_OUTLINE = `# Classic Medicinal Chemistry Structures & Catalytic Mechanisms
## 1. 经典药物结构式 · 多风格二维矢量
以青霉素 G (Penicillin G, 绛红手绘风) 与青蒿素 (Artemisinin, 药效团环填充风) 对照展示四种顶刊分子绘制范式。
SMILES: CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O
## 2. 立体三维构象 · 青蒿素过氧桥
CYLview 3D 隐藏非极性氢构象还原青蒿素五环刚性骨架与 1,2,4-三氧杂环过氧桥 (–O–O–) 裂解中心。
SMILES: C[C@@H]1CC[C@H]2[C@@H](C)C(=O)O[C@@H]3O[C@@]4(C)CC[C@@H]1[C@@]23OO4
## 3. 催化循环机理 · 偶联与极简线稿
Pd(0)/Pd(II) Buchwald–Hartwig C–N 催化循环驱动伊马替尼 (Imatinib) 关键二芳胺键高效构筑。
SMILES: Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc4nccc(n4)c5cccnc5`;

const CURATED_PLATES = [
  {
    id: "plate_01",
    tab: "目录",
    label: "分镜目录",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_01.png",
  },
  {
    id: "plate_02",
    tab: "2D 结构",
    label: "ChemDraw 2D",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_02.png",
  },
  {
    id: "plate_03",
    tab: "3D 结构",
    label: "3D 球棍模型",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_03.png",
  },
  {
    id: "plate_04",
    tab: "对比",
    label: "结构线稿",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_04.png",
  },
];

export function App() {
  const [palettes, setPalettes] = useState<PaletteInfo[]>([]);
  const [archetypes, setArchetypes] = useState<ArchetypeInfo[]>([]);
  const [deck, setDeck] = useState<DeckSpec | null>(null);
  const [selectedSlideNo, setSelectedSlideNo] = useState<number>(1);
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [assetUrls, setAssetUrls] = useState<Record<string, AssetUrlBundle>>({});
  const [activeLayers, setActiveLayers] = useState<string[]>(["L1", "L2", "L3"]);

  const [importOpen, setImportOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [modelSettingsOpen, setModelSettingsOpen] = useState(false);
  const [aiConfig, setAiConfig] = useState<AiConfig>(() => loadAiConfig());
  const [hostedCredits, setHostedCredits] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [featuredPlateIdx, setFeaturedPlateIdx] = useState<number>(1);
  const [plateLoadFailed, setPlateLoadFailed] = useState<boolean>(false);

  const [buildResult, setBuildResult] = useState<{
    pptx_url: string;
    deck_spec_url: string;
    preview_urls: string[];
    audit_report: AuditReport;
  } | null>(null);
  const [syncedUrl, setSyncedUrl] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchPalettes(), fetchArchetypes()])
      .then(([pals, archs]) => {
        setPalettes(pals);
        setArchetypes(archs);
      })
      .catch((err) => setErrorMsg(String(err)));
  }, []);

  useEffect(() => {
    if (aiConfig.provider === "hosted" && aiConfig.accessCode.trim()) {
      checkAccessCode(aiConfig.accessCode.trim())
        .then((res) => setHostedCredits(res.valid ? res.credits_left : 0))
        .catch(() => setHostedCredits(null));
    } else {
      setHostedCredits(null);
    }
  }, [aiConfig.provider, aiConfig.accessCode]);

  const appendCacheBust = (url: string | null | undefined, ts: number): string => {
    if (!url) return "";
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}t=${ts}`;
  };

  const bustAssetBundleMap = (
    map: Record<string, AssetUrlBundle>,
    ts: number,
  ): Record<string, AssetUrlBundle> => {
    const out: Record<string, AssetUrlBundle> = {};
    for (const [k, bundle] of Object.entries(map)) {
      out[k] = {
        ...bundle,
        png_url: bundle.png_url ? appendCacheBust(bundle.png_url, ts) : bundle.png_url,
        candidates: (bundle.candidates || []).map((c) => ({
          ...c,
          png_url: c.png_url ? appendCacheBust(c.png_url, ts) : c.png_url,
        })),
      };
    }
    return out;
  };

  const refreshSlidePreview = async (curDeck: DeckSpec, slideNo: number, layers: string[]) => {
    const res = await renderSlideLayersPreview(curDeck, slideNo, layers);
    const key = `slide_${String(slideNo).padStart(2, "0")}`;
    setPreviewUrls((prev) => ({ ...prev, [key]: appendCacheBust(res.preview_url, Date.now()) }));
  };

  const handlePlanText = async (payload: {
    source_text: string;
    deck_title?: string;
    author: string;
    affiliation: string;
    advisor?: string;
    date_str?: string;
    scenario: ScenarioType;
    target_slide_count: number;
    palette_id: string;
    is_proposal: boolean;
    design_style: DesignStyle;
    cover_template?: CoverTemplateId;
    include_dividers?: boolean;
  }) => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await planDeck(payload);
      setDeck(res.deck_spec);
      setPreviewUrls(res.artifact_urls);
      setAssetUrls(res.asset_urls);
      setSelectedSlideNo(res.deck_spec.slides[0]?.slide_no || 1);
      setImportOpen(false);
      setBuildResult(null);
      if (typeof res.billing?.credits_left === "number") {
        setHostedCredits(res.billing.credits_left);
      }
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleLoadNirmatrelvirDemo = async () => {
    await handlePlanText({
      source_text: NIRMATRELVIR_DEMO_OUTLINE,
      deck_title: "Classic Medicinal Chemistry Structures & Catalytic Mechanisms",
      author: "计算药化课题组",
      affiliation: "Nature Editorial Desk",
      advisor: "计算药化教研室",
      date_str: "2026 年 11 月",
      scenario: "literature_review",
      target_slide_count: 8,
      palette_id: "nejm",
      is_proposal: false,
      design_style: "defense_modular",
      cover_template: "hero_band_bottom_bar",
      include_dividers: true,
    });
  };

  const handlePlanFile = async (fd: FormData) => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await planDeckFromFile(fd);
      setDeck(res.deck_spec);
      setPreviewUrls(res.artifact_urls);
      setAssetUrls(res.asset_urls);
      setSelectedSlideNo(res.deck_spec.slides.find((s) => s.slide_type === "content")?.slide_no || 1);
      setImportOpen(false);
      setBuildResult(null);
      if (typeof res.billing?.credits_left === "number") {
        setHostedCredits(res.billing.credits_left);
      }
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const currentSlide: SlideSpec | undefined = deck?.slides.find((s) => s.slide_no === selectedSlideNo) || deck?.slides[0];

  const handleToggleLayer = async (layer: string) => {
    if (!deck || !currentSlide) return;
    const next = activeLayers.includes(layer)
      ? activeLayers.filter((l) => l !== layer)
      : [...activeLayers, layer];
    const safeNext = next.length > 0 ? next : ["L1"];
    setActiveLayers(safeNext);
    await refreshSlidePreview(deck, currentSlide.slide_no, safeNext);
  };

  const handleUpdateSlide = async (updatedSlide: SlideSpec) => {
    if (!deck) return;
    const nextDeck: DeckSpec = {
      ...deck,
      slides: deck.slides.map((s) => (s.slide_no === updatedSlide.slide_no ? updatedSlide : s)),
    };
    setDeck(nextDeck);
    await refreshSlidePreview(nextDeck, updatedSlide.slide_no, activeLayers);
  };

  const handleUpdateFonts = async (ea: string, latin: string) => {
    if (!deck || !currentSlide) return;
    const nextDeck: DeckSpec = {
      ...deck,
      locked_standards: {
        ...deck.locked_standards,
        fonts: { ea, latin },
      },
    };
    setDeck(nextDeck);
    await refreshSlidePreview(nextDeck, currentSlide.slide_no, activeLayers);
  };

  const handleUpdateCoverTemplate = async (cover_template: CoverTemplateId) => {
    if (!deck || !currentSlide) return;
    const nextDeck: DeckSpec = {
      ...deck,
      meta: {
        ...deck.meta,
        cover_template,
      },
    };
    setDeck(nextDeck);
    const targets = nextDeck.slides.filter(
      (s) => s.slide_type === "cover" || s.slide_type === "closing" || s.slide_no === currentSlide.slide_no,
    );
    await Promise.all(
      targets.map((s) => refreshSlidePreview(nextDeck, s.slide_no, activeLayers)),
    );
  };

  const handleAddContentSlide = async () => {
    if (!deck) return;
    const newNo = deck.slides.length + 1;
    const template = deck.slides.find((s) => s.slide_type === "content");
    const newSlide: SlideSpec = {
      slide_no: newNo,
      slide_type: "content",
      layout_id: "lit_overview_dual_card",
      section_name: `新增科学主题 ${newNo}`,
      eyebrow: `SECTION ${String(newNo).padStart(2, "0")} · NEW INSIGHT`,
      title: `新增科学分析页面 #${newNo}`,
      takeaway: "在此补充单句核心科学结论（≥14pt，简明精准）。",
      figure_spec: template?.figure_spec ? JSON.parse(JSON.stringify(template.figure_spec)) : null,
      kpis: [],
      insights: [{ index: "01", heading: "核心结论", body: "在此输入简明论据。", highlight: "简明论据" }],
      toc_items: [],
      footer_left: deck.meta.deck_title,
      speaker_notes: "",
    };
    const nextDeck: DeckSpec = {
      ...deck,
      meta: { ...deck.meta, target_slide_count: deck.slides.length + 1 },
      slides: [...deck.slides, newSlide],
    };
    setDeck(nextDeck);
    setSelectedSlideNo(newNo);
    await refreshSlidePreview(nextDeck, newNo, activeLayers);
  };

  const handleAddDividerSlide = async () => {
    if (!deck) return;
    const partCount = deck.slides.filter((s) => s.slide_type === "part_divider").length + 1;
    const insertAt = Math.max(1, deck.slides.length - 1);
    const dividerSlide: SlideSpec = {
      slide_no: insertAt + 1,
      slide_type: "part_divider",
      layout_id: "part_divider",
      section_name: `第${partCount}部分 章节过渡`,
      eyebrow: `PART 0${partCount}`,
      title: `研究进展第 ${partCount} 部分`,
      takeaway: "核心研究思路 · 关键实验结果 · 机理深入解析",
      figure_spec: null,
      kpis: [],
      insights: [],
      toc_items: [],
      footer_left: deck.meta.deck_title,
      speaker_notes: `过渡至第 ${partCount} 部分。`,
    };
    const merged = [
      ...deck.slides.slice(0, insertAt),
      dividerSlide,
      ...deck.slides.slice(insertAt),
    ].map((s, idx) => ({ ...s, slide_no: idx + 1 }));
    const nextDeck: DeckSpec = {
      ...deck,
      meta: { ...deck.meta, target_slide_count: merged.length },
      slides: merged,
    };
    setDeck(nextDeck);
    const addedNo = insertAt + 1;
    setSelectedSlideNo(addedNo);
    await refreshSlidePreview(nextDeck, addedNo, activeLayers);
  };

  const handleDeleteSlide = (slideNo: number) => {
    if (!deck || deck.slides.length <= 3) return;
    const filtered = deck.slides
      .filter((s) => s.slide_no !== slideNo)
      .map((s, idx) => ({ ...s, slide_no: idx + 1 }));
    setDeck({ ...deck, meta: { ...deck.meta, target_slide_count: filtered.length }, slides: filtered });
    setSelectedSlideNo(filtered[0].slide_no);
  };

  const handleRegenerateFigure = async () => {
    if (!deck || !currentSlide?.figure_spec) return;
    setBusy(true);
    try {
      const res = await regenerateFigure({
        deck_id: deck.meta.deck_id,
        slide_no: currentSlide.slide_no,
        palette_id: deck.meta.palette_id,
        scenario: deck.meta.scenario,
        is_proposal: deck.meta.is_proposal,
        figure_spec: currentSlide.figure_spec,
        best_of_n: 2,
      });
      const updatedSlide = { ...currentSlide, figure_spec: res.figure_spec };
      const nextDeck = { ...deck, slides: deck.slides.map((s) => (s.slide_no === updatedSlide.slide_no ? updatedSlide : s)) };
      setDeck(nextDeck);
      setAssetUrls((prev) => ({ ...prev, ...bustAssetBundleMap(res.asset_urls, Date.now()) }));
      await refreshSlidePreview(nextDeck, updatedSlide.slide_no, activeLayers);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRefineOrSwitch = async (params: {
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
  }) => {
    if (!deck || !currentSlide?.figure_spec) return;
    setBusy(true);
    try {
      const res = await selectOrRefineFigure({
        deck_id: deck.meta.deck_id,
        slide_no: currentSlide.slide_no,
        palette_id: deck.meta.palette_id,
        figure_spec: currentSlide.figure_spec,
        ...params,
      });
      const updatedSlide = { ...currentSlide, figure_spec: res.figure_spec };
      const nextDeck = { ...deck, slides: deck.slides.map((s) => (s.slide_no === updatedSlide.slide_no ? updatedSlide : s)) };
      setDeck(nextDeck);
      setAssetUrls((prev) => ({ ...prev, ...bustAssetBundleMap(res.asset_urls, Date.now()) }));
      await refreshSlidePreview(nextDeck, updatedSlide.slide_no, activeLayers);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleUploadReplacement = async (file: File, assetId: string) => {
    if (!deck || !currentSlide?.figure_spec) return;
    setBusy(true);
    try {
      const res = await uploadCustomFigure(file, deck.meta.deck_id, currentSlide.slide_no, assetId);
      const updatedAssets = currentSlide.figure_spec.assets.map((a) =>
        a.asset_id === assetId
          ? { ...a, engine: "uploaded_image" as const, png_path: String(res.asset.png_path || "") }
          : a,
      );
      const updatedSlide = { ...currentSlide, figure_spec: { ...currentSlide.figure_spec, assets: updatedAssets } };
      const nextDeck = { ...deck, slides: deck.slides.map((s) => (s.slide_no === updatedSlide.slide_no ? updatedSlide : s)) };
      setDeck(nextDeck);
      setAssetUrls((prev) => ({ ...prev, [assetId]: { png_url: appendCacheBust(res.png_url, Date.now()) } }));
      await refreshSlidePreview(nextDeck, updatedSlide.slide_no, activeLayers);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleApplyPalette = async (paletteId: string) => {
    if (!deck) return;
    setBusy(true);
    try {
      const res = await applyPaletteToDeck(deck, paletteId, true);
      const ts = Date.now();
      const bustedPreviews: Record<string, string> = {};
      for (const [k, u] of Object.entries(res.artifact_urls || {})) {
        bustedPreviews[k] = appendCacheBust(u, ts);
      }
      setDeck(res.deck_spec);
      setPreviewUrls(bustedPreviews);
      setAssetUrls(bustAssetBundleMap(res.asset_urls || {}, ts));
      setPaletteOpen(false);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleBuildPptx = async () => {
    if (!deck) return;
    setBusy(true);
    try {
      const res = await buildPptx(deck);
      setBuildResult(res);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSyncWord = async (file: File) => {
    if (!deck) return;
    setBusy(true);
    try {
      const res = await syncWordToPptx(file, deck.meta.deck_id);
      setSyncedUrl(res.synced_pptx_url);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setBusy(false);
    }
  };

  const previewKey = currentSlide ? `slide_${String(currentSlide.slide_no).padStart(2, "0")}` : "";
  const activePlate = CURATED_PLATES[featuredPlateIdx] || CURATED_PLATES[0];
  const activeAccent = deck ? resolvePaletteAccent(deck.meta.palette_id, palettes) : "#B5121B";

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--paper-bg)" }}>
      {/* Tier 1: Theme Accent Masthead Rule */}
      <div style={{ height: 3, background: activeAccent, flexShrink: 0, transition: "background-color 180ms ease" }} />

      {/* Tier 2: Archival White Masthead Bar */}
      <header
        style={{
          height: 60,
          padding: "0 24px",
          background: "var(--surface-pure)",
          borderBottom: "1px solid var(--rule-strong)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
          <button
            type="button"
            onClick={() => setDeck(null)}
            style={{
              background: "transparent",
              border: "none",
              padding: 0,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "baseline",
              gap: 6,
            }}
            title="返回 Nature 编辑部首页"
          >
            <span className="font-serif" style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-primary)", letterSpacing: "-0.02em" }}>
              Academic
            </span>
            <span className="font-serif" style={{ fontSize: 22, fontWeight: 600, fontStyle: "italic", color: "var(--nature-crimson)" }}>
              Studio
            </span>
          </button>

          <span style={{ width: 1, height: 22, background: "var(--rule-hairline)" }} />

          {deck ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <span
                className="font-serif"
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "var(--ink-primary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: 440,
                }}
              >
                {deck.meta.deck_title}
              </span>
            </div>
          ) : null}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          {deck && (
            <button type="button" className="btn-editorial-ghost" onClick={() => setDeck(null)}>
              返回
            </button>
          )}
          <button type="button" className="btn-editorial-ghost" onClick={() => setModelSettingsOpen(true)}>
            <span>AI 模型</span>
            <span
              className="font-mono"
              style={{
                fontSize: 10.5,
                padding: "1px 6px",
                background: isCloudAiActive(aiConfig) ? "#EBF5F0" : "var(--paper-bg)",
                color: isCloudAiActive(aiConfig) ? "var(--audit-sage)" : "var(--ink-muted)",
                border: `1px solid ${isCloudAiActive(aiConfig) ? "#B7DEC9" : "var(--rule-hairline)"}`,
              }}
            >
              {isHostedAiActive(aiConfig)
                ? hostedCredits !== null
                  ? `Pro · ${hostedCredits}`
                  : "Pro"
                : isCloudAiActive(aiConfig)
                  ? aiConfig.model || aiConfig.provider
                  : "本地"}
            </span>
          </button>
          <button type="button" className="btn-editorial-ghost" onClick={() => setImportOpen(true)}>
            新建 / 导入
          </button>
          {deck && (
            <>
              <button type="button" className="btn-editorial-ghost" onClick={() => setPaletteOpen(true)}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: activeAccent,
                    display: "inline-block",
                  }}
                />
                <span>配色</span>
                <span className="font-mono" style={{ fontSize: 11, color: activeAccent, fontWeight: 700 }}>
                  {formatPaletteLabel(deck.meta.palette_id, palettes)}
                </span>
              </button>
              <button
                type="button"
                className="btn-editorial-primary"
                onClick={() => setExportOpen(true)}
                style={{ background: activeAccent, borderColor: activeAccent }}
              >
                导出 PPTX
              </button>
            </>
          )}
        </div>
      </header>

      {/* Dismissible Editorial Error Banner */}
      {errorMsg && (
        <div
          style={{
            padding: "8px 24px",
            background: "#FDF2F2",
            borderBottom: "1px solid #E5B4B4",
            color: "var(--nature-crimson)",
            fontSize: 12.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{errorMsg}</span>
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            style={{ border: "none", background: "transparent", color: "var(--nature-crimson)", cursor: "pointer", padding: 2, fontSize: 16, lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      )}

      {/* Main Content Area: 3-Pane Editorial Desk OR Curated Nature Journal Cover Landing */}
      {deck && currentSlide ? (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <DeckOutlinePanel
            slides={deck.slides}
            selectedSlideNo={currentSlide.slide_no}
            accentColor={activeAccent}
            onSelectSlide={setSelectedSlideNo}
            onAddContentSlide={handleAddContentSlide}
            onAddDividerSlide={handleAddDividerSlide}
            onDeleteSlide={handleDeleteSlide}
          />
          <SlideCanvasPreview
            deck={deck}
            slide={currentSlide}
            previewUrl={previewUrls[previewKey]}
            accentColor={activeAccent}
            activeLayers={activeLayers}
            onToggleLayer={handleToggleLayer}
            onUpdateSlide={handleUpdateSlide}
            onUpdateFonts={handleUpdateFonts}
            onUpdateCoverTemplate={handleUpdateCoverTemplate}
          />
          <FigureWorkbench
            deckId={deck.meta.deck_id}
            paletteId={deck.meta.palette_id}
            accentColor={activeAccent}
            slide={currentSlide}
            archetypes={archetypes}
            assetUrls={assetUrls}
            busy={busy}
            onRegenerate={handleRegenerateFigure}
            onRefineOrSwitch={handleRefineOrSwitch}
            onUploadReplacement={handleUploadReplacement}
          />
        </div>
      ) : (
        <main style={{ flex: 1, overflowY: "auto", padding: "40px 32px" }}>
          <div className="editorial-fade-in" style={{ maxWidth: 1180, margin: "0 auto" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(320px, 0.95fr) minmax(380px, 1.15fr)",
                gap: 44,
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div
                  className="kicker"
                  style={{ color: "var(--nature-crimson)", marginBottom: 10, letterSpacing: "0.08em" }}
                >
                  药物化学 · 科研汇报工作台
                </div>
                <h1
                  className="font-serif"
                  style={{
                    margin: "0 0 14px 0",
                    fontSize: "clamp(28px, 3vw, 38px)",
                    lineHeight: 1.24,
                    fontWeight: 700,
                    color: "var(--ink-primary)",
                  }}
                >
                  学术汇报与分子结构排版台
                </h1>

                <p
                  style={{
                    margin: "0 0 18px 0",
                    fontSize: 15,
                    lineHeight: 1.7,
                    color: "var(--ink-secondary)",
                    maxWidth: 460,
                  }}
                >
                  导入 Word 自动提炼汇报大纲，定制多种 2D / 3D 分子结构式并一键导出全原生可编辑 PPT。
                </p>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 22 }}>
                  {["封面", "目录", "章节过渡", "可视化排版", "尾页"].map((st, idx) => (
                    <span
                      key={st}
                      style={{
                        fontSize: 11.5,
                        fontWeight: 600,
                        padding: "3px 9px",
                        borderRadius: 2,
                        background: "var(--surface-pure)",
                        border: "1px solid #DCD8CF",
                        color: idx === 2 ? "var(--oxford-navy)" : "var(--ink-secondary)",
                      }}
                    >
                      {st}
                    </span>
                  ))}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 28 }}>
                  <button
                    type="button"
                    className="btn-editorial-primary"
                    style={{ padding: "11px 22px", fontSize: 13.5 }}
                    onClick={() => setImportOpen(true)}
                  >
                    新建 / 导入 Word
                  </button>
                  <button
                    type="button"
                    className="btn-editorial-ghost"
                    style={{ padding: "11px 20px", fontSize: 13.5, borderColor: "var(--ink-primary)" }}
                    disabled={busy}
                    onClick={handleLoadNirmatrelvirDemo}
                  >
                    {busy ? "载入中..." : "载入示例"}
                  </button>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    borderTop: "1px solid var(--rule-strong)",
                    paddingTop: 16,
                    gap: 16,
                  }}
                >
                  <div>
                    <div className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: "var(--nature-crimson)" }}>
                      01
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-primary)", marginTop: 3 }}>
                      Word 总结大纲
                    </div>
                  </div>
                  <div style={{ borderLeft: "1px solid var(--rule-hairline)", paddingLeft: 16 }}>
                    <div className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: "var(--oxford-navy)" }}>
                      02
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-primary)", marginTop: 3 }}>
                      2D / 3D 结构式
                    </div>
                  </div>
                  <div style={{ borderLeft: "1px solid var(--rule-hairline)", paddingLeft: 16 }}>
                    <div className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: "var(--audit-sage)" }}>
                      03
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-primary)", marginTop: 3 }}>
                      换肤导出 PPTX
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column" }}>
                <div
                  style={{
                    background: "var(--surface-pure)",
                    border: "1px solid #D6D2C8",
                    borderTop: "2px solid var(--ink-primary)",
                    borderRadius: 2,
                    padding: 12,
                    boxShadow: "0 18px 42px rgba(23, 23, 23, 0.08)",
                  }}
                >
                  <div
                    style={{
                      width: "100%",
                      aspectRatio: "16 / 9",
                      background: "#FFFFFF",
                      border: "1px solid var(--rule-hairline)",
                      overflow: "hidden",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {!plateLoadFailed ? (
                      <img
                        src={activePlate.src}
                        alt={activePlate.label}
                        onError={() => setPlateLoadFailed(true)}
                        style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
                      />
                    ) : (
                      <div style={{ textAlign: "center", padding: 24, color: "var(--ink-muted)", fontSize: 13 }}>
                        点击左侧“载入示例”查看预览
                      </div>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: 8,
                    marginTop: 10,
                    paddingTop: 8,
                  }}
                >
                  {CURATED_PLATES.map((pl, idx) => {
                    const isActive = idx === featuredPlateIdx;
                    return (
                      <button
                        key={pl.id}
                        type="button"
                        onClick={() => {
                          setFeaturedPlateIdx(idx);
                          setPlateLoadFailed(false);
                        }}
                        style={{
                          textAlign: "left",
                          padding: "6px 4px",
                          background: "transparent",
                          border: "none",
                          borderTop: isActive ? "2px solid var(--nature-crimson)" : "2px solid var(--rule-hairline)",
                          cursor: "pointer",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 12,
                            fontWeight: isActive ? 700 : 500,
                            color: isActive ? "var(--nature-crimson)" : "var(--ink-secondary)",
                          }}
                        >
                          {pl.label}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </main>
      )}

      <ImportModal
        open={importOpen}
        palettes={palettes}
        loading={busy}
        onClose={() => setImportOpen(false)}
        onPlanText={handlePlanText}
        onPlanFile={handlePlanFile}
      />

      <ModelSettingsModal
        open={modelSettingsOpen}
        initialConfig={aiConfig}
        onClose={() => setModelSettingsOpen(false)}
        onCreditsUpdated={setHostedCredits}
        onSaved={(cfg) => {
          saveAiConfig(cfg);
          setAiConfig(cfg);
          setModelSettingsOpen(false);
        }}
      />

      {deck && (
        <>
          <PaletteSelector
            open={paletteOpen}
            palettes={palettes}
            activePaletteId={deck.meta.palette_id}
            busy={busy}
            onClose={() => setPaletteOpen(false)}
            onApplyPalette={handleApplyPalette}
          />
          <ExportPanel
            open={exportOpen}
            deck={deck}
            buildResult={buildResult}
            syncedUrl={syncedUrl}
            busy={busy}
            onClose={() => setExportOpen(false)}
            onBuildPptx={handleBuildPptx}
            onSyncWord={handleSyncWord}
          />
        </>
      )}
    </div>
  );
}

export default App;
