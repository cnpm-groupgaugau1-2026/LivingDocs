"use client";

import React, { useEffect, useState } from "react";

interface DocVersion {
  version_id: string;
  version_number: string;
  content: string;
  created_at: string;
  author: string;
  trigger_ref: string;
  status: "published" | "draft" | "superseded" | "rolled_back";
  change_summary: string;
}

interface DiffLine {
  line_type: "unchanged" | "added" | "removed" | "modified";
  old_line_num: number | null;
  new_line_num: number | null;
  old_text: string;
  new_text: string;
}

interface CodeChangeItem {
  change_type: "added" | "removed" | "modified";
  symbol_kind: string;
  signature: string;
  detail: string;
}

interface CodeVsDocComparison {
  code_changes_detected: CodeChangeItem[];
  doc_impact_points: string[];
  side_by_side_diff: DiffLine[];
  added_lines: number;
  removed_lines: number;
  drift_resolved_count: number;
}

interface AutoDocWorkflow {
  workflow_id: string;
  event_type: string;
  repo_name: string;
  branch: string;
  commit_sha: string;
  pr_number: number | null;
  pr_title: string | null;
  author: string;
  target_doc_path: string;
  code_diff: string;
  engine_used: string;
  current_published_version: DocVersion;
  active_draft_version: DocVersion | null;
  comparison: CodeVsDocComparison;
  version_history: DocVersion[];
}

const API_BASE = "http://localhost:8000/api/v1/auto-doc";

const PRESET_EVENTS = [
  {
    id: "pr_fe05_3",
    label: "1. PR #42: Bổ sung FE05.3 Consistency Endpoint",
    badge: "Pull Request",
    payload: {
      event_type: "pull_request",
      repo_name: "cnpm-groupgaugau1-2026/LivingDocs",
      branch: "feat/fe05-3-consistency",
      commit_sha: "8c3d91a",
      pr_number: 42,
      pr_title: "feat(multimodal): add VisualAssetConsistencyVerifier & /verify-consistency",
      author: "minh-dev",
      target_doc_path: "docs/architecture/multimodal_pipeline.md",
      use_local_git_diff: false,
      code_diff: [
        "@@ -24,6 +24,14 @@ class VisualAssetConsistencyVerifier:",
        "+class VisualAssetConsistencyVerifier:",
        "+    async def verify_consistency(file_bytes: bytes, filename: str, repo_path: str = ''):",
        "+@router.post('/verify-consistency', response_model=VisualCodeConsistencyResponse)",
        "+async def verify_visual_code_consistency(file: UploadFile, repo_path: str = ''):",
      ].join("\n"),
      current_doc_content: "",
    },
  },
  {
    id: "commit_refactor",
    label: "2. Commit a7f102b: Refactor hàm & đổi phiên bản API",
    badge: "Git Commit",
    payload: {
      event_type: "commit",
      repo_name: "cnpm-groupgaugau1-2026/LivingDocs",
      branch: "main",
      commit_sha: "a7f102b",
      pr_number: null,
      pr_title: "refactor(billing): rename process_payment to execute_billing_charge",
      author: "lan-backend",
      target_doc_path: "docs/services/billing_service.md",
      use_local_git_diff: false,
      code_diff: [
        "@@ -10,8 +10,9 @@ class BillingService:",
        "-    async def process_payment(order_id: str, amount: float):",
        "+    async def execute_billing_charge(order_id: str, amount: float, currency: str = 'VND'):",
        "-@router.post('/api/v1/billing/charge')",
        "+@router.post('/api/v2/billing/execute-charge')",
      ].join("\n"),
      current_doc_content:
        "# Dịch vụ Thanh toán (BillingService)\n\n" +
        "## API & Phương thức chính\n" +
        "- Endpoint: `POST /api/v1/billing/charge`\n" +
        "- Hàm xử lý: `process_payment(order_id: str, amount: float)`\n",
    },
  },
  {
    id: "local_git",
    label: "3. Quét Git Diff thật từ Repo D:\\CNPM\\LivingDocs",
    badge: "Live Repo Diff",
    payload: {
      event_type: "commit",
      repo_name: "cnpm-groupgaugau1-2026/LivingDocs",
      branch: "main",
      commit_sha: "HEAD",
      pr_number: null,
      pr_title: "Live git diff HEAD~1 scan from local repository",
      author: "local-git",
      target_doc_path: "docs/architecture/multimodal_pipeline.md",
      use_local_git_diff: true,
      code_diff: "",
      current_doc_content: "",
    },
  },
];

