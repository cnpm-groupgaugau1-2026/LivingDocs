"use client";

import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000/api/v1/governance-health";

type DriftStatus = "clean" | "warning" | "critical";
type NodeKind = "code" | "service" | "doc";
type EdgeRelation = "documents" | "impacts" | "depends_on";
type ExportFormat = "json" | "markdown";

interface DocumentHealthItem {
  doc_id: string;
  title: string;
  doc_path: string;
  module: string;
  freshness_days: number;
  freshness_threshold_days: number;
  coverage_pct: number;
  drift_status: DriftStatus;
  drift_reason?: string | null;
  last_updated_at: string;
}

interface DependencyNode {
  node_id: string;
  label: string;
  kind: NodeKind;
  path: string;
  module: string;
}

interface DependencyEdge {
  source: string;
  target: string;
  relation: EdgeRelation;
}

interface GovernanceMetrics {
  total_documents: number;
  fresh_documents: number;
  freshness_pct: number;
  coverage_pct: number;
  clean_count: number;
  warning_count: number;
  critical_count: number;
  active_drift_count: number;
  health_score: number;
}

interface GovernanceOverview {
  metrics: GovernanceMetrics;
  documents: DocumentHealthItem[];
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  generated_at: string;
}

interface ImpactAnalysisResult {
  source_node_id: string;
  source_label: string;
  impacted_nodes: DependencyNode[];
  impacted_documents: DocumentHealthItem[];
  impact_paths: string[][];
}

interface ComplianceExportPayload {
  format: ExportFormat;
  generated_at: string;
  filename: string;
  content: string;
}

