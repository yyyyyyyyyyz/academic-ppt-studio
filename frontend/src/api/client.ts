import type {
  ArchetypeId,
  ArchetypeInfo,
  AssetUrlBundle,
  AuditReport,
  CoverTemplateId,
  DeckSpec,
  DesignStyle,
  FigureSpec,
  PaletteInfo,
  ScenarioType,
} from "../types/deckSpec";

import { buildAiHeaders, loadAiConfig } from "../types/aiConfig";
import type { AiConfig } from "../types/aiConfig";

function extractApiError(status: number, text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (parsed && typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail.trim();
    }
  } catch {
    // plain text fallback
  }
  return `API ${status}: ${text}`;
}

export interface BillingStatus {
  hosted_ai_enabled: boolean;
  hosted_backend: string;
  model_label: string;
  purchase_note: string;
  plan_cost: number;
  require_code_for_hosted: boolean;
}

export interface RedeemCheckResult {
  valid: boolean;
  code: string;
  credits_left: number;
  credits_total: number;
  active: boolean;
  expired: boolean;
  label: string;
  expires_at: number | null;
  message: string;
}

export interface BillingReceipt {
  mode: string;
  code: string;
  cost: number;
  credits_left: number;
  credits_total: number;
}

export interface AdminCodeItem {
  code: string;
  label: string;
  credits_total: number;
  credits_left: number;
  active: boolean;
  expired: boolean;
  valid: boolean;
  created_at: number;
  expires_at: number | null;
  last_used_at: number | null;
}

async function jsonReq<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...buildAiHeaders(loadAiConfig()),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(extractApiError(res.status, text));
  }
  return res.json() as Promise<T>;
}

export async function fetchBillingStatus(): Promise<BillingStatus> {
  return jsonReq("/api/billing/status");
}