export default function AutoDocUpdatePage() {
  const [selectedPresetId, setSelectedPresetId] = useState<string>("pr_fe05_3");
  const [workflow, setWorkflow] = useState<AutoDocWorkflow | null>(null);
  const [viewMode, setViewMode] = useState<"side_by_side" | "preview">("side_by_side");

  // FE03.3 Action States
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editDraftText, setEditDraftText] = useState<string>("");
  const [editorNote, setEditorNote] = useState<string>("Bổ sung tham số & ví dụ minh họa");
  const [regenPrompt, setRegenPrompt] = useState<string>("");
  const [showRegenBox, setShowRegenBox] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const triggerPreset = async (preset: (typeof PRESET_EVENTS)[number]) => {
    setSelectedPresetId(preset.id);
    setLoading(true);
    setErrorMsg(null);
    setStatusBanner(null);
    setIsEditing(false);
    setShowRegenBox(false);

    try {
      const res = await fetch(`${API_BASE}/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(preset.payload),
      });
      if (!res.ok) {
        throw new Error(`API lỗi ${res.status}: ${await res.text()}`);
      }
      const data: AutoDocWorkflow = await res.json();
      setWorkflow(data);
      setEditDraftText(data.active_draft_version?.content || data.current_published_version.content);
      setStatusBanner(
        `Đã kích hoạt workflow ${data.workflow_id} từ ${
          data.pr_number ? `PR #${data.pr_number}` : `Commit ${data.commit_sha}`
        }.`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "Không thể kết nối tới Backend FastAPI.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    triggerPreset(PRESET_EVENTS[0]);
  }, []);

  // ==================== FE03.3 ACTION HANDLERS ====================

  const handleAcceptDraft = async () => {
    if (!workflow || !workflow.active_draft_version) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/actions/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflow.workflow_id,
          reviewer: "developer-lead",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AutoDocWorkflow = await res.json();
      setWorkflow(updated);
      setIsEditing(false);
      setStatusBanner(
        `Đã phê duyệt (Accept) và phát hành chính thức phiên bản ${updated.current_published_version.version_number}!`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi phê duyệt bản nháp.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!workflow) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/actions/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflow.workflow_id,
          edited_content: editDraftText,
          editor_note: editorNote || "Chỉnh sửa thủ công bởi developer",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AutoDocWorkflow = await res.json();
      setWorkflow(updated);
      setIsEditing(false);
      setStatusBanner("Đã lưu chỉnh sửa thủ công (Edit) và cập nhật bảng so sánh Side-by-Side.");
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi lưu chỉnh sửa.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!workflow) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/actions/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflow.workflow_id,
          custom_instruction: regenPrompt,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AutoDocWorkflow = await res.json();
      setWorkflow(updated);
      setEditDraftText(updated.active_draft_version?.content || "");
      setShowRegenBox(false);
      setStatusBanner("AI đã sinh lại (Regenerate) bản nháp tài liệu mới.");
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi sinh lại bản nháp.");
    } finally {
      setLoading(false);
    }
  };

  const handleRollback = async (targetVersionId: string, versionLabel: string) => {
    if (!workflow) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/actions/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflow.workflow_id,
          target_version_id: targetVersionId,
          reason: `Khôi phục về ${versionLabel} từ giao diện kiểm duyệt`,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AutoDocWorkflow = await res.json();
      setWorkflow(updated);
      setEditDraftText(updated.current_published_version.content);
      setIsEditing(false);
      setStatusBanner(`Đã khôi phục (Rollback) tài liệu về nội dung của ${versionLabel}.`);
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi rollback phiên bản.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-5">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-semibold text-white">
                FE03 • Automatic Documentation Update on Code Change
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-0.5 font-mono text-xs text-slate-700">
                Engine: {workflow?.engine_used || "loading..."}
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Event-Triggered Auto-Doc Workflow & Side-by-Side Diff Review
            </h1>
            <p className="text-sm text-slate-500">
              Tự động sinh bản nháp tài liệu khi có PR/Commit mới (FE03.1), đối chiếu song song
              Code-vs-Doc (FE03.2) và hỗ trợ Accept, Edit, Regenerate, Rollback (FE03.3).
            </p>
          </div>

          <a
            href="/multimodal-demo"
            className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
          >
            ← Quay lại FE05 Multimodal
          </a>
        </div>

        {/* FE03.1: Event Trigger Bar */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              FE03.1 • Mô phỏng sự kiện Pull Request / Git Commit kích hoạt cập nhật tài liệu
            </span>
            <span className="font-mono text-xs text-slate-400">
              Webhook: POST /api/v1/auto-doc/github-webhook
            </span>
          </div>

          <div className="flex flex-wrap gap-2.5">
            {PRESET_EVENTS.map((p) => (
              <button
                key={p.id}
                onClick={() => triggerPreset(p)}
                className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
                  selectedPresetId === p.id
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span>{p.label}</span>
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${
                    selectedPresetId === p.id
                      ? "bg-slate-700 text-slate-200"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {p.badge}
                </span>
              </button>
            ))}
          </div>
        </div>

        {errorMsg && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <strong>Lỗi:</strong> {errorMsg}
          </div>
        )}

        {statusBanner && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
            {statusBanner}
          </div>
        )}

        {loading && (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700">
            Đang xử lý quy trình cập nhật tài liệu tự động...
          </div>
        )}

        {workflow && (
          <>
            {/* KPI Summary Row */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Sự kiện kích hoạt</div>
                <div className="mt-1 font-mono text-base font-bold text-slate-900">
                  {workflow.pr_number ? `PR #${workflow.pr_number}` : `Commit ${workflow.commit_sha}`}
                </div>
                <div className="mt-1 truncate text-xs text-slate-400">
                  {workflow.branch} • @{workflow.author}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Phiên bản đang phát hành</div>
                <div className="mt-1 font-mono text-xl font-bold text-emerald-600">
                  {workflow.current_published_version.version_number}
                </div>
                <div className="mt-1 truncate font-mono text-xs text-slate-400">
                  {workflow.target_doc_path}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Bản nháp chờ duyệt (Draft)</div>
                <div className="mt-1 font-mono text-xl font-bold text-indigo-600">
                  {workflow.active_draft_version
                    ? workflow.active_draft_version.version_number
                    : "Đã đồng bộ"}
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  +{workflow.comparison.added_lines} dòng / -{workflow.comparison.removed_lines} dòng
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Thay đổi Code phát hiện</div>
                <div className="mt-1 text-xl font-bold text-amber-600">
                  {workflow.comparison.code_changes_detected.length} symbols
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  Đã ánh xạ sang tài liệu tự động
                </div>
              </div>
            </div>

            {/* Code Diff vs Documentation Impact Box */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-slate-900 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-white">
                  MÃ NGUỒN THAY ĐỔI (GIT DIFF TRIGGER)
                </div>
                <pre className="max-h-48 overflow-auto bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-200">
                  {workflow.code_diff.split("\n").map((line, i) => (
                    <div
                      key={i}
                      className={
                        line.startsWith("+")
                          ? "bg-emerald-950/60 text-emerald-300"
                          : line.startsWith("-")
                          ? "bg-rose-950/60 text-rose-300"
                          : "text-slate-400"
                      }
                    >
                      {line}
                    </div>
                  ))}
                </pre>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-slate-900 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-white">
                  PHÂN TÍCH TÁC ĐỘNG SANG TÀI LIỆU (CODE-VS-DOC MAPPING)
                </div>
                <div className="space-y-2 p-4 text-xs">
                  {workflow.comparison.doc_impact_points.map((pt, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2 text-slate-800"
                    >
                      {pt}
                    </div>
                  ))}
                  {workflow.active_draft_version?.change_summary && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-600">
                      <strong>Tóm tắt AI:</strong> {workflow.active_draft_version.change_summary}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* FE03.3: Developer Action Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  FE03.3 • Kiểm duyệt phiên bản:
                </span>
                <div className="flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs">
                  <button
                    onClick={() => setViewMode("side_by_side")}
                    className={`rounded-md px-2.5 py-1 font-semibold transition ${
                      viewMode === "side_by_side"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600"
                    }`}
                  >
                    Side-by-Side Diff
                  </button>
                  <button
                    onClick={() => setViewMode("preview")}
                    className={`rounded-md px-2.5 py-1 font-semibold transition ${
                      viewMode === "preview"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600"
                    }`}
                  >
                    Xem văn bản hoàn chỉnh
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={handleAcceptDraft}
                  disabled={!workflow.active_draft_version || loading}
                  className="rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ✓ Accept Draft
                </button>

                <button
                  onClick={() => {
                    setEditDraftText(
                      workflow.active_draft_version?.content ||
                        workflow.current_published_version.content
                    );
                    setIsEditing(!isEditing);
                  }}
                  className="rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-50"
                >
                  ✎ {isEditing ? "Đóng trình sửa" : "Edit Draft"}
                </button>

                <button
                  onClick={() => setShowRegenBox(!showRegenBox)}
                  className="rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700"
                >
                  ↻ Regenerate
                </button>
              </div>
            </div>

            {/* Regenerate Prompt Drawer */}
            {showRegenBox && (
              <div className="rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4 space-y-3">
                <div className="text-xs font-bold uppercase text-indigo-800">
                  Yêu cầu AI sinh lại bản nháp với chỉ dẫn bổ sung (Regenerate)
                </div>
                <div className="flex flex-wrap gap-2">
                  <input
                    type="text"
                    value={regenPrompt}
                    onChange={(e) => setRegenPrompt(e.target.value)}
                    placeholder="Ví dụ: Bổ sung ví dụ cURL và mô tả chi tiết tham số repo_path..."
                    className="flex-1 rounded-xl border border-indigo-200 bg-white px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
                  />
                  <button
                    onClick={handleRegenerate}
                    className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
                  >
                    Chạy Regenerate
                  </button>
                </div>
              </div>
            )}

            {/* Inline Draft Editor */}
            {isEditing && (
              <div className="rounded-2xl border border-amber-200 bg-white p-4 shadow-sm space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase text-slate-700">
                    Chỉnh sửa trực tiếp nội dung Markdown (Edit Draft)
                  </span>
                  <input
                    type="text"
                    value={editorNote}
                    onChange={(e) => setEditorNote(e.target.value)}
                    placeholder="Ghi chú chỉnh sửa..."
                    className="w-72 rounded-lg border border-slate-200 px-2.5 py-1 text-xs"
                  />
                </div>
                <textarea
                  rows={10}
                  value={editDraftText}
                  onChange={(e) => setEditDraftText(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-slate-950 p-3.5 font-mono text-xs text-emerald-300 focus:border-indigo-500 focus:outline-none"
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setIsEditing(false)}
                    className="rounded-xl border border-slate-200 px-3.5 py-1.5 text-xs font-semibold text-slate-600"
                  >
                    Hủy
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    className="rounded-xl bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
                  >
                    Lưu chỉnh sửa & Cập nhật Diff
                  </button>
                </div>
              </div>
            )}

            {/* FE03.2: Side-by-Side Version Comparison Viewer */}
            {viewMode === "side_by_side" ? (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="grid grid-cols-2 bg-slate-900 text-xs font-bold uppercase tracking-wider text-white">
                  <div className="border-r border-slate-700 px-4 py-3">
                    PHIÊN BẢN HIỆN HÀNH ({workflow.current_published_version.version_number})
                  </div>
                  <div className="px-4 py-3 text-emerald-300">
                    BẢN NHÁP CẬP NHẬT (
                    {workflow.active_draft_version
                      ? workflow.active_draft_version.version_number
                      : `${workflow.current_published_version.version_number} • Đã phát hành`}
                    )
                  </div>
                </div>

                <div className="divide-y divide-slate-100 font-mono text-xs">
                  {workflow.comparison.side_by_side_diff.map((row, idx) => {
                    const leftBg =
                      row.line_type === "removed" || row.line_type === "modified"
                        ? "bg-rose-50 text-rose-900"
                        : "bg-white text-slate-700";
                    const rightBg =
                      row.line_type === "added" || row.line_type === "modified"
                        ? "bg-emerald-50 text-emerald-900"
                        : "bg-white text-slate-700";

                    return (
                      <div key={idx} className="grid grid-cols-2">
                        <div className={`flex border-r border-slate-200 px-3 py-1.5 ${leftBg}`}>
                          <span className="w-8 shrink-0 select-none text-slate-400">
                            {row.old_line_num ?? ""}
                          </span>
                          <span className="whitespace-pre-wrap break-words">{row.old_text}</span>
                        </div>
                        <div className={`flex px-3 py-1.5 ${rightBg}`}>
                          <span className="w-8 shrink-0 select-none text-slate-400">
                            {row.new_line_num ?? ""}
                          </span>
                          <span className="whitespace-pre-wrap break-words">{row.new_text}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  NỘI DUNG TÀI LIỆU MỚI NHẤT
                </div>
                <pre className="whitespace-pre-wrap p-5 font-mono text-xs leading-relaxed text-slate-800">
                  {workflow.active_draft_version?.content ||
                    workflow.current_published_version.content}
                </pre>
              </div>
            )}

            {/* FE03.3: Version History & Rollback Timeline */}
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                <span>LỊCH SỬ PHIÊN BẢN TÀI LIỆU & ROLLBACK</span>
                <span className="text-slate-300">{workflow.version_history.length} phiên bản</span>
              </div>

              <div className="divide-y divide-slate-100 p-4">
                {[...workflow.version_history].reverse().map((ver) => (
                  <div
                    key={ver.version_id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-slate-900">
                          {ver.version_number}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                            ver.status === "published"
                              ? "bg-emerald-100 text-emerald-800"
                              : ver.status === "draft"
                              ? "bg-indigo-100 text-indigo-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {ver.status}
                        </span>
                        <span className="text-xs text-slate-500">
                          {ver.trigger_ref} • {ver.created_at}
                        </span>
                      </div>
                      <div className="text-xs text-slate-600">{ver.change_summary}</div>
                    </div>

                    {ver.status !== "published" && ver.status !== "draft" && (
                      <button
                        onClick={() => handleRollback(ver.version_id, ver.version_number)}
                        className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
                      >
                        ↺ Rollback về {ver.version_number}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}