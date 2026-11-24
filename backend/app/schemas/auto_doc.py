from typing import List, Optional
from pydantic import BaseModel, Field


class DocVersionSchema(BaseModel):
    version_id: str
    version_number: str
    content: str
    created_at: str
    author: str  # ai_workflow | developer_edit | rollback | initial_seed
    trigger_ref: str
    status: str  # published | draft | superseded | rolled_back
    change_summary: str = ""


class DiffLineSchema(BaseModel):
    line_type: str  # unchanged | added | removed | modified
    old_line_num: Optional[int] = None
    new_line_num: Optional[int] = None
    old_text: str = ""
    new_text: str = ""


class CodeChangeItemSchema(BaseModel):
    change_type: str  # added | removed | modified
    symbol_kind: str  # endpoint | function | class | parameter
    signature: str
    detail: str


class CodeVsDocComparisonSchema(BaseModel):
    code_changes_detected: List[CodeChangeItemSchema] = Field(default_factory=list)
    doc_impact_points: List[str] = Field(default_factory=list)
    side_by_side_diff: List[DiffLineSchema] = Field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0
    drift_resolved_count: int = 0


class CodeChangeEventRequest(BaseModel):
    event_type: str = "pull_request"  # pull_request | commit
    repo_name: str = "cnpm-groupgaugau1-2026/LivingDocs"
    branch: str = "feat/multimodal-consistency"
    commit_sha: str = "9f4b21c"
    pr_number: Optional[int] = 42
    pr_title: Optional[str] = "feat(multimodal): add FE05.3 visual-to-code consistency verification"
    author: str = "dev-livingdocs"
    target_doc_path: str = "docs/architecture/multimodal_pipeline.md"
    code_diff: str = ""
    current_doc_content: str = ""
    use_local_git_diff: bool = False


class AutoDocWorkflowResponse(BaseModel):
    workflow_id: str
    event_type: str
    repo_name: str
    branch: str
    commit_sha: str
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    author: str
    target_doc_path: str
    code_diff: str
    engine_used: str
    current_published_version: DocVersionSchema
    active_draft_version: Optional[DocVersionSchema] = None
    comparison: CodeVsDocComparisonSchema
    version_history: List[DocVersionSchema] = Field(default_factory=list)


class AcceptDraftRequest(BaseModel):
    workflow_id: str
    reviewer: str = "tech-lead"


class EditDraftRequest(BaseModel):
    workflow_id: str
    edited_content: str
    editor_note: str = "Chỉnh sửa thủ công bởi developer"


class RegenerateDraftRequest(BaseModel):
    workflow_id: str
    custom_instruction: str = ""


class RollbackVersionRequest(BaseModel):
    workflow_id: str
    target_version_id: str
    reason: str = "Rollback về phiên bản ổn định trước đó"