import React, { useEffect, useState } from "react";
import { CheckCircle2, Cpu, Eye, EyeOff, KeyRound, ShieldCheck, Wifi, X, AlertCircle } from "lucide-react";
import { testAiConnection } from "../api/client";
import { AI_PRESETS, DEFAULT_AI_CONFIG } from "../types/aiConfig";
import type { AiConfig } from "../types/aiConfig";

interface ModelSettingsModalProps {
  open: boolean;
  initialConfig: AiConfig;
  onClose: () => void;
  onSaved: (cfg: AiConfig) => void;
}

export const ModelSettingsModal: React.FC<ModelSettingsModalProps> = ({
  open,
  initialConfig,
  onClose,
  onSaved,
}) => {
  const [draft, setDraft] = useState<AiConfig>(initialConfig);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    backend: string;
    model: string;
    latency_ms: number;
    message: string;
  } | null>(null);

  useEffect(() => {
    if (open) {
      setDraft(initialConfig);
      setTestResult(null);
      setShowKey(false);
    }
  }, [open, initialConfig]);

  if (!open) return null;

  const activePreset = AI_PRESETS.find((p) => p.id === draft.presetId) || AI_PRESETS[0];

  const handleSelectPreset = (presetId: string) => {
    const p = AI_PRESETS.find((item) => item.id === presetId);
    if (!p) return;
    setTestResult(null);
    setDraft((prev) => ({
      presetId: p.id,
      provider: p.provider,
      baseUrl: p.baseUrl,
      model: p.model,
      apiKey: p.provider === "local" ? "" : prev.provider === p.provider ? prev.apiKey : "",
    }));
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testAiConnection(draft);
      setTestResult(res);
    } catch (err) {
      setTestResult({
        ok: false,
        backend: draft.provider,
        model: draft.model || "unknown",
        latency_ms: 0,
        message: `测试请求异常：${String(err)}`,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onSaved({
      ...draft,
      apiKey: draft.apiKey.trim(),
      baseUrl: draft.baseUrl.trim(),
      model: draft.model.trim(),
    });
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(23, 23, 23, 0.48)",
        backdropFilter: "blur(4px)",
        zIndex: 60,
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
          maxWidth: 740,
          maxHeight: "92vh",
          overflowY: "auto",
          background: "var(--surface-pure)",
          borderRadius: 2,
          border: "1px solid #D6D2C8",
          borderTop: "3px solid var(--nature-crimson)",
          boxShadow: "0 24px 60px rgba(23, 23, 23, 0.22)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 24px",
            borderBottom: "1px solid var(--rule-strong)",
            background: "var(--surface-pure)",
          }}
        >
          <div>
            <div className="kicker" style={{ color: "var(--nature-crimson)", marginBottom: 3 }}>
              BYOK MODEL CONFIGURATION · AI ENGINE
            </div>
            <div className="font-serif" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-primary)" }}>
              AI 模型与本地绘图引擎设置
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", padding: 4 }}
            aria-label="关闭模型设置"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSave} style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Privacy Notice */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "11px 14px",
              background: "#F4F8F6",
              border: "1px solid #C8DED2",
              fontSize: 12.5,
              color: "#1B4332",
              lineHeight: 1.55,
            }}
          >
            <ShieldCheck size={17} style={{ color: "var(--audit-sage)", flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong>密钥零留存（BYOK）：</strong>你的 API Key 仅保存在当前浏览器的{" "}
              <code>localStorage</code>，仅在生成文献大纲时通过请求头临时转发给模型接口，服务端不落盘、不记录日志。
              即使不配置任何 Key，<strong>RDKit 结构式、3D 构象、Pd 机理图与原生 PPTX 编译</strong>仍可免费离线使用。
            </div>
          </div>

          {/* Preset Selector */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-secondary)", marginBottom: 8 }}>
              1. 选择 AI 服务来源
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(205px, 1fr))", gap: 10 }}>
              {AI_PRESETS.map((preset) => {
                const selected = draft.presetId === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handleSelectPreset(preset.id)}
                    style={{
                      textAlign: "left",
                      padding: "11px 12px",
                      background: selected ? "#FDF8F8" : "var(--surface-pure)",
                      border: selected ? "1.5px solid var(--nature-crimson)" : "1px solid var(--rule-hairline)",
                      borderRadius: 2,
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: selected ? "var(--nature-crimson)" : "var(--ink-primary)" }}>
                        {preset.name}
                      </span>
                      <span
                        className="font-mono"
                        style={{
                          fontSize: 10,
                          padding: "1px 6px",
                          background: selected ? "var(--nature-crimson)" : "var(--paper-bg)",
                          color: selected ? "#FFFFFF" : "var(--ink-muted)",
                          border: selected ? "none" : "1px solid var(--rule-hairline)",
                        }}
                      >
                        {preset.badge}
                      </span>
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-muted)", lineHeight: 1.4 }}>
                      {preset.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Credentials when cloud provider selected */}
          {draft.provider !== "local" ? (
            <div
              style={{
                padding: 16,
                background: "var(--paper-bg)",
                border: "1px solid var(--rule-hairline)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-primary)", display: "flex", alignItems: "center", gap: 6 }}>
                <KeyRound size={14} color="var(--nature-crimson)" />
                <span>2. 填写接口参数（{activePreset.name}）</span>
              </div>

              <label style={{ fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)" }}>API Key</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="editorial-input"
                    type={showKey ? "text" : "password"}
                    value={draft.apiKey}
                    onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                    placeholder={activePreset.keyPlaceholder || "粘贴你的 API Key"}
                    autoComplete="off"
                    style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                  />
                  <button
                    type="button"
                    className="btn-editorial-ghost"
                    onClick={() => setShowKey((v) => !v)}
                    title={showKey ? "隐藏 Key" : "显示 Key"}
                  >
                    {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </label>

              <div style={{ display: "grid", gridTemplateColumns: draft.provider === "openai" ? "1.3fr 1fr" : "1fr", gap: 12 }}>
                {draft.provider === "openai" && (
                  <label style={{ fontSize: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)" }}>Base URL</div>
                    <input
                      className="editorial-input"
                      value={draft.baseUrl}
                      onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                      placeholder="https://api.deepseek.com/v1"
                      style={{ fontFamily: "var(--font-mono)" }}
                    />
                  </label>
                )}
                <label style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 5, color: "var(--ink-secondary)" }}>模型名称</div>
                  <input
                    className="editorial-input"
                    value={draft.model}
                    onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                    placeholder={draft.provider === "gemini" ? "gemini-2.5-flash" : "deepseek-chat"}
                    style={{ fontFamily: "var(--font-mono)" }}
                  />
                </label>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: 14,
                background: "var(--paper-bg)",
                border: "1px solid var(--rule-hairline)",
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12.5,
                color: "var(--ink-secondary)",
              }}
            >
              <Cpu size={16} color="var(--oxford-navy)" />
              <span>
                当前为 <strong>本地确定性模式</strong>：直接根据 Markdown 段落与 SMILES 构建幻灯片与四风格结构式，零 API 开销。
              </span>
            </div>
          )}

          {/* Connectivity Test Row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn-editorial-ghost"
              disabled={testing || (draft.provider !== "local" && !draft.apiKey.trim())}
              onClick={handleTest}
            >
              <Wifi size={14} color="var(--oxford-navy)" />
              <span>{testing ? "正在测试连通性..." : "测试连通性"}</span>
            </button>

            {testResult && (
              <div
                style={{
                  flex: 1,
                  minWidth: 240,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  color: testResult.ok ? "var(--audit-sage)" : "var(--nature-crimson)",
                  fontWeight: 600,
                }}
              >
                {testResult.ok ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                <span>
                  {testResult.message}
                  {testResult.ok && testResult.latency_ms > 0 ? ` (${testResult.latency_ms} ms)` : ""}
                </span>
              </div>
            )}
          </div>

          {/* Footer Buttons */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              paddingTop: 14,
              borderTop: "1px solid var(--rule-hairline)",
            }}
          >
            <button
              type="button"
              className="btn-editorial-ghost"
              onClick={() => {
                setDraft(DEFAULT_AI_CONFIG);
                setTestResult(null);
              }}
            >
              恢复本地免费模式
            </button>

            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="btn-editorial-ghost" onClick={onClose}>
                取消
              </button>
              <button type="submit" className="btn-editorial-primary">
                保存配置
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
