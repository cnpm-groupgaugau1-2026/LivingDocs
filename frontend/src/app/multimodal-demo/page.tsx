"use client";

import React, { useEffect, useRef, useState } from "react";

interface OcrToken {
  value: string;
  token_type: string;
  confidence: number;
  page?: number;
}

interface OcrResponse {
  filename: string;
  document_type: string;
  engine: string;
  page_count: number;
  average_confidence: number;
  image_dimensions?: string;
  preprocessing_steps: string[];
  tokens: OcrToken[];
  normalized_text: string;
  warning?: string | null;
}

interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  functions: string[];
  endpoints: string[];
  file_paths: string[];
  source_page: number;
  confidence: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  protocol: string;
  is_async: boolean;
  source_page: number;
}

interface ExecutionFlowStep {
  step_order: number;
  actor: string;
  action: string;
  target?: string | null;
  protocol_or_note: string;
}

interface ArchitecturalClaim {
  claim_id: string;
  category: string;
  statement: string;
  involved_entities: string[];
  verifiable_target: string;
  confidence: number;
}

interface VisionContextResponse {
  filename: string;
  asset_type: string;
  extractor_engine: string;
  ocr_engine_used: string;
  page_count: number;
  semantic_summary: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  execution_flows: ExecutionFlowStep[];
  architectural_claims: ArchitecturalClaim[];
  ocr_token_count: number;
  normalized_text: string;
}

interface CodeEvidence {
  file_path: string;
  line_number: number;
  symbol_name: string;
  symbol_type: string;
  snippet: string;
}

interface ClaimVerificationResult {
  claim_id: string;
  category: string;
  statement: string;
  verifiable_target: string;
  status: "consistent" | "drifted" | "unverified";
  severity: string;
  confidence: number;
  explanation: string;
  remediation: string;
  evidences: CodeEvidence[];
}

interface ConsistencyResponse {
  filename: string;
  asset_type: string;
  scanned_repo_root: string;
  scanned_files_count: number;
  indexed_symbols_count: number;
  consistency_score: number;
  overall_status: string;
  total_claims: number;
  consistent_count: number;
  drifted_count: number;
  unverified_count: number;
  semantic_summary: string;
  verification_results: ClaimVerificationResult[];
  vision_context: VisionContextResponse;
}

const API_BASE = "http://localhost:8000/api/v1/multimodal";

const SAMPLES = [
  {
    id: "arch",
    title: "1. Sơ đồ Kiến trúc Microservices",
    badge: "Architecture PNG",
    filename: "payment_architecture_diagram.png",
    hint: "Payment & Billing Microservices Architecture",
  },
  {
    id: "flow",
    title: "2. Lưu đồ Xác thực Token",
    badge: "Flowchart PNG",
    filename: "token_auth_flowchart.png",
    hint: "JWT Token Validation Flowchart",
  },
  {
    id: "pipe",
    title: "3. Sơ đồ Đồng bộ Repository",
    badge: "Pipeline PNG",
    filename: "repo_sync_pipeline.png",
    hint: "GitHub Webhook to Drift Analysis Pipeline",
  },
  {
    id: "live",
    title: "4. Kiến trúc LivingDocs Multimodal (Live Code)",
    badge: "Repo-Aligned PNG",
    filename: "livingdocs_multimodal_pipeline.png",
    hint: "LivingDocs Multimodal OCR, Vision Extractor & Consistency Pipeline",
  },
];

