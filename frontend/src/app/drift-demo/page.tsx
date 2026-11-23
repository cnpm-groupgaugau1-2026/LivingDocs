"use client";

import React, { useEffect, useMemo, useState } from "react";

type DriftCategory = "referential" | "signature" | "semantic";
type DriftSeverity = "low" | "medium" | "high" | "critical";
type GroundingStatus =
  | "verified_dual_anchor"
  | "candidate_match_found"
  | "doc_only_missing_target";

interface EvidenceLine {
  line_number: number;
  content: string;
  is_target: boolean;
  annotation?: string | null;
}

interface EvidenceSourceBlock {
  source_type: "markdown_doc" | "ast_code";
  file_path: string;
  start_line?: number | null;
  end_line?: number | null;
  exact_quote: string;
  context_lines: EvidenceLine[];
  ast_node_proof?: string | null;
}

interface GroundingContextAttachment {
  evidence_id: string;
  grounding_status: GroundingStatus;
  doc_evidence: EvidenceSourceBlock;
  code_evidence?: EvidenceSourceBlock | null;
  ast_facts: string[];
  related_symbols: string[];
  ai_grounding_payload: string;
}

interface DriftItem {
  drift_id: string;
  category: DriftCategory;
  sub_type: string;
  severity: DriftSeverity;
  severity_score: number;
  severity_factors: string[];
  symbol_name: string;
  file_path?: string | null;
  title: string;
  description: string;
  expected_in_doc: string;
  actual_in_code: string;
  confidence: number;
  suggestion: string;
  doc_line_range?: number[] | null;
  code_line_range?: number[] | null;
  grounding?: GroundingContextAttachment | null;
}

interface DriftClassificationSummary {
  total_drifts: number;
  referential_count: number;
  signature_count: number;
  semantic_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  overall_risk_score: number;
  overall_risk_level: DriftSeverity;
  grounded_drifts_count: number;
  dual_anchored_count: number;
  analyzed_symbols: number;
  documented_symbols: number;
  analysis_mode: "ast_rule_engine" | "ast_plus_llm_hybrid";
}

interface DriftClassifyResponse {
  doc_path: string;
  summary: DriftClassificationSummary;
  drifts: DriftItem[];
  warnings: string[];
}

interface DemoScenario {
  id: string;
  label: string;
  badge: string;
  dotColor: string;
  docPath: string;
  codePath: string;
  markdown: string;
  code: string;
}

const SCENARIOS: DemoScenario[] = [
  {
    id: "mixed",
    label: "1. Tổng hợp cả 3 loại Drift",
    badge: "6 drifts",
    dotColor: "bg-slate-800",
    docPath: "docs/billing.md",
    codePath: "app/services/billing_service.py",
    markdown: `# Billing Service API

### \`process_payment(user_id: int, amount: float) -> bool\`
Hàm read-only kiểm tra và xác nhận thanh toán, trả về trạng thái boolean.

### \`legacy_reconcile_invoice(invoice_id: str)\`
Đối soát hóa đơn cũ cuối ngày.`,
    code: `def process_payment(user_id: str, amount: float, currency: str = "USD") -> dict:
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    db.save_transaction(user_id=user_id, amount=amount, currency=currency)
    return {"status": "paid", "currency": currency}`,
  },
  {
    id: "referential",
    label: "2. Referential Drift",
    badge: "Tham chiếu",
    dotColor: "bg-rose-500",
    docPath: "docs/auth.md",
    codePath: "app/services/auth_service.py",
    markdown: `# Authentication Module
Cấu hình bảo mật nằm tại \`app/core/old_security_config.py\`.

### \`verify_access_token(token: str) -> dict\`
Giải mã và xác thực JWT token của người dùng.`,
    code: `def validate_access_token(token: str) -> dict:
    if not token:
        return {"valid": False}
    return {"valid": True, "sub": "user_01"}`,
  },
  {
    id: "signature",
    label: "3. Signature Drift",
    badge: "Chữ ký hàm",
    dotColor: "bg-amber-500",
    docPath: "docs/search.md",
    codePath: "app/services/search_service.py",
    markdown: `# Document Search

### \`search_documents(limit: int = 10, query: str) -> list\`
Tìm kiếm tài liệu theo từ khóa với giới hạn mặc định 10 kết quả.`,
    code: `def search_documents(query: str, limit: int = 50, include_archived: bool = False) -> dict:
    return {
        "query": query,
        "limit": limit,
        "include_archived": include_archived,
        "items": [],
    }`,
  },
  {
    id: "semantic",
    label: "4. Semantic Drift",
    badge: "Ngữ nghĩa AST",
    dotColor: "bg-indigo-500",
    docPath: "docs/cleanup.md",
    codePath: "app/services/user_cleanup_service.py",
    markdown: `# User Cleanup

### \`audit_inactive_users(days: int)\`
Hàm read-only chỉ đọc dữ liệu và trả về danh sách tài khoản không hoạt động quá số ngày quy định.`,
    code: `def audit_inactive_users(days: int):
    if days < 1:
        raise PermissionError("Minimum threshold is 1 day")
    db.delete_inactive_accounts(days=days)`,
  },
  {
    id: "clean",
    label: "5. Tài liệu khớp 100%",
    badge: "In Sync",
    dotColor: "bg-emerald-500",
    docPath: "docs/repository.md",
    codePath: "app/services/repo_service.py",
    markdown: `# Repository Sync

### \`sync_repository(repo_id: str, force: bool = False) -> bool\`
Đồng bộ dữ liệu repository và trả về trạng thái hoàn tất.`,
    code: `def sync_repository(repo_id: str, force: bool = False) -> bool:
    if not repo_id:
        return False
    return True`,
  },
];

