"use client";

import React, { useEffect, useState } from "react";
import { DocTemplateItem, FormattingConstraints } from "./TemplateLibraryPanel";

interface Props {
  templates: DocTemplateItem[];
  selectedTemplate: DocTemplateItem | null;
  apiBase: string;
  getAuthHeaders: () => Record<string, string>;
  onSelectTemplate: (tpl: DocTemplateItem) => void;
  onRefresh: () => Promise<void>;
}

interface ViolationItem {
  rule: string;
  severity: string;
  detail: string;
}

interface ValidationReport {
  template_id: number;
  template_name: string;
  enforce_strict_mode: boolean;
  decision: "APPROVED" | "BLOCKED_BY_POLICY" | "WARNING_ONLY";
  compliance_score: number;
  violations: ViolationItem[];
  passed_checks: string[];
  auto_remediated_markdown: string;
}

export default function ConstraintsEnforcementPanel({
  templates,
  selectedTemplate,
  apiBase,
  getAuthHeaders,
  onSelectTemplate,
  onRefresh,
}: Props) {
  const activeTpl = selectedTemplate || templates[0] || null;

  const [constraints, setConstraints] = useState<FormattingConstraints>({
    required_sections: [],
    forbidden_patterns: ["TODO", "TBD"],
    tone_style: "Technical & Concise",
    require_code_blocks: true,
    require_tables_for_params: true,
    max_section_words: 450,
    enforce_strict_mode: true,
  });

  const [newSection, setNewSection] = useState("## Error Handling");
  const [newForbidden, setNewForbidden] = useState("placeholder");
  const [savingRules, setSavingRules] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Sandbox AI Output Tester
  const [sampleOutput, setSampleOutput] = useState("");
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    if (activeTpl) {
      setConstraints({
        required_sections: activeTpl.formatting_constraints?.required_sections || [],
        forbidden_patterns: activeTpl.formatting_constraints?.forbidden_patterns || [],
        tone_style: activeTpl.formatting_constraints?.tone_style || "Technical & Concise",
        require_code_blocks: activeTpl.formatting_constraints?.require_code_blocks ?? true,
        require_tables_for_params:
          activeTpl.formatting_constraints?.require_tables_for_params ?? true,
        max_section_words: activeTpl.formatting_constraints?.max_section_words || 450,
        enforce_strict_mode: activeTpl.formatting_constraints?.enforce_strict_mode ?? true,
      });
      setSaveMsg(null);
      setReport(null);
      setSampleOutput(
        `# LivingDocs Enterprise — AI Draft\n\n` +
          `## Overview\nTài liệu được sinh tự động bởi LLM nhưng chưa kiểm tra ràng buộc.\n\n` +
          `TODO: Bổ sung danh sách endpoint sau khi hoàn thiện code.\n`
      );
    }
  }, [activeTpl?.id]);

  if (!activeTpl) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        Chưa có template nào để cấu hình ràng buộc.
      </div>
    );
  }

  const handleSaveConstraints = async () => {
    setSavingRules(true);
    setSaveMsg(null);
    try {
      const res = await fetch(`${apiBase}/templates/${activeTpl.id}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name: activeTpl.name,
          category: activeTpl.category,
          description: activeTpl.description,
          content: activeTpl.content,
          placeholder_mappings: activeTpl.placeholder_mappings,
          formatting_constraints: constraints,
          is_enforced: activeTpl.is_enforced,
          target_path_pattern: activeTpl.target_path_pattern,
          change_note: "Cập nhật bộ quy tắc AI Output Formatting Constraints",
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await onRefresh();
      setSaveMsg("Đã lưu bộ quy tắc AI Formatting Constraints xuống PostgreSQL.");
    } catch (err: any) {
      setSaveMsg(`Lỗi lưu quy tắc: ${err.message}`);
    } finally {
      setSavingRules(false);
    }
  };

  const handleRunValidation = async () => {
    setValidating(true);
    try {
      const res = await fetch(`${apiBase}/templates/${activeTpl.id}/validate-output`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ ai_generated_markdown: sampleOutput }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ValidationReport = await res.json();
      setReport(data);
    } catch {
      setReport(null);
    } finally {
      setValidating(false);
    }
  };

  const loadCompliantSample = () => {
    const sectionsText = constraints.required_sections
      .map(
        (sec) =>
          `${sec}\nNội dung chuẩn hóa tuân thủ phong cách **${constraints.tone_style}**.\n\n` +
          `| Field | Type | Description |\n| :--- | :--- | :--- |\n| \`id\` | \`int\` | Định danh bản ghi |\n\n` +
          "```json\n{\"status\": \"ok\"}\n```"
      )
      .join("\n\n");
    setSampleOutput(`# ${activeTpl.name} — Verified Output\n\n${sectionsText}`);
    setReport(null);
  };

  return (
    <div className="space-y-6">
      {/* TEMPLATE SELECTOR */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              AI Output Formatting Constraints Enforcement Engine
            </h3>
            <p className="text-xs text-slate-500">
              Thiết lập luật kiểm soát cấu trúc đầu ra của LLM (Heading bắt buộc, từ khóa cấm, Code Block, Table) và chạy thử nghiệm kiểm định.
            </p>
          </div>

          <select
            value={activeTpl.id}
            onChange={(e) => {
              const found = templates.find((t) => t.id === Number(e.target.value));
              if (found) onSelectTemplate(found);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-900 focus:border-indigo-500 focus:outline-none"
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.category} • {t.current_version})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 2 COLUMNS: LEFT = RULES CONFIGURATION | RIGHT = LIVE ENFORCEMENT SANDBOX */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* LEFT: RULES CONFIG */}
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-6">
          <h4 className="text-sm font-bold text-slate-900">1. Cấu hình quy tắc ràng buộc AI</h4>

          {/* REQUIRED SECTIONS */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-700">
              Đề mục Markdown bắt buộc (Required Headings)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {constraints.required_sections.map((sec) => (
                <span
                  key={sec}
                  className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 font-mono text-xs text-indigo-800"
                >
                  {sec}
                  <button
                    type="button"
                    onClick={() =>
                      setConstraints({
                        ...constraints,
                        required_sections: constraints.required_sections.filter((s) => s !== sec),
                      })
                    }
                    className="ml-1 text-indigo-400 hover:text-rose-600"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <input
                type="text"
                value={newSection}
                onChange={(e) => setNewSection(e.target.value)}
                placeholder="## Tên đề mục"
                className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => {
                  const val = newSection.trim();
                  if (val && !constraints.required_sections.includes(val)) {
                    setConstraints({
                      ...constraints,
                      required_sections: [...constraints.required_sections, val],
                    });
                    setNewSection("");
                  }
                }}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900"
              >
                + Thêm mục
              </button>
            </div>
          </div>

          {/* FORBIDDEN PATTERNS */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-700">
              Từ khóa / Mẫu bị cấm (Anti-Hallucination & Draft Guard)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {constraints.forbidden_patterns.map((pat) => (
                <span
                  key={pat}
                  className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2.5 py-1 font-mono text-xs text-rose-700"
                >
                  {pat}
                  <button
                    type="button"
                    onClick={() =>
                      setConstraints({
                        ...constraints,
                        forbidden_patterns: constraints.forbidden_patterns.filter((p) => p !== pat),
                      })
                    }
                    className="ml-1 text-rose-400 hover:text-rose-800"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <input
                type="text"
                value={newForbidden}
                onChange={(e) => setNewForbidden(e.target.value)}
                placeholder="Cụm từ cấm..."
                className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => {
                  const val = newForbidden.trim();
                  if (val && !constraints.forbidden_patterns.includes(val)) {
                    setConstraints({
                      ...constraints,
                      forbidden_patterns: [...constraints.forbidden_patterns, val],
                    });
                    setNewForbidden("");
                  }
                }}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900"
              >
                + Thêm từ cấm
              </button>
            </div>
          </div>

          {/* TONE & MAX WORDS */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Văn phong AI (Tone Style)
              </label>
              <select
                value={constraints.tone_style}
                onChange={(e) => setConstraints({ ...constraints, tone_style: e.target.value })}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              >
                <option value="Technical & Concise">Technical & Concise</option>
                <option value="Formal Architectural (ADR)">Formal Architectural (ADR)</option>
                <option value="Developer-Friendly Onboarding">Developer-Friendly Onboarding</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Giới hạn số từ / Section
              </label>
              <input
                type="number"
                min={50}
                max={3000}
                step={50}
                value={constraints.max_section_words}
                onChange={(e) =>
                  setConstraints({
                    ...constraints,
                    max_section_words: parseInt(e.target.value || "450", 10),
                  })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
              />
            </div>
          </div>

          {/* CHECKBOXES */}
          <div className="space-y-2 border-t border-slate-100 pt-3">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={constraints.require_code_blocks}
                onChange={(e) =>
                  setConstraints({ ...constraints, require_code_blocks: e.target.checked })
                }
                className="h-4 w-4 rounded accent-indigo-600"
              />
              Bắt buộc có khối mã nguồn minh họa (Fenced Code Block <code>```</code>)
            </label>

            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={constraints.require_tables_for_params}
                onChange={(e) =>
                  setConstraints({ ...constraints, require_tables_for_params: e.target.checked })
                }
                className="h-4 w-4 rounded accent-indigo-600"
              />
              Bắt buộc trình bày tham số / schema bằng bảng Markdown Table
            </label>

            <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-rose-700">
              <input
                type="checkbox"
                checked={constraints.enforce_strict_mode}
                onChange={(e) =>
                  setConstraints({ ...constraints, enforce_strict_mode: e.target.checked })
                }
                className="h-4 w-4 rounded accent-rose-600"
              />
              Strict Enforcement Mode (Chặn xuất bản nếu AI vi phạm bất kỳ quy tắc nào)
            </label>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-emerald-600">{saveMsg}</span>
            <button
              type="button"
              onClick={handleSaveConstraints}
              disabled={savingRules}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {savingRules ? "Đang lưu..." : "Lưu Quy Tắc Ràng Buộc"}
            </button>
          </div>
        </div>

        {/* RIGHT: LIVE ENFORCEMENT VALIDATION SANDBOX */}
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-bold text-slate-900">
              2. Kiểm định đầu ra AI (Live Enforcement Sandbox)
            </h4>
            <button
              type="button"
              onClick={loadCompliantSample}
              className="rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
            >
              Nạp mẫu đạt chuẩn 100%
            </button>
          </div>

          <textarea
            rows={9}
            value={sampleOutput}
            onChange={(e) => setSampleOutput(e.target.value)}
            placeholder="Dán nội dung Markdown do AI sinh ra vào đây để kiểm tra tuân thủ..."
            className="w-full rounded-lg border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-slate-100 focus:border-indigo-500 focus:outline-none"
          />

          <button
            type="button"
            onClick={handleRunValidation}
            disabled={validating}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
          >
            {validating
              ? "Đang phân tích cấu trúc..."
              : "Chạy AI Formatting Constraints Enforcement Engine"}
          </button>

          {report && (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${
                    report.decision === "APPROVED"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-rose-100 text-rose-800"
                  }`}
                >
                  {report.decision}
                </span>
                <span className="text-sm font-bold text-slate-900">
                  Compliance Score: {report.compliance_score}%
                </span>
              </div>

              {report.violations.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-bold text-rose-700">
                    Vi phạm phát hiện ({report.violations.length}):
                  </p>
                  {report.violations.map((v, i) => (
                    <div
                      key={i}
                      className="rounded border border-rose-200 bg-white p-2 text-xs text-rose-800"
                    >
                      <strong>[{v.severity}] {v.rule}:</strong> {v.detail}
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      setSampleOutput(report.auto_remediated_markdown);
                      setReport(null);
                    }}
                    className="mt-1 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700"
                  >
                    Tự động bổ sung các đề mục còn thiếu (Auto-Fix)
                  </button>
                </div>
              )}

              {report.passed_checks.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-bold text-emerald-700">Tiêu chí đạt chuẩn:</p>
                  {report.passed_checks.map((ok, idx) => (
                    <p key={idx} className="text-[11px] text-emerald-800">
                      ✓ {ok}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}