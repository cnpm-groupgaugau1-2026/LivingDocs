from typing import List, Optional
from pydantic import BaseModel, Field


class CodeDiffLine(BaseModel):
    line_index: int
    line_type: str  # context | added | removed | hunk_header
    old_line_num: Optional[int] = None
    new_line_num: Optional[int] = None
    content: str
    file_path: str = ""
    evidence_ids: List[str] = Field(default_factory=list)


class DocPatchLine(BaseModel):
    line_index: int
    line_type: str  # context | added | removed | hunk_header
    old_doc_line_num: Optional[int] = None
    new_doc_line_num: Optional[int] = None
    content: str
    evidence_ids: List[str] = Field(default_factory=list)


class DiffMappingLink(BaseModel):
    link_id: str
    evidence_id: str
    code_file_path: str
    code_line_indices: List[int] = Field(default_factory=list)
    doc_line_indices: List[int] = Field(default_factory=list)
    rationale: str
    confidence: float = 0.95


class GroundingEvidenceItem(BaseModel):
    evidence_id: str
    claim_summary: str
    symbol_name: str
    symbol_kind: str  # endpoint | class | function | config
    file_path: str
    start_line: int
    end_line: int
    commit_hash: str
    commit_short: str
    commit_message: str
    commit_author: str
    commit_date: str
    branch: str
    code_snippet: str
    doc_patch_excerpt: str
    repo_grounding_status: str  # VERIFIED_IN_REPO | VERIFIED_IN_GIT | PATCH_PREVIEW
    repo_actual_excerpt: str = ""
    reviewer_status: str = "pending"  # pending | verified | flagged
    reviewer_note: str = ""


class GroundingDiffSessionResponse(BaseModel):
    session_id: str
    preset_id: str
    title: str
    repo_name: str
    branch: str
    commit_hash: str
    pr_number: Optional[int] = None
    target_doc_path: str
    source_code_files: List[str] = Field(default_factory=list)
    code_diff_lines: List[CodeDiffLine] = Field(default_factory=list)
    doc_patch_lines: List[DocPatchLine] = Field(default_factory=list)
    mapping_links: List[DiffMappingLink] = Field(default_factory=list)
    evidences: List[GroundingEvidenceItem] = Field(default_factory=list)
    grounding_coverage_score: float = 100.0
    verified_count: int = 0
    flagged_count: int = 0
    pending_count: int = 0


class CreateGroundingSessionRequest(BaseModel):
    preset_id: str = "live_fe05_multimodal"
    title: str = ""
    repo_name: str = "cnpm-groupgaugau1-2026/LivingDocs"
    branch: str = "main"
    commit_hash: str = ""
    pr_number: Optional[int] = None
    target_doc_path: str = "docs/architecture/multimodal_pipeline.md"
    custom_code_diff: str = ""
    custom_doc_patch: str = ""


class VerifyGroundingEvidenceRequest(BaseModel):
    session_id: str
    evidence_id: str
    reviewer_status: str  # verified | flagged | pending
    reviewer_note: str = ""