const SEVERITY_META: Record<
  DriftSeverity,
  {
    label: string;
    viLabel: string;
    badgeBg: string;
    badgeText: string;
    barColor: string;
    cardTint: string;
  }
> = {
  critical: {
    label: "CRITICAL",
    viLabel: "Nghiêm trọng",
    badgeBg: "bg-red-600",
    badgeText: "text-white",
    barColor: "bg-red-600",
    cardTint: "bg-red-50/70 border-red-200 text-red-900",
  },
  high: {
    label: "HIGH",
    viLabel: "Rủi ro cao",
    badgeBg: "bg-orange-500",
    badgeText: "text-white",
    barColor: "bg-orange-500",
    cardTint: "bg-orange-50/70 border-orange-200 text-orange-900",
  },
  medium: {
    label: "MEDIUM",
    viLabel: "Trung bình",
    badgeBg: "bg-amber-400",
    badgeText: "text-slate-950",
    barColor: "bg-amber-400",
    cardTint: "bg-amber-50/70 border-amber-200 text-amber-900",
  },
  low: {
    label: "LOW",
    viLabel: "Rủi ro thấp",
    badgeBg: "bg-sky-500",
    badgeText: "text-white",
    barColor: "bg-sky-500",
    cardTint: "bg-sky-50/70 border-sky-200 text-sky-900",
  },
};

const CATEGORY_META: Record<
  DriftCategory,
  {
    label: string;
    badgeBg: string;
    badgeText: string;
    borderActive: string;
    docLineBg: string;
    codeLineBg: string;
  }
> = {
  referential: {
    label: "REFERENTIAL DRIFT",
    badgeBg: "bg-rose-100",
    badgeText: "text-rose-700",
    borderActive: "border-rose-400 ring-2 ring-rose-100",
    docLineBg: "bg-rose-500/15 border-l-4 border-rose-500",
    codeLineBg: "bg-rose-500/20 border-l-4 border-rose-500",
  },
  signature: {
    label: "SIGNATURE DRIFT",
    badgeBg: "bg-amber-100",
    badgeText: "text-amber-800",
    borderActive: "border-amber-400 ring-2 ring-amber-100",
    docLineBg: "bg-amber-400/20 border-l-4 border-amber-500",
    codeLineBg: "bg-amber-400/20 border-l-4 border-amber-400",
  },
  semantic: {
    label: "SEMANTIC DRIFT",
    badgeBg: "bg-indigo-100",
    badgeText: "text-indigo-700",
    borderActive: "border-indigo-400 ring-2 ring-indigo-100",
    docLineBg: "bg-indigo-500/15 border-l-4 border-indigo-500",
    codeLineBg: "bg-indigo-500/25 border-l-4 border-indigo-400",
  },
};

const GROUNDING_STATUS_META: Record<
  GroundingStatus,
  { label: string; badgeClass: string }
> = {
  verified_dual_anchor: {
    label: "Neo kép Doc ↔ AST",
    badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-300",
  },
  candidate_match_found: {
    label: "Gợi ý hàm đổi tên AST",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-300",
  },
  doc_only_missing_target: {
    label: "Chỉ neo ở Tài liệu",
    badgeClass: "bg-rose-100 text-rose-800 border-rose-300",
  },
};

