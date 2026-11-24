"use client";

import React, { useEffect, useMemo, useState } from "react";

interface CodeDiffLine {
  line_index: number;
  line_type: "context" | "added" | "removed" | "hunk_header";
  old_line_num: number | null;
  new_line_num: number | null;
  content: string;
  file_path: string;
  evidence_ids: string[];
}

interface DocPatchLine {
  line_index: number;
  line_type: "context" | "added" | "removed" | "hunk_header";
  old_doc_line_num: number | null;
  new_doc_line_num: number | null;
  content: string;
  evidence_ids: string[];
}

interface DiffMappingLink {
  link_id: string;
  evidence_id: string;
  code_file_path: string;
  code_line_indices: number[];
  doc_line_indices: number[];
  rationale: string;
  confidence: number;
}

interface GroundingEvidenceItem {
  evidence_id: string;
  claim_summary: string;
  symbol_name: string;
  symbol_kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  commit_hash: string;
  commit_short: string;
  commit_message: string;
  commit_author: string;
  commit_date: string;
  branch: string;
  code_snippet: string;
  doc_patch_excerpt: string;
  repo_grounding_status: "VERIFIED_IN_REPO" | "VERIFIED_IN_GIT" | "PATCH_PREVIEW";
  repo_actual_excerpt: string;
  reviewer_status: "pending" | "verified" | "flagged";
  reviewer_note: string;
}

interface GroundingDiffSession {
  session_id: string;
  preset_id: string;
  title: string;
  repo_name: string;
  branch: string;
  commit_hash: string;
  pr_number: number | null;
  target_doc_path: string;
  source_code_files: string[];
  code_diff_lines: CodeDiffLine[];
  doc_patch_lines: DocPatchLine[];
  mapping_links: DiffMappingLink[];
  evidences: GroundingEvidenceItem[];
  grounding_coverage_score: number;
  verified_count: number;
  flagged_count: number;
  pending_count: number;
}

const API_BASE = "http://localhost:8000/api/v1/grounding-diff";

const PRESETS = [
  {
    id: "live_fe05_multimodal",
    label: "1. PR #42: FE05.3 Consistency Endpoint (Live Repo Grounding)",
    badge: "Verified in Repo",
  },
  {
    id: "fe03_auto_doc",
    label: "2. Commit 8c3d91a: FE03 Webhook & Rollback Patch",
    badge: "Verified in Repo",
  },
  {
    id: "auth_token_rotation",
    label: "3. PR #51: JWT Refresh Token Rotation (Unmerged PR)",
    badge: "PR Patch Preview",
  },
];

// ==================== FE09.1: SIDE-BY-SIDE VISUAL CODE VS DOC DIFF COMPONENT ====================

