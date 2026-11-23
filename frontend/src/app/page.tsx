'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import AstDocGeneratorModal from '@/components/AstDocGeneratorModal';

const API_BASE_URL = 'http://localhost:8000/api/v1';

interface DocItem {
  id: string;
  title: string;
  content: string;
  updatedAt: string;
  filePath?: string;
  githubSha?: string;
}

interface UserProfile {
  id: number;
  email: string;
  username?: string;
  full_name?: string;
  role: string;
}

interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  default_branch?: string;
  private: boolean;
  html_url: string;
}

interface IntegrationStatus {
  integration_type: string;
  status: string;
  repo_full_name: string;
  default_branch: string;
  private: boolean;
  permissions: {
    pull?: boolean;
    push?: boolean;
    admin?: boolean;
  };
  synced_files_count: number;
  last_synced_at: string | null;
}

interface WebhookLogItem {
  id: number;
  event_type: string;
  commit_sha: string;
  pusher: string;
  affected_files: string[];
  status: string;
  message: string;
  created_at: string | null;
}

interface SyncedDocDTO {
  id: number;
  title: string;
  file_path: string;
  content: string;
  github_sha?: string;
  last_synced_at?: string | null;
}

interface BannerNotice {
  type: 'success' | 'error';
  message: string;
  linkUrl?: string;
  linkText?: string;
}

const DEFAULT_DOCS: DocItem[] = [
  {
    id: 'doc-1',
    title: 'Hướng dẫn dự án LivingDocs',
    filePath: 'docs/Huong_dan_du_an_LivingDocs.md',
    content: `# Chào mừng đến với LivingDocs

Đây là trình soạn thảo tài liệu thời gian thực được xây dựng bằng **Next.js 14** và **FastAPI**.

- [x] Thiết kế giao diện Frontend
- [x] Xây dựng RESTful API Backend
- [x] Tích hợp cơ sở dữ liệu & GitHub OAuth`,
    updatedAt: 'Vừa xong',
  },
  {
    id: 'doc-2',
    title: 'Ghi chú cuộc họp Backend',
    filePath: 'docs/Ghi_chu_cuoc_hop_Backend.md',
    content: `# Kiến trúc hệ thống & Phân quyền

- Xác thực qua **GitHub OAuth 2.0** với quyền \`repo\` và \`user:email\`.
- Lưu trữ phiên làm việc bằng **JWT Bearer Token**.
- Đồng bộ trực tiếp tài liệu Markdown lên nhánh mặc định của Repository.`,
    updatedAt: 'Vừa xong',
  },
];

