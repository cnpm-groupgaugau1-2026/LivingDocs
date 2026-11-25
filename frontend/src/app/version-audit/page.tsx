"use client";

import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000/api/v1/version-audit";

type ActorRole = "AI" | "Staff" | "Manager";

interface VersionEntry {
  version_id: string;
  version_number: number;
  doc_path: string;
  content_markdown: string;
  summary: string;
  actor_role: ActorRole;
  actor_name: string;
  trigger_event: string;
  trigger_commit_hash: string;
  rollback_from_version?: number | null;
  prev_hash: string;
  entry_hash: string;
  created_at: string;
}

interface DocumentAuditTrail {
  doc_id: string;
  title: string;
  doc_path: string;
  current_version: number;
  entries: VersionEntry[];
}

interface ChainVerificationResult {
  doc_id: string;
  valid: boolean;
  checked_entries: number;
  broken_at_version?: number | null;
  message: string;
}

export default function VersionAuditPage() {
  const [docs, setDocs] = useState<DocumentAuditTrail[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("doc-fe08-001");
  const [roleFilter, setRoleFilter] = useState<string>("ALL");
  const [actorRole, setActorRole] = useState<ActorRole>("Staff");
  const [actorName, setActorName] = useState<string>("staff.reviewer");
  const [summary, setSummary] = useState<string>("");
  const [contentMarkdown, setContentMarkdown] = useState<string>("");
  const [rollbackReason, setRollbackReason] = useState<string>(
    "Khôi phục lại phiên bản chuẩn đã kiểm duyệt"
  );
  const [chainResult, setChainResult] = useState<ChainVerificationResult | null>(null);
  const [banner, setBanner] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const loadDocs = async () => {
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/documents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DocumentAuditTrail[] = await res.json();
      setDocs(data);
      const active = data.find((d) => d.doc_id === selectedDocId) || data[0];
      if (active) {
        setSelectedDocId(active.doc_id);
        const latest = active.entries[active.entries.length - 1];
        if (latest && !contentMarkdown) {
          setContentMarkdown(latest.content_markdown);
        }
      }
    } catch (err) {
      setErrorMsg(String(err));
    }
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const currentDoc =
    docs.find((d) => d.doc_id === selectedDocId) || docs[0] || null;

  const visibleEntries = currentDoc
    ? [...currentDoc.entries]
        .reverse()
        .filter((e) => (roleFilter === "ALL" ? true : e.actor_role === roleFilter))
    : [];

  const handleVerifyChain = async () => {
    if (!currentDoc) return;
    setErrorMsg("");
    const res = await fetch(`${API_BASE}/documents/${currentDoc.doc_id}/verify-chain`);
    if (res.ok) {
      setChainResult(await res.json());
    } else {
      setErrorMsg("Không xác minh được chuỗi băm phiên bản.");
    }
  };

  const handleCreateVersion = async () => {
    if (!currentDoc || !summary.trim() || !contentMarkdown.trim()) return;
    setErrorMsg("");
    setBanner("");
    const res = await fetch(`${API_BASE}/documents/${currentDoc.doc_id}/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_markdown: contentMarkdown,
        summary: summary.trim(),
        actor_role: actorRole,
        actor_name: actorName.trim() || actorRole.toLowerCase(),
        trigger_event: "ui_version_update",
      }),
    });
    if (res.ok) {
      const updated: DocumentAuditTrail = await res.json();
      setDocs((prev) => prev.map((d) => (d.doc_id === updated.doc_id ? updated : d)));
      setSummary("");
      setBanner(`Đã ghi nhận phiên bản mới v${updated.current_version} bởi vai trò ${actorRole}.`);
      setChainResult(null);
    } else {
      setErrorMsg("Tạo phiên bản mới thất bại.");
    }
  };

  const handleRollback = async (targetVersionNumber: number) => {
    if (!currentDoc) return;
    setErrorMsg("");
    setBanner("");
    const res = await fetch(`${API_BASE}/documents/${currentDoc.doc_id}/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_version_number: targetVersionNumber,
        actor_role: actorRole,
        actor_name: actorName.trim() || actorRole.toLowerCase(),
        reason: rollbackReason.trim() || `Rollback to v${targetVersionNumber}`,
      }),
    });
    if (res.ok) {
      const updated: DocumentAuditTrail = await res.json();
      setDocs((prev) => prev.map((d) => (d.doc_id === updated.doc_id ? updated : d)));
      const latest = updated.entries[updated.entries.length - 1];
      if (latest) setContentMarkdown(latest.content_markdown);
      setBanner(
        `Đã rollback về v${targetVersionNumber} dưới dạng phiên bản mới v${updated.current_version}.`
      );
      setChainResult(null);
    } else {
      setErrorMsg("Rollback phiên bản thất bại.");
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6 text-slate-900">
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
            FE08 • Role-Attributed Change Log & Version Audit Trail
          </span>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">
            Document Version Audit & Rollback Workbench
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            11.1 Tamper-Evident Chain • 11.2 Role Attribution (AI / Staff / Manager) • 11.3 Full Rollback
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleVerifyChain}
            className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
          >
            Kiểm tra chuỗi băm (Verify Chain)
          </button>
          <button
            onClick={loadDocs}
            className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-200"
          >
            Làm mới
          </button>
        </div>
      </div>

      {banner && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">
          {banner}
        </div>
      )}
      {errorMsg && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {errorMsg}
        </div>
      )}
      {chainResult && (
        <div
          className={`rounded-lg border p-3 text-sm font-medium ${
            chainResult.valid
              ? "border-emerald-300 bg-emerald-50 text-emerald-900"
              : "border-rose-300 bg-rose-50 text-rose-900"
          }`}
        >
          {chainResult.valid ? "CHAIN INTACT: " : "CHAIN ALERT: "}
          {chainResult.message}
        </div>
      )}

      {currentDoc && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
              <h2 className="text-base font-semibold text-slate-900">
                11.2 Ghi nhận phiên bản mới theo vai trò
              </h2>
              <p className="text-xs text-slate-600">
                Tài liệu: <strong className="text-slate-900">{currentDoc.title}</strong> ({currentDoc.doc_path}) • Hiện tại: <strong>v{currentDoc.current_version}</strong>
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Acting Role</label>
                  <select
                    value={actorRole}
                    onChange={(e) => setActorRole(e.target.value as ActorRole)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    <option value="AI">AI</option>
                    <option value="Staff">Staff</option>
                    <option value="Manager">Manager</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Actor Name</label>
                  <input
                    value={actorName}
                    onChange={(e) => setActorName(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Tóm tắt thay đổi</label>
                <input
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="Ví dụ: Cập nhật endpoint schema sau khi review"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Nội dung Markdown đầy đủ</label>
                <textarea
                  value={contentMarkdown}
                  onChange={(e) => setContentMarkdown(e.target.value)}
                  rows={5}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-xs text-slate-900"
                />
              </div>

              <button
                onClick={handleCreateVersion}
                className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Lưu phiên bản mới vào Audit Trail
              </button>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-base font-semibold text-slate-900">
                  Lịch sử phiên bản & 11.3 Rollback
                </h2>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-900"
                >
                  <option value="ALL">Tất cả role</option>
                  <option value="AI">AI</option>
                  <option value="Staff">Staff</option>
                  <option value="Manager">Manager</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Lý do rollback</label>
                <input
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900"
                />
              </div>

              <div className="space-y-2.5 max-h-96 overflow-auto pr-1">
                {visibleEntries.map((entry) => (
                  <div
                    key={entry.version_id}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-900 space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-900">
                        v{entry.version_number} • [{entry.actor_role}] {entry.actor_name}
                      </span>
                      <button
                        onClick={() => handleRollback(entry.version_number)}
                        className="rounded border border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900 hover:bg-amber-100"
                      >
                        Rollback về v{entry.version_number}
                      </button>
                    </div>
                    <p className="font-medium text-slate-800">{entry.summary}</p>
                    <p className="text-[11px] text-slate-600">
                      Event: <span className="font-mono">{entry.trigger_event}</span> • Commit:{" "}
                      <span className="font-mono">{entry.trigger_commit_hash}</span>
                      {entry.rollback_from_version
                        ? ` • Rolled back from v${entry.rollback_from_version}`
                        : ""}
                    </p>
                    <p className="text-[11px] font-mono text-slate-500 break-all">
                      hash: {entry.entry_hash.slice(0, 16)}... (prev: {entry.prev_hash.slice(0, 12)}...)
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}