function SideBySideCodeVsDocDiffViewer({
  session,
  activeEvidenceId,
  onSelectEvidence,
}: {
  session: GroundingDiffSession;
  activeEvidenceId: string | null;
  onSelectEvidence: (evId: string) => void;
}) {
  const [onlyChanged, setOnlyChanged] = useState<boolean>(false);
  const [selectedFileFilter, setSelectedFileFilter] = useState<string>("ALL");

  const activeLink = useMemo(
    () => session.mapping_links.find((l) => l.evidence_id === activeEvidenceId) || null,
    [session.mapping_links, activeEvidenceId]
  );

  const visibleCodeLines = useMemo(() => {
    return session.code_diff_lines.filter((line) => {
      if (selectedFileFilter !== "ALL" && line.file_path !== selectedFileFilter) {
        return false;
      }
      if (onlyChanged && line.line_type === "context") {
        return false;
      }
      return true;
    });
  }, [session.code_diff_lines, selectedFileFilter, onlyChanged]);

  const visibleDocLines = useMemo(() => {
    return session.doc_patch_lines.filter((line) => {
      if (onlyChanged && line.line_type === "context") {
        return false;
      }
      return true;
    });
  }, [session.doc_patch_lines, onlyChanged]);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Component Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <span className="rounded bg-indigo-500 px-2 py-0.5 font-mono text-[11px] font-bold">
            FE09.1
          </span>
          <span className="text-xs font-bold uppercase tracking-wider">
            Side-by-Side Visual Code Diff vs Suggested Documentation Patch
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select
            value={selectedFileFilter}
            onChange={(e) => setSelectedFileFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-200 focus:outline-none"
          >
            <option value="ALL">Tất cả tệp code ({session.source_code_files.length})</option>
            {session.source_code_files.map((fp) => (
              <option key={fp} value={fp}>
                {fp}
              </option>
            ))}
          </select>

          <button
            onClick={() => setOnlyChanged(!onlyChanged)}
            className={`rounded-lg border px-2.5 py-1 font-semibold transition ${
              onlyChanged
                ? "border-indigo-400 bg-indigo-600 text-white"
                : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {onlyChanged ? "Đang lọc: Chỉ dòng +/-" : "Hiển thị tất cả dòng"}
          </button>
        </div>
      </div>

      {/* Active Correlation Banner */}
      {activeLink && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-200 bg-indigo-50 px-4 py-2 text-xs text-indigo-950">
          <div className="flex items-center gap-2">
            <span className="rounded bg-indigo-600 px-2 py-0.5 font-mono font-bold text-white">
              {activeLink.evidence_id}
            </span>
            <span>
              <strong>Lý do ánh xạ:</strong> {activeLink.rationale}
            </span>
          </div>
          <span className="font-mono text-[11px] font-semibold text-indigo-700">
            Độ tin cậy: {Math.round(activeLink.confidence * 100)}%
          </span>
        </div>
      )}

      {/* Dual Split Panes */}
      <div className="grid grid-cols-1 divide-y divide-slate-200 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        {/* LEFT PANE: MODIFIED SOURCE CODE DIFF */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-3.5 py-2 text-xs font-bold text-slate-700">
            <span>MODIFIED SOURCE CODE DIFF (GIT HUNK)</span>
            <span className="font-mono text-[11px] text-slate-500">
              {session.commit_hash.slice(0, 7)}
            </span>
          </div>

          <div className="max-h-[430px] overflow-auto divide-y divide-slate-100 font-mono text-xs">
            {visibleCodeLines.map((line) => {
              const isLinked =
                Boolean(activeEvidenceId) && line.evidence_ids.includes(activeEvidenceId!);

              if (line.line_type === "hunk_header") {
                return (
                  <div
                    key={line.line_index}
                    className="bg-slate-800 px-3 py-1.5 text-[11px] font-semibold text-sky-300"
                  >
                    {line.content}
                  </div>
                );
              }

              const bgClass = isLinked
                ? "bg-amber-100/90 ring-1 ring-inset ring-amber-400"
                : line.line_type === "added"
                ? "bg-emerald-50/80 text-emerald-950"
                : line.line_type === "removed"
                ? "bg-rose-50/80 text-rose-950"
                : "bg-white text-slate-700";

              return (
                <div
                  key={line.line_index}
                  onClick={() => {
                    if (line.evidence_ids.length > 0) {
                      onSelectEvidence(line.evidence_ids[0]);
                    }
                  }}
                  className={`flex items-start justify-between gap-2 px-2.5 py-1.5 transition ${bgClass} ${
                    line.evidence_ids.length > 0 ? "cursor-pointer hover:brightness-95" : ""
                  }`}
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <span className="w-7 shrink-0 select-none text-right text-[11px] text-slate-400">
                      {line.old_line_num ?? ""}
                    </span>
                    <span className="w-7 shrink-0 select-none text-right text-[11px] text-slate-400">
                      {line.new_line_num ?? ""}
                    </span>
                    <span className="whitespace-pre-wrap break-words">{line.content}</span>
                  </div>

                  {line.evidence_ids.length > 0 && (
                    <div className="flex shrink-0 gap-1">
                      {line.evidence_ids.map((evId) => (
                        <span
                          key={evId}
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            activeEvidenceId === evId
                              ? "bg-amber-500 text-white"
                              : "bg-indigo-100 text-indigo-800"
                          }`}
                        >
                          {evId}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT PANE: SUGGESTED DOCUMENTATION PATCH */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-3.5 py-2 text-xs font-bold text-slate-700">
            <span>SUGGESTED DOCUMENTATION PATCH</span>
            <span className="truncate font-mono text-[11px] text-indigo-700">
              {session.target_doc_path}
            </span>
          </div>

          <div className="max-h-[430px] overflow-auto divide-y divide-slate-100 font-mono text-xs">
            {visibleDocLines.map((line) => {
              const isLinked =
                Boolean(activeEvidenceId) && line.evidence_ids.includes(activeEvidenceId!);

              if (line.line_type === "hunk_header") {
                return (
                  <div
                    key={line.line_index}
                    className="bg-slate-800 px-3 py-1.5 text-[11px] font-semibold text-indigo-300"
                  >
                    {line.content}
                  </div>
                );
              }

              const bgClass = isLinked
                ? "bg-amber-100/90 ring-1 ring-inset ring-amber-400"
                : line.line_type === "added"
                ? "bg-emerald-50/80 text-emerald-950"
                : line.line_type === "removed"
                ? "bg-rose-50/80 text-rose-950"
                : "bg-white text-slate-700";

              return (
                <div
                  key={line.line_index}
                  onClick={() => {
                    if (line.evidence_ids.length > 0) {
                      onSelectEvidence(line.evidence_ids[0]);
                    }
                  }}
                  className={`flex items-start justify-between gap-2 px-2.5 py-1.5 transition ${bgClass} ${
                    line.evidence_ids.length > 0 ? "cursor-pointer hover:brightness-95" : ""
                  }`}
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <span className="w-7 shrink-0 select-none text-right text-[11px] text-slate-400">
                      {line.old_doc_line_num ?? ""}
                    </span>
                    <span className="w-7 shrink-0 select-none text-right text-[11px] text-slate-400">
                      {line.new_doc_line_num ?? ""}
                    </span>
                    <span className="whitespace-pre-wrap break-words">{line.content}</span>
                  </div>

                  {line.evidence_ids.length > 0 && (
                    <div className="flex shrink-0 gap-1">
                      {line.evidence_ids.map((evId) => (
                        <span
                          key={evId}
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            activeEvidenceId === evId
                              ? "bg-amber-500 text-white"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {evId}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== FE09.2: GROUNDING EVIDENCE NAVIGATOR COMPONENT ====================

function GroundingEvidenceNavigator({
  session,
  activeEvidenceId,
  onSelectEvidence,
  onVerifyEvidence,
  submitting,
}: {
  session: GroundingDiffSession;
  activeEvidenceId: string | null;
  onSelectEvidence: (evId: string) => void;
  onVerifyEvidence: (evId: string, status: "verified" | "flagged" | "pending", note: string) => void;
  submitting: boolean;
}) {
  const [statusFilter, setStatusFilter] = useState<"ALL" | "pending" | "verified" | "flagged">(
    "ALL"
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const filteredEvidences = useMemo(() => {
    return session.evidences.filter((ev) => {
      if (statusFilter !== "ALL" && ev.reviewer_status !== statusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const haystack =
          `${ev.evidence_id} ${ev.file_path} ${ev.symbol_name} ${ev.commit_hash} ${ev.claim_summary}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [session.evidences, statusFilter, searchQuery]);

  const copyText = (key: string, value: string) => {
    navigator.clipboard?.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Navigator Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <span className="rounded bg-emerald-500 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-950">
            FE09.2
          </span>
          <span className="text-xs font-bold uppercase tracking-wider">
            Grounding Evidence Navigator (Source File Path, Line Numbers & Commit Hash)
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {(["ALL", "pending", "verified", "flagged"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-2.5 py-1 font-semibold uppercase transition ${
                statusFilter === st
                  ? "bg-white text-slate-900"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Search Bar */}
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Tìm kiếm theo đường dẫn tệp (file path), tên hàm/endpoint, mã commit hash hoặc nội dung..."
          className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      {/* Evidence Cards */}
      <div className="divide-y divide-slate-200">
        {filteredEvidences.map((ev) => {
          const isSelected = activeEvidenceId === ev.evidence_id;
          const currentNote = noteDrafts[ev.evidence_id] ?? ev.reviewer_note ?? "";

          return (
            <div
              key={ev.evidence_id}
              onClick={() => onSelectEvidence(ev.evidence_id)}
              className={`cursor-pointer p-5 transition ${
                isSelected ? "bg-amber-50/60" : "bg-white hover:bg-slate-50/70"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-xs font-bold text-white">
                      {ev.evidence_id}
                    </span>
                    <span className="rounded-md bg-indigo-100 px-2 py-0.5 font-mono text-[11px] font-bold uppercase text-indigo-800">
                      {ev.symbol_kind}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                        ev.repo_grounding_status === "VERIFIED_IN_REPO"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {ev.repo_grounding_status}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase ${
                        ev.reviewer_status === "verified"
                          ? "bg-emerald-600 text-white"
                          : ev.reviewer_status === "flagged"
                          ? "bg-rose-600 text-white"
                          : "bg-slate-200 text-slate-700"
                      }`}
                    >
                      Reviewer: {ev.reviewer_status}
                    </span>
                  </div>

                  <div className="text-sm font-bold text-slate-900">{ev.claim_summary}</div>
                </div>

                {/* Reviewer Action Buttons */}
                <div
                  className="flex items-center gap-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    disabled={submitting}
                    onClick={() => onVerifyEvidence(ev.evidence_id, "verified", currentNote)}
                    className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
                  >
                    ✓ Verify Grounding
                  </button>
                  <button
                    disabled={submitting}
                    onClick={() => onVerifyEvidence(ev.evidence_id, "flagged", currentNote)}
                    className="rounded-xl bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700 disabled:opacity-50"
                  >
                    ⚑ Flag Drift
                  </button>
                </div>
              </div>

              {/* Metadata Grid: File Path, Line Numbers, Commit Hash */}
              <div className="mt-3 grid grid-cols-1 gap-2.5 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs md:grid-cols-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase text-slate-400">
                    Source File Path
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 font-mono font-semibold text-slate-900">
                    <span className="truncate">{ev.file_path}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyText(`${ev.evidence_id}_path`, `${ev.file_path}:${ev.start_line}`);
                      }}
                      className="shrink-0 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-600 hover:bg-slate-100"
                    >
                      {copiedKey === `${ev.evidence_id}_path` ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>

                <div>
                  <div className="text-[11px] font-semibold uppercase text-slate-400">
                    Exact Line Range
                  </div>
                  <div className="mt-0.5 font-mono font-bold text-indigo-700">
                    Lines L{ev.start_line} – L{ev.end_line} ({ev.symbol_name})
                  </div>
                </div>

                <div>
                  <div className="text-[11px] font-semibold uppercase text-slate-400">
                    Commit Hash & Branch
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 font-mono text-slate-900">
                    <span className="truncate" title={ev.commit_hash}>
                      <strong>{ev.commit_short}</strong> ({ev.branch})
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyText(`${ev.evidence_id}_sha`, ev.commit_hash);
                      }}
                      className="shrink-0 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-600 hover:bg-slate-100"
                    >
                      {copiedKey === `${ev.evidence_id}_sha` ? "Copied" : "SHA"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Commit Details & Real Repository Code Evidence */}
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs space-y-1">
                  <div className="font-bold text-slate-700">
                    Thông tin Commit ({ev.commit_short})
                  </div>
                  <div className="text-slate-600">
                    <strong>Message:</strong> {ev.commit_message}
                  </div>
                  <div className="text-slate-500">
                    <strong>Author:</strong> {ev.commit_author} • <strong>Date:</strong>{" "}
                    {ev.commit_date}
                  </div>
                  <div className="pt-1 text-slate-700">
                    <strong>Đoạn tài liệu được bảo chứng:</strong>{" "}
                    <span className="italic text-indigo-800">"{ev.doc_patch_excerpt}"</span>
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-xs">
                  <div className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5 text-[11px] font-semibold text-emerald-400">
                    <span>LIVE REPOSITORY CODE EVIDENCE ({ev.file_path})</span>
                    <span>L{ev.start_line}..L{ev.end_line}</span>
                  </div>
                  <pre className="max-h-36 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-slate-200">
                    {ev.repo_actual_excerpt || ev.code_snippet}
                  </pre>
                </div>
              </div>

              {/* Reviewer Note Input */}
              <div
                className="mt-3 flex items-center gap-2"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="text"
                  value={currentNote}
                  onChange={(e) =>
                    setNoteDrafts((prev) => ({ ...prev, [ev.evidence_id]: e.target.value }))
                  }
                  placeholder="Ghi chú kiểm duyệt của reviewer cho bằng chứng này..."
                  className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ==================== MAIN PAGE: FE09 INTERACTIVE VIEWER ====================

export default function GroundingDiffViewerPage() {
  const [selectedPresetId, setSelectedPresetId] = useState<string>("live_fe05_multimodal");
  const [session, setSession] = useState<GroundingDiffSession | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);

  const [showCustomModal, setShowCustomModal] = useState<boolean>(false);
  const [customDiff, setCustomDiff] = useState<string>(
    [
      "diff --git a/backend/app/api/grounding_diff.py b/backend/app/api/grounding_diff.py",
      "@@ -12,3 +12,6 @@",
      "+@router.post('/verify-evidence', response_model=GroundingDiffSessionResponse)",
      "+async def verify_grounding_evidence(request: VerifyGroundingEvidenceRequest):",
    ].join("\n")
  );
  const [customDocPatch, setCustomDocPatch] = useState<string>(
    [
      "@@ -1,2 +1,4 @@",
      "+- `POST /api/v1/grounding-diff/verify-evidence`: Xác nhận hoặc gắn cờ bằng chứng mã nguồn.",
    ].join("\n")
  );

  const [loading, setLoading] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadPresetSession = async (presetId: string) => {
    setSelectedPresetId(presetId);
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: presetId }),
      });
      if (!res.ok) throw new Error(`API lỗi ${res.status}: ${await res.text()}`);
      const data: GroundingDiffSession = await res.json();
      setSession(data);
      setActiveEvidenceId(data.evidences[0]?.evidence_id || null);
    } catch (err: any) {
      setErrorMsg(err?.message || "Không thể tải dữ liệu FE09 từ Backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeCustomDiff = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset_id: "custom",
          title: "Custom Code Diff vs Suggested Doc Patch Review",
          custom_code_diff: customDiff,
          custom_doc_patch: customDocPatch,
        }),
      });
      if (!res.ok) throw new Error(`API lỗi ${res.status}: ${await res.text()}`);
      const data: GroundingDiffSession = await res.json();
      setSession(data);
      setSelectedPresetId("custom");
      setActiveEvidenceId(data.evidences[0]?.evidence_id || null);
      setShowCustomModal(false);
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi phân tích custom diff.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEvidence = async (
    evidenceId: string,
    reviewerStatus: "verified" | "flagged" | "pending",
    reviewerNote: string
  ) => {
    if (!session) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/verify-evidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          evidence_id: evidenceId,
          reviewer_status: reviewerStatus,
          reviewer_note: reviewerNote,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: GroundingDiffSession = await res.json();
      setSession(updated);
      setActiveEvidenceId(evidenceId);
    } catch (err: any) {
      setErrorMsg(err?.message || "Lỗi khi cập nhật trạng thái bằng chứng.");
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    loadPresetSession("live_fe05_multimodal");
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-5">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-semibold text-white">
                FE09 • Interactive Code-vs-Doc Diff & Grounding Evidence Viewer
              </span>
              {session && (
                <span className="rounded-full bg-slate-100 px-3 py-0.5 font-mono text-xs text-slate-700">
                  Commit: {session.commit_hash.slice(0, 7)} • {session.branch}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Code-vs-Doc Patch Diff & Grounding Evidence Verifier
            </h1>
            <p className="text-sm text-slate-500">
              Đối chiếu trực quan từng dòng thay đổi mã nguồn với bản vá tài liệu đề xuất (FE09.1) và
              xác minh bằng chứng gốc qua File Path, Line Numbers và Commit Hash (FE09.2).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/multimodal-demo"
              className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              FE05 Multimodal
            </a>
            <a
              href="/auto-doc-update"
              className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              FE03 Auto-Doc
            </a>
          </div>
        </div>

        {/* Preset Selector Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => loadPresetSession(p.id)}
                className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
                  selectedPresetId === p.id
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span>{p.label}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    selectedPresetId === p.id
                      ? "bg-slate-700 text-emerald-300"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {p.badge}
                </span>
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowCustomModal(!showCustomModal)}
            className="rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
          >
            + Nhập Git Diff & Doc Patch tùy chỉnh
          </button>
        </div>

        {/* Custom Diff Input Drawer */}
        {showCustomModal && (
          <div className="rounded-2xl border border-indigo-200 bg-white p-5 shadow-sm space-y-3">
            <div className="text-xs font-bold uppercase text-indigo-800">
              Tạo phiên đối chiếu mới từ Git Code Diff và Suggested Doc Patch
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Source Code Git Diff
                </label>
                <textarea
                  rows={6}
                  value={customDiff}
                  onChange={(e) => setCustomDiff(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-emerald-300"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Suggested Documentation Patch
                </label>
                <textarea
                  rows={6}
                  value={customDocPatch}
                  onChange={(e) => setCustomDocPatch(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-sky-300"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCustomModal(false)}
                className="rounded-xl border border-slate-200 px-3.5 py-1.5 text-xs font-semibold text-slate-600"
              >
                Đóng
              </button>
              <button
                onClick={handleAnalyzeCustomDiff}
                className="rounded-xl bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                Phân tích & Đối chiếu Grounding
              </button>
            </div>
          </div>
        )}

        {errorMsg && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <strong>Lỗi:</strong> {errorMsg}
          </div>
        )}

        {loading && (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700">
            Đang đối chiếu mã nguồn và xác minh Grounding Evidence từ repository...
          </div>
        )}

        {session && (
          <>
            {/* KPI Summary Row */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Độ phủ bằng chứng (Grounding)</div>
                <div className="mt-1 text-2xl font-bold text-indigo-600">
                  {session.grounding_coverage_score}%
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {session.evidences.length} điểm neo mã nguồn
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Đã xác minh khớp (Verified)</div>
                <div className="mt-1 text-2xl font-bold text-emerald-600">
                  {session.verified_count} / {session.evidences.length}
                </div>
                <div className="mt-1 text-xs text-slate-400">Đã duyệt bởi reviewer</div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Chờ kiểm duyệt (Pending)</div>
                <div className="mt-1 text-2xl font-bold text-amber-600">
                  {session.pending_count}
                </div>
                <div className="mt-1 text-xs text-slate-400">Cần đối chiếu dòng code</div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Gắn cờ sai lệch (Flagged)</div>
                <div className="mt-1 text-2xl font-bold text-rose-600">
                  {session.flagged_count}
                </div>
                <div className="mt-1 text-xs text-slate-400">Yêu cầu chỉnh sửa patch</div>
              </div>
            </div>

            {/* FE09.1: Side-by-Side Visual Code vs Doc Diff UI Component */}
            <SideBySideCodeVsDocDiffViewer
              session={session}
              activeEvidenceId={activeEvidenceId}
              onSelectEvidence={(evId) => setActiveEvidenceId(evId)}
            />

            {/* FE09.2: Grounding Evidence Navigator */}
            <GroundingEvidenceNavigator
              session={session}
              activeEvidenceId={activeEvidenceId}
              onSelectEvidence={(evId) => setActiveEvidenceId(evId)}
              onVerifyEvidence={handleVerifyEvidence}
              submitting={submitting}
            />
          </>
        )}
      </div>
    </div>
  );
}