"use client";

import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000/api/v1/review-workflow";

interface VerificationCheck {
  check_name: string;
  passed: boolean;
  detail: string;
}

interface SectionComment {
  id: string;
  section_id: string;
  section_title: string;
  author: string;
  role: string;
  body: string;
  resolved: boolean;
  created_at: string;
}

interface ReviewItem {
  id: string;
  title: string;
  doc_type: string;
  target_path: string;
  source_ref: string;
  stage: string;
  assigned_staff: string;
  assigned_manager: string;
  template_sections: string[];
  content_markdown: string;
  checks: VerificationCheck[];
  comments: SectionComment[];
  publish_commit_hash?: string | null;
  published_at?: string | null;
  updated_at: string;
}

export default function ReviewWorkflowPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>("rev-fe07-001");
  const [stageFilter, setStageFilter] = useState<string>("all");
  const [sectionTitle, setSectionTitle] = useState<string>("API Endpoints");
  const [commentBody, setCommentBody] = useState<string>("");
  const [changeReason, setChangeReason] = useState<string>("");
  const [managerNote, setManagerNote] = useState<string>("");
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const loadItems = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/items`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ReviewItem[] = await res.json();
      setItems(data);
      if (data.length > 0 && !data.some((d) => d.id === selectedId)) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      setError(`Không tải được danh sách review: ${String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const filteredItems =
    stageFilter === "all" ? items : items.filter((i) => i.stage === stageFilter);

  const current =
    items.find((i) => i.id === selectedId) || filteredItems[0] || items[0] || null;

  const callAction = async (path: string, body?: object) => {
    if (!current) return;
    setError("");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/items/${current.id}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || `Lỗi HTTP ${res.status}`);
        return;
      }
      setItems((prev) => prev.map((it) => (it.id === data.id ? data : it)));
      setMessage(`Cập nhật thành công — Trạng thái hiện tại: ${data.stage}`);
    } catch (err) {
      setError(String(err));
    }
  };

  const toggleComment = async (commentId: string, resolved: boolean) => {
    if (!current) return;
    setError("");
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/items/${current.id}/comments/${commentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolved }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || `Lỗi HTTP ${res.status}`);
        return;
      }
      setItems((prev) => prev.map((it) => (it.id === data.id ? data : it)));
      setMessage(
        resolved ? "Đã đánh dấu comment là Resolved." : "Đã mở lại comment để xử lý."
      );
    } catch (err) {
      setError(String(err));
    }
  };

  const openCommentsCount = current
    ? current.comments.filter((c) => !c.resolved).length
    : 0;

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6 text-slate-900">
      <div className="rounded-xl border border-slate-200 p-5 bg-white text-slate-900 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
            FE07 • Governed 2-Tier Review & Approval Workflow
          </span>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">
            2-Tier Review & Publishing Workbench
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            9.1 Staff Queue & Template/Code Check • 9.2 Section Comments • 9.3 Manager Approval & Publish
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900"
          >
            <option value="all">Tất cả stage ({items.length})</option>
            <option value="staff_queue">staff_queue</option>
            <option value="changes_requested">changes_requested</option>
            <option value="manager_approval">manager_approval</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
            <option value="published">published</option>
          </select>
          <button
            onClick={loadItems}
            className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-medium text-slate-900 hover:bg-slate-200"
          >
            {loading ? "Đang tải..." : "Làm mới"}
          </button>
        </div>
      </div>

      {message && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {error}
        </div>
      )}

      {filteredItems.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {filteredItems.map((it) => {
            const active = current?.id === it.id;
            return (
              <button
                key={it.id}
                onClick={() => setSelectedId(it.id)}
                className={`rounded-lg border px-3 py-2 text-left text-xs transition ${
                  active
                    ? "border-indigo-600 bg-indigo-50 text-indigo-950 font-semibold"
                    : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
                }`}
              >
                <div>{it.title}</div>
                <div className="text-[11px] text-slate-600 mt-0.5">
                  ID: {it.id} • Stage: <strong>{it.stage}</strong>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {current && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 9.1 Staff Verification */}
            <div className="rounded-xl border border-slate-200 p-4 bg-white text-slate-900 shadow-sm space-y-3">
              <h2 className="font-semibold text-base text-slate-900">9.1 Staff Verification</h2>
              <p className="text-sm font-semibold text-slate-900">{current.title}</p>
              <div className="text-xs text-slate-700 space-y-1">
                <p>
                  Stage: <strong className="text-slate-900">{current.stage}</strong>
                </p>
                <p>
                  File: <span className="font-mono text-slate-900">{current.target_path}</span>
                </p>
                <p>
                  Open Comments: <strong className="text-slate-900">{openCommentsCount}</strong>
                </p>
              </div>
              <button
                onClick={() => callAction("/verify", {})}
                className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Chạy kiểm tra Template & Code
              </button>
              <div className="space-y-1.5 pt-1">
                {current.checks.length === 0 ? (
                  <p className="text-xs text-slate-600">
                    Chưa chạy kiểm tra. Bấm nút phía trên để đối chiếu template sections.
                  </p>
                ) : (
                  current.checks.map((chk, idx) => (
                    <div
                      key={idx}
                      className="text-xs rounded border border-slate-200 bg-slate-50 p-2 flex items-center justify-between gap-2 text-slate-900"
                    >
                      <span className="font-medium text-slate-900">{chk.check_name}</span>
                      <span
                        className={
                          chk.passed
                            ? "text-emerald-700 font-semibold shrink-0"
                            : "text-rose-700 font-semibold shrink-0"
                        }
                      >
                        {chk.passed ? "PASS" : "FAIL"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 9.2 Section Comments */}
            <div className="rounded-xl border border-slate-200 p-4 bg-white text-slate-900 shadow-sm space-y-3">
              <h2 className="font-semibold text-base text-slate-900">9.2 Section Comments</h2>
              <input
                value={sectionTitle}
                onChange={(e) => setSectionTitle(e.target.value)}
                placeholder="Tên section (vd: API Endpoints)"
                className="w-full rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-500"
              />
              <textarea
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
                placeholder="Nhập nhận xét theo section..."
                rows={2}
                className="w-full rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-500"
              />
              <button
                onClick={() => {
                  if (!commentBody.trim()) return;
                  callAction("/comments", {
                    section_id: sectionTitle.toLowerCase().trim().replace(/\s+/g, "-"),
                    section_title: sectionTitle.trim() || "General",
                    body: commentBody.trim(),
                  });
                  setCommentBody("");
                }}
                className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Thêm Section Comment
              </button>

              <div className="pt-2 border-t border-slate-200 space-y-2">
                <input
                  value={changeReason}
                  onChange={(e) => setChangeReason(e.target.value)}
                  placeholder="Lý do yêu cầu chỉnh sửa (Request Changes)..."
                  className="w-full rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-500"
                />
                <button
                  onClick={() => {
                    if (!changeReason.trim()) return;
                    callAction("/request-changes", { reason: changeReason.trim() });
                    setChangeReason("");
                  }}
                  className="w-full rounded-lg border border-amber-400 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                >
                  Trả lại yêu cầu chỉnh sửa (Request Changes)
                </button>
              </div>

              <div className="space-y-2 pt-1 max-h-56 overflow-auto">
                {current.comments.map((cmt) => (
                  <div
                    key={cmt.id}
                    className="rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-900 space-y-1"
                  >
                    <div className="flex justify-between font-semibold text-slate-900">
                      <span>
                        [{cmt.section_title}] {cmt.author}
                      </span>
                      <span className={cmt.resolved ? "text-emerald-700" : "text-amber-700"}>
                        {cmt.resolved ? "Resolved" : "Open"}
                      </span>
                    </div>
                    <p className="text-slate-800">{cmt.body}</p>
                    <button
                      onClick={() => toggleComment(cmt.id, !cmt.resolved)}
                      className="text-indigo-700 font-medium underline"
                    >
                      {cmt.resolved ? "Mở lại" : "Đánh dấu Resolved"}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* 9.3 Manager Approval & Publish */}
            <div className="rounded-xl border border-slate-200 p-4 bg-white text-slate-900 shadow-sm space-y-3">
              <h2 className="font-semibold text-base text-slate-900">9.3 Manager & Publish</h2>
              <button
                onClick={() => callAction("/forward-to-manager", {})}
                className="w-full rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-500"
              >
                Chuyển tiếp lên Manager
              </button>
              <input
                value={managerNote}
                onChange={(e) => setManagerNote(e.target.value)}
                placeholder="Ghi chú quyết định của Manager..."
                className="w-full rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-500"
              />
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() =>
                    callAction("/manager-decision", {
                      decision: "approve",
                      note: managerNote,
                    })
                  }
                  className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
                >
                  Approve
                </button>
                <button
                  onClick={() =>
                    callAction("/manager-decision", {
                      decision: "reject",
                      note: managerNote,
                    })
                  }
                  className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-500"
                >
                  Reject
                </button>
              </div>
              <button
                onClick={() => callAction("/publish", { target_branch: "main" })}
                className="w-full rounded-lg bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-600"
              >
                Commit & Publish
              </button>
              {current.publish_commit_hash && (
                <div className="rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900 space-y-0.5">
                  <p className="font-semibold">
                    Published commit: <span className="font-mono">{current.publish_commit_hash}</span>
                  </p>
                  {current.published_at && <p>Time: {current.published_at}</p>}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 p-4 bg-white text-slate-900 shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm text-slate-900">
                Bản nháp tài liệu ({current.target_path})
              </h3>
              <span className="text-xs text-slate-600">Source ref: {current.source_ref}</span>
            </div>
            <pre className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-900 overflow-x-auto whitespace-pre-wrap">
              {current.content_markdown}
            </pre>
          </div>
        </>
      )}
    </div>
  );
}