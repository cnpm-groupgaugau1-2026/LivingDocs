from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/review-workflow", tags=["fe07-review-workflow"])


class ReviewStage(str, Enum):
    STAFF_QUEUE = "staff_queue"
    CHANGES_REQUESTED = "changes_requested"
    MANAGER_APPROVAL = "manager_approval"
    REJECTED = "rejected"
    APPROVED = "approved"
    PUBLISHED = "published"


class VerificationCheck(BaseModel):
    check_name: str
    passed: bool
    detail: str


class SectionComment(BaseModel):
    id: str
    section_id: str
    section_title: str
    author: str
    role: str = "staff"
    body: str
    resolved: bool = False
    created_at: str


class ReviewItem(BaseModel):
    id: str
    title: str
    doc_type: str
    target_path: str
    source_ref: str
    stage: ReviewStage
    assigned_staff: str = "staff.reviewer"
    assigned_manager: str = "eng.manager"
    template_sections: List[str]
    content_markdown: str
    checks: List[VerificationCheck] = Field(default_factory=list)
    comments: List[SectionComment] = Field(default_factory=list)
    publish_commit_hash: Optional[str] = None
    published_at: Optional[str] = None
    updated_at: str


class VerifyPayload(BaseModel):
    required_sections: Optional[List[str]] = None
    code_symbols: Optional[List[str]] = None


class CommentPayload(BaseModel):
    section_id: str
    section_title: str
    author: str = "staff.reviewer"
    role: str = "staff"
    body: str


class ResolveCommentPayload(BaseModel):
    resolved: bool = True


class ForwardPayload(BaseModel):
    staff_actor: str = "staff.reviewer"
    summary_note: Optional[str] = None


class RequestChangesPayload(BaseModel):
    actor: str = "staff.reviewer"
    reason: str


class ManagerDecisionPayload(BaseModel):
    manager_actor: str = "eng.manager"
    decision: str  # "approve" | "reject"
    note: Optional[str] = None


class PublishPayload(BaseModel):
    actor: str = "eng.manager"
    commit_message: Optional[str] = None
    target_branch: str = "main"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_items() -> Dict[str, ReviewItem]:
    now = _now_iso()
    sample = ReviewItem(
        id="rev-fe07-001",
        title="FE03 Auto-Doc: API & Pipeline Reference",
        doc_type="technical-doc",
        target_path="docs/architecture/auto-doc-pipeline.md",
        source_ref="feat/fe03-fe09-sync",
        stage=ReviewStage.STAFF_QUEUE,
        template_sections=["Overview", "Architecture", "API Endpoints", "Verification"],
        content_markdown=(
            "## Overview\nAutomated documentation workflow for LivingDocs.\n\n"
            "## Architecture\nFastAPI router + Next.js review workbench.\n\n"
            "## API Endpoints\nPOST /api/v1/review-workflow/items\n\n"
            "## Verification\nChecked against backend/main.py."
        ),
        checks=[],
        comments=[
            SectionComment(
                id="cmt-101",
                section_id="sec-api",
                section_title="API Endpoints",
                author="staff.reviewer",
                role="staff",
                body="Bổ sung thêm ví dụ response status 200/404 cho endpoint chính.",
                resolved=False,
                created_at=now,
            )
        ],
        updated_at=now,
    )
    return {sample.id: sample}


_ITEMS: Dict[str, ReviewItem] = _seed_items()


def _get_item_or_404(item_id: str) -> ReviewItem:
    item = _ITEMS.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.get("/items", response_model=List[ReviewItem])
def list_review_items(stage: Optional[ReviewStage] = None):
    items = list(_ITEMS.values())
    if stage:
        items = [x for x in items if x.stage == stage]
    return items


@router.get("/items/{item_id}", response_model=ReviewItem)
def get_review_item(item_id: str):
    return _get_item_or_404(item_id)


@router.post("/items/{item_id}/verify", response_model=ReviewItem)
def run_staff_verification(item_id: str, payload: VerifyPayload):
    """9.1 Staff Review Queue & Code/Template Verification Engine."""
    item = _get_item_or_404(item_id)
    required = payload.required_sections or item.template_sections
    content_lower = item.content_markdown.lower()

    checks: List[VerificationCheck] = []
    for sec in required:
        found = sec.lower() in content_lower
        checks.append(
            VerificationCheck(
                check_name=f"Template Section: {sec}",
                passed=found,
                detail="Section present in draft" if found else f"Missing section '{sec}'",
            )
        )

    for sym in (payload.code_symbols or []):
        sym_ok = sym in item.content_markdown
        checks.append(
            VerificationCheck(
                check_name=f"Code Reference: {sym}",
                passed=sym_ok,
                detail="Referenced in documentation" if sym_ok else f"Symbol '{sym}' not found",
            )
        )

    item.checks = checks
    item.updated_at = _now_iso()
    return item


