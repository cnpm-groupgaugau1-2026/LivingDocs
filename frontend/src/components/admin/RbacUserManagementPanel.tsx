"use client";

import React, { useCallback, useEffect, useState } from "react";

type UserRole = "developer" | "staff" | "manager" | "tech_lead" | "administrator";
type UserStatus = "active" | "invited" | "suspended";

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  last_active_at?: string | null;
  created_at?: string | null;
}

interface UserSummaryStats {
  total_users: number;
  active_users: number;
  admin_count: number;
  invited_count: number;
}

interface RolePermissionSpec {
  role: UserRole;
  label: string;
  description: string;
  permissions: Record<string, boolean>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ROLE_OPTIONS: { value: UserRole; label: string; badgeClass: string }[] = [
  {
    value: "developer",
    label: "Developer",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  {
    value: "staff",
    label: "Staff",
    badgeClass: "bg-sky-50 text-sky-700 border-sky-200",
  },
  {
    value: "manager",
    label: "Manager",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
  },
  {
    value: "tech_lead",
    label: "Technical Lead",
    badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200",
  },
  {
    value: "administrator",
    label: "Administrator",
    badgeClass: "bg-purple-50 text-purple-700 border-purple-200",
  },
];

const PERMISSION_LABELS: { key: string; label: string }[] = [
  { key: "view_docs", label: "Xem tài liệu đã xuất bản" },
  { key: "create_draft", label: "Tạo bản thảo tài liệu (AST / Code)" },
  { key: "review_tier1", label: "Phê duyệt Vòng 1 (Staff Reviewer)" },
  { key: "approve_publish", label: "Phê duyệt chung cuộc & Xuất bản (Manager)" },
  { key: "governance_template", label: "Báo cáo sức khỏe & Template (Tech Lead)" },
  { key: "manage_rbac_users", label: "Quản trị thành viên & Phân quyền 5 Actor" },
  { key: "configure_ai_integrations", label: "Cấu hình tích hợp & AI Engine" },
];

function getAuthHeaders(): HeadersInit {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token") || localStorage.getItem("token") || ""
      : "";
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function RbacUserManagementPanel() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<UserSummaryStats>({
    total_users: 0,
    active_users: 0,
    admin_count: 0,
    invited_count: 0,
  });
  const [permissionsMatrix, setPermissionsMatrix] = useState<RolePermissionSpec[]>([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const [showMatrixModal, setShowMatrixModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("developer");
  const [submitting, setSubmitting] = useState(false);

  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (search.trim()) params.set("search", search.trim());
      if (roleFilter) params.set("role", roleFilter);
      if (statusFilter) params.set("status", statusFilter);

      const res = await fetch(`${API_BASE}/api/v1/admin/users?${params.toString()}`, {
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể tải danh sách người dùng.");
      }
      setUsers(data.items || []);
      if (data.stats) setStats(data.stats);
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message || "Lỗi tải dữ liệu RBAC." });
    } finally {
      setLoading(false);
    }
  }, [search, roleFilter, statusFilter]);

  const fetchPermissionMatrix = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/roles/permissions`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setPermissionsMatrix(data);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    fetchPermissionMatrix();
  }, [fetchPermissionMatrix]);

  const handleRoleChange = async (userId: string, newRole: UserRole) => {
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/users/${userId}/role`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({ role: newRole }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Cập nhật vai trò thất bại.");
      }
      const label = ROLE_OPTIONS.find((r) => r.value === newRole)?.label || newRole;
      setFeedback({ type: "success", message: `Đã cập nhật vai trò của ${data.email} thành ${label}.` });
      fetchUsers();
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message });
    }
  };

  const handleStatusToggle = async (user: AdminUser) => {
    setFeedback(null);
    const nextStatus: UserStatus = user.status === "suspended" ? "active" : "suspended";
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/users/${user.id}/status`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({ status: nextStatus }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Thay đổi trạng thái thất bại.");
      }
      setFeedback({
        type: "success",
        message:
          nextStatus === "suspended"
            ? `Đã đình chỉ tài khoản ${user.email}.`
            : `Đã kích hoạt lại tài khoản ${user.email}.`,
      });
      fetchUsers();
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message });
    }
  };

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/users/invite`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          full_name: inviteName.trim(),
          email: inviteEmail.trim(),
          role: inviteRole,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Mời thành viên thất bại.");
      }
      setShowInviteModal(false);
      setInviteName("");
      setInviteEmail("");
      setInviteRole("developer");
      setFeedback({ type: "success", message: `Đã gửi lời mời tới ${data.email}.` });
      fetchUsers();
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadgeStyle = (role: UserRole) =>
    ROLE_OPTIONS.find((r) => r.value === role)?.badgeClass || "bg-slate-100 text-slate-700 border-slate-200";

  return (
    <div className="space-y-6">
      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Tổng thành viên</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{stats?.total_users ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Đang hoạt động</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{stats?.active_users ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Quản trị viên (Admin)</p>
          <p className="mt-1 text-2xl font-bold text-purple-600">{stats?.admin_count ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Chờ kích hoạt</p>
          <p className="mt-1 text-2xl font-bold text-amber-600">{stats?.invited_count ?? 0}</p>
        </div>
      </div>

      {/* Feedback Banner */}
      {feedback && (
        <div
          className={`flex items-center justify-between rounded-xl border px-4 py-3 text-sm ${
            feedback.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-800"
          }`}
        >
          <span>{feedback.message}</span>
          <button onClick={() => setFeedback(null)} className="ml-4 font-semibold opacity-70 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {/* Filter & Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo tên hoặc email..."
            className="w-64 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none"
          />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="">Tất cả vai trò (5 Actor)</option>
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="active">Active</option>
            <option value="invited">Invited</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setShowMatrixModal(true)}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Ma trận quyền RBAC
          </button>
          <button
            type="button"
            onClick={() => setShowInviteModal(true)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
          >
            + Mời thành viên
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3.5">Thành viên</th>
                <th className="px-6 py-3.5">Vai trò (5 Actor)</th>
                <th className="px-6 py-3.5">Trạng thái</th>
                <th className="px-6 py-3.5">Hoạt động gần nhất</th>
                <th className="px-6 py-3.5 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-slate-400">
                    Đang tải danh sách thành viên...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-slate-400">
                    Không có dữ liệu người dùng phù hợp.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50/70">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{user.full_name}</div>
                      <div className="text-xs text-slate-500">{user.email}</div>
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value as UserRole)}
                        className={`rounded-full border px-3 py-1 text-xs font-semibold focus:outline-none ${getRoleBadgeStyle(
                          user.role
                        )}`}
                      >
                        {ROLE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value} className="bg-white text-slate-800">
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
                          user.status === "active"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : user.status === "invited"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-rose-200 bg-rose-50 text-rose-700"
                        }`}
                      >
                        {user.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">
                      {user.last_active_at
                        ? new Date(user.last_active_at).toLocaleString("vi-VN")
                        : "Chưa đăng nhập"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleStatusToggle(user)}
                        className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                          user.status === "suspended"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            : "border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100"
                        }`}
                      >
                        {user.status === "suspended" ? "Kích hoạt" : "Đình chỉ"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Ma trận phân quyền 5 Actor */}
      {showMatrixModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Ma trận phân quyền RBAC (5 Actor)</h3>
                <p className="text-xs text-slate-500">
                  Đặc tả quyền hạn chuẩn của Developer, Staff, Manager, Technical Lead và Administrator
                </p>
              </div>
              <button
                onClick={() => setShowMatrixModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700">Chức năng / Quyền hạn</th>
                    {permissionsMatrix.map((spec) => (
                      <th key={spec.role} className="px-3 py-3 text-center font-semibold text-slate-800">
                        {spec.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {PERMISSION_LABELS.map((perm) => (
                    <tr key={perm.key}>
                      <td className="px-4 py-3 font-medium text-slate-700">{perm.label}</td>
                      {permissionsMatrix.map((spec) => (
                        <td key={spec.role} className="px-3 py-3 text-center">
                          {spec.permissions[perm.key] ? (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 font-bold">
                              ✓
                            </span>
                          ) : (
                            <span className="text-slate-300">—</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Modal Mời thành viên */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-base font-bold text-slate-900">Mời thành viên mới</h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleInviteSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Họ và tên</label>
                <input
                  type="text"
                  required
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Ví dụ: Nguyễn Văn A"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Email</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@livingdocs.com"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Vai trò (5 Actor)</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as UserRole)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submitting ? "Đang gửi..." : "Gửi lời mời"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default RbacUserManagementPanel;