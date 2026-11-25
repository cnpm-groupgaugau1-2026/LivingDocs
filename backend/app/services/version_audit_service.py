from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_FILE = DATA_DIR / "fe08_version_audit.json"
REPO_ROOT = Path(__file__).resolve().parents[3]

ActorRole = Literal["AI", "Staff", "Manager"]


class VersionEntry(BaseModel):
    version_id: str
    version_number: int
    doc_path: str
    content_markdown: str
    summary: str
    actor_role: ActorRole
    actor_name: str
    trigger_event: str
    trigger_commit_hash: str
    rollback_from_version: int | None = None
    prev_hash: str
    entry_hash: str
    created_at: str


class DocumentAuditTrail(BaseModel):
    doc_id: str
    title: str
    doc_path: str
    current_version: int
    entries: list[VersionEntry] = Field(default_factory=list)


class VersionAuditState(BaseModel):
    documents: list[DocumentAuditTrail]


class CreateVersionRequest(BaseModel):
    content_markdown: str
    summary: str
    actor_role: ActorRole
    actor_name: str
    trigger_event: str = "manual_update"
    trigger_commit_hash: str | None = None


class RollbackRequest(BaseModel):
    target_version_number: int
    actor_role: ActorRole = "Staff"
    actor_name: str = "staff.reviewer"
    reason: str = "Rollback to verified baseline version"
    trigger_commit_hash: str | None = None


class ChainVerificationResult(BaseModel):
    doc_id: str
    valid: bool
    checked_entries: int
    broken_at_version: int | None = None
    message: str