export default function DriftDemoPage() {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("mixed");
  const [docPath, setDocPath] = useState<string>(SCENARIOS[0].docPath);
  const [codePath, setCodePath] = useState<string>(SCENARIOS[0].codePath);
  const [markdown, setMarkdown] = useState<string>(SCENARIOS[0].markdown);
  const [code, setCode] = useState<string>(SCENARIOS[0].code);

  const [editMode, setEditMode] = useState<boolean>(false);
  const [useLlm, setUseLlm] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [result, setResult] = useState<DriftClassifyResponse | null>(null);
  const [selectedDriftId, setSelectedDriftId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<"all" | DriftCategory>("all");
  const [severityFilter, setSeverityFilter] = useState<"all" | DriftSeverity>("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const runClassification = async (
    targetDocPath: string,
    targetMd: string,
    targetCodePath: string,
    targetCode: string,
    llmFlag: boolean
  ) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await fetch(`${apiBase}/api/v1/drift/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_path: targetDocPath,
          markdown_content: targetMd,
          code_files: [
            {
              file_path: targetCodePath,
              content: targetCode,
              language: "python",
            },
          ],
          use_llm_semantic: llmFlag,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
      }

      const data: DriftClassifyResponse = await response.json();
      setResult(data);
      setEditMode(false);
      setCategoryFilter("all");
      setSeverityFilter("all");
      setSelectedDriftId(data.drifts.length > 0 ? data.drifts[0].drift_id : null);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Không thể kết nối Backend API.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runClassification(
      SCENARIOS[0].docPath,
      SCENARIOS[0].markdown,
      SCENARIOS[0].codePath,
      SCENARIOS[0].code,
      false
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelectScenario = (sc: DemoScenario) => {
    setSelectedScenarioId(sc.id);
    setDocPath(sc.docPath);
    setCodePath(sc.codePath);
    setMarkdown(sc.markdown);
    setCode(sc.code);
    runClassification(sc.docPath, sc.markdown, sc.codePath, sc.code, useLlm);
  };

  const handleCopyPayload = (driftId: string, payload: string) => {
    navigator.clipboard.writeText(payload);
    setCopiedId(driftId);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const filteredDrifts = useMemo(() => {
    if (!result) return [];
    return result.drifts.filter((d) => {
      const matchCat = categoryFilter === "all" || d.category === categoryFilter;
      const matchSev = severityFilter === "all" || d.severity === severityFilter;
      return matchCat && matchSev;
    });
  }, [result, categoryFilter, severityFilter]);

  const activeDrift = useMemo(() => {
    if (!result || result.drifts.length === 0) return null;
    return (
      filteredDrifts.find((d) => d.drift_id === selectedDriftId) ||
      filteredDrifts[0] ||
      result.drifts[0]
    );
  }, [result, filteredDrifts, selectedDriftId]);

  const isLineInRange = (lineNum: number, range?: number[] | null) => {
    if (!range || range.length < 2) return false;
    return lineNum >= range[0] && lineNum <= range[1];
  };

  const summary = result?.summary;
  const total = summary?.total_drifts || 0;
  const overallMeta = SEVERITY_META[summary?.overall_risk_level || "low"];

  const isReferentialMissing =
    activeDrift?.category === "referential" &&
    (!activeDrift.code_line_range || activeDrift.code_line_range.length < 2);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 py-8 px-4 sm:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* TOP HEADER */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-600 text-white">
                FE04 • Complete Pipeline (5.1 + 5.2 + 5.3)
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                Engine: {summary?.analysis_mode || "ast_rule_engine"}
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Documentation Drift Detection &amp; Grounding Suite
            </h1>
            <p className="text-sm text-slate-600">
              <span className="font-semibold text-slate-800">5.1</span> Phân loại 3 tầng •{" "}
              <span className="font-semibold text-slate-800">5.2</span> Chấm điểm rủi ro 0–100 •{" "}
              <span className="font-semibold text-emerald-700">5.3</span> Trích xuất bằng chứng dòng lệnh &amp; AI Grounding Payload.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1 text-xs font-medium">
              <button
                type="button"
                onClick={() => setEditMode(false)}
                className={`px-3 py-1.5 rounded-lg transition ${
                  !editMode ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Soi dòng lỗi
              </button>
              <button
                type="button"
                onClick={() => setEditMode(true)}
                className={`px-3 py-1.5 rounded-lg transition ${
                  editMode ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Sửa trực tiếp
              </button>
            </div>

            <label className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 cursor-pointer hover:bg-slate-50">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              Hybrid LLM
            </label>

            <button
              type="button"
              disabled={loading}
              onClick={() => runClassification(docPath, markdown, codePath, code, useLlm)}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold shadow-sm transition"
            >
              {loading ? "Đang phân tích..." : "Chạy Phân Loại"}
            </button>
          </div>
        </div>

        {/* SCENARIO TOOLBAR */}
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Kịch bản kiểm thử trực quan
            </span>
            <span className="text-xs text-slate-400">
              Bấm chọn kịch bản để tự động chạy 5.1 + 5.2 + 5.3
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {SCENARIOS.map((sc) => {
              const active = selectedScenarioId === sc.id;
              return (
                <button
                  key={sc.id}
                  type="button"
                  onClick={() => handleSelectScenario(sc)}
                  className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border text-xs font-semibold transition ${
                    active
                      ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                      : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${active ? "bg-emerald-400" : sc.dotColor}`} />
                  <span>{sc.label}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] ${
                      active ? "bg-slate-700 text-slate-200" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {sc.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {errorMsg && (
          <div className="rounded-xl bg-rose-50 border border-rose-200 p-4 text-sm text-rose-700">
            <strong>Lỗi kết nối:</strong> {errorMsg}
          </div>
        )}

        {/* SUMMARY: 5.1 CATEGORY + 5.2 SEVERITY + 5.3 GROUNDING */}
        {summary && (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
            {/* LEFT: 5.1 CATEGORY DISTRIBUTION */}
            <div className="xl:col-span-6 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex flex-wrap items-center gap-3 font-medium">
                  <span className="text-slate-600 font-semibold">5.1 Phân loại Drift:</span>
                  <span className="inline-flex items-center gap-1.5 text-rose-600">
                    <span className="w-2.5 h-2.5 rounded-sm bg-rose-500" />
                    Referential ({summary.referential_count})
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-amber-600">
                    <span className="w-2.5 h-2.5 rounded-sm bg-amber-400" />
                    Signature ({summary.signature_count})
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-indigo-600">
                    <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500" />
                    Semantic ({summary.semantic_count})
                  </span>
                </div>
                <div className="text-slate-500">
                  Markdown: <strong className="text-slate-800">{summary.documented_symbols}</strong> • AST:{" "}
                  <strong className="text-slate-800">{summary.analyzed_symbols}</strong>
                </div>
              </div>

              <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden flex">
                {total === 0 ? (
                  <div className="h-full w-full bg-emerald-500" />
                ) : (
                  <>
                    <div
                      style={{ width: `${(summary.referential_count / total) * 100}%` }}
                      className="h-full bg-rose-500 transition-all"
                    />
                    <div
                      style={{ width: `${(summary.signature_count / total) * 100}%` }}
                      className="h-full bg-amber-400 transition-all"
                    />
                    <div
                      style={{ width: `${(summary.semantic_count / total) * 100}%` }}
                      className="h-full bg-indigo-500 transition-all"
                    />
                  </>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <button
                  type="button"
                  onClick={() => setCategoryFilter("all")}
                  className={`text-left p-3 rounded-xl border transition ${
                    categoryFilter === "all"
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-slate-50 text-slate-900 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <div className="text-[11px] opacity-80">Tất cả</div>
                  <div className="text-xl font-bold mt-0.5">{summary.total_drifts}</div>
                </button>

                <button
                  type="button"
                  onClick={() => setCategoryFilter("referential")}
                  className={`text-left p-3 rounded-xl border transition ${
                    categoryFilter === "referential"
                      ? "bg-rose-100 border-rose-400 ring-2 ring-rose-100"
                      : "bg-rose-50/70 border-rose-200 hover:bg-rose-50"
                  }`}
                >
                  <div className="text-[11px] text-rose-700 font-medium">Referential</div>
                  <div className="text-xl font-bold text-rose-900 mt-0.5">{summary.referential_count}</div>
                </button>

                <button
                  type="button"
                  onClick={() => setCategoryFilter("signature")}
                  className={`text-left p-3 rounded-xl border transition ${
                    categoryFilter === "signature"
                      ? "bg-amber-100 border-amber-400 ring-2 ring-amber-100"
                      : "bg-amber-50/70 border-amber-200 hover:bg-amber-50"
                  }`}
                >
                  <div className="text-[11px] text-amber-800 font-medium">Signature</div>
                  <div className="text-xl font-bold text-amber-950 mt-0.5">{summary.signature_count}</div>
                </button>

                <button
                  type="button"
                  onClick={() => setCategoryFilter("semantic")}
                  className={`text-left p-3 rounded-xl border transition ${
                    categoryFilter === "semantic"
                      ? "bg-indigo-100 border-indigo-400 ring-2 ring-indigo-100"
                      : "bg-indigo-50/70 border-indigo-200 hover:bg-indigo-50"
                  }`}
                >
                  <div className="text-[11px] text-indigo-700 font-medium">Semantic</div>
                  <div className="text-xl font-bold text-indigo-950 mt-0.5">{summary.semantic_count}</div>
                </button>
              </div>
            </div>

            {/* RIGHT: 5.2 SEVERITY + 5.3 GROUNDING COVERAGE */}
            <div className="xl:col-span-6 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-slate-600">
                    5.2 Điểm rủi ro &amp; 5.3 Neo bằng chứng Grounding
                  </div>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold text-slate-900">
                      {summary.overall_risk_score}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">/ 100đ</span>
                    <span
                      className={`ml-1 px-2.5 py-0.5 rounded-md text-[11px] font-extrabold tracking-wide ${overallMeta.badgeBg} ${overallMeta.badgeText}`}
                    >
                      {total === 0 ? "IN SYNC" : overallMeta.label}
                    </span>
                  </div>
                </div>

                {/* 5.3 Grounding Anchor Counter */}
                <div className="flex items-center gap-2 bg-emerald-50/80 border border-emerald-200 rounded-xl px-3.5 py-2">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                      5.3 Grounding Anchors
                    </div>
                    <div className="text-xs text-emerald-950 mt-0.5">
                      Đã neo: <strong>{summary.grounded_drifts_count}</strong>/{summary.total_drifts} • Neo kép AST:{" "}
                      <strong>{summary.dual_anchored_count}</strong>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Lọc theo mức độ nghiêm trọng (5.2):</span>
                  {severityFilter !== "all" && (
                    <button
                      type="button"
                      onClick={() => setSeverityFilter("all")}
                      className="text-indigo-600 font-semibold hover:underline"
                    >
                      Xóa lọc mức độ
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {(["critical", "high", "medium", "low"] as DriftSeverity[]).map((sev) => {
                    const meta = SEVERITY_META[sev];
                    const countMap: Record<DriftSeverity, number> = {
                      critical: summary.critical_count,
                      high: summary.high_count,
                      medium: summary.medium_count,
                      low: summary.low_count,
                    };
                    const isSelected = severityFilter === sev;
                    return (
                      <button
                        key={sev}
                        type="button"
                        onClick={() => setSeverityFilter(isSelected ? "all" : sev)}
                        className={`p-2.5 rounded-xl border text-left transition ${
                          isSelected
                            ? `${meta.cardTint} ring-2 ring-slate-300 font-bold`
                            : "bg-slate-50 border-slate-200 hover:bg-slate-100"
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${meta.barColor}`} />
                          <span className="text-[10px] font-bold uppercase text-slate-700">
                            {meta.label}
                          </span>
                        </div>
                        <div className="text-xl font-bold text-slate-900 mt-0.5">{countMap[sev]}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SIDE-BY-SIDE MARKDOWN & AST CODE VIEWER */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* LEFT PANEL: MARKDOWN */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <div className="bg-slate-900 text-white px-4 py-2.5 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-bold tracking-wide">
                <span className="w-2 h-2 rounded-full bg-sky-400" />
                TÀI LIỆU MARKDOWN
              </div>
              <div className="flex items-center gap-2">
                {activeDrift?.doc_line_range && (
                  <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-400/30 text-[11px] font-mono">
                    Đang soi: L{activeDrift.doc_line_range[0]}-L{activeDrift.doc_line_range[1]}
                  </span>
                )}
                <span className="px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px] font-mono border border-slate-700">
                  {docPath}
                </span>
              </div>
            </div>

            {editMode ? (
              <textarea
                value={markdown}
                onChange={(e) => setMarkdown(e.target.value)}
                rows={9}
                className="w-full p-4 font-mono text-xs text-slate-800 bg-white focus:outline-none resize-y leading-6"
              />
            ) : (
              <div className="p-3 font-mono text-xs overflow-x-auto divide-y divide-slate-100/60">
                {markdown.split("\n").map((line, idx) => {
                  const lineNum = idx + 1;
                  const highlighted = activeDrift && isLineInRange(lineNum, activeDrift.doc_line_range);
                  const catStyle = activeDrift ? CATEGORY_META[activeDrift.category].docLineBg : "";
                  return (
                    <div
                      key={lineNum}
                      className={`flex items-start px-2 py-1 rounded-sm ${
                        highlighted ? catStyle : "hover:bg-slate-50"
                      }`}
                    >
                      <span
                        className={`w-8 shrink-0 select-none text-right pr-3 ${
                          highlighted ? "font-bold text-slate-900" : "text-slate-400"
                        }`}
                      >
                        {lineNum}
                      </span>
                      <pre className="whitespace-pre-wrap break-all text-slate-800 flex-1">{line || " "}</pre>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* RIGHT PANEL: AST CODE */}
          <div className="bg-slate-950 rounded-2xl border border-slate-800 shadow-sm overflow-hidden flex flex-col">
            <div className="bg-slate-900 text-white px-4 py-2.5 flex items-center justify-between gap-2 border-b border-slate-800">
              <div className="flex items-center gap-2 text-xs font-bold tracking-wide">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                MÃ NGUỒN THỰC TẾ (AST)
              </div>
              <div className="flex items-center gap-2">
                {isReferentialMissing ? (
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[11px] font-medium">
                    Không tồn tại trong AST
                  </span>
                ) : (
                  activeDrift?.code_line_range && (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[11px] font-mono">
                      Đang soi: L{activeDrift.code_line_range[0]}-L{activeDrift.code_line_range[1]}
                    </span>
                  )
                )}
                <span className="px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px] font-mono border border-slate-700">
                  {codePath}
                </span>
              </div>
            </div>

            {!editMode && isReferentialMissing && activeDrift && (
              <div className="bg-rose-950/90 border-b border-rose-800/80 px-4 py-2.5 text-xs text-rose-200 flex items-center justify-between gap-2">
                <span>
                  {activeDrift.sub_type === "broken_file_reference" ? (
                    <>
                      Tệp <strong className="text-white">{activeDrift.symbol_name}</strong> không tồn tại trong repository.
                    </>
                  ) : (
                    <>
                      Ký hiệu <strong className="text-white">{activeDrift.symbol_name}</strong> không tồn tại trong cây AST của tệp này.
                    </>
                  )}
                </span>
                <span className="text-[11px] font-mono text-rose-300 shrink-0">
                  {activeDrift.sub_type === "broken_file_reference" ? "FILE NOT FOUND" : "REFERENTIAL MISSING"}
                </span>
              </div>
            )}

            {editMode ? (
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                rows={9}
                className="w-full p-4 font-mono text-xs text-slate-100 bg-slate-950 focus:outline-none resize-y leading-6"
              />
            ) : (
              <div className="p-3 font-mono text-xs overflow-x-auto divide-y divide-slate-900">
                {code.split("\n").map((line, idx) => {
                  const lineNum = idx + 1;
                  const highlighted = activeDrift && isLineInRange(lineNum, activeDrift.code_line_range);
                  const catStyle = activeDrift ? CATEGORY_META[activeDrift.category].codeLineBg : "";
                  return (
                    <div
                      key={lineNum}
                      className={`flex items-start px-2 py-1 rounded-sm ${
                        highlighted ? catStyle : "hover:bg-slate-900/70"
                      }`}
                    >
                      <span
                        className={`w-8 shrink-0 select-none text-right pr-3 ${
                          highlighted ? "font-bold text-white" : "text-slate-600"
                        }`}
                      >
                        {lineNum}
                      </span>
                      <pre className="whitespace-pre-wrap break-all text-slate-100 flex-1">{line || " "}</pre>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* DRIFT LIST WITH 5.2 SEVERITY & 5.3 GROUNDING EVIDENCE */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
              Danh sách sai lệch ưu tiên &amp; Bằng chứng Grounding ({filteredDrifts.length})
            </h2>
            <span className="text-xs text-slate-500">
              Bấm chọn từng thẻ để soi dòng và kiểm tra bằng chứng AST đính kèm
            </span>
          </div>

          {summary && summary.total_drifts === 0 ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 text-center space-y-1">
              <div className="text-base font-bold text-emerald-800">
                Tài liệu và mã nguồn AST khớp nhau 100% — Điểm rủi ro: 0/100 (LOW)
              </div>
              <p className="text-xs text-emerald-700">
                Không phát hiện sai lệch tham chiếu, chữ ký hàm hay hành vi ngữ nghĩa nào.
              </p>
            </div>
          ) : filteredDrifts.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-6 text-center text-sm text-slate-500">
              Không có sai lệch nào khớp với bộ lọc hiện tại.
            </div>
          ) : (
            <div className="space-y-4">
              {filteredDrifts.map((item, idx) => {
                const cat = CATEGORY_META[item.category];
                const sev = SEVERITY_META[item.severity];
                const isSelected = activeDrift?.drift_id === item.drift_id;
                const grounding = item.grounding;
                const gMeta = grounding ? GROUNDING_STATUS_META[grounding.grounding_status] : null;

                return (
                  <div
                    key={item.drift_id}
                    onClick={() => setSelectedDriftId(item.drift_id)}
                    className={`bg-white rounded-2xl border p-5 shadow-sm cursor-pointer transition space-y-4 ${
                      isSelected ? cat.borderActive : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    {/* CARD HEADER */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-slate-900 text-white text-xs font-bold inline-flex items-center justify-center">
                          {idx + 1}
                        </span>

                        <span
                          className={`px-2.5 py-0.5 rounded-md text-[11px] font-extrabold tracking-wide ${sev.badgeBg} ${sev.badgeText}`}
                        >
                          {sev.label} • {item.severity_score}/100
                        </span>

                        <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-bold ${cat.badgeBg} ${cat.badgeText}`}>
                          {cat.label}
                        </span>

                        {gMeta && (
                          <span className={`px-2.5 py-0.5 rounded-md border text-[11px] font-semibold ${gMeta.badgeClass}`}>
                            {gMeta.label}
                          </span>
                        )}

                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[11px]">
                          {item.sub_type}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>Độ tin cậy:</span>
                        <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            style={{ width: `${Math.round(item.confidence * 100)}%` }}
                            className="h-full bg-slate-800"
                          />
                        </div>
                        <strong className="text-slate-800">{Math.round(item.confidence * 100)}%</strong>
                      </div>
                    </div>

                    {/* TITLE & DESCRIPTION */}
                    <div>
                      <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
                      <p className="text-sm text-slate-600 mt-1">{item.description}</p>
                    </div>

                    {/* 5.2 EXPLAINABLE SEVERITY FACTORS */}
                    {item.severity_factors && item.severity_factors.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 bg-slate-50 border border-slate-200/80 rounded-xl px-3 py-2">
                        <span className="text-[11px] font-semibold text-slate-600 mr-1">
                          5.2 Điểm rủi ro:
                        </span>
                        {item.severity_factors.map((factor, fIdx) => (
                          <span
                            key={fIdx}
                            className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-[11px] text-slate-700 font-medium"
                          >
                            {factor}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* DIFF BOXES */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                      <div className="rounded-xl bg-rose-50/70 border border-rose-200 p-3">
                        <div className="text-[11px] font-sans font-semibold text-rose-700 mb-1">
                          − Tài liệu đang mô tả:
                        </div>
                        <div className="text-rose-950 break-all">{item.expected_in_doc}</div>
                      </div>
                      <div className="rounded-xl bg-emerald-50/70 border border-emerald-200 p-3">
                        <div className="text-[11px] font-sans font-semibold text-emerald-700 mb-1">
                          + Mã nguồn AST thực tế:
                        </div>
                        <div className="text-emerald-950 break-all">{item.actual_in_code}</div>
                      </div>
                    </div>

                    {/* 5.3 GROUNDING EVIDENCE & CONTEXT ATTACHMENT BLOCK */}
                    {grounding && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="rounded-xl border border-slate-200 bg-slate-50/90 p-3.5 space-y-3 cursor-default"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded bg-slate-900 text-white text-[10px] font-bold uppercase tracking-wider">
                              5.3 Grounding Evidence
                            </span>
                            <span className="text-xs font-mono text-slate-500">{grounding.evidence_id}</span>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleCopyPayload(item.drift_id, grounding.ai_grounding_payload)}
                            className="px-2.5 py-1 rounded-lg bg-white hover:bg-slate-100 border border-slate-300 text-[11px] font-semibold text-slate-700 transition"
                          >
                            {copiedId === item.drift_id
                              ? "Đã chép AI Grounding Prompt"
                              : "Sao chép AI Grounding Payload"}
                          </button>
                        </div>

                        {/* Pinpoint Evidence Windows */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs font-mono">
                          {/* Doc Context Window */}
                          <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                            <div className="bg-slate-100 px-3 py-1.5 text-[11px] font-sans font-semibold text-slate-700 flex justify-between">
                              <span>Ngữ cảnh Tài liệu ({grounding.doc_evidence.file_path})</span>
                              <span>
                                L{grounding.doc_evidence.start_line}–L{grounding.doc_evidence.end_line}
                              </span>
                            </div>
                            <div className="p-2 space-y-0.5">
                              {grounding.doc_evidence.context_lines.map((cl) => (
                                <div
                                  key={cl.line_number}
                                  className={`px-2 py-0.5 rounded ${
                                    cl.is_target
                                      ? "bg-amber-50 border-l-2 border-amber-500 text-slate-950 font-semibold"
                                      : "text-slate-500"
                                  }`}
                                >
                                  <span className="inline-block w-6 text-slate-400 select-none">
                                    {cl.line_number}
                                  </span>
                                  <span>{cl.content || " "}</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* AST Code Context Window */}
                          <div className="rounded-lg border border-slate-800 bg-slate-950 text-slate-100 overflow-hidden">
                            <div className="bg-slate-900 px-3 py-1.5 text-[11px] font-sans font-semibold text-emerald-300 flex justify-between">
                              <span>
                                {grounding.code_evidence
                                  ? `Bằng chứng AST (${grounding.code_evidence.file_path})`
                                  : "Không tìm thấy nút AST tương ứng"}
                              </span>
                              {grounding.code_evidence && (
                                <span>
                                  Pinpoint L{grounding.code_evidence.start_line}–L{grounding.code_evidence.end_line}
                                </span>
                              )}
                            </div>
                            {grounding.code_evidence ? (
                              <div className="p-2 space-y-1">
                                {grounding.code_evidence.ast_node_proof && (
                                  <div className="px-2 py-1 rounded bg-emerald-950/80 border border-emerald-800/70 text-[11px] text-emerald-300">
                                    Node Proof: {grounding.code_evidence.ast_node_proof}
                                  </div>
                                )}
                                {grounding.code_evidence.context_lines.map((cl) => (
                                  <div key={cl.line_number}>
                                    <div
                                      className={`px-2 py-0.5 rounded ${
                                        cl.is_target
                                          ? "bg-emerald-500/20 border-l-2 border-emerald-400 text-white font-semibold"
                                          : "text-slate-400"
                                      }`}
                                    >
                                      <span className="inline-block w-6 text-slate-600 select-none">
                                        {cl.line_number}
                                      </span>
                                      <span>{cl.content || " "}</span>
                                    </div>
                                    {cl.annotation && (
                                      <div className="ml-8 text-[10px] font-sans text-emerald-300">
                                        ↳ {cl.annotation}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="p-3 text-xs font-sans text-rose-300">
                                Ký hiệu không tồn tại trong AST. Các ký hiệu hợp lệ hiện có:{" "}
                                <strong className="font-mono text-white">
                                  {grounding.related_symbols.join(", ") || "Không có"}
                                </strong>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Verified AST Facts */}
                        <div className="space-y-1">
                          <div className="text-[11px] font-semibold text-slate-700">
                            Sự thật AST đã kiểm chứng (Verified AST Facts):
                          </div>
                          <ul className="list-disc list-inside text-xs text-slate-700 space-y-0.5">
                            {grounding.ast_facts.map((fact, idxFact) => (
                              <li key={idxFact}>{fact}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Collapsible AI Grounding Prompt */}
                        <details className="rounded-lg border border-slate-200 bg-white">
                          <summary className="px-3 py-1.5 text-[11px] font-semibold text-indigo-700 cursor-pointer select-none">
                            Xem gói ngữ cảnh chống ảo giác cho AI Auto-Repair (AI Grounding Payload)
                          </summary>
                          <pre className="p-3 text-[11px] font-mono text-slate-800 bg-slate-50 border-t border-slate-200 whitespace-pre-wrap overflow-x-auto">
                            {grounding.ai_grounding_payload}
                          </pre>
                        </details>
                      </div>
                    )}

                    {/* SUGGESTION */}
                    <div className="rounded-xl bg-blue-50/70 border border-blue-200 px-3.5 py-2.5 text-xs text-blue-900">
                      <strong className="text-blue-700">Đề xuất sửa:</strong> {item.suggestion}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}