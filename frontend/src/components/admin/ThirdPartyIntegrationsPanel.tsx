"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ConnectionStatus,
  fetchIntegrations,
  IntegrationItem,
  IntegrationProvider,
  testIntegrationApi,
  updateIntegrationApi,
} from "@/lib/api/adminIntegrations";

const STATUS_META: Record<ConnectionStatus, { label: string; badgeClass: string; dotClass: string }> = {
  connected: {
    label: "Connected",
    badgeClass: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    dotClass: "bg-emerald-500",
  },
  failed: {
    label: "Connection Failed",
    badgeClass: "bg-red-50 text-red-700 ring-red-600/20",
    dotClass: "bg-red-500",
  },
  unconfigured: {
    label: "Not Configured",
    badgeClass: "bg-slate-100 text-slate-600 ring-slate-500/20",
    dotClass: "bg-slate-400",
  },
};

const PROVIDER_ACCENT: Record<IntegrationProvider, { tag: string; tagBg: string }> = {
  github: { tag: "GH", tagBg: "bg-slate-900 text-white" },
  jira: { tag: "JR", tagBg: "bg-blue-600 text-white" },
  slack: { tag: "SL", tagBg: "bg-fuchsia-700 text-white" },
};

interface FormDraft {
  is_enabled: boolean;
  config: Record<string, any>;
  secret: string;
  webhook_secret: string;
}

