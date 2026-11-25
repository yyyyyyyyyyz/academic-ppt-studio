import React, { useEffect, useState } from "react";
import {
  adminGenerateCodes,
  adminListCodes,
  adminSetCodeActive,
  checkAccessCode,
  fetchBillingStatus,
  testAiConnection,
} from "../api/client";
import type { AdminCodeItem, BillingStatus, RedeemCheckResult } from "../api/client";
import { AI_PRESETS, DEFAULT_AI_CONFIG } from "../types/aiConfig";
import type { AiConfig } from "../types/aiConfig";

interface ModelSettingsModalProps {
  open: boolean;
  initialConfig: AiConfig;
  onClose: () => void;
  onSaved: (cfg: AiConfig) => void;
  onCreditsUpdated?: (credits: number | null) => void;
}

export const ModelSettingsModal: React.FC<ModelSettingsModalProps> = ({
  open,
  initialConfig,
  onClose,
  onSaved,
  onCreditsUpdated,
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

  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [checkingCode, setCheckingCode] = useState(false);
  const [redeemResult, setRedeemResult] = useState<RedeemCheckResult | null>(null);

  const [adminOpen, setAdminOpen] = useState(false);
  const [adminSecret, setAdminSecret] = useState("");
  const [adminBusy, setAdminBusy] = useState(false);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminCodes, setAdminCodes] = useState<AdminCodeItem[]>([]);
  const [newCount, setNewCount] = useState(5);
  const [newCredits, setNewCredits] = useState(5);
  const [newLabel, setNewLabel] = useState("");
  const [newValidDays, setNewValidDays] = useState("");
  const [lastCreatedCodes, setLastCreatedCodes] = useState<string[]>([]);
  const [copiedFlag, setCopiedFlag] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft(initialConfig);
      setTestResult(null);
      setRedeemResult(null);
      setShowKey(false);
      fetchBillingStatus()
        .then((st) => setBillingStatus(st))
        .catch(() => setBillingStatus(null));
      if (initialConfig.provider === "hosted" && initialConfig.accessCode.trim()) {
        checkAccessCode(initialConfig.accessCode.trim())
          .then((res) => {
            setRedeemResult(res);
            onCreditsUpdated?.(res.valid ? res.credits_left : 0);
          })
          .catch(() => {});
      }
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
      accessCode: prev.accessCode,
      apiKey: p.provider === "local" || p.provider === "hosted" ? prev.apiKey : prev.provider === p.provider ? prev.apiKey : "",
    }));
  };

  const handleCheckCode = async () => {
    const code = draft.accessCode.trim();
    if (!code) return;
    setCheckingCode(true);
    setRedeemResult(null);
    try {
      const res = await checkAccessCode(code);
      setRedeemResult(res);
      onCreditsUpdated?.(res.valid ? res.credits_left : 0);
    } catch (err) {
      setRedeemResult({
        valid: false,
        code,
        credits_left: 0,
        credits_total: 0,
        active: false,
        expired: false,
        label: "",
        expires_at: null,
        message: String(err),
      });
    } finally {
      setCheckingCode(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testAiConnection(draft);
      setTestResult(res);
      if (typeof res.credits_left === "number") {
        onCreditsUpdated?.(res.credits_left);
      }
    } catch (err) {
      setTestResult({
        ok: false,
        backend: draft.provider,
        model: draft.model || "unknown",
        latency_ms: 0,
        message: String(err),
      });
    } finally {
      setTesting(false);
    }
  };

  const handleAdminLoad = async () => {
    if (!adminSecret.trim()) {
      setAdminError("请输入管理员密钥");
      return;
    }
    setAdminBusy(true);
    setAdminError(null);
    try {
      const res = await adminListCodes(adminSecret.trim());
      setAdminCodes(res.codes);
    } catch (err) {
      setAdminError(String(err));
    } finally {
      setAdminBusy(false);
    }
  };

  const handleAdminGenerate = async () => {
    if (!adminSecret.trim()) {
      setAdminError("请输入管理员密钥");
      return;
    }
    setAdminBusy(true);
    setAdminError(null);
    setCopiedFlag(false);
    try {
      const validDaysNum = newValidDays.trim() ? Number(newValidDays.trim()) : null;
      const res = await adminGenerateCodes(adminSecret.trim(), {
        count: Math.max(1, Math.min(100, newCount || 1)),
        credits: Math.max(1, Math.min(10000, newCredits || 1)),
        prefix: "PRO",
        label: newLabel.trim(),
        valid_days: validDaysNum && validDaysNum > 0 ? validDaysNum : null,
      });
      setLastCreatedCodes(res.codes.map((c) => `${c.code} (${c.credits_left}次)`));
      const listed = await adminListCodes(adminSecret.trim());
      setAdminCodes(listed.codes);
    } catch (err) {
      setAdminError(String(err));
    } finally {
      setAdminBusy(false);
    }
  };

  const handleToggleCodeActive = async (code: string, nextActive: boolean) => {
    if (!adminSecret.trim()) return;
    setAdminBusy(true);
    setAdminError(null);
    try {
      await adminSetCodeActive(adminSecret.trim(), code, nextActive);
      const listed = await adminListCodes(adminSecret.trim());
      setAdminCodes(listed.codes);
    } catch (err) {
      setAdminError(String(err));
    } finally {
      setAdminBusy(false);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onSaved({
      ...draft,
      apiKey: draft.apiKey.trim(),
      accessCode: draft.accessCode.trim().toUpperCase(),
      baseUrl: draft.baseUrl.trim(),
      model: draft.model.trim(),
    });
  };

  const testDisabled =
    testing ||
    (draft.provider === "hosted" && !draft.accessCode.trim()) ||
    (draft.provider !== "local" && draft.provider !== "hosted" && !draft.apiKey.trim());

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
          maxWidth: 660,
          maxHeight: "90vh",
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
            padding: "13px 20px",
            borderBottom: "1px solid var(--rule-strong)",
          }}
        >
          <div className="font-serif" style={{ fontSize: 17.5, fontWeight: 700, color: "var(--ink-primary)" }}>
            AI 模型设置
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-secondary)", fontSize: 20, lineHeight: 1, padding: 4 }}
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSave} style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Compact 3-Column Service Selector */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {AI_PRESETS.map((preset) => {
              const selected = draft.presetId === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleSelectPreset(preset.id)}
                  style={{
                    textAlign: "left",
                    padding: "9px 11px",
                    background: selected ? "#FDF8F8" : "var(--surface-pure)",
                    border: selected ? "1.5px solid var(--nature-crimson)" : "1px solid var(--rule-hairline)",
                    borderRadius: 2,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: selected ? "var(--nature-crimson)" : "var(--ink-primary)" }}>
                      {preset.name}
                    </span>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: 9.5,
                        padding: "1px 5px",
                        background: selected ? "var(--nature-crimson)" : "var(--paper-bg)",
                        color: selected ? "#FFFFFF" : "var(--ink-muted)",
                      }}
                    >
                      {preset.badge}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 3 }}>{preset.description}</div>
                </button>
              );
            })}
          </div>

          {/* Credentials Box */}
          {draft.provider === "hosted" ? (
            <div
              style={{
                padding: 13,
                background: "var(--paper-bg)",
                border: "1px solid var(--rule-hairline)",
                display: "flex",
                flexDirection: "column",
                gap: 9,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-primary)" }}>兑换码</span>
                {billingStatus && (
                  <span className="font-mono" style={{ fontSize: 11, color: billingStatus.hosted_ai_enabled ? "var(--audit-sage)" : "var(--nature-crimson)" }}>
                    {billingStatus.hosted_ai_enabled ? billingStatus.model_label : "未配置服务"}
                  </span>
                )}
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="editorial-input"
                  value={draft.accessCode}
                  onChange={(e) => {
                    setDraft({ ...draft, accessCode: e.target.value.toUpperCase() });
                    setRedeemResult(null);
                  }}
                  placeholder="PRO-XXXX-XXXX"
                  autoComplete="off"
                  style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                />
                <button
                  type="button"
                  className="btn-editorial-ghost"
                  disabled={checkingCode || !draft.accessCode.trim()}
                  onClick={handleCheckCode}
                >
                  {checkingCode ? "查询中..." : "查余额"}
                </button>
              </div>

              {redeemResult && (
                <div style={{ fontSize: 12, color: redeemResult.valid ? "var(--audit-sage)" : "var(--nature-crimson)" }}>
                  {redeemResult.message}
                </div>
              )}
            </div>
          ) : draft.provider !== "local" ? (
            <div
              style={{
                padding: 13,
                background: "var(--paper-bg)",
                border: "1px solid var(--rule-hairline)",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <label style={{ fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>API Key ({activePreset.name})</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    className="editorial-input"
                    type={showKey ? "text" : "password"}
                    value={draft.apiKey}
                    onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                    placeholder={activePreset.keyPlaceholder || "API Key"}
                    autoComplete="off"
                    style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                  />
                  <button type="button" className="btn-editorial-ghost" onClick={() => setShowKey((v) => !v)} style={{ fontSize: 11.5 }}>
                    {showKey ? "隐藏" : "显示"}
                  </button>
                </div>
              </label>

              <div style={{ display: "grid", gridTemplateColumns: draft.provider === "openai" ? "1.3fr 1fr" : "1fr", gap: 10 }}>
                {draft.provider === "openai" && (
                  <label style={{ fontSize: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>Base URL</div>
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
                  <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--ink-secondary)" }}>模型</div>
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
            <div style={{ padding: "10px 12px", background: "var(--paper-bg)", border: "1px solid var(--rule-hairline)", fontSize: 12, color: "var(--ink-secondary)" }}>
              离线解析 Word、表格与 2D / 3D 分子结构，无需 API Key。
            </div>
          )}

          {/* Connection Test Row */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button type="button" className="btn-editorial-ghost" disabled={testDisabled} onClick={handleTest} style={{ fontSize: 12 }}>
              {testing ? "测试中..." : "测试连接"}
            </button>
            {testResult && (
              <span style={{ fontSize: 12, color: testResult.ok ? "var(--audit-sage)" : "var(--nature-crimson)", fontWeight: 600 }}>
                {testResult.message}
                {testResult.ok && testResult.latency_ms > 0 ? ` (${testResult.latency_ms} ms)` : ""}
              </span>
            )}
          </div>

          {/* Collapsible Admin Panel */}
          <div style={{ borderTop: "1px dashed var(--rule-hairline)", paddingTop: 10 }}>
            <button
              type="button"
              onClick={() => setAdminOpen((v) => !v)}
              style={{
                background: "transparent",
                border: "none",
                padding: 0,
                cursor: "pointer",
                fontSize: 11.5,
                fontWeight: 600,
                color: "var(--ink-muted)",
              }}
            >
              {adminOpen ? "▾ 收起站长发码" : "▸ 站长发码"}
            </button>

            {adminOpen && (
              <div style={{ marginTop: 10, padding: 12, background: "#FAF8F5", border: "1px solid var(--rule-hairline)", display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="editorial-input"
                    type="password"
                    value={adminSecret}
                    onChange={(e) => setAdminSecret(e.target.value)}
                    placeholder="ADMIN_SECRET"
                    style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                  />
                  <button type="button" className="btn-editorial-ghost" disabled={adminBusy} onClick={handleAdminLoad} style={{ fontSize: 12 }}>
                    列表
                  </button>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
                  <label style={{ fontSize: 11 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 3 }}>数量</div>
                    <input className="editorial-input" type="number" min={1} max={100} value={newCount} onChange={(e) => setNewCount(Number(e.target.value))} />
                  </label>
                  <label style={{ fontSize: 11 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 3 }}>次数</div>
                    <input className="editorial-input" type="number" min={1} max={10000} value={newCredits} onChange={(e) => setNewCredits(Number(e.target.value))} />
                  </label>
                  <label style={{ fontSize: 11 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 3 }}>标签</div>
                    <input className="editorial-input" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="5次卡" />
                  </label>
                  <label style={{ fontSize: 11 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 3 }}>天数</div>
                    <input className="editorial-input" type="number" min={1} value={newValidDays} onChange={(e) => setNewValidDays(e.target.value)} placeholder="30" />
                  </label>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button type="button" className="btn-editorial-primary" disabled={adminBusy} onClick={handleAdminGenerate} style={{ fontSize: 12 }}>
                    生成兑换码
                  </button>
                  {lastCreatedCodes.length > 0 && (
                    <button
                      type="button"
                      className="btn-editorial-ghost"
                      style={{ fontSize: 12 }}
                      onClick={() => {
                        navigator.clipboard?.writeText(lastCreatedCodes.join("\n"));
                        setCopiedFlag(true);
                      }}
                    >
                      {copiedFlag ? "已复制" : "复制"}
                    </button>
                  )}
                </div>

                {adminError && <div style={{ fontSize: 12, color: "var(--nature-crimson)" }}>{adminError}</div>}

                {lastCreatedCodes.length > 0 && (
                  <div className="font-mono" style={{ padding: 8, background: "#FFF", border: "1px solid var(--rule-hairline)", fontSize: 11, whiteSpace: "pre-wrap" }}>
                    {lastCreatedCodes.join("\n")}
                  </div>
                )}

                {adminCodes.length > 0 && (
                  <div style={{ maxHeight: 160, overflowY: "auto", border: "1px solid var(--rule-hairline)", background: "#FFF" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                      <thead>
                        <tr style={{ background: "var(--paper-bg)", textAlign: "left" }}>
                          <th style={{ padding: "5px 8px" }}>兑换码</th>
                          <th style={{ padding: "5px 8px" }}>余/总</th>
                          <th style={{ padding: "5px 8px" }}>状态</th>
                          <th style={{ padding: "5px 8px" }}>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminCodes.map((row) => (
                          <tr key={row.code} style={{ borderTop: "1px solid var(--rule-hairline)" }}>
                            <td className="font-mono" style={{ padding: "5px 8px" }}>{row.code}</td>
                            <td className="font-mono" style={{ padding: "5px 8px" }}>{row.credits_left}/{row.credits_total}</td>
                            <td style={{ padding: "5px 8px" }}>{!row.active ? "停用" : row.expired ? "过期" : row.credits_left <= 0 ? "用尽" : "有效"}</td>
                            <td style={{ padding: "5px 8px" }}>
                              <button type="button" className="btn-editorial-ghost" style={{ padding: "2px 6px", fontSize: 10.5 }} onClick={() => handleToggleCodeActive(row.code, !row.active)}>
                                {row.active ? "停用" : "启用"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 10, borderTop: "1px solid var(--rule-hairline)" }}>
            <button
              type="button"
              className="btn-editorial-ghost"
              style={{ fontSize: 12 }}
              onClick={() => {
                setDraft(DEFAULT_AI_CONFIG);
                setTestResult(null);
                setRedeemResult(null);
              }}
            >
              恢复本地
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn-editorial-ghost" onClick={onClose}>
                取消
              </button>
              <button type="submit" className="btn-editorial-primary">
                保存
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
