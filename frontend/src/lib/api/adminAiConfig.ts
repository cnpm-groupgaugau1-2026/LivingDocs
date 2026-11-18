export interface ModelOption {
  id: string;
  label: string;
  provider: string;
  context_window: string;
}

export interface AiEngineConfig {
  generation_model: string;
  fallback_model: string;
  embedding_model: string;
  temperature: number;
  max_output_tokens: number;

  daily_token_limit: number;
  monthly_token_limit: number;
  tokens_used_today: number;
  tokens_used_month: number;
  budget_alert_percent: number;
  hard_stop_on_limit: boolean;

  drift_detection_threshold: number;
  auto_approve_confidence: number;
  rag_similarity_threshold: number;

  updated_by: string | null;
  updated_at: string | null;

  available_generation_models: ModelOption[];
  available_embedding_models: ModelOption[];
}

export type UpdateAiEngineConfigPayload = Omit<
  AiEngineConfig,
  | "tokens_used_today"
  | "tokens_used_month"
  | "updated_by"
  | "updated_at"
  | "available_generation_models"
  | "available_embedding_models"
>;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
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
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchAiEngineConfig(): Promise<AiEngineConfig> {
  const res = await fetch(`${API_BASE}/api/v1/admin/ai-config`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return handleResponse<AiEngineConfig>(res);
}

export async function updateAiEngineConfigApi(
  payload: UpdateAiEngineConfigPayload
): Promise<AiEngineConfig> {
  const res = await fetch(`${API_BASE}/api/v1/admin/ai-config`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<AiEngineConfig>(res);
}

export async function resetAiEngineConfigApi(): Promise<AiEngineConfig> {
  const res = await fetch(`${API_BASE}/api/v1/admin/ai-config/reset`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<AiEngineConfig>(res);
}