export default function ThirdPartyIntegrationsPanel() {
  const [items, setItems] = useState<IntegrationItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, FormDraft>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<IntegrationProvider | null>(null);
  const [testingProvider, setTestingProvider] = useState<IntegrationProvider | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const notify = (type: "success" | "error", text: string) => {
    setToast({ type, text });
    setTimeout(() => setToast(null), 4500);
  };

  const loadIntegrations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchIntegrations();
      setItems(data);
      const initialDrafts: Record<string, FormDraft> = {};
      data.forEach((item) => {
        initialDrafts[item.provider] = {
          is_enabled: item.is_enabled,
          config: { ...item.config },
          secret: "",
          webhook_secret: "",
        };
      });
      setDrafts(initialDrafts);
    } catch (err: unknown) {
      notify("error", err instanceof Error ? err.message : "Không thể tải cấu hình tích hợp.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  const updateDraftField = (provider: IntegrationProvider, key: string, value: any) => {
    setDrafts((prev) => ({
      ...prev,
      [provider]: {
        ...prev[provider],
        config: {
          ...prev[provider]?.config,
          [key]: value,
        },
      },
    }));
  };

  const handleSave = async (provider: IntegrationProvider) => {
    const draft = drafts[provider];
    if (!draft) return;
    setSavingProvider(provider);
    try {
      const updated = await updateIntegrationApi(provider, {
        is_enabled: draft.is_enabled,
        config: draft.config,
        secret: draft.secret || undefined,
        webhook_secret: draft.webhook_secret || undefined,
      });
      setItems((prev) => prev.map((it) => (it.provider === provider ? updated : it)));
      setDrafts((prev) => ({
        ...prev,
        [provider]: {
          is_enabled: updated.is_enabled,
          config: { ...updated.config },
          secret: "",
          webhook_secret: "",
        },
      }));
      notify("success", `Đã lưu cấu hình ${updated.display_name}.`);
    } catch (err: unknown) {
      notify("error", err instanceof Error ? err.message : "Lỗi khi lưu cấu hình.");
    } finally {
      setSavingProvider(null);
    }
  };

  const handleTest = async (provider: IntegrationProvider) => {
    const draft = drafts[provider];
    if (!draft) return;
    setTestingProvider(provider);
    try {
      const res = await testIntegrationApi(provider, {
        config: draft.config,
        secret: draft.secret || undefined,
      });
      setItems((prev) =>
        prev.map((it) =>
          it.provider === provider
            ? {
                ...it,
                connection_status: res.connection_status,
                status_message: res.message,
                last_tested_at: res.tested_at,
              }
            : it
        )
      );
      notify(res.success ? "success" : "error", res.message);
    } catch (err: unknown) {
      notify("error", err instanceof Error ? err.message : "Không thể kiểm tra kết nối.");
    } finally {
      setTestingProvider(null);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
        Đang tải cấu hình kết nối dịch vụ bên thứ ba...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && (
        <div
          className={`fixed bottom-5 right-5 z-50 max-w-md rounded-lg border px-4 py-3 text-sm font-medium shadow-lg ${
            toast.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {toast.text}
        </div>
      )}

      {items.map((item) => {
        const draft = drafts[item.provider] || {
          is_enabled: item.is_enabled,
          config: item.config,
          secret: "",
          webhook_secret: "",
        };
        const statusInfo = STATUS_META[item.connection_status];
        const accent = PROVIDER_ACCENT[item.provider];
        const isSaving = savingProvider === item.provider;
        const isTesting = testingProvider === item.provider;

        return (
          <div
            key={item.provider}
            className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="flex flex-col justify-between gap-4 border-b border-slate-100 bg-slate-50/70 px-6 py-4 sm:flex-row sm:items-center">
              <div className="flex items-start gap-3.5">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-bold tracking-wider ${accent.tagBg}`}
                >
                  {accent.tag}
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h3 className="text-base font-bold text-slate-900">{item.display_name}</h3>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusInfo.badgeClass}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${statusInfo.dotClass}`} />
                      {statusInfo.label}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{item.description}</p>
                </div>
              </div>

              <label className="inline-flex cursor-pointer items-center gap-2.5 self-start sm:self-center">
                <input
                  type="checkbox"
                  checked={draft.is_enabled}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [item.provider]: { ...draft, is_enabled: e.target.checked },
                    }))
                  }
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm font-medium text-slate-700">
                  {draft.is_enabled ? "Đang bật" : "Đang tắt"}
                </span>
              </label>
            </div>

            <div className="space-y-4 p-6">
              {item.provider === "github" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      GitHub Organization / Owner
                    </label>
                    <input
                      type="text"
                      value={draft.config.owner_or_org || ""}
                      onChange={(e) => updateDraftField("github", "owner_or_org", e.target.value)}
                      placeholder="VD: cnpm-groupgaugau1-2026"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Nhánh mặc định (Default Branch)
                    </label>
                    <input
                      type="text"
                      value={draft.config.default_branch || "main"}
                      onChange={(e) => updateDraftField("github", "default_branch", e.target.value)}
                      placeholder="main"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Personal Access Token / App Token{" "}
                      {item.has_secret && (
                        <span className="font-mono text-emerald-700">({item.masked_secret})</span>
                      )}
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        type={showSecrets["github"] ? "text" : "password"}
                        value={draft.secret}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            github: { ...draft, secret: e.target.value },
                          }))
                        }
                        placeholder={item.has_secret ? "Nhập token mới nếu muốn thay đổi" : "ghp_xxxxxxxxxxxx"}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowSecrets((p) => ({ ...p, github: !p["github"] }))
                        }
                        className="rounded-lg border border-slate-300 px-3 text-xs text-slate-600 hover:bg-slate-50"
                      >
                        {showSecrets["github"] ? "Ẩn" : "Hiện"}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Webhook Secret{" "}
                      {item.has_webhook_secret && (
                        <span className="font-mono text-emerald-700">
                          ({item.masked_webhook_secret})
                        </span>
                      )}
                    </label>
                    <input
                      type="password"
                      value={draft.webhook_secret}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          github: { ...draft, webhook_secret: e.target.value },
                        }))
                      }
                      placeholder={item.has_webhook_secret ? "Đã lưu (nhập mới để ghi đè)" : "whsec_..."}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-6 md:col-span-2">
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.auto_sync_on_pr)}
                        onChange={(e) =>
                          updateDraftField("github", "auto_sync_on_pr", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Tự động phân tích AST & cập nhật tài liệu khi mở Pull Request
                    </label>
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.enforce_ci_gate)}
                        onChange={(e) =>
                          updateDraftField("github", "enforce_ci_gate", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Bật CI/CD Merge Policy Gate (chặn merge khi có Drift chưa duyệt)
                    </label>
                  </div>
                </div>
              )}

              {item.provider === "jira" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Jira Cloud Base URL
                    </label>
                    <input
                      type="url"
                      value={draft.config.base_url || ""}
                      onChange={(e) => updateDraftField("jira", "base_url", e.target.value)}
                      placeholder="https://your-team.atlassian.net"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Atlassian Account Email
                    </label>
                    <input
                      type="email"
                      value={draft.config.account_email || ""}
                      onChange={(e) => updateDraftField("jira", "account_email", e.target.value)}
                      placeholder="admin@company.com"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Jira API Token{" "}
                      {item.has_secret && (
                        <span className="font-mono text-emerald-700">({item.masked_secret})</span>
                      )}
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        type={showSecrets["jira"] ? "text" : "password"}
                        value={draft.secret}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            jira: { ...draft, secret: e.target.value },
                          }))
                        }
                        placeholder={item.has_secret ? "Nhập API token mới nếu thay đổi" : "ATATT3xFfGF0..."}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecrets((p) => ({ ...p, jira: !p["jira"] }))}
                        className="rounded-lg border border-slate-300 px-3 text-xs text-slate-600 hover:bg-slate-50"
                      >
                        {showSecrets["jira"] ? "Ẩn" : "Hiện"}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Default Project Key
                    </label>
                    <input
                      type="text"
                      value={draft.config.project_key || "LDOC"}
                      onChange={(e) =>
                        updateDraftField("jira", "project_key", e.target.value.toUpperCase())
                      }
                      placeholder="LDOC"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.auto_create_drift_ticket)}
                        onChange={(e) =>
                          updateDraftField("jira", "auto_create_drift_ticket", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Tự động tạo Jira Task khi mức độ Documentation Drift vượt ngưỡng cảnh báo
                    </label>
                  </div>
                </div>
              )}

              {item.provider === "slack" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Slack Bot User OAuth Token{" "}
                      {item.has_secret && (
                        <span className="font-mono text-emerald-700">({item.masked_secret})</span>
                      )}
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        type={showSecrets["slack"] ? "text" : "password"}
                        value={draft.secret}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            slack: { ...draft, secret: e.target.value },
                          }))
                        }
                        placeholder={item.has_secret ? "Nhập Bot Token mới nếu thay đổi" : "xoxb-..."}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecrets((p) => ({ ...p, slack: !p["slack"] }))}
                        className="rounded-lg border border-slate-300 px-3 text-xs text-slate-600 hover:bg-slate-50"
                      >
                        {showSecrets["slack"] ? "Ẩn" : "Hiện"}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700">
                      Kênh nhận thông báo mặc định (Channel ID / Name)
                    </label>
                    <input
                      type="text"
                      value={draft.config.default_channel || "#livingdocs-alerts"}
                      onChange={(e) =>
                        updateDraftField("slack", "default_channel", e.target.value)
                      }
                      placeholder="#livingdocs-alerts"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-6 md:col-span-2">
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.notify_on_drift)}
                        onChange={(e) =>
                          updateDraftField("slack", "notify_on_drift", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Cảnh báo khi phát hiện Drift
                    </label>
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.notify_on_review_required)}
                        onChange={(e) =>
                          updateDraftField("slack", "notify_on_review_required", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Thông báo yêu cầu duyệt 2 cấp (Tech & Governance)
                    </label>
                    <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.config.notify_on_ci_blocked)}
                        onChange={(e) =>
                          updateDraftField("slack", "notify_on_ci_blocked", e.target.checked)
                        }
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      Báo khi CI/CD Gate chặn PR
                    </label>
                  </div>
                </div>
              )}

              <div className="flex flex-col justify-between gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center">
                <div className="text-xs text-slate-500">
                  {item.status_message ? (
                    <span
                      className={
                        item.connection_status === "connected"
                          ? "text-emerald-700"
                          : item.connection_status === "failed"
                          ? "text-red-600"
                          : "text-slate-500"
                      }
                    >
                      {item.status_message}
                    </span>
                  ) : (
                    <span>Chưa kiểm tra kết nối.</span>
                  )}
                  {item.last_tested_at && (
                    <span className="ml-2 text-slate-400">
                      • Kiểm tra lúc {new Date(item.last_tested_at).toLocaleString("vi-VN")}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2.5">
                  <button
                    type="button"
                    disabled={isTesting || isSaving}
                    onClick={() => handleTest(item.provider)}
                    className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {isTesting ? "Đang kiểm tra..." : "Test Connection"}
                  </button>
                  <button
                    type="button"
                    disabled={isSaving || isTesting}
                    onClick={() => handleSave(item.provider)}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {isSaving ? "Đang lưu..." : "Lưu cấu hình"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}