"use client";

import React, { useEffect, useState } from "react";

interface AIConfig {
  primary_provider: string;
  primary_model: string;
  fallback_model: string;
  temperature: number;
  max_output_tokens: number;
  daily_token_budget: number;
  monthly_token_budget: number;
  budget_warning_percent: number;
  auto_pause_on_exceed: boolean;
  current_daily_tokens_used: number;
  drift_alert_threshold: number;
  cicd_block_threshold: number;
  auto_sync_minor_drift: boolean;
  updated_at?: string;
  updated_by?: string;
}

const MODEL_OPTIONS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4.1", "gpt-4o-mini", "o3-mini"],
  anthropic: ["claude-3-5-sonnet-20241022", "claude-3-7-sonnet", "claude-3-5-haiku"],
  google: ["gemini-2.5-pro", "gemini-2.5-flash"],
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function AIParameterTuningPanel() {
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const getAuthHeaders = () => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("token") ||
          localStorage.getItem("access_token") ||
          localStorage.getItem("livingdocs_token")
        : "";
    return {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
    };
  };

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/ai-config`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AIConfig = await res.json();
      setConfig(data);
    } catch (err: any) {
      setStatusMsg({
        type: "error",
        text: `Không tải được cấu hình AI (${err.message}). Kiểm tra lại phiên đăng nhập Admin.`,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      const res = await fetch(`${API_BASE}/admin/ai-config`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated: AIConfig = await res.json();
      setConfig(updated);
      const now = new Date().toLocaleTimeString("vi-VN");
      setStatusMsg({
        type: "success",
        text: `Đã lưu cấu hình AI Engine xuống PostgreSQL thành công. • Cập nhật lúc ${now}`,
      });
    } catch (err: any) {
      setStatusMsg({
        type: "error",
        text: `Lưu cấu hình thất bại (${err.message}).`,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    setStatusMsg(null);
    try {
      const res = await fetch(`${API_BASE}/admin/ai-config/reset`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const resetData: AIConfig = await res.json();
      setConfig(resetData);
      setStatusMsg({
        type: "success",
        text: "Đã khôi phục toàn bộ tham số AI về ngưỡng khuyến nghị mặc định.",
      });
    } catch (err: any) {
      setStatusMsg({
        type: "error",
        text: `Khôi phục mặc định thất bại (${err.message}).`,
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading || !config) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        Đang tải tham số AI Engine...
      </div>
    );
  }

  const dailyUsagePercent = Math.min(
    100,
    Math.round((config.current_daily_tokens_used / Math.max(1, config.daily_token_budget)) * 100)
  );

  return (
    <div className="space-y-6">
      {/* CARD 1: LLM MODELS & GENERATION */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              AI
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h3 className="text-base font-semibold text-slate-900">
                  LLM Models & Generation Settings
                </h3>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Engine Active
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Chọn mô hình ngôn ngữ chính, mô hình dự phòng và độ sáng tạo khi sinh/cập nhật tài liệu kỹ thuật.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Nhà cung cấp (LLM Provider)
            </label>
            <select
              value={config.primary_provider}
              onChange={(e) => {
                const provider = e.target.value;
                setConfig({
                  ...config,
                  primary_provider: provider,
                  primary_model: MODEL_OPTIONS[provider][0],
                });
              }}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            >
              <option value="openai">OpenAI Enterprise</option>
              <option value="anthropic">Anthropic Claude</option>
              <option value="google">Google Gemini</option>
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Primary LLM Model
            </label>
            <select
              value={config.primary_model}
              onChange={(e) => setConfig({ ...config, primary_model: e.target.value })}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            >
              {(MODEL_OPTIONS[config.primary_provider] || [config.primary_model]).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Fallback Model (Khi Rate-Limit / Timeout)
            </label>
            <select
              value={config.fallback_model}
              onChange={(e) => setConfig({ ...config, fallback_model: e.target.value })}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            >
              <option value="gpt-4o-mini">gpt-4o-mini</option>
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="claude-3-5-haiku">claude-3-5-haiku</option>
            </select>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs font-medium text-slate-700">
                Temperature (Độ ngẫu nhiên / Sáng tạo)
              </label>
              <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                {config.temperature.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={config.temperature}
              onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
              className="w-full accent-indigo-600"
            />
            <div className="mt-1 flex justify-between text-[11px] text-slate-400">
              <span>0.0 (Bám sát code tuyệt đối)</span>
              <span>1.0 (Sáng tạo cao)</span>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Max Output Tokens / Request
            </label>
            <input
              type="number"
              min={512}
              max={32768}
              step={512}
              value={config.max_output_tokens}
              onChange={(e) =>
                setConfig({ ...config, max_output_tokens: parseInt(e.target.value || "4096", 10) })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-slate-400">
              Khuyến nghị 4,096 – 8,192 tokens cho tài liệu kiến trúc và OpenAPI spec.
            </p>
          </div>
        </div>
      </div>

      {/* CARD 2: TOKEN BUDGET & COST GUARDRAILS */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
            TK
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Token Budget & Cost Guardrails
            </h3>
            <p className="text-xs text-slate-500">
              Kiểm soát hạn mức tiêu thụ token theo ngày/tháng và tự động cảnh báo khi sắp chạm trần ngân sách.
            </p>
          </div>
        </div>

        <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="font-medium text-slate-700">Mức tiêu thụ Token hôm nay</span>
            <span className="font-semibold text-slate-900">
              {config.current_daily_tokens_used.toLocaleString()} /{" "}
              {config.daily_token_budget.toLocaleString()} tokens ({dailyUsagePercent}%)
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className={`h-full transition-all ${
                dailyUsagePercent >= config.budget_warning_percent
                  ? "bg-amber-500"
                  : "bg-emerald-500"
              }`}
              style={{ width: `${dailyUsagePercent}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Hạn mức ngày (Daily Token Budget)
            </label>
            <input
              type="number"
              step={50000}
              value={config.daily_token_budget}
              onChange={(e) =>
                setConfig({ ...config, daily_token_budget: parseInt(e.target.value || "0", 10) })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Hạn mức tháng (Monthly Token Budget)
            </label>
            <input
              type="number"
              step={500000}
              value={config.monthly_token_budget}
              onChange={(e) =>
                setConfig({ ...config, monthly_token_budget: parseInt(e.target.value || "0", 10) })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Ngưỡng cảnh báo ngân sách (%)
            </label>
            <input
              type="number"
              min={10}
              max={100}
              value={config.budget_warning_percent}
              onChange={(e) =>
                setConfig({ ...config, budget_warning_percent: parseInt(e.target.value || "80", 10) })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-xs text-slate-700">
          <input
            type="checkbox"
            checked={config.auto_pause_on_exceed}
            onChange={(e) => setConfig({ ...config, auto_pause_on_exceed: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
          />
          Tự động tạm dừng quét AI nền khi vượt 100% Daily Token Budget (vẫn cho phép chạy thủ công)
        </label>
      </div>

      {/* CARD 3: DOCUMENTATION DRIFT & CI/CD THRESHOLDS */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-600 text-sm font-bold text-white">
            DR
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Documentation Drift & CI/CD Gate Thresholds
            </h3>
            <p className="text-xs text-slate-500">
              Thiết lập ngưỡng sai lệch giữa mã nguồn và tài liệu để kích hoạt Jira Ticket, Slack Alert và chặn PR.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs font-medium text-slate-700">
                Drift Alert Threshold (Tạo Jira Task & Gửi Slack)
              </label>
              <span className="rounded bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                {config.drift_alert_threshold.toFixed(2)} ({Math.round(config.drift_alert_threshold * 100)}%)
              </span>
            </div>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.05}
              value={config.drift_alert_threshold}
              onChange={(e) =>
                setConfig({ ...config, drift_alert_threshold: parseFloat(e.target.value) })
              }
              className="w-full accent-amber-600"
            />
            <p className="mt-1 text-[11px] text-slate-400">
              Vượt ngưỡng này sẽ tự động tạo issue trong project Jira (CG) và bắn cảnh báo Slack.
            </p>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs font-medium text-slate-700">
                CI/CD Gate Block Threshold (Chặn Merge Pull Request)
              </label>
              <span className="rounded bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
                {config.cicd_block_threshold.toFixed(2)} ({Math.round(config.cicd_block_threshold * 100)}%)
              </span>
            </div>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.05}
              value={config.cicd_block_threshold}
              onChange={(e) =>
                setConfig({ ...config, cicd_block_threshold: parseFloat(e.target.value) })
              }
              className="w-full accent-rose-600"
            />
            <p className="mt-1 text-[11px] text-slate-400">
              Yêu cầu phê duyệt 2 cấp (Tech & Governance) trước khi cho phép merge PR.
            </p>
          </div>
        </div>

        <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-xs text-slate-700">
          <input
            type="checkbox"
            checked={config.auto_sync_minor_drift}
            onChange={(e) => setConfig({ ...config, auto_sync_minor_drift: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
          />
          Tự động tạo bản nháp cập nhật tài liệu đối với các thay đổi nhỏ dưới ngưỡng Drift Alert Threshold
        </label>

        {/* FOOTER ACTIONS */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-4">
          <div className="text-xs">
            {statusMsg && (
              <span className={statusMsg.type === "success" ? "text-emerald-600" : "text-rose-600"}>
                {statusMsg.text}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleReset}
              disabled={saving}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Khôi phục mặc định
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Đang lưu..." : "Lưu cấu hình"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}