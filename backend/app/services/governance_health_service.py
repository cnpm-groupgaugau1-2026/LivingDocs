from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_FILE = DATA_DIR / "fe10_governance_health.json"

DriftStatus = Literal["clean", "warning", "critical"]
NodeKind = Literal["code", "service", "doc"]
EdgeRelation = Literal["documents", "impacts", "depends_on"]
ExportFormat = Literal["json", "markdown"]


class DocumentHealthItem(BaseModel):
    doc_id: str
    title: str
    doc_path: str
    module: str
    freshness_days: int
    freshness_threshold_days: int = 14
    coverage_pct: float
    drift_status: DriftStatus
    drift_reason: str | None = None
    last_updated_at: str


class DependencyNode(BaseModel):
    node_id: str
    label: str
    kind: NodeKind
    path: str
    module: str


class DependencyEdge(BaseModel):
    source: str
    target: str
    relation: EdgeRelation


class GovernanceMetrics(BaseModel):
    total_documents: int
    fresh_documents: int
    freshness_pct: float
    coverage_pct: float
    clean_count: int
    warning_count: int
    critical_count: int
    active_drift_count: int
    health_score: float


class GovernanceOverview(BaseModel):
    metrics: GovernanceMetrics
    documents: list[DocumentHealthItem]
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    generated_at: str


class ImpactAnalysisResult(BaseModel):
    source_node_id: str
    source_label: str
    impacted_nodes: list[DependencyNode]
    impacted_documents: list[DocumentHealthItem]
    impact_paths: list[list[str]]


class ComplianceExportPayload(BaseModel):
    format: ExportFormat
    generated_at: str
    filename: str
    content: str


class GovernanceHealthState(BaseModel):
    documents: list[DocumentHealthItem] = Field(default_factory=list)
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)


