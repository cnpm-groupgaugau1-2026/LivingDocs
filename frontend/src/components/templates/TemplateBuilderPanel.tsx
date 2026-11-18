"use client";

import React, { useEffect, useState } from "react";
import {
  DocTemplateItem,
  FormattingConstraints,
  PlaceholderMapping,
} from "./TemplateLibraryPanel";

interface CatalogPlaceholder {
  placeholder: string;
  ast_source: string;
  data_type: string;
  description: string;
  sample_value: string;
}

interface Props {
  editingTemplate: DocTemplateItem | null;
  apiBase: string;
  getAuthHeaders: () => Record<string, string>;
  onSaved: () => Promise<void>;
}

const TEMPLATE_CATEGORIES = [
  "API Reference",
  "README",
  "Module Guide",
  "Onboarding Guide",
  "ADR",
];

const DEFAULT_CONSTRAINTS: FormattingConstraints = {
  required_sections: ["## Overview", "## Details"],
  forbidden_patterns: ["TODO", "TBD", "FIXME"],
  tone_style: "Technical & Concise",
  require_code_blocks: true,
  require_tables_for_params: false,
  max_section_words: 450,
  enforce_strict_mode: true,
};

export default function TemplateBuilderPanel({
  editingTemplate,
  apiBase,
  getAuthHeaders,
  onSaved,
}: Props) {
  const [catalog, setCatalog] = useState<CatalogPlaceholder[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("API Reference");
  const [description, setDescription] = useState("");
  const [targetPathPattern, setTargetPathPattern] = useState("docs/api/**/*.md");
  const [isEnforced, setIsEnforced] = useState(true);
  const [changeNote, setChangeNote] = useState("");
  const [content, setContent] = useState("");
  const [mappings, setMappings] = useState<PlaceholderMapping[]>([]);

  // Custom placeholder form
  const [newPh, setNewPh] = useState("{{custom.entity}}");
  const [newAst, setNewAst] = useState("ast.classes.CustomService");
  const [newType, setNewType] = useState("code_block");

  // Live AST Preview
  const [previewMarkdown, setPreviewMarkdown] = useState<string | null>(null);
  const [unresolvedList, setUnresolvedList] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetch(`${apiBase}/templates/placeholders/catalog`, {
      headers: getAuthHeaders(),
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setCatalog(data))
      .catch(() => setCatalog([]));
  }, [apiBase]);

  useEffect(() => {
    setPreviewMarkdown(null);
    setStatusMsg(null);
    if (editingTemplate) {
      setName(editingTemplate.name);
      setCategory(editingTemplate.category);
      setDescription(editingTemplate.description);
      setTargetPathPattern(editingTemplate.target_path_pattern);
      setIsEnforced(editingTemplate.is_enforced);
      setContent(editingTemplate.content);
      setMappings(editingTemplate.placeholder_mappings || []);
      setChangeNote(`Cập nhật cấu trúc & AST placeholder cho ${editingTemplate.name}`);
    } else {
      setName("Microservice Endpoint Specification");
      setCategory("API Reference");
      setDescription("Template chuẩn cho các service mới tích hợp AST Parser.");
      setTargetPathPattern("docs/services/**/*.md");
      setIsEnforced(true);
      setChangeNote("Khởi tạo template mới từ Dynamic Builder");
      setContent(
        "# {{project.name}} — {{module.name}}\n\n" +
          "## Overview\nTài liệu kỹ thuật tự động đồng bộ từ mã nguồn.\n\n" +
          "## Endpoints\n{{api.endpoints}}\n\n" +
          "## Core Classes\n{{classes.signatures}}\n"
      );
      setMappings([
        {
          placeholder: "{{project.name}}",
          ast_source: "ast.repository.name",
          data_type: "inline_text",
          fallback_value: "LivingDocs",
          required: true,
        },
        {
          placeholder: "{{module.name}}",
          ast_source: "ast.module.identifier",
          data_type: "inline_text",
          fallback_value: "service.core",
          required: true,
        },
        {
          placeholder: "{{api.endpoints}}",
          ast_source: "ast.routers[*].endpoints",
          data_type: "markdown_table",
          fallback_value: "| - | - |",
          required: true,
        },
        {
          placeholder: "{{classes.signatures}}",
          ast_source: "ast.classes[*].signature",
          data_type: "code_block",
          fallback_value: "```python\npass\n```",
          required: false,
        },
      ]);
    }
  }, [editingTemplate]);

  const handleInsertCatalogPlaceholder = (item: CatalogPlaceholder) => {
    setContent((prev) => `${prev.trimEnd()}\n${item.placeholder}\n`);
    if (!mappings.some((m) => m.placeholder === item.placeholder)) {
      setMappings([
        ...mappings,
        {
          placeholder: item.placeholder,
          ast_source: item.ast_source,
          data_type: item.data_type,
          fallback_value: "N/A",
          required: true,
        },
      ]);
    }
  };

  const handleAddCustomMapping = () => {
    const cleanPh = newPh.trim();
    if (!cleanPh.startsWith("{{") || !cleanPh.endsWith("}}")) {
      setStatusMsg({
        type: "error",
        text: "Placeholder phải có định dạng {{ten_bien}}.",
      });
      return;
    }
    setMappings([
      ...mappings.filter((m) => m.placeholder !== cleanPh),
      {
        placeholder: cleanPh,
        ast_source: newAst.trim() || "ast.custom.node",
        data_type: newType,
        fallback_value: "N/A",
        required: true,
      },
    ]);
    setContent((prev) => `${prev.trimEnd()}\n${cleanPh}\n`);
    setStatusMsg(null);
  };

  const handleRunAstPreview = async () => {
    if (editingTemplate) {
      try {
        const res = await fetch(`${apiBase}/templates/${editingTemplate.id}/preview`, {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({
            content,
            placeholder_mappings: mappings,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setPreviewMarkdown(data.rendered_markdown);
          setUnresolvedList(data.unresolved_placeholders || []);
          return;
        }
      } catch {
        // Fallback client-side preview
      }
    }

    let rendered = content;
    for (const item of catalog) {
      rendered = rendered.split(item.placeholder).join(item.sample_value);
    }
    for (const m of mappings) {
      if (rendered.includes(m.placeholder)) {
        rendered = rendered.split(m.placeholder).join(`[AST Bound: ${m.ast_source}]`);
      }
    }
    const unresolved = Array.from(new Set(rendered.match(/\{\{[a-zA-Z0-9_.-]+\}\}/g) || []));
    setPreviewMarkdown(rendered);
    setUnresolvedList(unresolved);
  };

  const handleSaveTemplate = async () => {
    setSaving(true);
    setStatusMsg(null);
    try {
      const isEdit = Boolean(editingTemplate);
      const url = isEdit ? `${apiBase}/templates/${editingTemplate!.id}` : `${apiBase}/templates`;
      const method = isEdit ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name,
          category,
          description,
          content,
          placeholder_mappings: mappings,
          formatting_constraints: editingTemplate?.formatting_constraints || DEFAULT_CONSTRAINTS,
          is_enforced: isEnforced,
          target_path_pattern: targetPathPattern,
          change_note: changeNote,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const saved: DocTemplateItem = await res.json();
      await onSaved();
      setStatusMsg({
        type: "success",
        text: isEdit
          ? `Đã cập nhật "${saved.name}" lên phiên bản ${saved.current_version} trong PostgreSQL.`
          : `Đã tạo mới template "${saved.name}" (${saved.current_version}) thành công.`,
      });
    } catch (err: any) {
      setStatusMsg({ type: "error", text: `Lưu template thất bại (${err.message}).` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* METADATA CARD */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              {editingTemplate
                ? `Chỉnh sửa Template: ${editingTemplate.name} (${editingTemplate.current_version})`
                : "Tạo mới Documentation Template"}
            </h3>
            <p className="text-xs text-slate-500">
              Thiết kế cấu trúc Markdown và ánh xạ trực tiếp biến giữ chỗ (Placeholders) tới thực thể mã nguồn AST.
            </p>
          </div>
          {editingTemplate && (
            <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 border border-indigo-200">
              Lưu sẽ tạo phiên bản mới
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Tên Template</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Phân loại tài liệu</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            >
              {TEMPLATE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">
              Target Repository Path (Glob)
            </label>
            <input
              type="text"
              value={targetPathPattern}
              onChange={(e) => setTargetPathPattern(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">Mô tả phạm vi áp dụng</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-700">
              Ghi chú phiên bản (Commit / Version Note)
            </label>
            <input
              type="text"
              value={changeNote}
              onChange={(e) => setChangeNote(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* AST PLACEHOLDER PALETTE & MARKDOWN EDITOR */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* LEFT: AST ENTITY PALETTE */}
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5">
          <div>
            <h4 className="text-sm font-bold text-slate-900">Code-Entity Placeholder Catalog</h4>
            <p className="text-[11px] text-slate-500">
              Bấm vào biến bên dưới để chèn vào nội dung và tự động ánh xạ với AST Parser.
            </p>
          </div>

          <div className="space-y-2">
            {catalog.map((item) => (
              <button
                key={item.placeholder}
                type="button"
                onClick={() => handleInsertCatalogPlaceholder(item)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-left transition hover:border-indigo-300 hover:bg-indigo-50/50"
              >
                <div className="flex items-center justify-between">
                  <code className="font-mono text-xs font-bold text-indigo-700">{item.placeholder}</code>
                  <span className="rounded bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-600 border border-slate-200">
                    {item.ast_source}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-slate-600">{item.description}</p>
              </button>
            ))}
          </div>

          {/* CUSTOM MAPPING */}
          <div className="border-t border-slate-100 pt-3">
            <p className="mb-2 text-xs font-semibold text-slate-800">Thêm ánh xạ AST tùy chỉnh</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                value={newPh}
                onChange={(e) => setNewPh(e.target.value)}
                placeholder="{{custom.var}}"
                className="rounded border border-slate-300 px-2.5 py-1.5 font-mono text-xs"
              />
              <input
                type="text"
                value={newAst}
                onChange={(e) => setNewAst(e.target.value)}
                placeholder="ast.path"
                className="rounded border border-slate-300 px-2.5 py-1.5 font-mono text-xs"
              />
            </div>
            <div className="mt-2 flex items-center gap-2">
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="rounded border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="inline_text">inline_text</option>
                <option value="code_block">code_block</option>
                <option value="markdown_table">markdown_table</option>
                <option value="bullet_list">bullet_list</option>
              </select>
              <button
                type="button"
                onClick={handleAddCustomMapping}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900"
              >
                + Chèn & Ánh xạ
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: TEMPLATE MARKDOWN EDITOR & AST PREVIEW */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-7">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm font-bold text-slate-900">
                Markdown Template Blueprint
              </label>
              <button
                type="button"
                onClick={handleRunAstPreview}
                className="rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
              >
                Render Preview với dữ liệu AST mẫu
              </button>
            </div>

            <textarea
              rows={13}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-950 p-3.5 font-mono text-xs leading-relaxed text-emerald-300 focus:border-indigo-500 focus:outline-none"
            />

            {/* ACTIVE MAPPINGS PILLS */}
            <div className="mt-3">
              <p className="mb-1.5 text-[11px] font-semibold text-slate-600">
                Danh sách Placeholder đang ánh xạ ({mappings.length}):
              </p>
              <div className="flex flex-wrap gap-1.5">
                {mappings.map((m) => (
                  <span
                    key={m.placeholder}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700"
                  >
                    <strong className="text-indigo-700">{m.placeholder}</strong> → {m.ast_source}
                    <button
                      type="button"
                      onClick={() =>
                        setMappings(mappings.filter((item) => item.placeholder !== m.placeholder))
                      }
                      className="ml-1 text-slate-400 hover:text-rose-600"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* AST RENDERED PREVIEW BOX */}
            {previewMarkdown !== null && (
              <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50/40 p-3.5">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-800">
                    Kết quả Render sau khi AST Engine điền dữ liệu:
                  </span>
                  {unresolvedList.length > 0 && (
                    <span className="text-[11px] font-semibold text-rose-600">
                      Biến chưa map: {unresolvedList.join(", ")}
                    </span>
                  )}
                </div>
                <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded bg-white p-3 font-mono text-xs text-slate-800 border border-slate-200">
                  {previewMarkdown}
                </pre>
              </div>
            )}
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={isEnforced}
                onChange={(e) => setIsEnforced(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
              />
              Áp đặt bắt buộc (Enforce) lên các file khớp{" "}
              <code className="font-mono text-indigo-700">{targetPathPattern}</code>
            </label>

            <button
              type="button"
              onClick={handleSaveTemplate}
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Đang lưu..." : "Lưu Template & Tạo Phiên Bản"}
            </button>
          </div>

          {statusMsg && (
            <p
              className={`mt-2 text-xs font-medium ${
                statusMsg.type === "success" ? "text-emerald-600" : "text-rose-600"
              }`}
            >
              {statusMsg.text}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}