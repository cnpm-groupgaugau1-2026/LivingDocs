export type IntegrationProvider = "github" | "jira" | "slack";
export type ConnectionStatus = "connected" | "failed" | "unconfigured";

export interface IntegrationItem {
  provider: IntegrationProvider;
  display_name: string;
  description: string;
  is_enabled: boolean;
  config: Record<string, any>;
  has_secret: boolean;
  masked_secret: string;
  has_webhook_secret: boolean;
  masked_webhook_secret: string;
  connection_status: ConnectionStatus;
  status_message: string | null;
  last_tested_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface TestIntegrationResponse {
  provider: IntegrationProvider;
  success: boolean;
  connection_status: ConnectionStatus;
  message: string;
  details: Record<string, any>;
  tested_at: string;
}

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
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchIntegrations(): Promise<IntegrationItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/integrations`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return handleResponse<IntegrationItem[]>(res);
}

export async function updateIntegrationApi(
  provider: IntegrationProvider,
  payload: {
    is_enabled: boolean;
    config: Record<string, any>;
    secret?: string;
    webhook_secret?: string;
  }
): Promise<IntegrationItem> {
  const res = await fetch(`${API_BASE}/api/v1/admin/integrations/${provider}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<IntegrationItem>(res);
}

export async function testIntegrationApi(
  provider: IntegrationProvider,
  payload: {
    config: Record<string, any>;
    secret?: string;
  }
): Promise<TestIntegrationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/admin/integrations/${provider}/test`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<TestIntegrationResponse>(res);
}