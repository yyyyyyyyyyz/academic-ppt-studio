import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Cpu,
  Eye,
  EyeOff,
  KeyRound,
  Lock,
  PlusCircle,
  RefreshCw,
  ShieldCheck,
  Ticket,
  Wifi,
  X,
} from "lucide-react";
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
      setAdminError("请先输入管理员密钥（ADMIN_SECRET）。");
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
      setAdminError("请先输入管理员密钥（ADMIN_SECRET）。");
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
      setLastCreatedCodes(res.codes.map((c) => `${c.code}（${c.credits_left}次）`));
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
          maxWidth: 760,
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
              HOSTED PRO &amp; BYOK CONFIGURATION
            </div>
            <div className="font-serif" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-primary)" }}>
              AI 模型、官方兑换码与本地引擎设置
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
              <strong>三种接入方式自由切换：</strong>可用站长托管的 <strong>官方 Pro 学术模型（兑换码）</strong>、免费离线的{" "}
              <strong>本地确定性引擎</strong>，或填入个人 API Key（仅存本地 <code>localStorage</code>）。
            </div>
          </div>

          {/* Preset Selector */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-secondary)", marginBottom: 8 }}>
              1. 选择 AI 服务来源
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10 }}>
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

          {/* Section 2: Hosted / BYOK / Local */}
          {draft.provider === "hosted" ? (
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
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-primary)", display: "flex", alignItems: "center", gap: 6 }}>
                  <Ticket size={15} color="var(--nature-crimson)" />
                  <span>2. 输入官方 Pro 次数兑换码</span>
                </div>
                {billingStatus && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      background: billingStatus.hosted_ai_enabled ? "#EBF5F0" : "#FDF2F2",
                      color: billingStatus.hosted_ai_enabled ? "var(--audit-sage)" : "var(--nature-crimson)",
                      border: `1px solid ${billingStatus.hosted_ai_enabled ? "#B7DEC9" : "#F5C2C2"}`,
                    }}
                  >
                    {billingStatus.hosted_ai_enabled
                      ? `${billingStatus.model_label} · 每次消耗 ${billingStatus.plan_cost} 次`
                      : "服务端尚未配置官方模型 Key"}
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
                  placeholder="输入兑换码，如 PRO-8K2M-9X4Q"
                  autoComplete="off"
                  style={{ flex: 1, fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}
                />
                <button
                  type="button"
                  className="btn-editorial-ghost"
                  disabled={checkingCode || !draft.accessCode.trim()}
                  onClick={handleCheckCode}
                >
                  <RefreshCw size={13} />
                  <span>{checkingCode ? "查询中..." : "查询余额"}</span>
                </button>
              </div>

              {redeemResult && (
                <div
                  style={{
                    padding: "9px 12px",
                    background: redeemResult.valid ? "#EBF5F0" : "#FDF2F2",
                    border: `1px solid ${redeemResult.valid ? "#B7DEC9" : "#F5C2C2"}`,
                    fontSize: 12,
                    color: redeemResult.valid ? "#1B4332" : "var(--nature-crimson)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                  }}
                >
                  <span>{redeemResult.message}</span>
                  {redeemResult.label && <span className="font-mono">标签：{redeemResult.label}</span>}
                </div>
              )}

              {billingStatus?.purchase_note && (
                <div style={{ fontSize: 12, color: "var(--ink-muted)", lineHeight: 1.5 }}>
                  获取说明：{billingStatus.purchase_note}
                </div>
              )}
            </div>
          ) : draft.provider !== "local" ? (
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
                当前为 <strong>本地确定性模式</strong>：直接根据 Word/Markdown 段落与 SMILES 构建幻灯片与四风格结构式，零 API 开销。
              </span>
            </div>
          )}

          {/* Connectivity Test Row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <button type="button" className="btn-editorial-ghost" disabled={testDisabled} onClick={handleTest}>
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

          {/* Collapsible Owner Admin Panel */}
          <div style={{ borderTop: "1px dashed var(--rule-hairline)", paddingTop: 12 }}>
            <button
              type="button"
              onClick={() => setAdminOpen((v) => !v)}
              style={{
                background: "transparent",
                border: "none",
                padding: 0,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                color: "var(--ink-muted)",
              }}
            >
              <Lock size={13} />
              <span>站长发码管理（仅管理员使用）</span>
              {adminOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {adminOpen && (
              <div
                style={{
                  marginTop: 12,
                  padding: 14,
                  background: "#FAF8F5",
                  border: "1px solid var(--rule-hairline)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    className="editorial-input"
                    type="password"
                    value={adminSecret}
                    onChange={(e) => setAdminSecret(e.target.value)}
                    placeholder="输入服务器 ADMIN_SECRET"
                    style={{ flex: 1, minWidth: 200, fontFamily: "var(--font-mono)" }}
                  />
                  <button type="button" className="btn-editorial-ghost" disabled={adminBusy} onClick={handleAdminLoad}>
                    <RefreshCw size={13} />
                    <span>加载卡密列表</span>
                  </button>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
                  <label style={{ fontSize: 11.5 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 4 }}>生成数量</div>
                    <input
                      className="editorial-input"
                      type="number"
                      min={1}
                      max={100}
                      value={newCount}
                      onChange={(e) => setNewCount(Number(e.target.value))}
                    />
                  </label>
                  <label style={{ fontSize: 11.5 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 4 }}>每码可用次数</div>
                    <input
                      className="editorial-input"
                      type="number"
                      min={1}
                      max={10000}
                      value={newCredits}
                      onChange={(e) => setNewCredits(Number(e.target.value))}
                    />
                  </label>
                  <label style={{ fontSize: 11.5 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 4 }}>套餐标签</div>
                    <input
                      className="editorial-input"
                      value={newLabel}
                      onChange={(e) => setNewLabel(e.target.value)}
                      placeholder="如 体验卡5次"
                    />
                  </label>
                  <label style={{ fontSize: 11.5 }}>
                    <div style={{ color: "var(--ink-muted)", marginBottom: 4 }}>有效天数（留空永久）</div>
                    <input
                      className="editorial-input"
                      type="number"
                      min={1}
                      value={newValidDays}
                      onChange={(e) => setNewValidDays(e.target.value)}
                      placeholder="30"
                    />
                  </label>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <button type="button" className="btn-editorial-primary" disabled={adminBusy} onClick={handleAdminGenerate}>
                    <PlusCircle size={13} />
                    <span>批量生成兑换码</span>
                  </button>
                  {lastCreatedCodes.length > 0 && (
                    <button
                      type="button"
                      className="btn-editorial-ghost"
                      onClick={() => {
                        navigator.clipboard?.writeText(lastCreatedCodes.join("\n"));
                        setCopiedFlag(true);
                      }}
                    >
                      <Copy size={13} />
                      <span>{copiedFlag ? "已复制" : `复制新生成的 ${lastCreatedCodes.length} 个卡密`}</span>
                    </button>
                  )}
                </div>

                {adminError && (
                  <div style={{ fontSize: 12, color: "var(--nature-crimson)", fontWeight: 600 }}>{adminError}</div>
                )}

                {lastCreatedCodes.length > 0 && (
                  <div
                    className="font-mono"
                    style={{
                      padding: 10,
                      background: "var(--surface-pure)",
                      border: "1px solid var(--rule-hairline)",
                      fontSize: 11.5,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {lastCreatedCodes.join("\n")}
                  </div>
                )}

                {adminCodes.length > 0 && (
                  <div style={{ maxHeight: 190, overflowY: "auto", border: "1px solid var(--rule-hairline)", background: "#FFF" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
                      <thead>
                        <tr style={{ background: "var(--paper-bg)", textAlign: "left" }}>
                          <th style={{ padding: "6px 8px" }}>兑换码</th>
                          <th style={{ padding: "6px 8px" }}>标签</th>
                          <th style={{ padding: "6px 8px" }}>余/总次</th>
                          <th style={{ padding: "6px 8px" }}>状态</th>
                          <th style={{ padding: "6px 8px" }}>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminCodes.map((row) => (
                          <tr key={row.code} style={{ borderTop: "1px solid var(--rule-hairline)" }}>
                            <td className="font-mono" style={{ padding: "6px 8px", fontWeight: 600 }}>
                              {row.code}
                            </td>
                            <td style={{ padding: "6px 8px", color: "var(--ink-muted)" }}>{row.label || "—"}</td>
                            <td className="font-mono" style={{ padding: "6px 8px" }}>
                              {row.credits_left} / {row.credits_total}
                            </td>
                            <td style={{ padding: "6px 8px", color: row.valid ? "var(--audit-sage)" : "var(--nature-crimson)" }}>
                              {!row.active ? "已停用" : row.expired ? "已过期" : row.credits_left <= 0 ? "已用尽" : "有效"}
                            </td>
                            <td style={{ padding: "6px 8px" }}>
                              <button
                                type="button"
                                className="btn-editorial-ghost"
                                style={{ padding: "2px 8px", fontSize: 11 }}
                                onClick={() => handleToggleCodeActive(row.code, !row.active)}
                              >
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
                setRedeemResult(null);
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
