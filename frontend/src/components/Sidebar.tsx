'use client';

import { useState } from 'react';
import { Document } from '@/types/document';
import { Plus, Search, Trash2, FileText } from 'lucide-react';

interface SidebarProps {
  documents: Document[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({
  documents,
  selectedId,
  onSelect,
  onNew,
  onDelete,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <aside className="w-72 bg-gray-900 text-gray-200 h-screen p-4 flex flex-col border-r border-gray-800 select-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <FileText className="w-6 h-6 text-blue-500" />
          LivingDocs
        </h2>
        <button
          onClick={onNew}
          className="flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Mới
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative mb-4">
        <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-500" />
        <input
          type="text"
          placeholder="Tìm kiếm tài liệu..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-gray-950 text-gray-200 text-sm pl-9 pr-3 py-2 rounded-lg border border-gray-800 focus:outline-none focus:border-blue-500 transition placeholder-gray-500"
        />
      </div>

      {/* Document List */}
      <nav className="flex-1 overflow-y-auto space-y-1 pr-1">
        {filteredDocs.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-6">
            Không tìm thấy tài liệu
          </p>
        ) : (
          filteredDocs.map((doc) => {
            const isSelected = selectedId === doc.id;
            return (
              <div
                key={doc.id}
                onClick={() => onSelect(doc.id)}
                className={`group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm cursor-pointer transition ${
                  isSelected
                    ? 'bg-blue-600/10 text-blue-400 font-semibold border border-blue-500/20'
                    : 'hover:bg-gray-800/60 text-gray-400 hover:text-gray-200'
                }`}
              >
                <span className="truncate flex-1 mr-2">
                  {doc.title.trim() || 'Tài liệu chưa đặt tên'}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Bạn có chắc chắn muốn xóa tài liệu này?')) {
                      onDelete(doc.id);
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 hover:text-red-400 p-1 rounded transition"
                  title="Xóa tài liệu"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })
        )}
      </nav>
    </aside>
  );
}