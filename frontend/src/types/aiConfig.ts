export type AiProviderMode = "local" | "openai" | "gemini";

export interface AiConfig {
  presetId: string;
  provider: AiProviderMode;
  apiKey: string;
  baseUrl: string;
  model: string;
}

export interface AiPreset {
  id: string;
  name: string;
  badge: string;
  description: string;
  provider: AiProviderMode;
  baseUrl: string;
  model: string;
  keyPlaceholder: string;
}

export const AI_PRESETS: AiPreset[] = [
  {
    id: "local",
    name: "本地确定性引擎",
    badge: "免费离线",
    description: "RDKit 2D / 3D 球棍、Pd 催化循环与原生 PPTX 无需任何 API Key",
    provider: "local",
    baseUrl: "",
    model: "",
    keyPlaceholder: "",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    badge: "推荐",
    description: "性价比极高，擅长文献结构提取与学术大纲规划（¥0.01–0.05/篇）",
    provider: "openai",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    keyPlaceholder: "sk-...",
  },
  {
    id: "qwen",
    name: "通义千问 DashScope",
    badge: "国内直连",
    description: "阿里云百炼 OpenAI 兼容接口，中文学术术语理解稳定",
    provider: "openai",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    keyPlaceholder: "sk-...",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    badge: "多模态",
    description: "原生支持长文献分析与多模态结构解析",
    provider: "gemini",
    baseUrl: "",
    model: "gemini-2.5-flash",
    keyPlaceholder: "AIza...",
  },
  {
    id: "openai",
    name: "OpenAI / 兼容中转",
    badge: "通用接口",
    description: "支持任意 OpenAI Compatible Base URL 与自定义模型名",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    keyPlaceholder: "sk-...",
  },
];

export const DEFAULT_AI_CONFIG: AiConfig = {
  presetId: "local",
  provider: "local",
  apiKey: "",
  baseUrl: "",
  model: "",
};

const STORAGE_KEY = "academic_studio_byok_v1";

export function loadAiConfig(): AiConfig {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_AI_CONFIG;
    const parsed = JSON.parse(raw) as Partial<AiConfig>;
    const provider: AiProviderMode =
      parsed.provider === "openai" || parsed.provider === "gemini" || parsed.provider === "local"
        ? parsed.provider
        : "local";
    return {
      presetId: parsed.presetId || provider,
      provider,
      apiKey: typeof parsed.apiKey === "string" ? parsed.apiKey : "",
      baseUrl: typeof parsed.baseUrl === "string" ? parsed.baseUrl : "",
      model: typeof parsed.model === "string" ? parsed.model : "",
    };
  } catch {
    return DEFAULT_AI_CONFIG;
  }
}

export function saveAiConfig(cfg: AiConfig): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  } catch {
    // Ignore storage quota errors in private browsing modes
  }
}

export function isCloudAiActive(cfg: AiConfig): boolean {
  return cfg.provider !== "local" && cfg.apiKey.trim().length > 0;
}

export function buildAiHeaders(cfg?: AiConfig): Record<string, string> {
  const active = cfg || loadAiConfig();
  if (active.provider === "local" || !active.apiKey.trim()) {
    return {
      "X-LLM-Provider": "local",
      "X-Figure-Provider": "local",
    };
  }
  const headers: Record<string, string> = {
    "X-LLM-Provider": active.provider,
    "X-LLM-Api-Key": active.apiKey.trim(),
    "X-Figure-Provider": "local",
  };
  if (active.baseUrl.trim() && active.provider === "openai") {
    headers["X-LLM-Base-Url"] = active.baseUrl.trim();
  }
  if (active.model.trim()) {
    headers["X-LLM-Model"] = active.model.trim();
  }
  return headers;
}
