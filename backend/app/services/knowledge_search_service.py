from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_FILE = DATA_DIR / "fe12_knowledge_base.json"

EntityKind = Literal["document", "code_entity"]
CodeEntityType = Literal["service", "router", "workflow", "page"]
SearchMode = Literal["hybrid", "semantic", "keyword"]
RelationType = Literal["documents", "implemented_by", "referenced_in", "verifies"]


class LinkedRef(BaseModel):
    target_id: str
    label: str
    kind: EntityKind
    path: str
    relation: RelationType


class KnowledgeItem(BaseModel):
    item_id: str
    title: str
    kind: EntityKind
    entity_type: str
    collection: str
    path: str
    content: str
    tags: list[str] = Field(default_factory=list)
    linked_items: list[LinkedRef] = Field(default_factory=list)
    updated_at: str


class SearchHit(BaseModel):
    item: KnowledgeItem
    score: float
    keyword_score: float
    semantic_score: float
    snippet: str
    bidirectional_links: list[LinkedRef] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    collection: str
    total: int
    results: list[SearchHit]
    rag_context: str


class CreateKnowledgeItemRequest(BaseModel):
    title: str
    kind: EntityKind = "document"
    entity_type: str = "guide"
    collection: str = "general"
    path: str
    content: str
    tags: list[str] = Field(default_factory=list)
    linked_item_ids: list[str] = Field(default_factory=list)


class KnowledgeBaseState(BaseModel):
    items: list[KnowledgeItem] = Field(default_factory=list)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_./-]+", text.lower())


