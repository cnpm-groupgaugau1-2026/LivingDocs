'use client';

import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import Editor from '@/components/Editor';
import { Document } from '@/types/document';

const MOCK_DOCS: Document[] = [
  {
    id: '1',
    title: 'Hướng dẫn dự án LivingDocs',
    content:
      '# Chào mừng đến với LivingDocs\n\nĐây là trình soạn thảo tài liệu thời gian thực được xây dựng bằng **Next.js 14** và **FastAPI**.\n\n- [x] Thiết kế giao diện Frontend\n- [ ] Xây dựng RESTful API Backend\n- [ ] Tích hợp cơ sở dữ liệu',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: '2',
    title: 'Ghi chú cuộc họp Backend',
    content:
      '## Kiến trúc hệ thống\n\n1. Sử dụng FastAPI cho hiệu năng cao\n2. Cơ sở dữ liệu SQLite / PostgreSQL\n3. Authentication với JWT tokens',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

export default function HomePage() {
  const [documents, setDocuments] = useState<Document[]>(MOCK_DOCS);
  const [selectedId, setSelectedId] = useState<string | null>('1');

  const selectedDocument =
    documents.find((doc) => doc.id === selectedId) || null;

  const handleUpdate = (updatedDoc: Document) => {
    setDocuments((prev) =>
      prev.map((doc) => (doc.id === updatedDoc.id ? updatedDoc : doc))
    );
  };

  const handleCreateNew = () => {
    const newDoc: Document = {
      id: Date.now().toString(),
      title: 'Tài liệu mới',
      content: '',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setDocuments((prev) => [newDoc, ...prev]);
    setSelectedId(newDoc.id);
  };

  const handleDelete = (id: string) => {
    setDocuments((prev) => {
      const nextDocs = prev.filter((doc) => doc.id !== id);
      if (selectedId === id) {
        setSelectedId(nextDocs.length > 0 ? nextDocs[0].id : null);
      }
      return nextDocs;
    });
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        documents={documents}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onNew={handleCreateNew}
        onDelete={handleDelete}
      />
      <Editor document={selectedDocument} onChange={handleUpdate} />
    </div>
  );
}