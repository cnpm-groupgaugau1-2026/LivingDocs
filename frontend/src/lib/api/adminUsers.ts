export type UserRole = "admin" | "reviewer" | "developer" | "viewer";
export type UserStatus = "active" | "suspended" | "invited";

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  last_active_at: string | null;
  created_at: string | null;
}

export interface UserSummaryStats {
  total_users: number;
  active_users: number;
  admin_count: number;
  invited_count: number;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
  stats: UserSummaryStats;
}

export interface RolePermissionSpec {
  role: UserRole;
  label: string;
  description: string;
  permissions: Record<string, boolean>;
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

export async function fetchAdminUsers(params: {
  search?: string;
  role?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<AdminUserListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.role && params.role !== "all") query.set("role", params.role);
  if (params.status && params.status !== "all") query.set("status", params.status);
  query.set("page", String(params.page || 1));
  query.set("page_size", String(params.pageSize || 10));

  const res = await fetch(`${API_BASE}/api/v1/admin/users?${query.toString()}`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return handleResponse<AdminUserListResponse>(res);
}

export async function fetchRoleMatrix(): Promise<RolePermissionSpec[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/roles/permissions`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return handleResponse<RolePermissionSpec[]>(res);
}

export async function inviteUserApi(payload: {
  email: string;
  full_name: string;
  role: UserRole;
}): Promise<AdminUser> {
  const res = await fetch(`${API_BASE}/api/v1/admin/users/invite`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<AdminUser>(res);
}

export async function updateUserRoleApi(userId: string, role: UserRole): Promise<AdminUser> {
  const res = await fetch(`${API_BASE}/api/v1/admin/users/${userId}/role`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ role }),
  });
  return handleResponse<AdminUser>(res);
}

export async function updateUserStatusApi(userId: string, status: UserStatus): Promise<AdminUser> {
  const res = await fetch(`${API_BASE}/api/v1/admin/users/${userId}/status`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  return handleResponse<AdminUser>(res);
}
