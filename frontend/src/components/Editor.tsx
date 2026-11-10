'use client';

import { useState } from 'react';
import { Document } from '@/types/document';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Edit3,
  Eye,
  Bold,
  Italic,
  Heading,
  Code,
  List,
  Clock,
} from 'lucide-react';

interface EditorProps {
  document: Document | null;
  onChange: (updatedDoc: Document) => void;
}

export default function Editor({ document, onChange }: EditorProps) {
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');

  if (!document) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-500 bg-gray-950">
        <p className="text-lg">Chọn hoặc tạo một tài liệu để bắt đầu</p>
      </div>
    );
  }

  const insertMarkdown = (prefix: string, suffix: string = '') => {
    const textarea = window.document.getElementById(
      'markdown-textarea'
    ) as HTMLTextAreaElement;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = document.content;
    const selectedText = text.substring(start, end) || 'nội dung';
    const replacement = `${prefix}${selectedText}${suffix}`;

    const newContent =
      text.substring(0, start) + replacement + text.substring(end);
    onChange({ ...document, content: newContent, updatedAt: new Date().toISOString() });
  };

  const charCount = document.content.length;
  const wordCount = document.content.trim()
    ? document.content.trim().split(/\s+/).length
    : 0;

  return (
    <main className="flex-1 flex flex-col bg-gray-950 text-gray-100 overflow-hidden">
      {/* Top Action Toolbar */}
      <div className="flex items-center justify-between px-8 py-3 border-b border-gray-800/80 bg-gray-900/40">
        <div className="flex items-center gap-1">
          <button
            onClick={() => insertMarkdown('**', '**')}
            className="p-1.5 hover:bg-gray-800 text-gray-400 hover:text-gray-200 rounded transition"
            title="In đậm (**text**)"
          >
            <Bold className="w-4 h-4" />
          </button>
          <button
            onClick={() => insertMarkdown('*', '*')}
            className="p-1.5 hover:bg-gray-800 text-gray-400 hover:text-gray-200 rounded transition"
            title="In nghiêng (*text*)"
          >
            <Italic className="w-4 h-4" />
          </button>
          <button
            onClick={() => insertMarkdown('# ')}
            className="p-1.5 hover:bg-gray-800 text-gray-400 hover:text-gray-200 rounded transition"
            title="Tiêu đề (# H1)"
          >
            <Heading className="w-4 h-4" />
          </button>
          <button
            onClick={() => insertMarkdown('- ')}
            className="p-1.5 hover:bg-gray-800 text-gray-400 hover:text-gray-200 rounded transition"
            title="Danh sách (- item)"
          >
            <List className="w-4 h-4" />
          </button>
          <button
            onClick={() => insertMarkdown('`', '`')}
            className="p-1.5 hover:bg-gray-800 text-gray-400 hover:text-gray-200 rounded transition"
            title="Mã nguồn (`code`)"
          >
            <Code className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center bg-gray-900 p-1 rounded-lg border border-gray-800">
          <button
            onClick={() => setMode('edit')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
              mode === 'edit'
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Edit3 className="w-3.5 h-3.5" />
            Chỉnh sửa
          </button>
          <button
            onClick={() => setMode('preview')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
              mode === 'preview'
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            Xem trước
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col p-8 overflow-y-auto">
        <input
          type="text"
          value={document.title}
          onChange={(e) =>
            onChange({
              ...document,
              title: e.target.value,
              updatedAt: new Date().toISOString(),
            })
          }
          placeholder="Tiêu đề tài liệu..."
          className="bg-transparent text-3xl font-bold mb-6 focus:outline-none text-white placeholder-gray-600 border-b border-transparent focus:border-gray-800 pb-2 transition"
        />

        {mode === 'edit' ? (
          <textarea
            id="markdown-textarea"
            value={document.content}
            onChange={(e) =>
              onChange({
                ...document,
                content: e.target.value,
                updatedAt: new Date().toISOString(),
              })
            }
            placeholder="Viết nội dung tài liệu bằng Markdown tại đây..."
            className="flex-1 bg-transparent resize-none focus:outline-none leading-relaxed text-gray-300 placeholder-gray-600 font-mono text-sm"
          />
        ) : (
          <div className="flex-1 prose prose-invert max-w-none text-gray-200 leading-relaxed">
            {document.content ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {document.content}
              </ReactMarkdown>
            ) : (
              <span className="text-gray-600 italic">Chưa có nội dung...</span>
            )}
          </div>
        )}
      </div>

      {/* Bottom Status Bar */}
      <div className="px-8 py-2 border-t border-gray-800/80 bg-gray-900/30 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <span>{wordCount} từ</span>
          <span>{charCount} ký tự</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          <span suppressHydrationWarning>
            Cập nhật lần cuối: {new Date(document.updatedAt).toLocaleTimeString('vi-VN')}
          </span>
        </div>
      </div>
    </main>
  );
}