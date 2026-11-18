"use client";

import React, { useCallback, useEffect, useState } from "react";
import TemplateLibraryPanel, {
  DocTemplateItem,
} from "@/components/templates/TemplateLibraryPanel";
import TemplateBuilderPanel from "@/components/templates/TemplateBuilderPanel";
import ConstraintsEnforcementPanel from "@/components/templates/ConstraintsEnforcementPanel";

type TemplateTab = "library" | "builder" | "constraints";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function DynamicTemplatesPage() {
  const [activeTab, setActiveTab] = useState<TemplateTab>("builder");
  const [templates, setTemplates] = useState<DocTemplateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<DocTemplateItem | null>(null);

  const getAuthHeaders = useCallback(() => {
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
  }, []);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/templates`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DocTemplateItem[] = await res.json();
      setTemplates(data);
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Dynamic Template Management Library
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Khởi tạo, nhân bản, quản lý phiên bản và áp đặt chuẩn cấu trúc tài liệu gắn với thực thể mã nguồn AST.
            </p>
          </div>
          <a
            href="/admin"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            ← Quay lại System Admin
          </a>
        </div>

        <div className="mb-6 border-b border-slate-200">
          <nav className="-mb-px flex space-x-6">
            <button
              type="button"
              onClick={() => setActiveTab("library")}
              className={`border-b-2 pb-3 text-sm font-semibold ${
                activeTab === "library"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              3.2 Template Library & Version Control
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("builder")}
              className={`border-b-2 pb-3 text-sm font-semibold ${
                activeTab === "builder"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              3.1 Dynamic Template Builder & AST Mapper
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("constraints")}
              className={`border-b-2 pb-3 text-sm font-semibold ${
                activeTab === "constraints"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              3.3 AI Output Formatting Constraints
            </button>
          </nav>
        </div>

        {activeTab === "library" && (
          <TemplateLibraryPanel
            templates={templates}
            loading={loading}
            apiBase={API_BASE}
            getAuthHeaders={getAuthHeaders}
            onRefresh={fetchTemplates}
            onEditTemplate={(tpl) => {
              setSelectedTemplate(tpl);
              setActiveTab("builder");
            }}
            onCreateNew={() => {
              setSelectedTemplate(null);
              setActiveTab("builder");
            }}
            onOpenConstraints={(tpl) => {
              setSelectedTemplate(tpl);
              setActiveTab("constraints");
            }}
          />
        )}

        {activeTab === "builder" && (
          <TemplateBuilderPanel
            editingTemplate={selectedTemplate}
            apiBase={API_BASE}
            getAuthHeaders={getAuthHeaders}
            onSaved={fetchTemplates}
          />
        )}

        {activeTab === "constraints" && (
          <ConstraintsEnforcementPanel
            templates={templates}
            selectedTemplate={selectedTemplate}
            apiBase={API_BASE}
            getAuthHeaders={getAuthHeaders}
            onSelectTemplate={(tpl) => setSelectedTemplate(tpl)}
            onRefresh={fetchTemplates}
          />
        )}
      </div>
    </div>
  );
}