function normalizeOcrResponse(raw: any, fallbackFilename: string): OcrResponse {
  const obj = raw && typeof raw === "object" ? raw : {};

  let rawTokens: any[] =
    obj.tokens ||
    obj.technical_tokens ||
    obj.extracted_tokens ||
    obj.technical_entities ||
    obj.entities ||
    obj.ocr_tokens ||
    [];

  if (!Array.isArray(rawTokens) || rawTokens.length === 0) {
    for (const val of Object.values(obj)) {
      if (Array.isArray(val) && val.length > 0 && typeof val[0] === "object" && val[0] !== null) {
        rawTokens = val;
        break;
      }
    }
  }

  let rawSteps: string[] =
    obj.preprocessing_steps ||
    obj.preprocessing_pipeline ||
    obj.applied_preprocessing ||
    obj.preprocessing ||
    [];

  if (!Array.isArray(rawSteps) || rawSteps.length === 0) {
    for (const val of Object.values(obj)) {
      if (Array.isArray(val) && val.length > 0 && typeof val[0] === "string") {
        rawSteps = val;
        break;
      }
    }
  }

  let engineName: string =
    obj.engine ||
    obj.ocr_engine ||
    obj.ocr_engine_used ||
    obj.engine_used ||
    obj.engine_name ||
    obj.extraction_engine ||
    "";

  if (!engineName) {
    for (const [k, v] of Object.entries(obj)) {
      if (
        typeof v === "string" &&
        !k.toLowerCase().includes("text") &&
        !k.toLowerCase().includes("warn") &&
        /tesseract|pypdf|gemini|ocr/i.test(v)
      ) {
        engineName = v;
        break;
      }
    }
  }

  let avgConf: number | undefined =
    obj.average_confidence ??
    obj.overall_confidence ??
    obj.avg_confidence ??
    obj.mean_confidence ??
    obj.confidence_score ??
    obj.confidence;

  if (avgConf === undefined) {
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v === "number" && k.toLowerCase().includes("conf")) {
        avgConf = v;
        break;
      }
    }
  }
  const normalizedConf =
    typeof avgConf === "number" ? (avgConf > 1 ? avgConf / 100 : avgConf) : 0;

  let normText: string =
    obj.normalized_text ||
    obj.normalized_ocr_text ||
    obj.standardized_text ||
    obj.extracted_text ||
    obj.full_text ||
    obj.ocr_text ||
    obj.text ||
    "";

  if (!normText) {
    let longest = "";
    for (const [k, v] of Object.entries(obj)) {
      if (
        typeof v === "string" &&
        !k.toLowerCase().includes("file") &&
        v.length > longest.length
      ) {
        longest = v;
      }
    }
    normText = longest;
  }

  return {
    filename: obj.filename || obj.file_name || fallbackFilename,
    document_type: obj.document_type || obj.detected_asset_type || "unknown",
    engine: engineName || "tesseract_ocr_preprocessed",
    page_count: Number(obj.page_count ?? obj.total_pages ?? 1),
    average_confidence: normalizedConf,
    image_dimensions: obj.image_dimensions || obj.resolution || obj.dimensions,
    preprocessing_steps: Array.isArray(rawSteps) ? rawSteps : [],
    tokens: (Array.isArray(rawTokens) ? rawTokens : []).map((t: any) => {
      const rawC = Number(t?.confidence ?? t?.score ?? 0.9);
      return {
        value: String(
          t?.value ?? t?.text ?? t?.token ?? t?.symbol ?? t?.identifier ?? t?.label ?? t?.name ?? ""
        ),
        token_type: String(
          t?.token_type ?? t?.entity_type ?? t?.category ?? t?.kind ?? t?.type ?? "Entity"
        ),
        confidence: rawC > 1 ? rawC / 100 : rawC,
        page: Number(t?.page ?? t?.page_number ?? t?.source_page ?? 1),
      };
    }),
    normalized_text: normText,
    warning: obj.warning ?? null,
  };
}

