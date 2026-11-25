"use client";

import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000/api/v1/ci-policy";

type SeverityLevel = "low" | "medium" | "high" | "critical";
type PolicyMode = "warn" | "block";

interface MergePolicyConfig {
  mode: PolicyMode;
  block_on_severities: SeverityLevel[];
  protected_paths: string[];
  doc_paths: string[];
  allow_override_label: string;
  updated_at: string;
}

interface PREvaluationRun {
  run_id: string;
  repo: string;
  pr_number: number;
  base_sha: string;
  head_sha: string;
  policy_mode: PolicyMode;
  detected_severity: SeverityLevel;
  drift_detected: boolean;
  waived_by_label: boolean;
  decision: "allow" | "warn" | "block";
  exit_code: number;
  reason: string;
  affected_code_files: string[];
  missing_doc_updates: boolean;
  evaluated_at: string;
}

const ALL_SEVERITIES: SeverityLevel[] = ["low", "medium", "high", "critical"];

export default function CIPolicyPage() {
  const [policy, setPolicy] = useState<MergePolicyConfig | null>(null);
  const [runs, setRuns] = useState<PREvaluationRun[]>([]);
  const [prNumber, setPrNumber] = useState<number>(102);
  const [changedFilesInput, setChangedFilesInput] = useState<string>(
    "backend/app/api/review_workflow.py"
  );
  const [severity, setSeverity] = useState<SeverityLevel>("critical");
  const [labelsInput, setLabelsInput] = useState<string>("");
  const [statusMsg, setStatusMsg] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const loadData = async () => {
    setErrorMsg("");
    try {
      const [polRes, runsRes] = await Promise.all([
        fetch(`${API_BASE}/policy`),
        fetch(`${API_BASE}/runs`),
      ]);
      if (!polRes.ok || !runsRes.ok) throw new Error("Failed to load FE06 data");
      setPolicy(await polRes.json());
      setRuns(await runsRes.json());
    } catch (err) {
      setErrorMsg(String(err));
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const toggleSeverity = (sev: SeverityLevel) => {
    if (!policy) return;
    const exists = policy.block_on_severities.includes(sev);
    const next = exists
      ? policy.block_on_severities.filter((s) => s !== sev)
      : [...policy.block_on_severities, sev];
    setPolicy({ ...policy, block_on_severities: next });
  };

  const handleSavePolicy = async () => {
    if (!policy) return;
    setErrorMsg("");
    setStatusMsg("");
    const res = await fetch(`${API_BASE}/policy`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(policy),
    });
    if (res.ok) {
      setPolicy(await res.json());
      setStatusMsg("Đã lưu cấu hình PR Merge Policy.");
    } else {
      setErrorMsg("Không lưu được cấu hình policy.");
    }
  };

  const handleSimulatePR = async () => {
    setErrorMsg("");
    setStatusMsg("");
    const changed_files = changedFilesInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const labels = labelsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await fetch(`${API_BASE}/evaluate-pr`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pr_number: prNumber,
        changed_files,
        labels,
        detected_severity: severity,
      }),
    });
    if (res.ok) {
      const created: PREvaluationRun = await res.json();
      setRuns((prev) => [created, ...prev]);
      setStatusMsg(`PR #${created.pr_number} -> Decision: ${created.decision.toUpperCase()} (exit ${created.exit_code})`);
    } else {
      setErrorMsg("Đánh giá PR thất bại.");
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6 text-slate-900">
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm">
        <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
          FE06 • Automated CI/CD Pipeline & Merge Policy Integration
        </span>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">
          GitHub Actions & PR Merge Policy Workbench
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Cấu hình Warn/Block merge trên Pull Request khi phát hiện documentation drift và theo dõi lịch sử kiểm tra CI.
        </p>
      </div>

      {statusMsg && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">
          {statusMsg}
        </div>
      )}
      {errorMsg && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {errorMsg}
        </div>
      )}

      {policy && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-4">
            <h2 className="text-base font-semibold text-slate-900">
              PR Merge Policy Enforcement Engine
            </h2>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Chế độ xử lý (Policy Mode)</label>
              <select
                value={policy.mode}
                onChange={(e) =>
                  setPolicy({ ...policy, mode: e.target.value as PolicyMode })
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="block">block (Chặn merge khi vi phạm ngưỡng)</option>
                <option value="warn">warn (Cảnh báo nhưng vẫn cho phép merge)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">
                Mức độ drift kích hoạt chính sách
              </label>
              <div className="flex flex-wrap gap-2">
                {ALL_SEVERITIES.map((sev) => {
                  const active = policy.block_on_severities.includes(sev);
                  return (
                    <button
                      key={sev}
                      type="button"
                      onClick={() => toggleSeverity(sev)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                        active
                          ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                          : "border-slate-300 bg-white text-slate-700"
                      }`}
                    >
                      {sev.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">
                Label ngoại lệ (Waive PR)
              </label>
              <input
                value={policy.allow_override_label}
                onChange={(e) =>
                  setPolicy({ ...policy, allow_override_label: e.target.value })
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </div>

            <button
              onClick={handleSavePolicy}
              className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Lưu Merge Policy
            </button>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-4">
            <h2 className="text-base font-semibold text-slate-900">
              Mô phỏng đánh giá Pull Request (CI Runner)
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-700">PR Number</label>
                <input
                  type="number"
                  value={prNumber}
                  onChange={(e) => setPrNumber(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700">Detected Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as SeverityLevel)}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                >
                  {ALL_SEVERITIES.map((sev) => (
                    <option key={sev} value={sev}>
                      {sev}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">
                Changed Files (phân tách bằng dấu phẩy)
              </label>
              <input
                value={changedFilesInput}
                onChange={(e) => setChangedFilesInput(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">
                PR Labels (vd: docs-drift-waived)
              </label>
              <input
                value={labelsInput}
                onChange={(e) => setLabelsInput(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </div>

            <button
              onClick={handleSimulatePR}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Chạy đánh giá PR
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
        <h2 className="text-base font-semibold text-slate-900">Lịch sử đánh giá PR / CI Runs</h2>
        <div className="space-y-2">
          {runs.map((r) => (
            <div
              key={r.run_id}
              className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-900 flex flex-wrap items-center justify-between gap-2"
            >
              <div className="space-y-0.5">
                <p className="font-semibold text-slate-900">
                  PR #{r.pr_number} • {r.run_id} • Severity: {r.detected_severity.toUpperCase()}
                </p>
                <p className="text-slate-700">{r.reason}</p>
              </div>
              <span
                className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  r.decision === "block"
                    ? "bg-rose-100 text-rose-800"
                    : r.decision === "warn"
                    ? "bg-amber-100 text-amber-900"
                    : "bg-emerald-100 text-emerald-800"
                }`}
              >
                {r.decision.toUpperCase()} (exit {r.exit_code})
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}