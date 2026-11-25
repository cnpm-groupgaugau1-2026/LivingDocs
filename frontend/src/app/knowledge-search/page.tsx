"use client";

import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000/api/v1/knowledge-search";

type EntityKind = "document" | "code_entity";
type SearchMode = "hybrid" | "semantic" | "keyword";
type RelationType = "documents" | "implemented_by" | "referenced_in" | "verifies";

interface LinkedRef {
  target_id: string;
  label: string;
  kind: EntityKind;
  path: string;
  relation: RelationType;
}

interface KnowledgeItem {
  item_id: string;
  title: string;
  kind: EntityKind;
  entity_type: string;
  collection: string;
  path: string;
  content: string;
  tags: string[];
  linked_items: LinkedRef[];
  updated_at: string;
}

interface SearchHit {
  item: KnowledgeItem;
  score: number;
  keyword_score: number;
  semantic_score: number;
  snippet: string;
  bidirectional_links: LinkedRef[];
}

interface SearchResponse {
  query: string;
  mode: SearchMode;
  collection: string;
  total: number;
  results: SearchHit[];
  rag_context: string;
}

export default function KnowledgeSearchPage() {
  const [query, setQuery] = useState<string>("drift merge policy rollback");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [collection, setCollection] = useState<string>("ALL");
  const [searchData, setSearchData] = useState<SearchResponse | null>(null);
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const runSearch = async (
    nextQ = query,
    nextMode = mode,
    nextCollection = collection
  ) => {
    setErrorMsg("");
    try {
      const params = new URLSearchParams({
        q: nextQ,
        mode: nextMode,
        collection: nextCollection,
      });
      const res = await fetch(`${API_BASE}/search?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: SearchResponse = await res.json();
      setSearchData(data);
      const keep =
        selectedHit &&
        data.results.find((r) => r.item.item_id === selectedHit.item.item_id);
      setSelectedHit(keep || data.results[0] || null);
    } catch (err) {
      setErrorMsg(String(err));
    }
  };

  useEffect(() => {
    runSearch();
  }, []);

  const handleNavigateToTarget = async (targetId: string, targetLabel: string) => {
    if (!searchData) return;
    const found = searchData.results.find((r) => r.item.item_id === targetId);
    if (found) {
      setSelectedHit(found);
      return;
    }
    setQuery(targetLabel);
    await runSearch(targetLabel, mode, "ALL");
  };

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6 text-slate-900">
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
            FE12 • Knowledge Base & Code-Doc Dependency Search
          </span>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">
            Hybrid Retrieval & Bidirectional Doc ↔ Code Explorer
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            13.1 Vector Search & Hybrid RAG Retrieval Engine • 13.2 Interactive Bidirectional Navigation UI
          </p>
        </div>

        <button
          type="button"
          onClick={() => runSearch()}
          className="rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-900 hover:bg-slate-200"
        >
          Làm mới chỉ mục
        </button>
      </div>

      {errorMsg && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {errorMsg}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") runSearch();
            }}
            placeholder="Nhập từ khóa hoặc câu hỏi ngữ nghĩa..."
            className="md:col-span-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          />

          <select
            value={mode}
            onChange={(e) => {
              const next = e.target.value as SearchMode;
              setMode(next);
              runSearch(query, next, collection);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            <option value="hybrid">Mode: Hybrid (Keyword + Semantic)</option>
            <option value="semantic">Mode: Semantic Vector</option>
            <option value="keyword">Mode: Keyword / Full-Text</option>
          </select>

          <select
            value={collection}
            onChange={(e) => {
              const next = e.target.value;
              setCollection(next);
              runSearch(query, mode, next);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            <option value="ALL">Collection: Tất cả</option>
            <option value="ci-cd">ci-cd</option>
            <option value="audit">audit</option>
            <option value="governance">governance</option>
          </select>
        </div>

        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-slate-600">
            {searchData
              ? `Tìm thấy ${searchData.total} mục (${searchData.mode})`
              : "Đang tải kết quả..."}
          </p>
          <button
            type="button"
            onClick={() => runSearch()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
          >
            Tìm kiếm
          </button>
        </div>
      </div>

      {searchData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
            <h2 className="text-base font-semibold text-slate-900">
              13.1 Kết quả tìm kiếm Hybrid & RAG
            </h2>

            <div className="space-y-2.5 max-h-[460px] overflow-auto pr-1">
              {searchData.results.map((hit) => {
                const isSelected = selectedHit?.item.item_id === hit.item.item_id;
                return (
                  <button
                    key={hit.item.item_id}
                    type="button"
                    onClick={() => setSelectedHit(hit)}
                    className={`w-full text-left rounded-lg border p-3 text-xs transition ${
                      isSelected
                        ? "border-indigo-600 bg-indigo-50 text-slate-900"
                        : "border-slate-200 bg-slate-50 text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-900">
                        [{hit.item.kind === "document" ? "DOC" : "CODE"}] {hit.item.title}
                      </span>
                      <span className="rounded bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-800 border border-indigo-200">
                        score {hit.score}
                      </span>
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-slate-600">
                      {hit.item.path} • collection: {hit.item.collection}
                    </p>
                    <p className="mt-1.5 text-slate-800">{hit.snippet}</p>
                    <p className="mt-1 text-[11px] text-slate-600">
                      kw: {hit.keyword_score} • sem: {hit.semantic_score} • links:{" "}
                      {hit.bidirectional_links.length}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-3">
              <h2 className="text-base font-semibold text-slate-900">
                13.2 Bidirectional Navigation (Document ↔ Code Entity)
              </h2>

              {selectedHit ? (
                <div className="space-y-3 text-xs text-slate-900">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                    <p className="font-bold text-slate-900">{selectedHit.item.title}</p>
                    <p className="font-mono text-[11px] text-slate-700">
                      {selectedHit.item.path} ({selectedHit.item.kind} / {selectedHit.item.entity_type})
                    </p>
                    <p className="text-slate-800 leading-relaxed">
                      {selectedHit.item.content}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <p className="font-semibold text-slate-800">
                      Liên kết hai chiều ({selectedHit.bidirectional_links.length}):
                    </p>
                    {selectedHit.bidirectional_links.length > 0 ? (
                      selectedHit.bidirectional_links.map((ref, idx) => (
                        <div
                          key={`${ref.target_id}-${ref.relation}-${idx}`}
                          className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white p-2.5"
                        >
                          <div>
                            <p className="font-semibold text-slate-900">
                              [{ref.kind === "document" ? "DOC" : "CODE"}] {ref.label}
                            </p>
                            <p className="font-mono text-[11px] text-slate-600">
                              {ref.path} • relation: {ref.relation}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleNavigateToTarget(ref.target_id, ref.label)}
                            className="rounded-lg border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-900 hover:bg-indigo-100"
                          >
                            Chuyển tới →
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-600">Chưa có liên kết hai chiều cho mục này.</p>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-600">Chọn một mục bên trái để xem quan hệ hai chiều.</p>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm space-y-2">
              <h2 className="text-base font-semibold text-slate-900">
                13.1 RAG Retrieved Context
              </h2>
              <textarea
                readOnly
                value={searchData.rag_context}
                rows={5}
                className="w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-[11px] text-slate-900"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}