def _cosine_similarity(vec_a: Counter[str], vec_b: Counter[str]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeSearchService:
    def __init__(self, storage_path: Path = DATA_FILE) -> None:
        self.storage_path = storage_path
        self._state = self._load_or_init()

    def _load_or_init(self) -> KnowledgeBaseState:
        if self.storage_path.exists():
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return KnowledgeBaseState.model_validate(raw)

        now_iso = datetime.now(timezone.utc).isoformat()
        initial = KnowledgeBaseState(
            items=[
                KnowledgeItem(
                    item_id="doc-fe06-ci",
                    title="FE06 CI/CD Pipeline & PR Merge Policy Runbook",
                    kind="document",
                    entity_type="runbook",
                    collection="ci-cd",
                    path="docs/features/fe06-ci-policy.md",
                    content=(
                        "Evaluates pull request documentation drift against protected code paths. "
                        "Supports warn and block merge modes, severity thresholds, and override labels "
                        "such as docs-drift-waived inside GitHub Actions."
                    ),
                    tags=["ci-cd", "drift", "merge-policy", "github-actions"],
                    linked_items=[
                        LinkedRef(
                            target_id="code-ci-policy-svc",
                            label="ci_policy_service.py",
                            kind="code_entity",
                            path="backend/app/services/ci_policy_service.py",
                            relation="implemented_by",
                        ),
                        LinkedRef(
                            target_id="code-ci-policy-page",
                            label="ci-policy/page.tsx",
                            kind="code_entity",
                            path="frontend/src/app/ci-policy/page.tsx",
                            relation="referenced_in",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="code-ci-policy-svc",
                    title="ci_policy_service.py",
                    kind="code_entity",
                    entity_type="service",
                    collection="ci-cd",
                    path="backend/app/services/ci_policy_service.py",
                    content=(
                        "Service class evaluating PR changed_files, detected_severity, and labels "
                        "against protected_paths and doc_paths to emit allow, warn, or block with exit_code."
                    ),
                    tags=["python", "service", "evaluate-pr", "policy"],
                    linked_items=[
                        LinkedRef(
                            target_id="doc-fe06-ci",
                            label="FE06 CI/CD Pipeline & PR Merge Policy Runbook",
                            kind="document",
                            path="docs/features/fe06-ci-policy.md",
                            relation="documents",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="code-ci-policy-page",
                    title="ci-policy/page.tsx",
                    kind="code_entity",
                    entity_type="page",
                    collection="ci-cd",
                    path="frontend/src/app/ci-policy/page.tsx",
                    content=(
                        "Next.js workbench for configuring warn/block merge policies, simulating PR drift "
                        "evaluations, and inspecting CI run history."
                    ),
                    tags=["nextjs", "ui", "ci-policy"],
                    linked_items=[
                        LinkedRef(
                            target_id="doc-fe06-ci",
                            label="FE06 CI/CD Pipeline & PR Merge Policy Runbook",
                            kind="document",
                            path="docs/features/fe06-ci-policy.md",
                            relation="documents",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="doc-fe08-audit",
                    title="FE08 Role-Attributed Version Audit & Rollback Spec",
                    kind="document",
                    entity_type="specification",
                    collection="audit",
                    path="docs/features/fe08-version-audit.md",
                    content=(
                        "Maintains tamper-evident SHA-256 hash-chained document versions attributed to "
                        "AI, Staff, or Manager roles with triggering commit hashes and full rollback."
                    ),
                    tags=["audit-trail", "sha256", "rollback", "role-attribution"],
                    linked_items=[
                        LinkedRef(
                            target_id="code-version-audit-svc",
                            label="version_audit_service.py",
                            kind="code_entity",
                            path="backend/app/services/version_audit_service.py",
                            relation="implemented_by",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="code-version-audit-svc",
                    title="version_audit_service.py",
                    kind="code_entity",
                    entity_type="service",
                    collection="audit",
                    path="backend/app/services/version_audit_service.py",
                    content=(
                        "Implements append_version, rollback_version, and verify_chain using SHA-256 "
                        "prev_hash chaining and role attribution (AI, Staff, Manager)."
                    ),
                    tags=["python", "service", "rollback", "verify-chain"],
                    linked_items=[
                        LinkedRef(
                            target_id="doc-fe08-audit",
                            label="FE08 Role-Attributed Version Audit & Rollback Spec",
                            kind="document",
                            path="docs/features/fe08-version-audit.md",
                            relation="documents",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="doc-fe10-health",
                    title="FE10 Governance Health, Impact Graph & Compliance Guide",
                    kind="document",
                    entity_type="guide",
                    collection="governance",
                    path="docs/features/fe10-governance-health.md",
                    content=(
                        "Aggregates document freshness, coverage, and drift status, traverses dependency "
                        "graphs for impact analysis, and exports Markdown or JSON compliance reports."
                    ),
                    tags=["governance", "freshness", "coverage", "impact-graph"],
                    linked_items=[
                        LinkedRef(
                            target_id="code-governance-svc",
                            label="governance_health_service.py",
                            kind="code_entity",
                            path="backend/app/services/governance_health_service.py",
                            relation="implemented_by",
                        ),
                    ],
                    updated_at=now_iso,
                ),
                KnowledgeItem(
                    item_id="code-governance-svc",
                    title="governance_health_service.py",
                    kind="code_entity",
                    entity_type="service",
                    collection="governance",
                    path="backend/app/services/governance_health_service.py",
                    content=(
                        "Computes health metrics, runs BFS impact traversal across dependency nodes/edges, "
                        "and generates Markdown or JSON compliance exports."
                    ),
                    tags=["python", "service", "impact-analysis", "export"],
                    linked_items=[
                        LinkedRef(
                            target_id="doc-fe10-health",
                            label="FE10 Governance Health, Impact Graph & Compliance Guide",
                            kind="document",
                            path="docs/features/fe10-governance-health.md",
                            relation="documents",
                        ),
                    ],
                    updated_at=now_iso,
                ),
            ]
        )
        self._save(initial)
        return initial

    def _save(self, state: KnowledgeBaseState) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def _enrich_bidirectional_links(self, item: KnowledgeItem) -> list[LinkedRef]:
        links_by_key: dict[tuple[str, str], LinkedRef] = {}
        for ref in item.linked_items:
            links_by_key[(ref.target_id, ref.relation)] = ref

        for other in self._state.items:
            if other.item_id == item.item_id:
                continue
            for ref in other.linked_items:
                if ref.target_id == item.item_id:
                    reverse_rel: RelationType = (
                        "documents" if ref.relation == "implemented_by" else ref.relation
                    )
                    key = (other.item_id, reverse_rel)
                    if key not in links_by_key:
                        links_by_key[key] = LinkedRef(
                            target_id=other.item_id,
                            label=other.title,
                            kind=other.kind,
                            path=other.path,
                            relation=reverse_rel,
                        )
        return list(links_by_key.values())

    def list_items(self, collection: str = "ALL") -> list[dict]:
        out = []
        for item in self._state.items:
            if collection != "ALL" and item.collection != collection:
                continue
            out.append(
                {
                    **item.model_dump(),
                    "bidirectional_links": [
                        r.model_dump() for r in self._enrich_bidirectional_links(item)
                    ],
                }
            )
        return out

    def create_item(self, req: CreateKnowledgeItemRequest) -> KnowledgeItem:
        by_id = {it.item_id: it for it in self._state.items}
        slug = re.sub(r"[^a-z0-9]+", "-", req.title.lower()).strip("-") or "item"
        item_id = f"{req.kind[:3]}-{slug}-{len(self._state.items) + 1}"

        linked_refs: list[LinkedRef] = []
        for tid in req.linked_item_ids:
            target = by_id.get(tid)
            if target:
                rel: RelationType = (
                    "implemented_by"
                    if req.kind == "document" and target.kind == "code_entity"
                    else "documents"
                )
                linked_refs.append(
                    LinkedRef(
                        target_id=target.item_id,
                        label=target.title,
                        kind=target.kind,
                        path=target.path,
                        relation=rel,
                    )
                )

        new_item = KnowledgeItem(
            item_id=item_id,
            title=req.title.strip(),
            kind=req.kind,
            entity_type=req.entity_type.strip(),
            collection=req.collection.strip() or "general",
            path=req.path.strip(),
            content=req.content.strip(),
            tags=[t.strip().lower() for t in req.tags if t.strip()],
            linked_items=linked_refs,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._state.items.append(new_item)
        self._save(self._state)
        return new_item

    def search(
        self,
        q: str = "",
        mode: SearchMode = "hybrid",
        collection: str = "ALL",
    ) -> SearchResponse:
        query_str = q.strip()
        q_tokens = _tokenize(query_str)
        q_vec = Counter(q_tokens)

        candidates = [
            it
            for it in self._state.items
            if collection == "ALL" or it.collection == collection
        ]

        hits: list[SearchHit] = []
        for item in candidates:
            haystack_text = f"{item.title} {item.path} {' '.join(item.tags)} {item.content}"
            doc_tokens = _tokenize(haystack_text)
            doc_vec = Counter(doc_tokens)

            if not q_tokens:
                kw_score = 0.5
                sem_score = 0.5
            else:
                matched = sum(1 for tok in q_tokens if tok in doc_vec)
                substring_bonus = (
                    0.25
                    if query_str.lower() in haystack_text.lower()
                    else 0.0
                )
                kw_score = min(1.0, (matched / len(q_tokens)) * 0.75 + substring_bonus)
                sem_score = min(1.0, _cosine_similarity(q_vec, doc_vec) * 1.35)

            if mode == "keyword":
                final_score = kw_score
            elif mode == "semantic":
                final_score = sem_score
            else:
                final_score = round(0.55 * kw_score + 0.45 * sem_score, 4)

            snippet = item.content if len(item.content) <= 180 else f"{item.content[:177]}..."
            hits.append(
                SearchHit(
                    item=item,
                    score=round(final_score, 4),
                    keyword_score=round(kw_score, 4),
                    semantic_score=round(sem_score, 4),
                    snippet=snippet,
                    bidirectional_links=self._enrich_bidirectional_links(item),
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        top_for_rag = hits[:3]
        rag_parts = [
            f"[{h.item.title} ({h.item.path}) — score={h.score}]: {h.item.content}"
            for h in top_for_rag
        ]
        rag_context = "\n".join(rag_parts) if rag_parts else "No matching context found."

        return SearchResponse(
            query=query_str,
            mode=mode,
            collection=collection,
            total=len(hits),
            results=hits,
            rag_context=rag_context,
        )


knowledge_search_service = KnowledgeSearchService()