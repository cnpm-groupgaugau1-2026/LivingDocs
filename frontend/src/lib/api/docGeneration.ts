const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function buildHeaders(explicitToken?: string | null): HeadersInit {
  const token =
    explicitToken ||
    (typeof window !== "undefined"
      ? localStorage.getItem("livingdocs_token") || localStorage.getItem("access_token")
      : null);

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((d: { msg?: string }) => d.msg).join(", ")
      : err.detail;
    throw new Error(detail || `Lỗi gọi API (${res.status})`);
  }
  return res.json();
}

export interface DocumentationGap {
  entity_name: string;
  entity_type: "class" | "function" | "method";
  parent_name: string | null;
  signature: string;
  start_line: number;
  end_line: number;
  complexity_score: number;
  gap_type: "missing_docstring" | "brief_docstring" | "missing_type_hints";
  severity: "high" | "medium" | "low";
  recommendation: string;
}

export interface CoverageReport {
  file_path: string;
  language: string;
  total_entities: number;
  documented_entities: number;
  undocumented_entities: number;
  coverage_percentage: number;
  weighted_coverage_percentage: number;
  status: "good" | "needs_improvement" | "critical";
  high_priority_gaps: number;
  gaps: DocumentationGap[];
}

export interface DraftGenerationResponse {
  file_path: string;
  language: string;
  template_used: string;
  generation_mode: "llm_live" | "ast_template_fallback";
  provider_used: string;
  model_used: string;
  tokens_estimated: number;
  markdown_content: string;
  coverage_report: CoverageReport;
  warnings: string[];
}

export interface RepoCodeFile {
  path: string;
  sha: string;
  language: string;
}

export interface DocTemplateOption {
  id: number;
  name: string;
  slug: string;
  category: string;
  current_version: string;
}

export async function fetchRepoCodeFiles(
  repoName: string,
  token?: string | null
): Promise<RepoCodeFile[]> {
  const res = await fetch(
    `${API_BASE}/doc-generation/repo-code-files?repo_name=${encodeURIComponent(repoName)}`,
    { headers: buildHeaders(token) }
  );
  const data = await handleResponse<{ files: RepoCodeFile[] }>(res);
  return data.files || [];
}

export async function fetchRepoFileContent(
  repoName: string,
  filePath: string,
  token?: string | null
): Promise<{ file_path: string; language: string; source_code: string }> {
  const res = await fetch(
    `${API_BASE}/doc-generation/repo-file-content?repo_name=${encodeURIComponent(
      repoName
    )}&file_path=${encodeURIComponent(filePath)}`,
    { headers: buildHeaders(token) }
  );
  return handleResponse(res);
}

export async function fetchTemplatesList(
  token?: string | null
): Promise<DocTemplateOption[]> {
  const res = await fetch(`${API_BASE}/templates`, {
    headers: buildHeaders(token),
  });
  if (!res.ok) return [];
  const data = await res.json();
  if (Array.isArray(data)) return data;
  return data.items || data.templates || [];
}

export async function analyzeCodeCoverage(
  payload: { file_path: string; source_code: string; language?: string },
  token?: string | null
): Promise<CoverageReport> {
  const res = await fetch(`${API_BASE}/doc-generation/analyze-gaps`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(payload),
  });
  return handleResponse<CoverageReport>(res);
}

export async function generateAstDocDraft(
  payload: {
    file_path: string;
    source_code: string;
    language?: string;
    template_id?: number | null;
    custom_instructions?: string;
    include_coverage_gaps?: boolean;
  },
  token?: string | null
): Promise<DraftGenerationResponse> {
  const res = await fetch(`${API_BASE}/doc-generation/generate-draft`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(payload),
  });
  return handleResponse<DraftGenerationResponse>(res);
}