function toSafeFileName(title: string): string {
  const normalized = title
    .trim()
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9\s_-]/g, '')
    .replace(/\s+/g, '_');

  return `${normalized || 'untitled_document'}.md`;
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-bold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return (
        <em key={idx} className="italic text-gray-200">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={idx}
          className="rounded bg-[#1f242c] px-1.5 py-0.5 font-mono text-sm text-[#79c0ff]"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

function MarkdownPreview({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="space-y-3 text-gray-300 leading-relaxed">
      {lines.map((line, index) => {
        if (line.startsWith('### ')) {
          return (
            <h3 key={index} className="mt-4 text-xl font-semibold text-white">
              {renderInlineMarkdown(line.slice(4))}
            </h3>
          );
        }
        if (line.startsWith('## ')) {
          return (
            <h2 key={index} className="mt-5 text-2xl font-bold text-white">
              {renderInlineMarkdown(line.slice(3))}
            </h2>
          );
        }
        if (line.startsWith('# ')) {
          return (
            <h1
              key={index}
              className="mt-2 border-b border-[#30363d] pb-2 text-3xl font-bold text-white"
            >
              {renderInlineMarkdown(line.slice(2))}
            </h1>
          );
        }
        if (line.startsWith('- [x] ') || line.startsWith('- [X] ')) {
          return (
            <div key={index} className="flex items-center gap-2.5 pl-1">
              <input
                type="checkbox"
                checked
                readOnly
                className="h-4 w-4 accent-[#238636]"
              />
              <span className="line-through text-gray-400">
                {renderInlineMarkdown(line.slice(6))}
              </span>
            </div>
          );
        }
        if (line.startsWith('- [ ] ')) {
          return (
            <div key={index} className="flex items-center gap-2.5 pl-1">
              <input
                type="checkbox"
                checked={false}
                readOnly
                className="h-4 w-4 accent-[#238636]"
              />
              <span>{renderInlineMarkdown(line.slice(6))}</span>
            </div>
          );
        }
        if (line.startsWith('- ')) {
          return (
            <div key={index} className="flex items-start gap-2 pl-2">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#58a6ff]" />
              <span>{renderInlineMarkdown(line.slice(2))}</span>
            </div>
          );
        }
        if (line.trim() === '') {
          return <div key={index} className="h-2" />;
        }
        return <p key={index}>{renderInlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

export default function LivingDocsPage() {
  const [docs, setDocs] = useState<DocItem[]>(DEFAULT_DOCS);
  const [activeDocId, setActiveDocId] = useState<string>(DEFAULT_DOCS[0].id);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [loadingWorkspaces, setLoadingWorkspaces] = useState<boolean>(false);

  // State cho mục 1.2: GitHub App Integration & Repository Synchronization
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatus | null>(null);
  const [syncing, setSyncing] = useState<boolean>(false);

  // State cho mục 1.3: Webhook Handler & Real-time Ingestion Pipeline
  const [webhookLogs, setWebhookLogs] = useState<WebhookLogItem[]>([]);
  const [simulatingWebhook, setSimulatingWebhook] = useState<boolean>(false);

  const [pushing, setPushing] = useState<boolean>(false);
  const [banner, setBanner] = useState<BannerNotice | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const activeDoc = docs.find((d) => d.id === activeDocId) || docs[0];

  useEffect(() => {
    try {
      const savedDocs = localStorage.getItem('livingdocs_documents');
      if (savedDocs) {
        const parsed = JSON.parse(savedDocs);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setDocs(parsed);
          setActiveDocId(parsed[0].id);
        }
      }
    } catch {
      // Bỏ qua nếu dữ liệu localStorage không hợp lệ
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('livingdocs_documents', JSON.stringify(docs));
    } catch {
      // Bỏ qua lỗi quota
    }
  }, [docs]);

  const mergeSyncedDocuments = useCallback((syncedList: SyncedDocDTO[], selectFirst = false) => {
    if (!Array.isArray(syncedList) || syncedList.length === 0) return;

    const mappedDocs: DocItem[] = syncedList.map((d) => ({
      id: `db-${d.id}`,
      title: d.title,
      content: d.content,
      filePath: d.file_path,
      githubSha: d.github_sha,
      updatedAt: d.last_synced_at
        ? new Date(d.last_synced_at + 'Z').toLocaleTimeString('vi-VN')
        : 'Đã đồng bộ',
    }));

    setDocs((prev) => {
      const syncedPaths = new Set(mappedDocs.map((m) => m.filePath));
      const localOnly = prev.filter(
        (item) => !item.id.startsWith('db-') && (!item.filePath || !syncedPaths.has(item.filePath))
      );
      return [...mappedDocs, ...localOnly];
    });

    if (selectFirst && mappedDocs.length > 0) {
      setActiveDocId(mappedDocs[0].id);
    }
  }, []);

  const fetchIntegrationAndDocs = useCallback(
    async (jwtToken: string, repoName: string) => {
      if (!jwtToken || !repoName) return;
      const headers = { Authorization: `Bearer ${jwtToken}` };
      const encodedRepo = encodeURIComponent(repoName);

      try {
        const [statusRes, docsRes, logsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/github/integration-status?repo_name=${encodedRepo}`, { headers }),
          fetch(`${API_BASE_URL}/documents?repo_name=${encodedRepo}`, { headers }),
          fetch(`${API_BASE_URL}/github/webhook/logs?repo_name=${encodedRepo}`, { headers }),
        ]);

        if (statusRes.ok) {
          const statusData: IntegrationStatus = await statusRes.json();
          setIntegrationStatus(statusData);
        } else {
          setIntegrationStatus(null);
        }

        if (docsRes.ok) {
          const dbDocs: SyncedDocDTO[] = await docsRes.json();
          if (dbDocs.length > 0) {
            mergeSyncedDocuments(dbDocs, false);
          }
        }

        if (logsRes.ok) {
          const logData: WebhookLogItem[] = await logsRes.json();
          setWebhookLogs(logData);
        }
      } catch {
        setIntegrationStatus(null);
      }
    },
    [mergeSyncedDocuments]
  );

  // Polling thời gian thực mỗi 5 giây để nhận dữ liệu mới từ Webhook Ingestion Pipeline
  useEffect(() => {
    if (!token || !selectedRepo) {
      setIntegrationStatus(null);
      setWebhookLogs([]);
      return;
    }

    fetchIntegrationAndDocs(token, selectedRepo);
    const interval = setInterval(() => {
      fetchIntegrationAndDocs(token, selectedRepo);
    }, 5000);

    return () => clearInterval(interval);
  }, [token, selectedRepo, fetchIntegrationAndDocs]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token');
    const urlEmail = params.get('email');

    if (urlToken) {
      localStorage.setItem('access_token', urlToken);
      if (urlEmail) localStorage.setItem('user_email', urlEmail);
      window.history.replaceState({}, '', '/');
    }

    const storedToken = urlToken || localStorage.getItem('access_token');
    if (storedToken) {
      setToken(storedToken);
      fetchUserAndWorkspaces(storedToken);
    }
  }, []);

  const fetchUserAndWorkspaces = async (jwtToken: string) => {
    setLoadingWorkspaces(true);
    try {
      const headers = { Authorization: `Bearer ${jwtToken}` };

      const [meRes, wsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/users/me`, { headers }),
        fetch(`${API_BASE_URL}/github/workspaces`, { headers }),
      ]);

      if (meRes.status === 401 || wsRes.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_email');
        setToken(null);
        setUser(null);
        setRepos([]);
        setIntegrationStatus(null);
        setWebhookLogs([]);
        setBanner({
          type: 'error',
          message: 'Phiên đăng nhập đã hết hạn. Vui lòng bấm "Kết nối GitHub OAuth" để đăng nhập lại.',
        });
        return;
      }

      if (meRes.ok) {
        const userData: UserProfile = await meRes.json();
        setUser(userData);
      }

      if (wsRes.ok) {
        const repoList: GitHubRepo[] = await wsRes.json();
        setRepos(repoList);
        if (repoList.length > 0) {
          setSelectedRepo((prev) => prev || repoList[0].full_name);
        }
      } else {
        const errData = await wsRes.json().catch(() => ({}));
        setBanner({
          type: 'error',
          message: errData.detail || 'Không thể tải danh sách GitHub Repositories.',
        });
      }
    } catch {
      setBanner({
        type: 'error',
        message: 'Không thể kết nối đến Backend FastAPI (http://localhost:8000).',
      });
    } finally {
      setLoadingWorkspaces(false);
    }
  };

  const handleGitHubLogin = () => {
    window.location.href = `${API_BASE_URL}/auth/github/login`;
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_email');
    setToken(null);
    setUser(null);
    setRepos([]);
    setSelectedRepo('');
    setIntegrationStatus(null);
    setWebhookLogs([]);
    setBanner(null);
  };

  const handleCreateDoc = () => {
    const newTitle = `Tài liệu mới ${docs.length + 1}`;
    const newDoc: DocItem = {
      id: `doc-${Date.now()}`,
      title: newTitle,
      filePath: `docs/${toSafeFileName(newTitle)}`,
      content: `# Tài liệu mới\n\nNhập nội dung Markdown tại đây...`,
      updatedAt: new Date().toLocaleTimeString('vi-VN'),
    };
    setDocs([newDoc, ...docs]);
    setActiveDocId(newDoc.id);
    setMode('edit');
    setBanner(null);
  };

  const handleUpdateTitle = (newTitle: string) => {
    setDocs((prev) =>
      prev.map((doc) =>
        doc.id === activeDoc.id
          ? {
              ...doc,
              title: newTitle,
              filePath: doc.id.startsWith('db-') ? doc.filePath : `docs/${toSafeFileName(newTitle)}`,
              updatedAt: new Date().toLocaleTimeString('vi-VN'),
            }
          : doc
      )
    );
  };

  const handleUpdateContent = (newContent: string) => {
    setDocs((prev) =>
      prev.map((doc) =>
        doc.id === activeDoc.id
          ? { ...doc, content: newContent, updatedAt: new Date().toLocaleTimeString('vi-VN') }
          : doc
      )
    );
  };

  const insertMarkdownSyntax = (prefix: string, suffix = '') => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = activeDoc.content.substring(start, end) || 'văn bản';
    const updated =
      activeDoc.content.substring(0, start) +
      prefix +
      selectedText +
      suffix +
      activeDoc.content.substring(end);

    handleUpdateContent(updated);
    setMode('edit');
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length);
    }, 0);
  };

  // Hàm đồng bộ Repository từ GitHub về PostgreSQL (FE01 - 1.2)
  const handleSyncRepo = async () => {
    if (!token || !user) {
      setBanner({
        type: 'error',
        message: 'Vui lòng bấm "Kết nối GitHub OAuth" trước khi đồng bộ Repository.',
      });
      return;
    }

    if (!selectedRepo) {
      setBanner({
        type: 'error',
        message: 'Vui lòng chọn một Repository trong mục GitHub Workspace.',
      });
      return;
    }

    setSyncing(true);
    setBanner(null);

    try {
      const response = await fetch(`${API_BASE_URL}/github/sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ repo_name: selectedRepo }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setBanner({
          type: 'error',
          message: `Đồng bộ thất bại (${response.status}): ${data.detail || 'Lỗi không xác định'}`,
        });
        return;
      }

      if (Array.isArray(data.documents) && data.documents.length > 0) {
        mergeSyncedDocuments(data.documents, true);
      }

      await fetchIntegrationAndDocs(token, selectedRepo);

      const summary = data.summary || { total_md_files: 0, added: 0, updated: 0 };
      setBanner({
        type: 'success',
        message: `${data.message} (Thêm mới: ${summary.added}, Cập nhật: ${summary.updated})`,
        linkUrl: `https://github.com/${selectedRepo}`,
        linkText: 'Mở Repository →',
      });
    } catch {
      setBanner({
        type: 'error',
        message: 'Lỗi kết nối mạng khi gọi API đồng bộ Repository.',
      });
    } finally {
      setSyncing(false);
    }
  };

  // Hàm kích hoạt & kiểm thử Webhook Ingestion Pipeline (FE01 - 1.3)
  const handleSimulateWebhook = async () => {
    if (!token || !selectedRepo) return;

    setSimulatingWebhook(true);
    setBanner(null);

    try {
      const response = await fetch(`${API_BASE_URL}/github/webhook/simulate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ repo_name: selectedRepo }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setBanner({
          type: 'error',
          message: `Webhook Ingestion lỗi: ${data.detail || 'Không thể xử lý sự kiện'}`,
        });
        return;
      }

      await fetchIntegrationAndDocs(token, selectedRepo);
      setBanner({
        type: 'success',
        message: data.message || 'Đã tiếp nhận sự kiện Webhook Push và cập nhật dữ liệu thời gian thực!',
      });
    } catch {
      setBanner({
        type: 'error',
        message: 'Lỗi kết nối khi kích hoạt Webhook Pipeline.',
      });
    } finally {
      setSimulatingWebhook(false);
    }
  };

  const handlePushGitHub = async () => {
    if (!token || !user) {
      setBanner({
        type: 'error',
        message: 'Bạn chưa đăng nhập. Vui lòng bấm "Kết nối GitHub OAuth" ở thanh bên trái trước khi Push.',
      });
      return;
    }

    if (!selectedRepo) {
      setBanner({
        type: 'error',
        message: 'Vui lòng chọn một Repository trong mục GitHub Workspace.',
      });
      return;
    }

    setPushing(true);
    setBanner(null);

    const fileName = toSafeFileName(activeDoc.title);
    const filePath = activeDoc.filePath || `docs/${fileName}`;

    try {
      const response = await fetch(`${API_BASE_URL}/github/commit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          repo_name: selectedRepo,
          file_path: filePath,
          content: activeDoc.content,
          commit_message: `docs: sync ${filePath} from LivingDocs`,
        }),
      });

      const rawText = await response.text();
      let data: Record<string, unknown> | string | null = null;
      try {
        data = rawText ? JSON.parse(rawText) : null;
      } catch {
        data = rawText;
      }

      if (!response.ok) {
        const detail = typeof data === 'object' && data !== null ? data.detail : data;
        const errorDetail = Array.isArray(detail)
          ? detail
              .map((err: { loc?: (string | number)[]; msg?: string }) =>
                `${err.loc ? err.loc.slice(1).join('.') : 'field'}: ${err.msg || 'không hợp lệ'}`
              )
              .join(' | ')
          : typeof detail === 'string'
            ? detail
            : JSON.stringify(detail || data || 'Lỗi không xác định');

        setBanner({
          type: 'error',
          message: `Push thất bại (${response.status}): ${errorDetail}`,
        });
        return;
      }

      const repoObj = repos.find((r) => r.full_name === selectedRepo);
      const branch = repoObj?.default_branch || 'main';
      const customUrl =
        typeof data === 'object' && data !== null
          ? (data.html_url as string) || (data.file_url as string)
          : undefined;
      const githubFileUrl =
        customUrl || `https://github.com/${selectedRepo}/blob/${branch}/${filePath}`;

      setBanner({
        type: 'success',
        message: `Đã commit thành công lên ${selectedRepo}/${filePath}`,
        linkUrl: githubFileUrl,
        linkText: 'Xem file trên GitHub →',
      });
    } catch {
      setBanner({
        type: 'error',
        message: 'Lỗi kết nối mạng khi gửi yêu cầu đến Backend FastAPI.',
      });
    } finally {
      setPushing(false);
    }
  };

  const [isAstModalOpen, setIsAstModalOpen] = useState(false);

  const handleApplyAstMarkdown = (
    generatedMd: string,
    applyMode: 'replace' | 'append',
    suggestedTitle?: string,
    suggestedFilePath?: string
  ) => {
    setDocs((prev) =>
      prev.map((doc) => {
        if (doc.id !== activeDoc.id) return doc;
        const updatedContent =
          applyMode === 'replace'
            ? generatedMd
            : `${doc.content.trimEnd()}

${generatedMd}`;
        const isDefaultTitle =
          doc.title.startsWith('Hướng dẫn dự án') ||
          doc.title.startsWith('Tài liệu mới') ||
          !doc.title.trim();
        return {
          ...doc,
          title: applyMode === 'replace' && suggestedTitle && isDefaultTitle ? suggestedTitle : doc.title,
          filePath:
            applyMode === 'replace' && suggestedFilePath && !doc.githubSha
              ? suggestedFilePath
              : doc.filePath,
          content: updatedContent,
          updatedAt: new Date().toLocaleTimeString('vi-VN'),
        };
      })
    );
    setMode('preview');
    setBanner({
      type: 'success',
      message: 'Đã nạp bản nháp tài liệu sinh từ AST vào trình soạn thảo!',
    });
  };

  const filteredDocs = docs.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const wordCount = activeDoc.content.trim()
    ? activeDoc.content.trim().split(/\s+/).length
    : 0;
  const charCount = activeDoc.content.length;
  const targetPath = activeDoc.filePath || `docs/${toSafeFileName(activeDoc.title)}`;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#0d1117] text-[#c9d1d9] font-sans">
      <aside className="flex w-72 flex-col border-r border-[#30363d] bg-[#161b22]">
        <div className="flex items-center justify-between border-b border-[#30363d] px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#1f6feb]/20 text-[#58a6ff]">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="text-base font-bold tracking-tight text-white">LivingDocs</span>
          </div>
          <button
            onClick={handleCreateDoc}
            className="rounded-md bg-[#1f6feb] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#388bfd]"
          >
            + Mới
          </button>
        </div>

        <div className="border-b border-[#30363d] p-3 space-y-2.5">
          <div className="rounded-lg border border-[#30363d] bg-[#0d1117] p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8b949e]">
                GITHUB WORKSPACE
              </span>
              {token && (
                <button
                  onClick={() => fetchUserAndWorkspaces(token)}
                  title="Tải lại danh sách Repository"
                  className="text-xs text-[#58a6ff] hover:underline"
                >
                  Làm mới
                </button>
              )}
            </div>

            {!token ? (
              <button
                onClick={handleGitHubLogin}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-[#238636] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#2ea043]"
              >
                <svg className="h-4 w-4 fill-current" viewBox="0 0 16 16">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
                Kết nối GitHub OAuth
              </button>
            ) : loadingWorkspaces ? (
              <div className="py-1.5 text-center text-xs text-[#8b949e]">
                Đang nạp Repositories...
              </div>
            ) : repos.length > 0 ? (
              <>
                <select
                  value={selectedRepo}
                  onChange={(e) => setSelectedRepo(e.target.value)}
                  className="w-full rounded-md border border-[#30363d] bg-[#161b22] px-2.5 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                >
                  {repos.map((repo) => (
                    <option key={repo.id} value={repo.full_name}>
                      {repo.full_name} {repo.private ? '(Private)' : ''}
                    </option>
                  ))}
                </select>

                {/* Thẻ trạng thái GitHub App Integration (FE01 - 1.2) */}
                {integrationStatus && (
                  <div className="mt-2.5 rounded-md border border-[#30363d] bg-[#161b22] p-2.5 text-[11px] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-semibold text-[#3fb950]">
                        <span className="h-2 w-2 rounded-full bg-[#3fb950] animate-pulse" />
                        GitHub App Active
                      </span>
                      <span className="rounded bg-[#21262d] px-1.5 py-0.5 text-[10px] text-[#8b949e]">
                        {integrationStatus.private ? 'Private' : 'Public'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[#8b949e]">
                      <span>
                        Nhánh: <strong className="text-[#c9d1d9]">{integrationStatus.default_branch}</strong>
                      </span>
                      <span>
                        Quyền:{' '}
                        <strong className="text-[#c9d1d9]">
                          {integrationStatus.permissions?.push ? 'Read/Write' : 'Read'}
                        </strong>
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[#8b949e]">
                      <span>Đã đồng bộ DB:</span>
                      <strong className="text-[#58a6ff]">
                        {integrationStatus.synced_files_count} file .md
                      </strong>
                    </div>
                  </div>
                )}

                {/* Thẻ trạng thái Webhook & Real-time Ingestion Pipeline (FE01 - 1.3) */}
                <div className="mt-2.5 rounded-md border border-[#30363d] bg-[#161b22] p-2.5 text-[11px] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#a371f7]">Ingestion Pipeline</span>
                    <button
                      onClick={handleSimulateWebhook}
                      disabled={simulatingWebhook}
                      title="Kích hoạt luồng nhận sự kiện Push Webhook thời gian thực"
                      className="rounded bg-[#8957e5]/20 px-1.5 py-0.5 text-[10px] font-semibold text-[#d2a8ff] transition hover:bg-[#8957e5]/35 disabled:opacity-50"
                    >
                      {simulatingWebhook ? 'Đang nạp...' : '⚡ Test Webhook'}
                    </button>
                  </div>
                  <div className="truncate font-mono text-[10px] text-[#8b949e]">
                    POST /api/v1/github/webhook
                  </div>
                  {webhookLogs.length > 0 ? (
                    <div className="space-y-1 border-t border-[#30363d] pt-1.5">
                      {webhookLogs.slice(0, 2).map((log) => (
                        <div key={log.id} className="flex items-center justify-between gap-1 text-[10px]">
                          <span className="truncate text-[#c9d1d9]" title={log.message}>
                            [{log.commit_sha || log.event_type}] {log.message}
                          </span>
                          <span className="shrink-0 rounded bg-[#238636]/20 px-1 text-[#3fb950]">
                            LIVE
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[10px] text-[#8b949e]">
                      Sẵn sàng nhận sự kiện Push từ GitHub...
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-xs text-[#8b949e]">Không tìm thấy repository nào.</div>
            )}
          </div>
        </div>

        <div className="px-3 pt-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Tìm kiếm tài liệu..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-[#30363d] bg-[#0d1117] py-1.5 pl-8 pr-3 text-xs text-white placeholder-[#8b949e] focus:border-[#58a6ff] focus:outline-none"
            />
            <svg
              className="absolute left-2.5 top-2 h-3.5 w-3.5 text-[#8b949e]"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 104.5 4.5a7.5 7.5 0 0012.15 12.15z" />
            </svg>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {filteredDocs.map((doc) => {
            const isActive = doc.id === activeDoc.id;
            const isSynced = doc.id.startsWith('db-');
            return (
              <button
                key={doc.id}
                onClick={() => setActiveDocId(doc.id)}
                className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-xs font-medium transition ${
                  isActive
                    ? 'border border-[#1f6feb] bg-[#1f6feb]/15 text-[#58a6ff]'
                    : 'text-[#8b949e] hover:bg-[#21262d] hover:text-white'
                }`}
              >
                <span className="truncate">{doc.title || 'Không tiêu đề'}</span>
                {isSynced && (
                  <span
                    title="Đã đồng bộ với GitHub & PostgreSQL"
                    className="shrink-0 rounded bg-[#238636]/20 px-1.5 py-0.5 text-[9px] font-semibold text-[#3fb950]"
                  >
                    SYNC
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {user && (
          <div className="border-t border-[#30363d] bg-[#0d1117]/60 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-white">
                  {user.full_name || user.username || user.email}
                </p>
                <p className="truncate text-[11px] text-[#8b949e]">{user.email}</p>
              </div>
              <button
                onClick={handleLogout}
                className="shrink-0 rounded border border-[#30363d] px-2 py-1 text-[11px] text-[#f85149] transition hover:bg-[#f85149]/10"
              >
                Thoát
              </button>
            </div>
            <div className="mt-2">
              <span className="inline-block rounded bg-[#1f6feb]/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#58a6ff]">
                {user.role}
              </span>
            </div>
          </div>
        )}
      </aside>

      <main className="flex flex-1 flex-col bg-[#0d1117]">
        <header className="flex items-center justify-between border-b border-[#30363d] px-6 py-2.5">
          <div className="flex items-center gap-1 text-xs text-[#8b949e]">
            <button
              onClick={() => insertMarkdownSyntax('**', '**')}
              title="In đậm"
              className="rounded px-2.5 py-1.5 font-bold hover:bg-[#21262d] hover:text-white"
            >
              B
            </button>
            <button
              onClick={() => insertMarkdownSyntax('*', '*')}
              title="In nghiêng"
              className="rounded px-2.5 py-1.5 italic hover:bg-[#21262d] hover:text-white"
            >
              I
            </button>
            <button
              onClick={() => insertMarkdownSyntax('# ', '')}
              title="Tiêu đề"
              className="rounded px-2.5 py-1.5 font-semibold hover:bg-[#21262d] hover:text-white"
            >
              H
            </button>
            <button
              onClick={() => insertMarkdownSyntax('- [ ] ', '')}
              title="Checklist"
              className="rounded px-2.5 py-1.5 hover:bg-[#21262d] hover:text-white"
            >
              ☰
            </button>
            <button
              onClick={() => insertMarkdownSyntax('`', '`')}
              title="Inline Code"
              className="rounded px-2.5 py-1.5 font-mono hover:bg-[#21262d] hover:text-white"
            >
              &lt;&gt;
            </button>
            <span className="mx-1 h-4 w-px bg-[#30363d]" />
            <button
              onClick={() => setIsAstModalOpen(true)}
              title="Phân tích AST mã nguồn & sinh tài liệu tự động (FE02)"
              className="flex items-center gap-1.5 rounded-md border border-[#a371f7]/40 bg-[#a371f7]/15 px-2.5 py-1 text-xs font-semibold text-[#d2a8ff] transition hover:bg-[#a371f7]/25 hover:text-white"
            >
              <span>✨</span>
              <span>Sinh tài liệu AI (AST)</span>
            </button>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="flex rounded-md border border-[#30363d] bg-[#161b22] p-0.5">
              <button
                onClick={() => setMode('edit')}
                className={`rounded px-3 py-1 text-xs font-medium transition ${
                  mode === 'edit'
                    ? 'bg-[#1f6feb] text-white'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                Chỉnh sửa
              </button>
              <button
                onClick={() => setMode('preview')}
                className={`rounded px-3 py-1 text-xs font-medium transition ${
                  mode === 'preview'
                    ? 'bg-[#1f6feb] text-white'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                Xem trước
              </button>
            </div>

            {/* Nút Pull / Sync Repo từ GitHub (FE01 - 1.2) */}
            <button
              onClick={handleSyncRepo}
              disabled={syncing || !selectedRepo}
              title="Kéo toàn bộ tài liệu Markdown từ GitHub Repository về PostgreSQL"
              className="flex items-center gap-1.5 rounded-md border border-[#30363d] bg-[#21262d] px-3 py-1.5 text-xs font-semibold text-[#c9d1d9] transition hover:border-[#58a6ff] hover:text-white disabled:opacity-50"
            >
              {syncing ? 'Đang Sync...' : '↓ Sync Repo'}
            </button>

            <button
              onClick={handlePushGitHub}
              disabled={pushing}
              className="flex items-center gap-1.5 rounded-md bg-[#238636] px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-[#2ea043] disabled:opacity-50"
            >
              {pushing ? 'Đang Push...' : 'Push GitHub'}
            </button>
          </div>
        </header>

        {banner && (
          <div
            className={`flex items-center justify-between border-b px-6 py-2.5 text-xs ${
              banner.type === 'success'
                ? 'border-[#238636]/40 bg-[#238636]/15 text-[#3fb950]'
                : 'border-[#f85149]/40 bg-[#f85149]/15 text-[#ff7b72]'
            }`}
          >
            <div className="flex items-center gap-3">
              <span>{banner.message}</span>
              {banner.linkUrl && (
                <a
                  href={banner.linkUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold underline hover:text-white"
                >
                  {banner.linkText}
                </a>
              )}
            </div>
            <button
              onClick={() => setBanner(null)}
              className="text-xs opacity-75 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-12 py-10">
          <div className="mx-auto max-w-3xl">
            <input
              type="text"
              value={activeDoc.title}
              onChange={(e) => handleUpdateTitle(e.target.value)}
              placeholder="Tiêu đề tài liệu..."
              className="mb-6 w-full bg-transparent text-3xl font-bold text-white placeholder-[#484f58] focus:outline-none"
            />

            {mode === 'edit' ? (
              <textarea
                ref={textareaRef}
                value={activeDoc.content}
                onChange={(e) => handleUpdateContent(e.target.value)}
                placeholder="Bắt đầu viết nội dung Markdown tại đây..."
                className="h-[calc(100vh-260px)] w-full resize-none bg-transparent font-mono text-sm leading-relaxed text-[#c9d1d9] placeholder-[#484f58] focus:outline-none"
              />
            ) : (
              <div className="min-h-[calc(100vh-260px)]">
                <MarkdownPreview content={activeDoc.content} />
              </div>
            )}
          </div>
        </div>

        <footer className="flex items-center justify-between border-t border-[#30363d] px-6 py-2 text-[11px] text-[#8b949e]">
          <div className="flex items-center gap-4">
            <span>{wordCount} từ</span>
            <span>{charCount} ký tự</span>
            {selectedRepo && (
              <span className="text-[#58a6ff]">
                Đích: {selectedRepo}/{targetPath}
              </span>
            )}
          </div>
          <div suppressHydrationWarning>Cập nhật lần cuối: {activeDoc.updatedAt}</div>
        </footer>
      </main>

      <AstDocGeneratorModal
        isOpen={isAstModalOpen}
        onClose={() => setIsAstModalOpen(false)}
        token={token}
        selectedRepo={selectedRepo}
        repos={repos}
        onApplyMarkdown={handleApplyAstMarkdown}
      />
    </div>
  );
}