export default function GovernanceHealthPage() {
  const [overview, setOverview] = useState<GovernanceOverview | null>(null);
  const [driftFilter, setDriftFilter] = useState<string>("ALL");
  const [selectedNodeId, setSelectedNodeId] = useState<string>("code-ci-service");
  const [impact, setImpact] = useState<ImpactAnalysisResult | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("markdown");
  const [exportedReport, setExportedReport] =
    useState<ComplianceExportPayload | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const loadImpact = async (nodeId: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/impact?node_id=${encodeURIComponent(nodeId)}`
      );
      if (res.ok) {
        setImpact(await res.json());
      }
    } catch {
      // handled via overview error state if needed
    }
  };

  const loadOverview = async (nodeIdToKeep?: string) => {
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/overview`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: GovernanceOverview = await res.json();
      setOverview(data);
      const targetNode =
        nodeIdToKeep ||
        (data.nodes.some((n) => n.node_id === selectedNodeId)
          ? selectedNodeId
          : data.nodes[0]?.node_id || "");
      if (targetNode) {
        setSelectedNodeId(targetNode);
        await loadImpact(targetNode);
      }
    } catch (err) {
      setErrorMsg(String(err));
    }
  };

  useEffect(() => {
    loadOverview();
  }, []);

  const handleSelectNode = async (nodeId: string) => {
    setSelectedNodeId(nodeId);
    await loadImpact(nodeId);
  };

  const handleExport = async (fmt: ExportFormat) => {
    setExportFormat(fmt);
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/export?format=${fmt}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload: ComplianceExportPayload = await res.json();
      setExportedReport(payload);
    } catch (err) {
      setErrorMsg(String(err));
    }
  };

  const handleDownloadReport = () => {
    if (!exportedReport) return;
    const blob = new Blob([exportedReport.content], {
      type:
        exportedReport.format === "json"
          ? "application/json;charset=utf-8"
          : "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportedReport.filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredDocs = overview
    ? overview.documents.filter((d) =>
        driftFilter === "ALL" ? true : d.drift_status === driftFilter
      )
    : [];

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6 text-slate-900">
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
            FE10 • Documentation Governance & Health Analytics
          </span>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">
            Technical Lead Governance & Health Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            12.1 Health Dashboard UI • 12.2 Freshness, Coverage & Drift Aggregator • 12.3 Impact Graph & Compliance Export
          </p>
        </div>

        <button
          onClick={() => loadOverview(selectedNodeId)}
          className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-200"
        >
          Làm mới số liệu
        </button>
      </div>

      {errorMsg && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {errorMsg}
        </div>
      )}

      {overview && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
              <p className="text-xs font-semibold text-slate-600">Overall Health Score</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {overview.metrics.health_score}
                <span className="text-sm font-normal text-slate-600"> / 100</span>
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
              <p className="text-xs font-semibold text-slate-600">Freshness Rate</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {overview.metrics.freshness_pct}%
              </p>
              <p className="text-xs text-slate-600">
                {overview.metrics.fresh_documents}/{overview.metrics.total_documents} docs tươi mới
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
              <p className="text-xs font-semibold text-slate-600">Average Coverage</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {overview.metrics.coverage_pct}%
              </p>
              <p className="text-xs text-slate-600">Độ bao phủ tài liệu theo module</p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
              <p className="text-xs font-semibold text-slate-600">Active Drift Status</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {overview.metrics.active_drift_count}
              </p>
              <p className="text-xs text-slate-700">
                Critical: {overview.metrics.critical_count} • Warning: {overview.metrics.warning_count} • Clean: {overview.metrics.clean_count}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-slate-900">
                12.2 Freshness, Coverage & Drift Metrics theo tài liệu
              </h2>
              <select
                value={driftFilter}
                onChange={(e) => setDriftFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-900"
              >
                <option value="ALL">Tất cả trạng thái drift</option>
                <option value="critical">critical</option>
                <option value="warning">warning</option>
                <option value="clean">clean</option>
              </select>
            </div>

            <div className="space-y-2">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.doc_id}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-900 flex flex-wrap items-center justify-between gap-2"
                >
                  <div className="space-y-0.5">
                    <p className="font-bold text-slate-900">
                      {doc.title}{" "}
                      <span className="font-mono font-normal text-slate-600">
                        ({doc.doc_path})
                      </span>
                    </p>
                    <p className="text-slate-700">
                      Module: <strong>{doc.module}</strong> • Age:{" "}
                      <strong>{doc.freshness_days}d</strong> (ngưỡng {doc.freshness_threshold_days}d) • Coverage:{" "}
                      <strong>{doc.coverage_pct}%</strong>
                    </p>
                    {doc.drift_reason && (
                      <p className="text-rose-800 font-medium">{doc.drift_reason}</p>
                    )}
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                      doc.drift_status === "critical"
                        ? "bg-rose-100 text-rose-900"
                        : doc.drift_status === "warning"
                        ? "bg-amber-100 text-amber-900"
                        : "bg-emerald-100 text-emerald-900"
                    }`}
                  >
                    {doc.drift_status.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
              <h2 className="text-base font-semibold text-slate-900">
                12.3 Code-Doc Dependency Impact Graph
              </h2>
              <p className="text-xs text-slate-600">
                Chọn một node để phân tích chuỗi phụ thuộc và tài liệu chịu ảnh hưởng:
              </p>

              <div className="flex flex-wrap gap-2">
                {overview.nodes.map((node) => {
                  const active = node.node_id === selectedNodeId;
                  return (
                    <button
                      key={node.node_id}
                      type="button"
                      onClick={() => handleSelectNode(node.node_id)}
                      className={`rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${
                        active
                          ? "border-indigo-600 bg-indigo-50 text-indigo-950"
                          : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
                      }`}
                    >
                      [{node.kind}] {node.label}
                    </button>
                  );
                })}
              </div>

              {impact && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-900 space-y-2">
                  <p className="font-bold text-slate-900">
                    Nguồn thay đổi: {impact.source_label} ({impact.source_node_id})
                  </p>
                  <p className="text-slate-700">
                    Nodes bị ảnh hưởng ({impact.impacted_nodes.length}):{" "}
                    {impact.impacted_nodes.length > 0
                      ? impact.impacted_nodes.map((n) => n.label).join(", ")
                      : "Không có node phụ thuộc xuôi chiều"}
                  </p>
                  <p className="text-slate-700">
                    Tài liệu liên quan ({impact.impacted_documents.length}):{" "}
                    {impact.impacted_documents.length > 0
                      ? impact.impacted_documents.map((d) => d.title).join(", ")
                      : "Không có"}
                  </p>
                  {impact.impact_paths.length > 0 && (
                    <div className="space-y-1">
                      <p className="font-semibold text-slate-800">Đường dẫn tác động:</p>
                      {impact.impact_paths.map((p, idx) => (
                        <p key={idx} className="font-mono text-[11px] text-slate-700">
                          {p.join(" -> ")}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
              <h2 className="text-base font-semibold text-slate-900">
                12.3 Compliance Report Exporter
              </h2>
              <p className="text-xs text-slate-600">
                Xuất báo cáo tuân thủ & sức khỏe tài liệu theo định dạng Markdown hoặc JSON:
              </p>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleExport("markdown")}
                  className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
                >
                  Xuất Markdown
                </button>
                <button
                  type="button"
                  onClick={() => handleExport("json")}
                  className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                >
                  Xuất JSON
                </button>
                {exportedReport && (
                  <button
                    type="button"
                    onClick={handleDownloadReport}
                    className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-200"
                  >
                    Tải file ({exportedReport.filename})
                  </button>
                )}
              </div>

              {exportedReport && (
                <textarea
                  readOnly
                  value={exportedReport.content}
                  rows={8}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-[11px] text-slate-900"
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}