function renderSampleDiagramToBlob(sampleId: string): Promise<{ blob: Blob; dataUrl: string }> {
  return new Promise((resolve) => {
    const canvas = document.createElement("canvas");
    canvas.width = 980;
    canvas.height = 320;
    const ctx = canvas.getContext("2d")!;

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 2;
    ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);

    const drawBox = (
      x: number,
      y: number,
      w: number,
      h: number,
      border: string,
      title: string,
      sub: string
    ) => {
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = border;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(x, y, w, h);

      ctx.textAlign = "left";
      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 15px monospace";
      ctx.fillText(title, x + 14, y + 34);

      ctx.fillStyle = "#334155";
      ctx.font = "12px monospace";
      ctx.fillText(sub, x + 14, y + 62);
    };

    const drawArrow = (x1: number, y1: number, x2: number, y2: number, label: string) => {
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      const angle = Math.atan2(y2 - y1, x2 - x1);
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - 10 * Math.cos(angle - Math.PI / 6), y2 - 10 * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(x2 - 10 * Math.cos(angle + Math.PI / 6), y2 - 10 * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fillStyle = "#475569";
      ctx.fill();

      ctx.textAlign = "center";
      ctx.fillStyle = "#1e293b";
      ctx.font = "bold 12px monospace";
      ctx.fillText(label, (x1 + x2) / 2, (y1 + y2) / 2 - 10);
      ctx.textAlign = "left";
    };

    ctx.textAlign = "left";
    ctx.fillStyle = "#0f172a";
    ctx.font = "bold 14px monospace";

    if (sampleId === "flow") {
      ctx.fillText("JWT TOKEN VALIDATION FLOWCHART", 32, 42);
      drawBox(30, 115, 220, 88, "#0284c7", "ClientRequest", "Bearer access_token");
      drawBox(370, 115, 230, 88, "#0d9488", "AuthMiddleware", "verify_jwt_signature()");
      drawBox(720, 50, 225, 86, "#4f46e5", "SessionCache", "check_revoked_jti()");
      drawBox(720, 180, 225, 86, "#16a34a", "ProtectedAPI", "dispatch_controller()");
      drawArrow(250, 159, 370, 159, "Authorization");
      drawArrow(600, 140, 720, 93, "Redis Lookup");
      drawArrow(600, 176, 720, 223, "Valid Token");
    } else if (sampleId === "pipe") {
      ctx.fillText("REPOSITORY DRIFT SYNC PIPELINE", 32, 42);
      drawBox(30, 115, 230, 88, "#334155", "GitHubWebhook", "POST /api/v1/github/webhook");
      drawBox(380, 115, 220, 88, "#0d9488", "RepoService", "sync_repository()");
      drawBox(720, 50, 225, 86, "#4f46e5", "ASTParser", "parse_python_symbols()");
      drawBox(720, 180, 225, 86, "#d97706", "DriftEngine", "classify_doc_drift()");
      drawArrow(260, 159, 380, 159, "push_event");
      drawArrow(600, 140, 720, 93, "Code AST");
      drawArrow(600, 176, 720, 223, "Compare Diff");
    } else if (sampleId === "live") {
      ctx.fillText("LIVINGDOCS MULTIMODAL VERIFICATION ARCHITECTURE", 32, 42);
      drawBox(25, 115, 255, 88, "#0284c7", "MultimodalRouter", "POST /api/v1/multimodal/ocr");
      drawBox(375, 115, 240, 88, "#0d9488", "VisionContextExtractor", "extract_context()");
      drawBox(705, 50, 250, 86, "#4f46e5", "TechnicalAssetOcrEngine", "extract_from_bytes()");
      drawBox(705, 180, 250, 86, "#16a34a", "VisualAssetConsistencyVerifier", "verify_consistency()");
      drawArrow(280, 159, 375, 159, "HTTP/JSON");
      drawArrow(615, 140, 705, 93, "OCR Tokens");
      drawArrow(615, 176, 705, 223, "AST Verify");
    } else {
      ctx.fillText("PAYMENT & BILLING SYSTEM ARCHITECTURE", 32, 42);
      drawBox(30, 115, 235, 88, "#334155", "ApiGateway", "POST /api/v1/billing/charge");
      drawBox(385, 115, 215, 88, "#0d9488", "BillingService", "process_payment()");
      drawBox(720, 50, 225, 86, "#4f46e5", "AuthService", "validate_access_token()");
      drawBox(720, 180, 225, 86, "#b45309", "TransactionDB", "save_transaction()");
      drawArrow(265, 159, 385, 159, "HTTP/JSON");
      drawArrow(600, 140, 720, 93, "verify_jwt");
      drawArrow(600, 176, 720, 223, "SQL Write");
    }

    const dataUrl = canvas.toDataURL("image/png");
    canvas.toBlob((blob) => {
      resolve({ blob: blob!, dataUrl });
    }, "image/png");
  });
}

