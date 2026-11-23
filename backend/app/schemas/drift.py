from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class DriftCategory(str, Enum):
    REFERENTIAL = "referential"
    SIGNATURE = "signature"
    SEMANTIC = "semantic"


class DriftSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CodeFileInput(BaseModel):
    file_path: str
    content: str
    language: Optional[str] = None


class EvidenceLine(BaseModel):
    line_number: int
    content: str
    is_target: bool = False
    annotation: Optional[str] = None


class EvidenceSourceBlock(BaseModel):
    source_type: Literal["markdown_doc", "ast_code"]
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    exact_quote: str
    context_lines: List[EvidenceLine] = Field(default_factory=list)
    ast_node_proof: Optional[str] = None


class GroundingContextAttachment(BaseModel):
    evidence_id: str
    grounding_status: Literal[
        "verified_dual_anchor",
        "candidate_match_found",
        "doc_only_missing_target",
    ]
    doc_evidence: EvidenceSourceBlock
    code_evidence: Optional[EvidenceSourceBlock] = None
    ast_facts: List[str] = Field(default_factory=list)
    related_symbols: List[str] = Field(default_factory=list)
    ai_grounding_payload: str


class DriftItem(BaseModel):
    drift_id: str
    category: DriftCategory
    sub_type: str
    severity: DriftSeverity = DriftSeverity.MEDIUM
    severity_score: int = Field(default=50, ge=0, le=100)
    severity_factors: List[str] = Field(default_factory=list)
    symbol_name: str
    file_path: Optional[str] = None
    title: str
    description: str
    expected_in_doc: str
    actual_in_code: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggestion: str
    doc_line_range: Optional[List[int]] = None
    code_line_range: Optional[List[int]] = None
    grounding: Optional[GroundingContextAttachment] = None


class DriftClassificationSummary(BaseModel):
    total_drifts: int
    referential_count: int
    signature_count: int
    semantic_count: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    overall_risk_score: int = Field(default=0, ge=0, le=100)
    overall_risk_level: DriftSeverity = DriftSeverity.LOW
    grounded_drifts_count: int = 0
    dual_anchored_count: int = 0
    analyzed_symbols: int
    documented_symbols: int
    analysis_mode: Literal["ast_rule_engine", "ast_plus_llm_hybrid"] = "ast_rule_engine"


class DriftClassifyRequest(BaseModel):
    doc_path: str = "docs/README.md"
    markdown_content: str
    code_files: List[CodeFileInput]
    use_llm_semantic: bool = False


class DriftClassifyResponse(BaseModel):
    doc_path: str
    summary: DriftClassificationSummary
    drifts: List[DriftItem]
    warnings: List[str] = Field(default_factory=list)