def _compute_entry_hash(
    *,
    doc_id: str,
    version_number: int,
    doc_path: str,
    content_markdown: str,
    summary: str,
    actor_role: str,
    actor_name: str,
    trigger_event: str,
    trigger_commit_hash: str,
    rollback_from_version: int | None,
    prev_hash: str,
    created_at: str,
) -> str:
    payload = {
        "doc_id": doc_id,
        "version_number": version_number,
        "doc_path": doc_path,
        "content_markdown": content_markdown,
        "summary": summary,
        "actor_role": actor_role,
        "actor_name": actor_name,
        "trigger_event": trigger_event,
        "trigger_commit_hash": trigger_commit_hash,
        "rollback_from_version": rollback_from_version,
        "prev_hash": prev_hash,
        "created_at": created_at,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve_commit_hash(provided: str | None) -> str:
    if provided and provided.strip():
        return provided.strip()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return "local-head"


class VersionAuditService:
    def __init__(self, storage_path: Path = DATA_FILE) -> None:
        self.storage_path = storage_path
        self._state = self._load_or_init()

    def _build_entry(
        self,
        *,
        doc_id: str,
        version_number: int,
        doc_path: str,
        content_markdown: str,
        summary: str,
        actor_role: ActorRole,
        actor_name: str,
        trigger_event: str,
        trigger_commit_hash: str,
        prev_hash: str,
        rollback_from_version: int | None = None,
        created_at: str | None = None,
    ) -> VersionEntry:
        ts = created_at or datetime.now(timezone.utc).isoformat()
        commit_sha = _resolve_commit_hash(trigger_commit_hash)
        entry_hash = _compute_entry_hash(
            doc_id=doc_id,
            version_number=version_number,
            doc_path=doc_path,
            content_markdown=content_markdown,
            summary=summary,
            actor_role=actor_role,
            actor_name=actor_name,
            trigger_event=trigger_event,
            trigger_commit_hash=commit_sha,
            rollback_from_version=rollback_from_version,
            prev_hash=prev_hash,
            created_at=ts,
        )
        return VersionEntry(
            version_id=f"{doc_id}-v{version_number}",
            version_number=version_number,
            doc_path=doc_path,
            content_markdown=content_markdown,
            summary=summary,
            actor_role=actor_role,
            actor_name=actor_name,
            trigger_event=trigger_event,
            trigger_commit_hash=commit_sha,
            rollback_from_version=rollback_from_version,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=ts,
        )

    def _load_or_init(self) -> VersionAuditState:
        if self.storage_path.exists():
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return VersionAuditState.model_validate(raw)

        doc_id = "doc-fe08-001"
        doc_path = "docs/architecture/review-workflow.md"
        v1 = self._build_entry(
            doc_id=doc_id,
            version_number=1,
            doc_path=doc_path,
            content_markdown="# Review Workflow\n\nInitial draft generated by AI pipeline.",
            summary="AI generated initial documentation draft",
            actor_role="AI",
            actor_name="livingdocs-ai-bot",
            trigger_event="ai_auto_doc",
            trigger_commit_hash="8c3d91a",
            prev_hash="GENESIS",
        )
        v2 = self._build_entry(
            doc_id=doc_id,
            version_number=2,
            doc_path=doc_path,
            content_markdown="# Review Workflow\n\n## Overview\nVerified section structure and added API notes.",
            summary="Staff verified sections and resolved open comments",
            actor_role="Staff",
            actor_name="staff.reviewer",
            trigger_event="staff_verification_passed",
            trigger_commit_hash="9f4a21b",
            prev_hash=v1.entry_hash,
        )
        v3 = self._build_entry(
            doc_id=doc_id,
            version_number=3,
            doc_path=doc_path,
            content_markdown="# Review Workflow\n\n## Overview\nApproved and published for release.",
            summary="Manager approved and published version 3",
            actor_role="Manager",
            actor_name="eng.manager",
            trigger_event="manager_approved_publish",
            trigger_commit_hash="a71e09c",
            prev_hash=v2.entry_hash,
        )

        initial = VersionAuditState(
            documents=[
                DocumentAuditTrail(
                    doc_id=doc_id,
                    title="FE07 Governed 2-Tier Review Workflow",
                    doc_path=doc_path,
                    current_version=3,
                    entries=[v1, v2, v3],
                )
            ]
        )
        self._save(initial)
        return initial

    def _save(self, state: VersionAuditState) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def _get_doc(self, doc_id: str) -> DocumentAuditTrail:
        for doc in self._state.documents:
            if doc.doc_id == doc_id:
                return doc
        raise KeyError(f"Document '{doc_id}' not found")

    def list_documents(self) -> list[DocumentAuditTrail]:
        return self._state.documents

    def get_history(self, doc_id: str) -> DocumentAuditTrail:
        return self._get_doc(doc_id)

    def append_version(self, doc_id: str, req: CreateVersionRequest) -> DocumentAuditTrail:
        doc = self._get_doc(doc_id)
        last_entry = doc.entries[-1] if doc.entries else None
        prev_hash = last_entry.entry_hash if last_entry else "GENESIS"
        next_num = (last_entry.version_number if last_entry else 0) + 1

        entry = self._build_entry(
            doc_id=doc.doc_id,
            version_number=next_num,
            doc_path=doc.doc_path,
            content_markdown=req.content_markdown,
            summary=req.summary,
            actor_role=req.actor_role,
            actor_name=req.actor_name,
            trigger_event=req.trigger_event,
            trigger_commit_hash=_resolve_commit_hash(req.trigger_commit_hash),
            prev_hash=prev_hash,
        )
        doc.entries.append(entry)
        doc.current_version = next_num
        self._save(self._state)
        return doc

    def rollback_version(self, doc_id: str, req: RollbackRequest) -> DocumentAuditTrail:
        doc = self._get_doc(doc_id)
        target = next(
            (e for e in doc.entries if e.version_number == req.target_version_number),
            None,
        )
        if target is None:
            raise ValueError(f"Version v{req.target_version_number} not found")

        last_entry = doc.entries[-1]
        next_num = last_entry.version_number + 1
        entry = self._build_entry(
            doc_id=doc.doc_id,
            version_number=next_num,
            doc_path=doc.doc_path,
            content_markdown=target.content_markdown,
            summary=f"Rollback to v{target.version_number}: {req.reason}",
            actor_role=req.actor_role,
            actor_name=req.actor_name,
            trigger_event="version_rollback",
            trigger_commit_hash=_resolve_commit_hash(req.trigger_commit_hash),
            rollback_from_version=target.version_number,
            prev_hash=last_entry.entry_hash,
        )
        doc.entries.append(entry)
        doc.current_version = next_num
        self._save(self._state)
        return doc

    def verify_chain(self, doc_id: str) -> ChainVerificationResult:
        doc = self._get_doc(doc_id)
        expected_prev = "GENESIS"
        for idx, entry in enumerate(doc.entries):
            if entry.prev_hash != expected_prev:
                return ChainVerificationResult(
                    doc_id=doc_id,
                    valid=False,
                    checked_entries=idx + 1,
                    broken_at_version=entry.version_number,
                    message=f"Chain broken at v{entry.version_number}: prev_hash mismatch.",
                )
            recomputed = _compute_entry_hash(
                doc_id=doc.doc_id,
                version_number=entry.version_number,
                doc_path=entry.doc_path,
                content_markdown=entry.content_markdown,
                summary=entry.summary,
                actor_role=entry.actor_role,
                actor_name=entry.actor_name,
                trigger_event=entry.trigger_event,
                trigger_commit_hash=entry.trigger_commit_hash,
                rollback_from_version=entry.rollback_from_version,
                prev_hash=entry.prev_hash,
                created_at=entry.created_at,
            )
            if recomputed != entry.entry_hash:
                return ChainVerificationResult(
                    doc_id=doc_id,
                    valid=False,
                    checked_entries=idx + 1,
                    broken_at_version=entry.version_number,
                    message=f"Tamper detected at v{entry.version_number}: hash mismatch.",
                )
            expected_prev = entry.entry_hash

        return ChainVerificationResult(
            doc_id=doc_id,
            valid=True,
            checked_entries=len(doc.entries),
            broken_at_version=None,
            message=f"Verified all {len(doc.entries)} version entries with intact SHA-256 chain.",
        )


version_audit_service = VersionAuditService()