@router.post("/items/{item_id}/comments", response_model=ReviewItem)
def add_section_comment(item_id: str, payload: CommentPayload):
    """9.2 Section-level Commenting & Feedback Pipeline."""
    item = _get_item_or_404(item_id)
    comment = SectionComment(
        id=f"cmt-{uuid4().hex[:8]}",
        section_id=payload.section_id,
        section_title=payload.section_title,
        author=payload.author,
        role=payload.role,
        body=payload.body,
        resolved=False,
        created_at=_now_iso(),
    )
    item.comments.append(comment)
    item.updated_at = _now_iso()
    return item


@router.patch("/items/{item_id}/comments/{comment_id}", response_model=ReviewItem)
def toggle_comment_resolved(item_id: str, comment_id: str, payload: ResolveCommentPayload):
    item = _get_item_or_404(item_id)
    for cmt in item.comments:
        if cmt.id == comment_id:
            cmt.resolved = payload.resolved
            item.updated_at = _now_iso()
            return item
    raise HTTPException(status_code=404, detail="Comment not found")


@router.post("/items/{item_id}/request-changes", response_model=ReviewItem)
def request_changes(item_id: str, payload: RequestChangesPayload):
    item = _get_item_or_404(item_id)
    item.comments.append(
        SectionComment(
            id=f"cmt-{uuid4().hex[:8]}",
            section_id="general",
            section_title="Changes Requested",
            author=payload.actor,
            role="staff",
            body=payload.reason,
            resolved=False,
            created_at=_now_iso(),
        )
    )
    item.stage = ReviewStage.CHANGES_REQUESTED
    item.updated_at = _now_iso()
    return item


@router.post("/items/{item_id}/forward-to-manager", response_model=ReviewItem)
def forward_to_manager(item_id: str, payload: ForwardPayload):
    """Chuyển hồ sơ từ cấp Staff sang cấp Manager."""
    item = _get_item_or_404(item_id)
    unresolved = [c for c in item.comments if not c.resolved]
    if unresolved:
        raise HTTPException(
            status_code=400,
            detail=f"Still {len(unresolved)} unresolved section comment(s) before forwarding to Manager",
        )
    if item.checks and not all(c.passed for c in item.checks):
        raise HTTPException(
            status_code=400,
            detail="Some template/code verification checks failed",
        )
    item.stage = ReviewStage.MANAGER_APPROVAL
    item.updated_at = _now_iso()
    return item


@router.post("/items/{item_id}/manager-decision", response_model=ReviewItem)
def manager_decision(item_id: str, payload: ManagerDecisionPayload):
    """9.3 Manager Approval Workflow."""
    item = _get_item_or_404(item_id)
    if item.stage != ReviewStage.MANAGER_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Item must be in 'manager_approval' stage (current: {item.stage})",
        )
    decision = payload.decision.lower().strip()
    if decision == "approve":
        item.stage = ReviewStage.APPROVED
    elif decision == "reject":
        item.stage = ReviewStage.REJECTED
    else:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    if payload.note:
        item.comments.append(
            SectionComment(
                id=f"cmt-{uuid4().hex[:8]}",
                section_id="manager-decision",
                section_title=f"Manager {decision.title()}",
                author=payload.manager_actor,
                role="manager",
                body=payload.note,
                resolved=True,
                created_at=_now_iso(),
            )
        )
    item.updated_at = _now_iso()
    return item


@router.post("/items/{item_id}/publish", response_model=ReviewItem)
def publish_and_commit(item_id: str, payload: PublishPayload):
    """9.3 Automated Commit / Publishing step after Manager approval."""
    item = _get_item_or_404(item_id)
    if item.stage != ReviewStage.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Item must be 'approved' by Manager before publishing/committing",
        )
    item.stage = ReviewStage.PUBLISHED
    item.publish_commit_hash = uuid4().hex[:8]
    item.published_at = _now_iso()
    item.updated_at = item.published_at
    return item