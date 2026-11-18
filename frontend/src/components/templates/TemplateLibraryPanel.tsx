"use client";

import React, { useState } from "react";

export interface PlaceholderMapping {
  placeholder: string;
  ast_source: string;
  data_type: string;
  fallback_value: string;
  required: boolean;
}

export interface FormattingConstraints {
  required_sections: string[];
  forbidden_patterns: string[];
  tone_style: string;
  require_code_blocks: boolean;
  require_tables_for_params: boolean;
  max_section_words: number;
  enforce_strict_mode: boolean;
}

export interface DocTemplateItem {
  id: number;
  name: string;
  slug: string;
  category: string;
  description: string;
  content: string;
  placeholder_mappings: PlaceholderMapping[];
  formatting_constraints: FormattingConstraints;
  current_version: string;
  version_number: number;
  version_count: number;
  is_enforced: boolean;
  target_path_pattern: string;
  is_system_default: boolean;
  created_by: string;
  updated_by: string;
  updated_at?: string;
}

interface TemplateVersionItem {
  id: number;
  version_label: string;
  version_number: number;
  content: string;
  change_note: string;
  created_by: string;
  created_at?: string;
}

interface Props {
  templates: DocTemplateItem[];
  loading: boolean;
  apiBase: string;
  getAuthHeaders: () => Record<string, string>;
  onRefresh: () => Promise<void>;
  onEditTemplate: (tpl: DocTemplateItem) => void;
  onCreateNew: () => void;
  onOpenConstraints: (tpl: DocTemplateItem) => void;
}

const CATEGORIES = ["ALL", "API Reference", "README", "Module Guide", "Onboarding Guide", "ADR"];

