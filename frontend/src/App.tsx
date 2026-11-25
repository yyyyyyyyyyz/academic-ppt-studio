import React, { useEffect, useState } from "react";
import {
  FilePlus2,
  Palette,
  Download,
  BookOpen,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Cpu,
  X,
} from "lucide-react";
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
    tab: "PLATE 01",
    label: "绛红目录",
    caption: "Fig. 1 | Archival Crimson Contents — Cohesive Nature Editorial Palette matching web workbench",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_01.png",
  },
  {
    id: "plate_02",
    tab: "PLATE 02",
    label: "双风格 2D",
    caption: "Fig. 2 | Penicillin G (Nature Burgundy) vs. (+)-Artemisinin (Ring-Shaded Pharmacophore) — 2D Vectors",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_02.png",
  },
  {
    id: "plate_03",
    tab: "PLATE 03",
    label: "3D 过氧桥",
    caption: "Fig. 3 | (+)-Artemisinin 3D CYLview Conformation & SMARTS-Anchored Endoperoxide Mechanism",
    src: "/api/artifacts/decks/nature_editorial_showcase/previews/slide_03.png",
  },
  {
    id: "plate_04",
    tab: "PLATE 04",
    label: "机理 + 线稿",
    caption: "Fig. 4 | Pd(0)/Pd(II) Buchwald–Hartwig Catalytic Cycle & Minimal-Mono Highlighted Imatinib",
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
      target_slide_count: 6,
      palette_id: "nejm",
      is_proposal: false,
      design_style: "defense_modular",
      cover_template: "hero_band_bottom_bar",
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

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--paper-bg)" }}>
      {/* Tier 1: Nature Journal 3px Crimson Masthead Rule */}
      <div style={{ height: 3, background: "var(--nature-crimson)", flexShrink: 0 }} />

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
              <span className="kicker" style={{ color: "var(--nature-crimson)", flexShrink: 0 }}>MANUSCRIPT</span>
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
          ) : (
            <span className="kicker" style={{ color: "var(--ink-muted)" }}>
              NATURE-STYLE EDITORIAL WORKBENCH · VOL. 5.0
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          {deck && (
            <button type="button" className="btn-editorial-ghost" onClick={() => setDeck(null)}>
              <ArrowLeft size={14} /> 返回封面
            </button>
          )}
          <button type="button" className="btn-editorial-ghost" onClick={() => setModelSettingsOpen(true)}>
            <Cpu size={14} color={isCloudAiActive(aiConfig) ? "var(--audit-sage)" : "var(--ink-muted)"} />
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
                  ? `官方 Pro · 剩 ${hostedCredits} 次`
                  : "官方 Pro"
                : isCloudAiActive(aiConfig)
                  ? aiConfig.model || aiConfig.provider
                  : "本地引擎"}
            </span>
          </button>
          <button type="button" className="btn-editorial-ghost" onClick={() => setImportOpen(true)}>
            <FilePlus2 size={14} /> 新建 / 导入手稿
          </button>
          {deck && (
            <>
              <button type="button" className="btn-editorial-ghost" onClick={() => setPaletteOpen(true)}>
                <Palette size={14} color="var(--oxford-navy)" />
                <span>期刊色板</span>
                <span className="font-mono" style={{ fontSize: 11, color: "var(--oxford-navy)" }}>
                  {deck.meta.palette_id}
                </span>
              </button>
              <button type="button" className="btn-editorial-primary" onClick={() => setExportOpen(true)}>
                <Download size={14} /> 编译 & 导出 .pptx
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
            style={{ border: "none", background: "transparent", color: "var(--nature-crimson)", cursor: "pointer", padding: 2 }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Content Area: 3-Pane Editorial Desk OR Curated Nature Journal Cover Landing */}
      {deck && currentSlide ? (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <DeckOutlinePanel
            slides={deck.slides}
            selectedSlideNo={currentSlide.slide_no}
            onSelectSlide={setSelectedSlideNo}
            onAddContentSlide={handleAddContentSlide}
            onDeleteSlide={handleDeleteSlide}
          />
          <SlideCanvasPreview
            deck={deck}
            slide={currentSlide}
            previewUrl={previewUrls[previewKey]}
            activeLayers={activeLayers}
            onToggleLayer={handleToggleLayer}
            onUpdateSlide={handleUpdateSlide}
            onUpdateFonts={handleUpdateFonts}
            onUpdateCoverTemplate={handleUpdateCoverTemplate}
          />
          <FigureWorkbench
            deckId={deck.meta.deck_id}
            paletteId={deck.meta.palette_id}
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
        <main style={{ flex: 1, overflowY: "auto", padding: "28px 32px 44px" }}>
          <div className="editorial-fade-in" style={{ maxWidth: 1240, margin: "0 auto" }}>
            {/* Top Swiss Issue Strip */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
                paddingBottom: 12,
                borderBottom: "1px solid var(--rule-hairline)",
                marginBottom: 34,
              }}
            >
              <span className="kicker" style={{ color: "var(--ink-secondary)" }}>
                ISSUE 05 · COMPUTATIONAL MEDICINAL CHEMISTRY
              </span>
              <span className="kicker" style={{ color: "var(--ink-muted)" }}>
                NATIVE EDITABLE PPTX ENGINE · 100% ZERO-RASTER VECTOR PIPELINE
              </span>
            </div>

            {/* Asymmetric 2-Column Editorial Cover Spread */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(340px, 1.05fr) minmax(380px, 1.05fr)",
                gap: 48,
                alignItems: "start",
              }}
            >
              {/* Left Feature Copy */}
              <div style={{ display: "flex", flexDirection: "column", paddingTop: 6 }}>
                <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 14 }}>
                  EDITORIAL WORKBENCH · SCIENTIFIC PRESENTATION
                </div>

                <h1
                  className="font-serif"
                  style={{
                    margin: "0 0 18px 0",
                    fontSize: "clamp(30px, 3vw, 40px)",
                    lineHeight: 1.24,
                    fontWeight: 700,
                    color: "var(--ink-primary)",
                    letterSpacing: "-0.015em",
                  }}
                >
                  将顶刊论文与实验数据，编排为发表级原生可编辑演示稿
                </h1>

                <p
                  style={{
                    margin: "0 0 28px 0",
                    fontSize: 15,
                    lineHeight: 1.78,
                    color: "var(--ink-secondary)",
                    maxWidth: 540,
                  }}
                >
                  专为药学、计算药化与材料科研打造的期刊级排版工作台。自动生成带手性楔形键的{" "}
                  <strong>ChemDraw 2D 矢量分子</strong>、<strong>PyMOL 级 3D 球棍构象</strong>与嵌入式 Excel
                  数据源柱状图——全页纯白留白、零栅格图拼接，支持在 PowerPoint 中任意取消组合编辑。
                </p>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 38 }}>
                  <button
                    type="button"
                    className="btn-editorial-primary"
                    style={{ padding: "12px 22px", fontSize: 13.5 }}
                    onClick={() => setImportOpen(true)}
                  >
                    <FilePlus2 size={16} /> 新建手稿 / 导入论文
                  </button>
                  <button
                    type="button"
                    className="btn-editorial-ghost"
                    style={{ padding: "12px 20px", fontSize: 13.5, borderColor: "var(--ink-primary)" }}
                    disabled={busy}
                    onClick={handleLoadNirmatrelvirDemo}
                  >
                    <BookOpen size={16} color="var(--nature-crimson)" />
                    <span>{busy ? "正在装配 4 页示范稿..." : "载入 Nature 经典药化示范工作台"}</span>
                    <ArrowRight size={14} />
                  </button>
                </div>

                {/* Bottom Swiss 3-Column Telemetry Strip */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    borderTop: "1px solid var(--rule-strong)",
                    paddingTop: 20,
                    gap: 18,
                  }}
                >
                  <div>
                    <div className="font-serif" style={{ fontSize: 28, fontWeight: 700, color: "var(--ink-primary)", lineHeight: 1.1 }}>
                      15
                    </div>
                    <div style={{ fontSize: 12, color: "var(--ink-secondary)", marginTop: 4, fontWeight: 600 }}>
                      顶刊实测科研色板
                    </div>
                    <div className="font-mono" style={{ fontSize: 10.5, color: "var(--ink-muted)", marginTop: 2 }}>
                      Lancet · Nature · Science
                    </div>
                  </div>
                  <div style={{ borderLeft: "1px solid var(--rule-hairline)", paddingLeft: 18 }}>
                    <div className="font-serif" style={{ fontSize: 28, fontWeight: 700, color: "var(--nature-crimson)", lineHeight: 1.1 }}>
                      100%
                    </div>
                    <div style={{ fontSize: 12, color: "var(--ink-secondary)", marginTop: 4, fontWeight: 600 }}>
                      原生矢量可编辑
                    </div>
                    <div className="font-mono" style={{ fontSize: 10.5, color: "var(--ink-muted)", marginTop: 2 }}>
                      GroupShape + OOXML Chart
                    </div>
                  </div>
                  <div style={{ borderLeft: "1px solid var(--rule-hairline)", paddingLeft: 18 }}>
                    <div className="font-serif" style={{ fontSize: 28, fontWeight: 700, color: "var(--oxford-navy)", lineHeight: 1.1 }}>
                      ≥14 pt
                    </div>
                    <div style={{ fontSize: 12, color: "var(--ink-secondary)", marginTop: 4, fontWeight: 600 }}>
                      双字体自动合规门禁
                    </div>
                    <div className="font-mono" style={{ fontSize: 10.5, color: "var(--ink-muted)", marginTop: 2 }}>
                      微软雅黑 + Arial XML
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Curated Printed Specimen Plate */}
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div
                  style={{
                    background: "var(--surface-pure)",
                    border: "1px solid #D6D2C8",
                    borderRadius: 2,
                    padding: 12,
                    boxShadow: "0 18px 42px rgba(23, 23, 23, 0.08)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      paddingBottom: 8,
                      marginBottom: 10,
                      borderBottom: "1px solid var(--rule-hairline)",
                    }}
                  >
                    <span className="kicker" style={{ color: "var(--ink-secondary)" }}>
                      CURATED SPECIMEN · {activePlate.tab}
                    </span>
                    <span
                      className="font-mono"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        fontSize: 10.5,
                        color: "var(--audit-sage)",
                        fontWeight: 600,
                      }}
                    >
                      <CheckCircle2 size={12} /> AUDIT PASSED · 0 VIOLATIONS
                    </span>
                  </div>

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
                        点击左侧“载入 Nature 经典药化示范工作台”即时生成高清科研图版。
                      </div>
                    )}
                  </div>
                </div>

                {/* Printed Figure Legend Caption + 4 Minimalist Plate Tabs */}
                <div
                  className="font-serif"
                  style={{
                    marginTop: 12,
                    fontSize: 12.5,
                    color: "var(--ink-secondary)",
                    lineHeight: 1.5,
                  }}
                >
                  {activePlate.caption}
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: 8,
                    marginTop: 12,
                    borderTop: "1px solid var(--rule-hairline)",
                    paddingTop: 10,
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
                          borderTop: isActive ? "2px solid var(--nature-crimson)" : "2px solid transparent",
                          cursor: "pointer",
                          transition: "border-color 140ms ease",
                        }}
                      >
                        <div
                          className="font-mono"
                          style={{
                            fontSize: 10,
                            fontWeight: 600,
                            color: isActive ? "var(--nature-crimson)" : "var(--ink-muted)",
                          }}
                        >
                          {pl.tab}
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            fontWeight: isActive ? 700 : 500,
                            color: isActive ? "var(--ink-primary)" : "var(--ink-secondary)",
                            marginTop: 2,
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