export default function MultimodalDemoPage() {
  const [activeTab, setActiveTab] = useState<"fe05_3" | "fe05_2" | "fe05_1">("fe05_3");
  const [selectedSample, setSelectedSample] = useState<string>("live");
  const [repoPathInput, setRepoPathInput] = useState<string>("");
  const [claimFilter, setClaimFilter] = useState<"all" | "consistent" | "drifted" | "unverified">("all");

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [currentFilename, setCurrentFilename] = useState<string>("livingdocs_multimodal_pipeline.png");
  const [isPdfUpload, setIsPdfUpload] = useState<boolean>(false);

  const [ocrData, setOcrData] = useState<OcrResponse | null>(null);
  const [visionData, setVisionData] = useState<VisionContextResponse | null>(null);
  const [consistencyData, setConsistencyData] = useState<ConsistencyResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const analyzeFile = async (fileBlob: Blob, filename: string, hint: string = "") => {
    setLoading(true);
    setErrorMsg(null);
    setCurrentFilename(filename);
    setIsPdfUpload(filename.toLowerCase().endsWith(".pdf"));

    try {
      const formOcr = new FormData();
      formOcr.append("file", fileBlob, filename);

      const formVerify = new FormData();
      formVerify.append("file", fileBlob, filename);
      formVerify.append("context_hint", hint);
      formVerify.append("repo_path", repoPathInput);

      const [ocrRes, verifyRes] = await Promise.all([
        fetch(`${API_BASE}/ocr`, { method: "POST", body: formOcr }),
        fetch(`${API_BASE}/verify-consistency`, { method: "POST", body: formVerify }),
      ]);

      if (!ocrRes.ok) {
        throw new Error(`OCR API lỗi ${ocrRes.status}: ${await ocrRes.text()}`);
      }
      if (!verifyRes.ok) {
        throw new Error(`Consistency API lỗi ${verifyRes.status}: ${await verifyRes.text()}`);
      }

      const rawOcr = await ocrRes.json();
      const ocrJson = normalizeOcrResponse(rawOcr, filename);
      const verifyJson: ConsistencyResponse = await verifyRes.json();
      const visionJson = verifyJson.vision_context;

      setOcrData(ocrJson);
      setConsistencyData(verifyJson);
      setVisionData(visionJson);

      const nodesList = visionJson.nodes || [];
      const defaultNode =
        nodesList.find((n) => (n.functions?.length || 0) > 0 || (n.endpoints?.length || 0) > 0) ||
        nodesList[0] ||
        null;
      setSelectedNode(defaultNode);
    } catch (err: any) {
      setErrorMsg(err?.message || "Không thể kết nối Backend FastAPI.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSample = async (sample: (typeof SAMPLES)[number]) => {
    setSelectedSample(sample.id);
    const { blob, dataUrl } = await renderSampleDiagramToBlob(sample.id);
    setPreviewUrl(dataUrl);
    await analyzeFile(blob, sample.filename, sample.hint);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedSample("custom");
    if (file.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(file));
    } else {
      setPreviewUrl(null);
    }
    await analyzeFile(file, file.name, "User Uploaded Technical Asset");
  };

  useEffect(() => {
    handleSelectSample(SAMPLES[3]);
  }, []);

  const getNodePositions = (nodes: GraphNode[]) => {
    const positions: Record<string, { x: number; y: number }> = {};
    const count = nodes.length;
    if (count === 0) return positions;

    nodes.forEach((node, idx) => {
      if (count <= 4) {
        if (idx === 0) positions[node.label] = { x: 110, y: 155 };
        else if (idx === 1) positions[node.label] = { x: 385, y: 155 };
        else if (idx === 2) positions[node.label] = { x: 665, y: 75 };
        else positions[node.label] = { x: 665, y: 235 };
      } else {
        const col = idx % 3;
        const row = Math.floor(idx / 3);
        positions[node.label] = {
          x: 130 + col * 265,
          y: 75 + row * 125,
        };
      }
    });
    return positions;
  };

  const safeNodes = visionData?.nodes || [];
  const safeEdges = visionData?.edges || [];
  const safeFlows = visionData?.execution_flows || [];
  const safeClaims = visionData?.architectural_claims || [];
  const safeTokens = ocrData?.tokens || [];
  const safeSteps = ocrData?.preprocessing_steps || [];
  const safeVerifications = (consistencyData?.verification_results || []).filter(
    (item) => claimFilter === "all" || item.status === claimFilter
  );

  const nodePositions = getNodePositions(safeNodes);
  const svgHeight =
    safeNodes.length > 4 ? Math.max(320, Math.ceil(safeNodes.length / 3) * 145) : 320;

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-5">
        {/* Header + Mode Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-emerald-600 px-3 py-0.5 text-xs font-semibold text-white">
                {activeTab === "fe05_3"
                  ? "FE05 • Sub-feature 3 (Visual-Code Consistency Pipeline)"
                  : activeTab === "fe05_2"
                  ? "FE05 • Sub-feature 2 (Vision-LLM Context Extractor)"
                  : "FE05 • Sub-feature 1 (OCR Engine)"}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-0.5 font-mono text-xs text-slate-700">
                Engine:{" "}
                {activeTab === "fe05_3"
                  ? "ast_symbol_consistency_verifier"
                  : activeTab === "fe05_2"
                  ? visionData?.extractor_engine || "loading..."
                  : ocrData?.engine || "loading..."}
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {activeTab === "fe05_3"
                ? "Visual Asset - Code Consistency Verification Pipeline"
                : activeTab === "fe05_2"
                ? "Vision-LLM Context Extractor (Diagrams, Flowcharts & PDFs)"
                : "OCR Engine for Technical Assets (Diagrams, Flowcharts & PDFs)"}
            </h1>
            <p className="text-sm text-slate-500">
              {activeTab === "fe05_3"
                ? "Đối chiếu tự động các khẳng định kiến trúc từ sơ đồ/PDF với mã nguồn thật (Python AST & API Routes) để phát hiện Drift."
                : activeTab === "fe05_2"
                ? "Tái dựng đồ thị kiến trúc có hướng (Nodes, Edges), luồng thực thi và khẳng định kỹ thuật phục vụ đối chiếu drift FE05.3."
                : "Tiền xử lý hình ảnh sơ đồ kiến trúc, tách trang PDF và trích xuất thực thể kỹ thuật (Service, Function, API Endpoint, Flow Arrow)."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex rounded-xl border border-slate-200 bg-slate-100 p-1">
              <button
                onClick={() => setActiveTab("fe05_1")}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "fe05_1"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                FE05.1 OCR
              </button>
              <button
                onClick={() => setActiveTab("fe05_2")}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "fe05_2"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                FE05.2 Vision Graph
              </button>
              <button
                onClick={() => setActiveTab("fe05_3")}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "fe05_3"
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                FE05.3 Drift Check
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
            >
              Tải lên Ảnh / PDF thật
            </button>
          </div>
        </div>

        {/* Sample Selector & Target Repo Input */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Sơ đồ kỹ thuật mẫu (Chạy xuyên suốt FE05.1 OCR $\rightarrow$ FE05.2 Graph $\rightarrow$ FE05.3 Code Verify)
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Thư mục mã nguồn đối chiếu:</span>
              <input
                type="text"
                value={repoPathInput}
                onChange={(e) => setRepoPathInput(e.target.value)}
                placeholder="Mặc định: D:\CNPM\LivingDocs"
                className="w-60 rounded-lg border border-slate-200 px-2.5 py-1 font-mono text-xs text-slate-700 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2.5">
            {SAMPLES.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSelectSample(s)}
                className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
                  selectedSample === s.id
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span>{s.title}</span>
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${
                    selectedSample === s.id
                      ? "bg-slate-700 text-slate-200"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {s.badge}
                </span>
              </button>
            ))}
          </div>
        </div>

        {errorMsg && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <strong>Lỗi API:</strong> {errorMsg}
          </div>
        )}

        {loading && (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm font-medium text-indigo-700">
            Đang chạy pipeline FE05.1 OCR $\rightarrow$ FE05.2 Vision Graph $\rightarrow$ FE05.3 Code Consistency Verification...
          </div>
        )}

        {/* ==================== TAB FE05.3: VISUAL-CODE CONSISTENCY PIPELINE ==================== */}
        {activeTab === "fe05_3" && consistencyData && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Điểm nhất quán (Consistency Score)</div>
                <div
                  className={`mt-1 text-2xl font-bold ${
                    consistencyData.consistency_score >= 0.8
                      ? "text-emerald-600"
                      : consistencyData.consistency_score >= 0.5
                      ? "text-amber-600"
                      : "text-rose-600"
                  }`}
                >
                  {Math.round(consistencyData.consistency_score * 100)}%
                </div>
                <div className="mt-1 font-mono text-xs text-slate-400">
                  Trạng thái: {consistencyData.overall_status}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Khẳng định khớp mã nguồn</div>
                <div className="mt-1 text-2xl font-bold text-emerald-600">
                  {consistencyData.consistent_count} / {consistencyData.total_claims}
                </div>
                <div className="mt-1 text-xs text-slate-400">Verified in Repository AST</div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Sai lệch phát hiện (Drift)</div>
                <div className="mt-1 text-2xl font-bold text-rose-600">
                  {consistencyData.drifted_count}
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {consistencyData.unverified_count} chưa triển khai (unverified)
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Phạm vi mã nguồn đã lập chỉ mục</div>
                <div className="mt-1 text-2xl font-bold text-indigo-600">
                  {consistencyData.scanned_files_count} files
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {consistencyData.indexed_symbols_count} classes / functions / routes
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 shadow-sm flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="font-bold text-slate-800">Repository Root:</span>{" "}
                <span className="font-mono text-indigo-700">{consistencyData.scanned_repo_root}</span>
              </div>
              <div className="flex gap-1.5">
                {(["all", "consistent", "drifted", "unverified"] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => setClaimFilter(st)}
                    className={`rounded-lg px-2.5 py-1 font-semibold uppercase transition ${
                      claimFilter === st
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                <span>BÁO CÁO ĐỐI CHIẾU TỪNG KHẲNG ĐỊNH KIẾN TRÚC VỚI MÃ NGUỒN</span>
                <span className="text-emerald-300">{safeVerifications.length} mục hiển thị</span>
              </div>

              <div className="divide-y divide-slate-100 p-4 space-y-3">
                {safeVerifications.map((item) => {
                  const badgeStyle =
                    item.status === "consistent"
                      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                      : item.status === "drifted"
                      ? "bg-rose-100 text-rose-800 border-rose-200"
                      : "bg-amber-100 text-amber-800 border-amber-200";

                  return (
                    <div
                      key={item.claim_id}
                      className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-2.5"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-indigo-700">
                            {item.claim_id}
                          </span>
                          <span className="rounded bg-slate-200 px-2 py-0.5 font-mono text-[11px] text-slate-700">
                            {item.category}
                          </span>
                          <span
                            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase ${badgeStyle}`}
                          >
                            {item.status}
                          </span>
                        </div>
                        <span className="font-mono text-xs text-slate-500">
                          Target: <strong>{item.verifiable_target}</strong> • Tin cậy{" "}
                          {Math.round(item.confidence * 100)}%
                        </span>
                      </div>

                      <div className="text-sm font-semibold text-slate-900">{item.statement}</div>
                      <div className="text-xs text-slate-700">{item.explanation}</div>

                      {item.evidences.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <div className="text-[11px] font-bold uppercase text-slate-400">
                            Bằng chứng mã nguồn (Code Evidence):
                          </div>
                          {item.evidences.map((ev, idx) => (
                            <div
                              key={idx}
                              className="rounded-lg border border-slate-200 bg-slate-900 px-3 py-2 font-mono text-xs text-emerald-400"
                            >
                              <div className="text-indigo-300">
                                [{ev.symbol_type}] {ev.file_path}:{ev.line_number} —{" "}
                                <span className="font-bold text-white">{ev.symbol_name}</span>
                              </div>
                              {ev.snippet && (
                                <div className="mt-0.5 truncate text-slate-300">{ev.snippet}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {item.remediation && (
                        <div className="rounded-lg bg-white px-3 py-2 text-xs text-slate-600 border border-slate-200">
                          <strong className="text-slate-800">Đề xuất xử lý:</strong>{" "}
                          {item.remediation}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {/* ==================== TAB FE05.2: VISION-LLM CONTEXT EXTRACTOR ==================== */}
        {activeTab === "fe05_2" && visionData && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Loại tài liệu suy luận</div>
                <div className="mt-1 font-mono text-lg font-bold text-slate-900">
                  {visionData.asset_type}
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {visionData.page_count} trang • {visionData.ocr_token_count} OCR tokens
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Thành phần đồ thị (Nodes)</div>
                <div className="mt-1 text-2xl font-bold text-indigo-600">{safeNodes.length}</div>
                <div className="mt-1 text-xs text-slate-400">Service / Gateway / DB / Step</div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Luồng kết nối có hướng (Edges)</div>
                <div className="mt-1 text-2xl font-bold text-emerald-600">{safeEdges.length}</div>
                <div className="mt-1 text-xs text-slate-400">HTTP / RPC / SQL / Flow Arrows</div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Khẳng định đối chiếu FE05.3</div>
                <div className="mt-1 text-2xl font-bold text-amber-600">{safeClaims.length}</div>
                <div className="mt-1 text-xs text-slate-400">Sẵn sàng kiểm tra Drift với Code</div>
              </div>
            </div>

            <div className="rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4 text-sm text-slate-800">
              <span className="mr-2 rounded-md bg-indigo-600 px-2 py-0.5 text-xs font-bold text-white">
                Semantic Summary
              </span>
              {visionData.semantic_summary}
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:col-span-2">
                <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  <span>ĐỒ THỊ KIẾN TRÚC TÁI DỰNG (DIRECTED GRAPH)</span>
                  <span className="font-mono text-indigo-300">Bấm vào từng Node để xem chi tiết</span>
                </div>

                <div className="overflow-x-auto bg-slate-50 p-3">
                  <svg
                    width="100%"
                    height={svgHeight}
                    viewBox={`0 0 840 ${svgHeight}`}
                    className="rounded-xl border border-slate-200 bg-white"
                  >
                    <defs>
                      <marker
                        id="arrowhead"
                        markerWidth="10"
                        markerHeight="7"
                        refX="9"
                        refY="3.5"
                        orient="auto"
                      >
                        <polygon points="0 0, 10 3.5, 0 7" fill="#4f46e5" />
                      </marker>
                    </defs>

                    {safeEdges.map((edge) => {
                      const src = nodePositions[edge.source];
                      const dst = nodePositions[edge.target];
                      if (!src || !dst) return null;

                      const dx = dst.x - src.x;
                      const dy = dst.y - src.y;
                      const dist = Math.hypot(dx, dy) || 1;
                      const startX = src.x + (dx / dist) * 88;
                      const startY = src.y + (dy / dist) * 36;
                      const endX = dst.x - (dx / dist) * 90;
                      const endY = dst.y - (dy / dist) * 38;
                      const midX = (startX + endX) / 2;
                      const midY = (startY + endY) / 2 - 8;

                      return (
                        <g key={edge.id}>
                          <line
                            x1={startX}
                            y1={startY}
                            x2={endX}
                            y2={endY}
                            stroke="#4f46e5"
                            strokeWidth="2.2"
                            strokeDasharray={edge.is_async ? "6 4" : undefined}
                            markerEnd="url(#arrowhead)"
                          />
                          <rect
                            x={midX - 44}
                            y={midY - 11}
                            width="88"
                            height="16"
                            rx="4"
                            fill="#eef2ff"
                          />
                          <text
                            x={midX}
                            y={midY}
                            textAnchor="middle"
                            fontSize="10"
                            fontWeight="bold"
                            fill="#3730a3"
                            fontFamily="monospace"
                          >
                            {(edge.label || edge.protocol).slice(0, 16)}
                          </text>
                        </g>
                      );
                    })}

                    {safeNodes.map((node) => {
                      const pos = nodePositions[node.label];
                      if (!pos) return null;
                      const isSelected = selectedNode?.id === node.id;
                      const previewAttr =
                        (node.functions || [])[0] || (node.endpoints || [])[0] || "";

                      const borderCol =
                        node.node_type === "database"
                          ? "#d97706"
                          : node.node_type === "gateway"
                          ? "#0284c7"
                          : "#0d9488";

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${pos.x - 86}, ${pos.y - 36})`}
                          onClick={() => setSelectedNode(node)}
                          className="cursor-pointer"
                        >
                          <rect
                            width="172"
                            height="72"
                            rx="10"
                            fill={isSelected ? "#eef2ff" : "#ffffff"}
                            stroke={isSelected ? "#4f46e5" : borderCol}
                            strokeWidth={isSelected ? "3" : "2"}
                          />
                          <text
                            x="86"
                            y="24"
                            textAnchor="middle"
                            fontSize="11.5"
                            fontWeight="bold"
                            fill="#0f172a"
                            fontFamily="monospace"
                          >
                            {node.label.slice(0, 21)}
                          </text>
                          <text
                            x="86"
                            y="41"
                            textAnchor="middle"
                            fontSize="10"
                            fill="#64748b"
                            fontFamily="monospace"
                          >
                            [{node.node_type}] • p.{node.source_page}
                          </text>
                          {previewAttr && (
                            <text
                              x="86"
                              y="58"
                              textAnchor="middle"
                              fontSize="9.5"
                              fontWeight="bold"
                              fill="#059669"
                              fontFamily="monospace"
                            >
                              {previewAttr.slice(0, 24)}
                            </text>
                          )}
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  CHI TIẾT THÀNH PHẦN (NODE INSPECTOR)
                </div>
                {selectedNode ? (
                  <div className="space-y-4 p-4 text-sm">
                    <div>
                      <div className="font-mono text-lg font-bold text-slate-900">
                        {selectedNode.label}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs">
                        <span className="rounded bg-indigo-100 px-2 py-0.5 font-semibold text-indigo-700">
                          {selectedNode.node_type}
                        </span>
                        <span className="text-slate-500">
                          Trang {selectedNode.source_page} • Tin cậy{" "}
                          {Math.round(selectedNode.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-bold uppercase text-slate-400">
                        API Endpoints gắn kết
                      </div>
                      {(selectedNode.endpoints || []).length > 0 ? (
                        <div className="mt-1 space-y-1">
                          {selectedNode.endpoints.map((ep, i) => (
                            <div
                              key={i}
                              className="rounded bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-800"
                            >
                              {ep}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-1 text-xs italic text-slate-400">
                          Không có endpoint trực tiếp
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="text-xs font-bold uppercase text-slate-400">
                        Hàm / Phương thức (Functions)
                      </div>
                      {(selectedNode.functions || []).length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {selectedNode.functions.map((fn, i) => (
                            <span
                              key={i}
                              className="rounded bg-emerald-50 px-2 py-1 font-mono text-xs font-medium text-emerald-700"
                            >
                              {fn}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-1 text-xs italic text-slate-400">Chưa ánh xạ hàm</div>
                      )}
                    </div>

                    <div>
                      <div className="text-xs font-bold uppercase text-slate-400">
                        Đường dẫn mã nguồn (File Paths)
                      </div>
                      {(selectedNode.file_paths || []).length > 0 ? (
                        <div className="mt-1 space-y-1">
                          {selectedNode.file_paths.map((fp, i) => (
                            <div
                              key={i}
                              className="rounded bg-amber-50 px-2.5 py-1 font-mono text-xs text-amber-800"
                            >
                              {fp}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-1 text-xs italic text-slate-400">
                          Xem chi tiết đối chiếu tại tab FE05.3 Drift Check
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="p-6 text-center text-sm text-slate-400">
                    Chưa có thành phần nào được chọn.
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  LUỒNG THỰC THI TUẦN TỰ (EXECUTION FLOWS)
                </div>
                <div className="divide-y divide-slate-100 p-4">
                  {safeFlows.map((step) => (
                    <div key={step.step_order} className="flex items-start gap-3 py-2.5">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                        {step.step_order}
                      </span>
                      <div className="text-sm">
                        <span className="font-mono font-bold text-slate-900">{step.actor}</span>{" "}
                        <span className="text-slate-600">{step.action}</span>{" "}
                        {step.target && (
                          <span className="font-mono font-bold text-indigo-700">
                            → {step.target}
                          </span>
                        )}
                        <div className="mt-0.5 font-mono text-xs text-slate-400">
                          {step.protocol_or_note}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  <span>KHẲNG ĐỊNH KIẾN TRÚC (SẴN SÀNG CHO FE05.3 DRIFT CHECK)</span>
                  <span className="text-amber-300">{safeClaims.length} claims</span>
                </div>
                <div className="max-h-80 space-y-2.5 overflow-y-auto p-4">
                  {safeClaims.map((claim) => (
                    <div
                      key={claim.claim_id}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-indigo-700">
                          {claim.claim_id} • {claim.category}
                        </span>
                        <span className="font-mono text-slate-500">
                          {Math.round(claim.confidence * 100)}%
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-800">{claim.statement}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ==================== TAB FE05.1: OCR ENGINE VIEW ==================== */}
        {activeTab === "fe05_1" && ocrData && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Loại tài liệu nhận diện</div>
                <div className="mt-1 font-mono text-lg font-bold text-slate-900">
                  {ocrData.document_type}
                </div>
                <div className="mt-1 text-xs text-slate-400">{ocrData.page_count} trang</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Độ tin cậy OCR trung bình</div>
                <div className="mt-1 text-2xl font-bold text-emerald-600">
                  {Math.round((ocrData.average_confidence || 0) * 100)}%
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {ocrData.image_dimensions || "PDF Vector"}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Thực thể kỹ thuật trích xuất</div>
                <div className="mt-1 text-2xl font-bold text-indigo-600">{safeTokens.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-slate-500">Tiền xử lý ảnh (Preprocessing)</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {safeSteps.map((st, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700"
                    >
                      {st}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  <span>TÀI LIỆU TRỰC QUAN ĐẦU VÀO</span>
                  <span className="font-mono text-slate-300">{currentFilename}</span>
                </div>
                <div className="flex min-h-[260px] items-center justify-center p-4">
                  {previewUrl ? (
                    <img
                      src={previewUrl}
                      alt={currentFilename}
                      className="max-h-64 rounded-lg border border-slate-200 object-contain"
                    />
                  ) : (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
                      <div className="font-semibold text-slate-800">
                        {isPdfUpload ? `Tệp tài liệu PDF: ${currentFilename}` : currentFilename}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        Đã phân tách {ocrData.page_count} trang và trích xuất lớp văn bản kỹ thuật.
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  <span>THỰC THỂ KỸ THUẬT TRÍCH XUẤT (POST-OCR)</span>
                  <span className="text-emerald-300">{safeTokens.length} tokens</span>
                </div>
                <div className="max-h-72 space-y-2 overflow-y-auto p-4">
                  {safeTokens.map((tok, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5"
                    >
                      <div>
                        <div className="font-mono text-sm font-bold text-slate-900">{tok.value}</div>
                        <span className="mt-1 inline-block rounded bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                          {tok.token_type}
                        </span>
                      </div>
                      <div className="text-right text-xs text-slate-500">
                        <div>Trang {tok.page || 1}</div>
                        <div className="font-bold text-slate-700">
                          {Math.round((tok.confidence || 0.9) * 100)}%
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {ocrData.normalized_text && (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between bg-slate-900 px-4 py-3 text-xs font-bold uppercase tracking-wider text-white">
                  <span>VĂN BẢN OCR ĐÃ CHUẨN HÓA (SẴN SÀNG ĐƯA VÀO VISION-LLM FE05.2)</span>
                  <span className="text-slate-300">Đã chuẩn hóa ký hiệu mũi tên & định danh</span>
                </div>
                <pre className="max-h-60 overflow-auto bg-slate-950 p-4 font-mono text-xs text-emerald-400">
                  {ocrData.normalized_text}
                </pre>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}