export async function checkAccessCode(code: string): Promise<RedeemCheckResult> {
  return jsonReq("/api/billing/redeem-check", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function adminGenerateCodes(
  adminSecret: string,
  payload: { count: number; credits: number; prefix?: string; label?: string; valid_days?: number | null },
): Promise<{ codes: AdminCodeItem[] }> {
  return jsonReq("/api/admin/codes/generate", {
    method: "POST",
    headers: { "X-Admin-Secret": adminSecret },
    body: JSON.stringify(payload),
  });
}

export async function adminListCodes(adminSecret: string): Promise<{ codes: AdminCodeItem[]; total: number }> {
  return jsonReq("/api/admin/codes", {
    headers: { "X-Admin-Secret": adminSecret },
  });
}

export async function adminSetCodeActive(
  adminSecret: string,
  code: string,
  active: boolean,
): Promise<{ ok: boolean; code: string; active: boolean }> {
  return jsonReq("/api/admin/codes/revoke", {
    method: "POST",
    headers: { "X-Admin-Secret": adminSecret },
    body: JSON.stringify({ code, active }),
  });
}

export async function testAiConnection(cfg: AiConfig): Promise<{
  ok: boolean;
  backend: string;
  model: string;
  latency_ms: number;
  message: string;
  credits_left?: number;
  credits_total?: number;
}> {
  return jsonReq("/api/llm/test", {
    method: "POST",
    headers: buildAiHeaders(cfg),
  });
}

export async function fetchPalettes(): Promise<PaletteInfo[]> {
  const data = await jsonReq<{ palettes: PaletteInfo[] }>("/api/palettes");
  return data.palettes;
}

export async function fetchArchetypes(): Promise<ArchetypeInfo[]> {
  const data = await jsonReq<{ archetypes: ArchetypeInfo[] }>("/api/archetypes");
  return data.archetypes;
}

export async function planDeck(payload: {
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
  design_style?: DesignStyle;
  cover_template?: CoverTemplateId;
}): Promise<{
  deck_spec: DeckSpec;
  artifact_urls: Record<string, string>;
  asset_urls: Record<string, AssetUrlBundle>;
  billing?: BillingReceipt | null;
}> {
  return jsonReq("/api/plan", { method: "POST", body: JSON.stringify(payload) });
}

export async function planDeckFromFile(formData: FormData): Promise<{
  deck_spec: DeckSpec;
  artifact_urls: Record<string, string>;
  asset_urls: Record<string, AssetUrlBundle>;
  billing?: BillingReceipt | null;
}> {
  const res = await fetch("/api/plan/upload", {
    method: "POST",
    headers: buildAiHeaders(loadAiConfig()),
    body: formData,
  });
  if (!res.ok) {
    throw new Error(extractApiError(res.status, await res.text()));
  }
  return res.json();
}

export async function regenerateFigure(payload: {
  deck_id: string;
  slide_no: number;
  palette_id: string;
  scenario: ScenarioType;
  is_proposal: boolean;
  figure_spec: FigureSpec;
  best_of_n?: number;
}): Promise<{ figure_spec: FigureSpec; asset_urls: Record<string, AssetUrlBundle> }> {
  return jsonReq("/api/figures/generate", { method: "POST", body: JSON.stringify(payload) });
}

export async function selectOrRefineFigure(payload: {
  deck_id: string;
  slide_no: number;
  palette_id: string;
  figure_spec: FigureSpec;
  asset_id?: string;
  selected_candidate_idx?: number;
  refinement_instruction?: string;
  archetype_override?: ArchetypeId;
  smiles_override?: string;
  fixed_bond_length_px?: number;
  highlight_atoms?: number[];
  origin_preset?: string;
  render_mode?: string;
  chem_style_override?: string;
}): Promise<{ figure_spec: FigureSpec; asset_urls: Record<string, AssetUrlBundle> }> {
  return jsonReq("/api/figures/select-or-refine", { method: "POST", body: JSON.stringify(payload) });
}

export async function uploadCustomFigure(
  file: File,
  deckId: string,
  slideNo: number,
  assetId: string,
): Promise<{ asset: Record<string, unknown>; png_url: string }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("deck_id", deckId);
  fd.append("slide_no", String(slideNo));
  fd.append("asset_id", assetId);
  const res = await fetch("/api/figures/upload", { method: "POST", body: fd });
  if (!res.ok) {
    throw new Error(`Upload figure failed: ${await res.text()}`);
  }
  return res.json();
}

export async function applyPaletteToDeck(
  deck_spec: DeckSpec,
  palette_id: string,
  rerender_figures = true,
): Promise<{
  deck_spec: DeckSpec;
  artifact_urls: Record<string, string>;
  asset_urls: Record<string, AssetUrlBundle>;
}> {
  return jsonReq("/api/palettes/apply", {
    method: "POST",
    body: JSON.stringify({ deck_spec, palette_id, rerender_figures }),
  });
}

export async function renderSlideLayersPreview(
  deck_spec: DeckSpec,
  slide_no: number,
  layers: string[],
): Promise<{ preview_url: string }> {
  return jsonReq("/api/preview/slide", {
    method: "POST",
    body: JSON.stringify({ deck_spec, slide_no, layers }),
  });
}

export async function buildPptx(deck_spec: DeckSpec): Promise<{
  pptx_url: string;
  deck_spec_url: string;
  preview_urls: string[];
  audit_report: AuditReport;
}> {
  return jsonReq("/api/build/pptx", {
    method: "POST",
    body: JSON.stringify({ deck_spec, run_qa_loop: true }),
  });
}

export async function syncWordToPptx(
  file: File,
  deckId: string,
): Promise<{ updated_slides: number[]; synced_pptx_url: string }> {
  const fd = new FormData();
  fd.append("docx_file", file);
  fd.append("deck_id", deckId);
  const res = await fetch("/api/sync/word", { method: "POST", body: fd });
  if (!res.ok) {
    throw new Error(`Word sync failed: ${await res.text()}`);
  }
  return res.json();
}
