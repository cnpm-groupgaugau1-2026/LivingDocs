'use client';

import React, { useEffect, useState } from 'react';
import {
  analyzeCodeCoverage,
  CoverageReport,
  DocTemplateOption,
  DraftGenerationResponse,
  fetchRepoCodeFiles,
  fetchRepoFileContent,
  fetchTemplatesList,
  generateAstDocDraft,
  RepoCodeFile,
} from '@/lib/api/docGeneration';

interface RepoOption {
  id: number;
  name: string;
  full_name: string;
  default_branch?: string;
}

interface AstDocGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
  token: string | null;
  selectedRepo: string;
  repos: RepoOption[];
  onApplyMarkdown: (
    markdown: string,
    mode: 'replace' | 'append',
    suggestedTitle?: string,
    suggestedFilePath?: string
  ) => void;
}

const SAMPLE_PYTHON_CODE = `class PaymentProcessor:
    """Xử lý giao dịch thanh toán trực tuyến."""

    def process_order(self, order_id: str, amount: float, currency: str = "VND") -> bool:
        if amount <= 0:
            raise ValueError("Số tiền không hợp lệ")
        if currency == "VND" and amount < 1000:
            return False
        return True
`;

export default function AstDocGeneratorModal({
  isOpen,
  onClose,
  token,
  selectedRepo,
  repos,
  onApplyMarkdown,
}: AstDocGeneratorModalProps) {
  const [sourceMode, setSourceMode] = useState<'github' | 'manual'>('github');
  const [activeRepo, setActiveRepo] = useState<string>(selectedRepo || '');
  const [repoFiles, setRepoFiles] = useState<RepoCodeFile[]>([]);
  const [selectedRepoFile, setSelectedRepoFile] = useState<string>('');
  const [loadingRepo, setLoadingRepo] = useState(false);

  const [filePath, setFilePath] = useState('app/services/payment_processor.py');
  const [sourceCode, setSourceCode] = useState(SAMPLE_PYTHON_CODE);
  const [templates, setTemplates] = useState<DocTemplateOption[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | ''>('');
  const [customInstructions, setCustomInstructions] = useState('');

  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coverageReport, setCoverageReport] = useState<CoverageReport | null>(null);
  const [draftResult, setDraftResult] = useState<DraftGenerationResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'gaps' | 'draft'>('gaps');

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    const initialRepo = selectedRepo || (repos.length > 0 ? repos[0].full_name : '');
    setActiveRepo(initialRepo);
    if (!token || !initialRepo) {
      setSourceMode('manual');
    } else {
      setSourceMode('github');
    }
    fetchTemplatesList(token).then(setTemplates).catch(() => {});
  }, [isOpen, selectedRepo, repos, token]);

  useEffect(() => {
    if (!isOpen || sourceMode !== 'github' || !activeRepo || !token) return;
    setLoadingRepo(true);
    setRepoFiles([]);
    fetchRepoCodeFiles(activeRepo, token)
      .then((files) => {
        setRepoFiles(files);
        if (files.length > 0) {
          setSelectedRepoFile(files[0].path);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingRepo(false));
  }, [isOpen, sourceMode, activeRepo, token]);

  const handleLoadGithubFile = async (pathToLoad: string) => {
    setSelectedRepoFile(pathToLoad);
    if (!activeRepo || !pathToLoad) return;
    setLoadingRepo(true);
    setError(null);
    try {
      const data = await fetchRepoFileContent(activeRepo, pathToLoad, token);
      setFilePath(data.file_path);
      setSourceCode(data.source_code);
      setCoverageReport(null);
      setDraftResult(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể tải tệp từ GitHub');
    } finally {
      setLoadingRepo(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setFilePath(file.name);
      setSourceCode(String(ev.target?.result || ''));
      setCoverageReport(null);
      setDraftResult(null);
    };
    reader.readAsText(file);
  };

  const handleAnalyzeCoverage = async () => {
    if (!sourceCode.trim()) {
      setError('Vui lòng nhập hoặc chọn tệp mã nguồn trước khi phân tích.');
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
      const report = await analyzeCodeCoverage(
        { file_path: filePath, source_code: sourceCode },
        token
      );
      setCoverageReport(report);
      setActiveTab('gaps');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Lỗi phân tích AST');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerateDraft = async () => {
    if (!sourceCode.trim()) {
      setError('Vui lòng nhập hoặc chọn tệp mã nguồn trước khi sinh tài liệu.');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const res = await generateAstDocDraft(
        {
          file_path: filePath,
          source_code: sourceCode,
          template_id: selectedTemplateId === '' ? null : Number(selectedTemplateId),
          custom_instructions: customInstructions.trim() || undefined,
          include_coverage_gaps: true,
        },
        token
      );
      setDraftResult(res);
      setCoverageReport(res.coverage_report);
      setActiveTab('draft');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Lỗi sinh tài liệu AI');
    } finally {
      setGenerating(false);
    }
  };

  if (!isOpen) return null;

  const severityBadge = (sev: string) => {
    if (sev === 'high') return 'bg-[#f85149]/15 text-[#f85149] border-[#f85149]/40';
    if (sev === 'medium') return 'bg-[#d29922]/15 text-[#e3b341] border-[#d29922]/40';
    return 'bg-[#30363d]/60 text-[#8b949e] border-[#30363d]';
  };

  const buildSuggestedMetadata = () => {
    const baseName = filePath.split('/').pop()?.replace(/\.[^/.]+$/, '') || 'API_Documentation';
    return {
      title: `Tài liệu kỹ thuật - ${baseName}`,
      targetDocPath: `docs/${baseName}.md`,
    };
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-[#30363d] bg-[#161b22] text-[#c9d1d9] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#30363d] bg-[#0d1117] px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#a371f7]/40 bg-[#a371f7]/15 text-base text-[#a371f7]">
              ✨
            </span>
            <div>
              <h2 className="text-base font-bold text-white">
                FE02 — Sinh Tài Liệu Kỹ Thuật Từ Cây Cú Pháp AST
              </h2>
              <p className="text-xs text-[#8b949e]">
                Phân tích AST đa ngôn ngữ (Python, JS/TS), đo độ phủ Docstring và kết xuất tài liệu Markdown
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-[#30363d] px-2.5 py-1 text-xs font-semibold text-[#8b949e] hover:bg-[#21262d] hover:text-white"
          >
            ✕ Đóng
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-6 mt-3 rounded-md border border-[#f85149]/40 bg-[#f85149]/10 px-4 py-2 text-xs text-[#f85149]">
            ⚠ {error}
          </div>
        )}

        {/* Body */}
        <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-12">
          {/* Left Panel */}
          <div className="flex flex-col gap-3.5 overflow-y-auto border-r border-[#30363d] bg-[#0d1117]/60 p-5 lg:col-span-5">
            <div className="flex rounded-md border border-[#30363d] bg-[#0d1117] p-0.5">
              <button
                onClick={() => setSourceMode('github')}
                className={`flex-1 rounded py-1.5 text-xs font-semibold transition ${
                  sourceMode === 'github'
                    ? 'bg-[#1f6feb] text-white'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                Từ GitHub Workspace
              </button>
              <button
                onClick={() => setSourceMode('manual')}
                className={`flex-1 rounded py-1.5 text-xs font-semibold transition ${
                  sourceMode === 'manual'
                    ? 'bg-[#1f6feb] text-white'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                Dán / Tải tệp Code
              </button>
            </div>

            {sourceMode === 'github' ? (
              <div className="space-y-2.5">
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase text-[#8b949e]">
                    Repository GitHub
                  </label>
                  <select
                    value={activeRepo}
                    onChange={(e) => setActiveRepo(e.target.value)}
                    className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                  >
                    {repos.length === 0 && <option value="">Chưa có Repository</option>}
                    {repos.map((r) => (
                      <option key={r.id} value={r.full_name}>
                        {r.full_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase text-[#8b949e]">
                    Tệp mã nguồn (.py, .js, .ts, .tsx)
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={selectedRepoFile}
                      onChange={(e) => handleLoadGithubFile(e.target.value)}
                      disabled={loadingRepo || repoFiles.length === 0}
                      className="flex-1 rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                    >
                      {repoFiles.length === 0 && (
                        <option value="">
                          {loadingRepo ? 'Đang quét mã nguồn...' : 'Không có tệp mã nguồn hỗ trợ'}
                        </option>
                      )}
                      {repoFiles.map((f) => (
                        <option key={f.path} value={f.path}>
                          {f.path} [{f.language}]
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleLoadGithubFile(selectedRepoFile)}
                      disabled={loadingRepo || !selectedRepoFile}
                      className="rounded-md border border-[#30363d] bg-[#21262d] px-3 py-2 text-xs font-semibold text-white hover:border-[#58a6ff] disabled:opacity-50"
                    >
                      {loadingRepo ? '...' : 'Nạp'}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="Ví dụ: src/services/auth.ts"
                  className="flex-1 rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                />
                <label className="cursor-pointer rounded-md border border-[#30363d] bg-[#21262d] px-3 py-2 text-xs font-semibold text-white hover:border-[#58a6ff]">
                  Tải tệp
                  <input
                    type="file"
                    accept=".py,.js,.jsx,.ts,.tsx"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
              </div>
            )}

            <div className="flex min-h-[170px] flex-1 flex-col">
              <div className="mb-1 flex items-center justify-between text-[11px] text-[#8b949e]">
                <span>
                  Tệp: <code className="text-[#58a6ff]">{filePath}</code>
                </span>
                <span>{sourceCode.length} ký tự</span>
              </div>
              <textarea
                value={sourceCode}
                onChange={(e) => setSourceCode(e.target.value)}
                placeholder="Dán mã nguồn Python, JavaScript hoặc TypeScript tại đây..."
                className="flex-1 resize-none rounded-md border border-[#30363d] bg-[#0d1117] p-3 font-mono text-xs text-[#c9d1d9] focus:border-[#58a6ff] focus:outline-none"
              />
            </div>

            <div className="space-y-2 border-t border-[#30363d] pt-2.5">
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase text-[#8b949e]">
                  Template Tài liệu (FE11)
                </label>
                <select
                  value={selectedTemplateId}
                  onChange={(e) =>
                    setSelectedTemplateId(e.target.value ? Number(e.target.value) : '')
                  }
                  className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                >
                  <option value="">Mặc định (AST Technical Specification)</option>
                  {templates.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      {tpl.name} [{tpl.category} - {tpl.current_version}]
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase text-[#8b949e]">
                  Ghi chú ngữ cảnh bổ sung
                </label>
                <input
                  type="text"
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                  placeholder="VD: Giải thích rõ luồng xử lý tham số và ngoại lệ..."
                  className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-xs text-white focus:border-[#58a6ff] focus:outline-none"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleAnalyzeCoverage}
                disabled={analyzing || generating}
                className="flex-1 rounded-md border border-[#30363d] bg-[#21262d] px-3 py-2 text-xs font-semibold text-white transition hover:border-[#58a6ff] disabled:opacity-50"
              >
                {analyzing ? 'Đang quét AST...' : 'Phân tích AST & Độ phủ'}
              </button>
              <button
                onClick={handleGenerateDraft}
                disabled={analyzing || generating}
                className="flex-1 rounded-md bg-[#238636] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#2ea043] disabled:opacity-50"
              >
                {generating ? 'Đang sinh tài liệu...' : '✨ Sinh bản nháp Markdown'}
              </button>
            </div>
          </div>

          {/* Right Panel */}
          <div className="flex flex-col overflow-hidden bg-[#161b22] lg:col-span-7">
            <div className="flex items-center justify-between border-b border-[#30363d] bg-[#0d1117]/40 px-6 py-3">
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveTab('gaps')}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                    activeTab === 'gaps'
                      ? 'border border-[#30363d] bg-[#21262d] text-white'
                      : 'text-[#8b949e] hover:text-white'
                  }`}
                >
                  Độ phủ & Lỗ hổng AST
                  {coverageReport && (
                    <span className="ml-1.5 rounded bg-[#1f6feb]/25 px-1.5 py-0.5 text-[10px] text-[#58a6ff]">
                      {coverageReport.coverage_percentage}%
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setActiveTab('draft')}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                    activeTab === 'draft'
                      ? 'border border-[#30363d] bg-[#21262d] text-white'
                      : 'text-[#8b949e] hover:text-white'
                  }`}
                >
                  Bản nháp Markdown AI
                </button>
              </div>

              {draftResult && (
                <div className="flex items-center gap-2 text-[11px] text-[#8b949e]">
                  <span className="rounded border border-[#a371f7]/40 bg-[#a371f7]/15 px-2 py-0.5 text-[#a371f7]">
                    {draftResult.model_used}
                  </span>
                  <span>~{draftResult.tokens_estimated} tokens</span>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {activeTab === 'gaps' ? (
                coverageReport ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-4 gap-3">
                      <div className="rounded-lg border border-[#30363d] bg-[#0d1117] p-3">
                        <div className="text-[11px] text-[#8b949e]">Tổng thực thể AST</div>
                        <div className="mt-1 text-xl font-bold text-white">
                          {coverageReport.total_entities}
                        </div>
                      </div>
                      <div className="rounded-lg border border-[#30363d] bg-[#0d1117] p-3">
                        <div className="text-[11px] text-[#8b949e]">Đã có Docstring</div>
                        <div className="mt-1 text-xl font-bold text-[#3fb950]">
                          {coverageReport.documented_entities}
                        </div>
                      </div>
                      <div className="rounded-lg border border-[#30363d] bg-[#0d1117] p-3">
                        <div className="text-[11px] text-[#8b949e]">Độ phủ tài liệu</div>
                        <div className="mt-1 text-xl font-bold text-[#58a6ff]">
                          {coverageReport.coverage_percentage}%
                        </div>
                      </div>
                      <div className="rounded-lg border border-[#30363d] bg-[#0d1117] p-3">
                        <div className="text-[11px] text-[#8b949e]">Ưu tiên cao</div>
                        <div className="mt-1 text-xl font-bold text-[#f85149]">
                          {coverageReport.high_priority_gaps}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-[#8b949e]">
                        Thực thể thiếu tài liệu ({coverageReport.gaps.length})
                      </h3>
                      {coverageReport.gaps.length === 0 ? (
                        <div className="rounded-lg border border-[#238636]/40 bg-[#238636]/15 p-4 text-xs text-[#3fb950]">
                          ✓ Tất cả thực thể trong tệp này đều đã có Docstring đầy đủ.
                        </div>
                      ) : (
                        coverageReport.gaps.map((g, idx) => (
                          <div
                            key={`${g.entity_name}-${g.start_line}-${idx}`}
                            className="flex items-start justify-between gap-3 rounded-lg border border-[#30363d] bg-[#0d1117] p-3"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span
                                  className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${severityBadge(
                                    g.severity
                                  )}`}
                                >
                                  {g.severity}
                                </span>
                                <code className="text-xs font-semibold text-white">
                                  {g.parent_name ? `${g.parent_name}.${g.entity_name}` : g.entity_name}
                                </code>
                                <span className="text-[11px] text-[#8b949e]">
                                  Dòng {g.start_line}–{g.end_line}
                                </span>
                              </div>
                              <p className="text-xs text-[#c9d1d9]">{g.recommendation}</p>
                            </div>
                            <span className="shrink-0 text-[11px] text-[#8b949e]">
                              Complexity: {g.complexity_score}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-center text-xs text-[#8b949e]">
                    Bấm <strong className="text-white">Phân tích AST & Độ phủ</strong> hoặc{' '}
                    <strong className="text-white">✨ Sinh bản nháp Markdown</strong> ở cột bên trái để bắt đầu.
                  </div>
                )
              ) : draftResult ? (
                <div className="space-y-3">
                  {draftResult.warnings.length > 0 && (
                    <div className="rounded-md border border-[#d29922]/40 bg-[#d29922]/10 p-3 text-xs text-[#e3b341]">
                      {draftResult.warnings.map((w, i) => (
                        <div key={i}>• {w}</div>
                      ))}
                    </div>
                  )}
                  <pre className="whitespace-pre-wrap rounded-lg border border-[#30363d] bg-[#0d1117] p-4 font-mono text-xs leading-relaxed text-[#c9d1d9]">
                    {draftResult.markdown_content}
                  </pre>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-center text-xs text-[#8b949e]">
                  Chưa có bản nháp tài liệu. Bấm <strong className="text-white">✨ Sinh bản nháp Markdown</strong> để khởi tạo.
                </div>
              )}
            </div>

            {draftResult && (
              <div className="flex items-center justify-between border-t border-[#30363d] bg-[#0d1117] px-6 py-3">
                <span className="text-xs text-[#8b949e]">
                  Template: <strong className="text-white">{draftResult.template_used}</strong>
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const meta = buildSuggestedMetadata();
                      onApplyMarkdown(draftResult.markdown_content, 'append', meta.title, meta.targetDocPath);
                      onClose();
                    }}
                    className="rounded-md border border-[#30363d] bg-[#21262d] px-3 py-1.5 text-xs font-semibold text-white hover:border-[#58a6ff]"
                  >
                    Chèn nối tiếp
                  </button>
                  <button
                    onClick={() => {
                      const meta = buildSuggestedMetadata();
                      onApplyMarkdown(draftResult.markdown_content, 'replace', meta.title, meta.targetDocPath);
                      onClose();
                    }}
                    className="rounded-md bg-[#238636] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#2ea043]"
                  >
                    Đưa vào trình soạn thảo
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