export default function TemplateLibraryPanel({
  templates,
  loading,
  apiBase,
  getAuthHeaders,
  onRefresh,
  onEditTemplate,
  onCreateNew,
  onOpenConstraints,
}: Props) {
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [enforcedOnly, setEnforcedOnly] = useState(false);
  const [actionMsg, setActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Version Control Modal State
  const [historyTemplate, setHistoryTemplate] = useState<DocTemplateItem | null>(null);
  const [versions, setVersions] = useState<TemplateVersionItem[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  const filteredTemplates = templates.filter((t) => {
    if (selectedCategory !== "ALL" && t.category !== selectedCategory) return false;
    if (enforcedOnly && !t.is_enforced) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.target_path_pattern.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const handleClone = async (tpl: DocTemplateItem) => {
    setActionMsg(null);
    try {
      const res = await fetch(`${apiBase}/templates/${tpl.id}/clone`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await onRefresh();
      setActionMsg({
        type: "success",
        text: `Đã nhân bản thành công template "${tpl.name} (Clone)" ở phiên bản v1.0.`,
      });
    } catch (err: any) {
      setActionMsg({ type: "error", text: `Nhân bản thất bại (${err.message}).` });
    }
  };

  const handleToggleEnforce = async (tpl: DocTemplateItem) => {
    setActionMsg(null);
    try {
      const res = await fetch(`${apiBase}/templates/${tpl.id}/enforce`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          is_enforced: !tpl.is_enforced,
          target_path_pattern: tpl.target_path_pattern,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await onRefresh();
      setActionMsg({
        type: "success",
        text: !tpl.is_enforced
          ? `Đã bật Enforcement Policy cho "${tpl.name}" áp dụng trên đường dẫn ${tpl.target_path_pattern}.`
          : `Đã tắt Enforcement Policy cho "${tpl.name}".`,
      });
    } catch (err: any) {
      setActionMsg({ type: "error", text: `Cập nhật Enforcement thất bại (${err.message}).` });
    }
  };

  const openVersionHistory = async (tpl: DocTemplateItem) => {
    setHistoryTemplate(tpl);
    setLoadingVersions(true);
    try {
      const res = await fetch(`${apiBase}/templates/${tpl.id}/versions`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setVersions(data);
    } catch {
      setVersions([]);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleRollback = async (versionId: number, label: string) => {
    if (!historyTemplate) return;
    try {
      const res = await fetch(
        `${apiBase}/templates/${historyTemplate.id}/rollback/${versionId}`,
        {
          method: "POST",
          headers: getAuthHeaders(),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await onRefresh();
      setHistoryTemplate(null);
      setActionMsg({
        type: "success",
        text: `Đã khôi phục template "${historyTemplate.name}" về nội dung của ${label}.`,
      });
    } catch (err: any) {
      setActionMsg({ type: "error", text: `Rollback thất bại (${err.message}).` });
    }
  };

  return (
    <div className="space-y-5">
      {/* FILTER & TOOLBAR */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  selectedCategory === cat
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {cat === "ALL" ? `Tất cả (${templates.length})` : cat}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onCreateNew}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
          >
            + Tạo Template Mới
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm theo tên template, mô tả hoặc đường dẫn áp dụng (vd: docs/api/**/*.md)..."
            className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
          />

          <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-700">
            <input
              type="checkbox"
              checked={enforcedOnly}
              onChange={(e) => setEnforcedOnly(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
            />
            Chỉ hiển thị các Template đang áp đặt (Enforced Policy)
          </label>
        </div>

        {actionMsg && (
          <div
            className={`mt-4 rounded-lg px-3.5 py-2.5 text-xs font-medium ${
              actionMsg.type === "success"
                ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {actionMsg.text}
          </div>
        )}
      </div>

      {/* TEMPLATE CARDS GRID */}
      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Đang tải thư viện Template từ PostgreSQL...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {filteredTemplates.map((tpl) => (
            <div
              key={tpl.id}
              className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-indigo-200"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700 border border-indigo-200">
                        {tpl.category}
                      </span>
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-mono font-semibold text-slate-700">
                        {tpl.current_version}
                      </span>
                      {tpl.is_enforced ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                          Enforced
                        </span>
                      ) : (
                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
                          Optional / Draft
                        </span>
                      )}
                    </div>
                    <h3 className="mt-2 text-base font-bold text-slate-900">{tpl.name}</h3>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleToggleEnforce(tpl)}
                    className={`rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition ${
                      tpl.is_enforced
                        ? "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                        : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    }`}
                  >
                    {tpl.is_enforced ? "Tắt Enforce" : "Bật Enforce"}
                  </button>
                </div>

                <p className="mt-2 text-xs leading-relaxed text-slate-600">{tpl.description}</p>

                <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                  <span>
                    Target Path:{" "}
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-800">
                      {tpl.target_path_pattern}
                    </code>
                  </span>
                  <span>•</span>
                  <span>{tpl.placeholder_mappings.length} AST Placeholders</span>
                  <span>•</span>
                  <span>{tpl.formatting_constraints?.required_sections?.length || 0} Required Sections</span>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onEditTemplate(tpl)}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                  >
                    Chỉnh sửa (Builder)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleClone(tpl)}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Clone
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenConstraints(tpl)}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    AI Constraints
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => openVersionHistory(tpl)}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Lịch sử ({tpl.version_count} bản)
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* VERSION CONTROL & ROLLBACK MODAL */}
      {historyTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Version Control History — {historyTemplate.name}
                </h3>
                <p className="text-xs text-slate-500">
                  Phiên bản hiện hành: {historyTemplate.current_version} • Khôi phục bất kỳ bản lưu trước đó
                </p>
              </div>
              <button
                type="button"
                onClick={() => setHistoryTemplate(null)}
                className="rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-500 hover:bg-slate-100"
              >
                Đóng
              </button>
            </div>

            {loadingVersions ? (
              <p className="py-8 text-center text-xs text-slate-500">Đang tải lịch sử phiên bản...</p>
            ) : (
              <div className="mt-4 space-y-3">
                {versions.map((ver) => (
                  <div
                    key={ver.id}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-indigo-600 px-2 py-0.5 font-mono text-xs font-bold text-white">
                          {ver.version_label}
                        </span>
                        <span className="text-xs font-semibold text-slate-800">{ver.change_note}</span>
                      </div>
                      {ver.version_label !== historyTemplate.current_version && (
                        <button
                          type="button"
                          onClick={() => handleRollback(ver.id, ver.version_label)}
                          className="rounded-lg border border-indigo-300 bg-white px-3 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                        >
                          Rollback về {ver.version_label}
                        </button>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Tác giả: {ver.created_by} •{" "}
                      {ver.created_at ? new Date(ver.created_at).toLocaleString("vi-VN") : ""}
                    </p>
                    <pre className="mt-2 max-h-28 overflow-y-auto rounded bg-slate-900 p-2.5 text-[11px] text-slate-100">
                      {ver.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}