class GovernanceHealthService:
    def __init__(self, storage_path: Path = DATA_FILE) -> None:
        self.storage_path = storage_path
        self._state = self._load_or_init()

    def _load_or_init(self) -> GovernanceHealthState:
        if self.storage_path.exists():
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return GovernanceHealthState.model_validate(raw)

        now_iso = datetime.now(timezone.utc).isoformat()
        initial = GovernanceHealthState(
            documents=[
                DocumentHealthItem(
                    doc_id="doc-review-workflow",
                    title="Governed 2-Tier Review Workflow (FE07)",
                    doc_path="docs/features/fe07-review-workflow.md",
                    module="review",
                    freshness_days=3,
                    freshness_threshold_days=14,
                    coverage_pct=96.0,
                    drift_status="clean",
                    drift_reason=None,
                    last_updated_at=now_iso,
                ),
                DocumentHealthItem(
                    doc_id="doc-ci-policy",
                    title="CI/CD Pipeline & PR Merge Policy (FE06)",
                    doc_path="docs/features/fe06-ci-policy.md",
                    module="ci-cd",
                    freshness_days=18,
                    freshness_threshold_days=14,
                    coverage_pct=84.0,
                    drift_status="critical",
                    drift_reason="PR merge policy thresholds updated without refreshing runbook docs.",
                    last_updated_at=now_iso,
                ),
                DocumentHealthItem(
                    doc_id="doc-version-audit",
                    title="Role-Attributed Version Audit Trail (FE08)",
                    doc_path="docs/features/fe08-version-audit.md",
                    module="audit",
                    freshness_days=9,
                    freshness_threshold_days=14,
                    coverage_pct=91.5,
                    drift_status="warning",
                    drift_reason="Rollback payload fields added; verify sequence diagram.",
                    last_updated_at=now_iso,
                ),
                DocumentHealthItem(
                    doc_id="doc-governance-health",
                    title="Documentation Governance & Health Analytics (FE10)",
                    doc_path="docs/features/fe10-governance-health.md",
                    module="governance",
                    freshness_days=2,
                    freshness_threshold_days=14,
                    coverage_pct=94.0,
                    drift_status="clean",
                    drift_reason=None,
                    last_updated_at=now_iso,
                ),
            ],
            nodes=[
                DependencyNode(
                    node_id="code-review-api",
                    label="review_workflow.py",
                    kind="code",
                    path="backend/app/api/review_workflow.py",
                    module="review",
                ),
                DependencyNode(
                    node_id="code-ci-service",
                    label="ci_policy_service.py",
                    kind="code",
                    path="backend/app/services/ci_policy_service.py",
                    module="ci-cd",
                ),
                DependencyNode(
                    node_id="code-audit-service",
                    label="version_audit_service.py",
                    kind="code",
                    path="backend/app/services/version_audit_service.py",
                    module="audit",
                ),
                DependencyNode(
                    node_id="svc-governance",
                    label="GovernanceHealthService",
                    kind="service",
                    path="backend/app/services/governance_health_service.py",
                    module="governance",
                ),
                DependencyNode(
                    node_id="doc-review-workflow",
                    label="fe07-review-workflow.md",
                    kind="doc",
                    path="docs/features/fe07-review-workflow.md",
                    module="review",
                ),
                DependencyNode(
                    node_id="doc-ci-policy",
                    label="fe06-ci-policy.md",
                    kind="doc",
                    path="docs/features/fe06-ci-policy.md",
                    module="ci-cd",
                ),
                DependencyNode(
                    node_id="doc-version-audit",
                    label="fe08-version-audit.md",
                    kind="doc",
                    path="docs/features/fe08-version-audit.md",
                    module="audit",
                ),
                DependencyNode(
                    node_id="doc-governance-health",
                    label="fe10-governance-health.md",
                    kind="doc",
                    path="docs/features/fe10-governance-health.md",
                    module="governance",
                ),
            ],
            edges=[
                DependencyEdge(
                    source="code-review-api",
                    target="doc-review-workflow",
                    relation="documents",
                ),
                DependencyEdge(
                    source="code-ci-service",
                    target="doc-ci-policy",
                    relation="documents",
                ),
                DependencyEdge(
                    source="code-audit-service",
                    target="doc-version-audit",
                    relation="documents",
                ),
                DependencyEdge(
                    source="code-ci-service",
                    target="svc-governance",
                    relation="impacts",
                ),
                DependencyEdge(
                    source="code-audit-service",
                    target="svc-governance",
                    relation="depends_on",
                ),
                DependencyEdge(
                    source="svc-governance",
                    target="doc-governance-health",
                    relation="documents",
                ),
            ],
        )
        self._save(initial)
        return initial

    def _save(self, state: GovernanceHealthState) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def compute_metrics(self, docs: list[DocumentHealthItem]) -> GovernanceMetrics:
        total = len(docs)
        if total == 0:
            return GovernanceMetrics(
                total_documents=0,
                fresh_documents=0,
                freshness_pct=100.0,
                coverage_pct=100.0,
                clean_count=0,
                warning_count=0,
                critical_count=0,
                active_drift_count=0,
                health_score=100.0,
            )

        fresh_docs = sum(
            1 for d in docs if d.freshness_days <= d.freshness_threshold_days
        )
        freshness_pct = round((fresh_docs / total) * 100.0, 1)
        coverage_pct = round(sum(d.coverage_pct for d in docs) / total, 1)
        clean_count = sum(1 for d in docs if d.drift_status == "clean")
        warning_count = sum(1 for d in docs if d.drift_status == "warning")
        critical_count = sum(1 for d in docs if d.drift_status == "critical")
        active_drift = warning_count + critical_count

        penalty = warning_count * 6.0 + critical_count * 15.0
        raw_score = (freshness_pct * 0.45 + coverage_pct * 0.55) - penalty
        health_score = round(max(0.0, min(100.0, raw_score)), 1)

        return GovernanceMetrics(
            total_documents=total,
            fresh_documents=fresh_docs,
            freshness_pct=freshness_pct,
            coverage_pct=coverage_pct,
            clean_count=clean_count,
            warning_count=warning_count,
            critical_count=critical_count,
            active_drift_count=active_drift,
            health_score=health_score,
        )

    def get_overview(self) -> GovernanceOverview:
        metrics = self.compute_metrics(self._state.documents)
        return GovernanceOverview(
            metrics=metrics,
            documents=self._state.documents,
            nodes=self._state.nodes,
            edges=self._state.edges,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def analyze_impact(self, node_id: str) -> ImpactAnalysisResult:
        node_map = {n.node_id: n for n in self._state.nodes}
        if node_id not in node_map:
            raise KeyError(f"Dependency node '{node_id}' not found")

        adjacency: dict[str, list[str]] = {nid: [] for nid in node_map}
        for edge in self._state.edges:
            if edge.source in adjacency and edge.target in node_map:
                adjacency[edge.source].append(edge.target)

        visited: set[str] = {node_id}
        queue: deque[tuple[str, list[str]]] = deque([(node_id, [node_id])])
        impacted_ids: list[str] = []
        paths: list[list[str]] = []

        while queue:
            curr, path = queue.popleft()
            for nxt in adjacency.get(curr, []):
                next_path = path + [nxt]
                if nxt not in visited:
                    visited.add(nxt)
                    impacted_ids.append(nxt)
                    paths.append(next_path)
                    queue.append((nxt, next_path))

        impacted_nodes = [node_map[nid] for nid in impacted_ids]
        doc_by_id = {d.doc_id: d for d in self._state.documents}
        doc_by_path = {d.doc_path: d for d in self._state.documents}

        impacted_docs: list[DocumentHealthItem] = []
        seen_doc_ids: set[str] = set()
        for n in impacted_nodes:
            matched = doc_by_id.get(n.node_id) or doc_by_path.get(n.path)
            if matched and matched.doc_id not in seen_doc_ids:
                seen_doc_ids.add(matched.doc_id)
                impacted_docs.append(matched)

        return ImpactAnalysisResult(
            source_node_id=node_id,
            source_label=node_map[node_id].label,
            impacted_nodes=impacted_nodes,
            impacted_documents=impacted_docs,
            impact_paths=paths,
        )

    def export_compliance_report(
        self, fmt: ExportFormat = "markdown"
    ) -> ComplianceExportPayload:
        overview = self.get_overview()
        m = overview.metrics
        ts = overview.generated_at

        if fmt == "json":
            return ComplianceExportPayload(
                format="json",
                generated_at=ts,
                filename="livingdocs-fe10-compliance-report.json",
                content=overview.model_dump_json(indent=2),
            )

        lines = [
            "# LivingDocs FE10 — Documentation Governance & Health Report",
            f"- Generated at: `{ts}`",
            f"- Overall Health Score: **{m.health_score}/100**",
            f"- Freshness Rate: **{m.freshness_pct}%** ({m.fresh_documents}/{m.total_documents} fresh)",
            f"- Average Coverage: **{m.coverage_pct}%**",
            f"- Drift Summary: **{m.active_drift_count} active** (Critical: {m.critical_count}, Warning: {m.warning_count}, Clean: {m.clean_count})",
            "",
            "## Document Health Breakdown",
        ]
        for d in overview.documents:
            reason = f" — {d.drift_reason}" if d.drift_reason else ""
            lines.append(
                f"- **{d.title}** (`{d.doc_path}`): status=`{d.drift_status}`, coverage=`{d.coverage_pct}%`, age=`{d.freshness_days}d`{reason}"
            )

        lines.extend(["", "## Dependency Edges"])
        for e in overview.edges:
            lines.append(f"- `{e.source}` --[`{e.relation}`]--> `{e.target}`")

        return ComplianceExportPayload(
            format="markdown",
            generated_at=ts,
            filename="livingdocs-fe10-compliance-report.md",
            content="\n".join(lines),
        )


governance_health_service = GovernanceHealthService()