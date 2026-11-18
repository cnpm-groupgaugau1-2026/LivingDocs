"use client";

import React, { useState } from "react";
import RbacUserManagementPanel from "@/components/admin/RbacUserManagementPanel";
import ThirdPartyIntegrationsPanel from "@/components/admin/ThirdPartyIntegrationsPanel";
import AiParameterTuningPanel from "@/components/admin/AiParameterTuningPanel";

type AdminTab = "rbac" | "integrations" | "ai-tuning";

export default function SystemAdminPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>("rbac");

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">
            System Administration & AI Engine Configuration
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Quản lý phân quyền người dùng RBAC, tích hợp dịch vụ bên thứ ba và tinh chỉnh tham số AI.
          </p>
        </div>

        <div className="mb-6 border-b border-slate-200">
          <nav className="-mb-px flex space-x-6">
            <button
              type="button"
              onClick={() => setActiveTab("rbac")}
              className={`border-b-2 pb-3 text-sm font-semibold transition ${
                activeTab === "rbac"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              2.1 Users & RBAC Permissions
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("integrations")}
              className={`border-b-2 pb-3 text-sm font-semibold transition ${
                activeTab === "integrations"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              2.2 Third-Party Integrations
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("ai-tuning")}
              className={`border-b-2 pb-3 text-sm font-semibold transition ${
                activeTab === "ai-tuning"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              2.3 AI Parameter Tuning
            </button>
          </nav>
        </div>

        {activeTab === "rbac" && <RbacUserManagementPanel />}
        {activeTab === "integrations" && <ThirdPartyIntegrationsPanel />}
        {activeTab === "ai-tuning" && <AiParameterTuningPanel />}
      </div>
    </div>
  );
}