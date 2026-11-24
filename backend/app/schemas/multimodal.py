from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class VisualAssetType(str, Enum):
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    FLOWCHART = "flowchart"
    PDF_DOCUMENT = "pdf_document"
    UI_OR_SCREENSHOT = "ui_or_screenshot"
    UNKNOWN = "unknown"


class TechnicalTokenCategory(str, Enum):
    SYMBOL_OR_CLASS = "symbol_or_class"
    API_ENDPOINT = "api_endpoint"
    FILE_PATH = "file_path"
    SERVICE_OR_NODE = "service_or_node"
    FLOW_OPERATOR = "flow_operator"


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OcrTextBlock(BaseModel):
    block_id: str
    page_number: int = 1
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None
    is_technical_label: bool = False


class ExtractedTechnicalToken(BaseModel):
    token: str
    category: TechnicalTokenCategory
    page_number: int = 1
    confidence: float = Field(..., ge=0.0, le=1.0)
    occurrences: int = 1


class OcrPageResult(BaseModel):
    page_number: int
    width: Optional[int] = None
    height: Optional[int] = None
    raw_text: str
    cleaned_text: str
    mean_confidence: float = Field(..., ge=0.0, le=1.0)
    blocks: List[OcrTextBlock] = Field(default_factory=list)


class ImagePreprocessingTelemetry(BaseModel):
    applied_steps: List[str] = Field(default_factory=list)
    original_resolution: Optional[str] = None
    color_mode_converted: Optional[str] = None
    contrast_factor: float = 1.0


class OcrExtractionResponse(BaseModel):
    asset_id: str
    file_name: str
    mime_type: str
    detected_asset_type: VisualAssetType
    engine_used: str
    total_pages: int
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    preprocessing: ImagePreprocessingTelemetry
    full_extracted_text: str
    pages: List[OcrPageResult]
    technical_tokens: List[ExtractedTechnicalToken]
    token_summary: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

# ==============================================================================
# FE05.2: VISION-LLM CONTEXT EXTRACTOR SCHEMAS
# ==============================================================================

class GraphNodeSchema(BaseModel):
    id: str
    label: str
    node_type: str  # gateway | service | database | external | queue | decision | step
    functions: List[str] = Field(default_factory=list)
    endpoints: List[str] = Field(default_factory=list)
    file_paths: List[str] = Field(default_factory=list)
    source_page: int = 1
    confidence: float = 0.9


class GraphEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""
    protocol: str = "internal_call"  # HTTP/JSON | RPC/Auth | SQL | Webhook | Flow
    is_async: bool = False
    source_page: int = 1


class ExecutionFlowStepSchema(BaseModel):
    step_order: int
    actor: str
    action: str
    target: Optional[str] = None
    protocol_or_note: str = ""


class ArchitecturalClaimSchema(BaseModel):
    claim_id: str
    category: str  # service_dependency | api_contract | data_persistence | auth_guard | code_mapping
    statement: str
    involved_entities: List[str] = Field(default_factory=list)
    verifiable_target: str = ""
    confidence: float = 0.9


class VisionContextExtractionResponse(BaseModel):
    filename: str
    asset_type: str  # architecture_diagram | flowchart | pipeline_diagram | pdf_document
    extractor_engine: str  # gemini_vision_llm | structural_graph_reconstructor
    ocr_engine_used: str
    page_count: int
    semantic_summary: str
    nodes: List[GraphNodeSchema] = Field(default_factory=list)
    edges: List[GraphEdgeSchema] = Field(default_factory=list)
    execution_flows: List[ExecutionFlowStepSchema] = Field(default_factory=list)
    architectural_claims: List[ArchitecturalClaimSchema] = Field(default_factory=list)
    ocr_token_count: int = 0
    normalized_text: str = ""

class CodeEvidenceSchema(BaseModel):
    file_path: str
    line_number: int = 1
    symbol_name: str
    symbol_type: str  # class | function | endpoint | call | file
    snippet: str = ""


class ClaimVerificationResultSchema(BaseModel):
    claim_id: str
    category: str
    statement: str
    verifiable_target: str
    status: str  # consistent | drifted | unverified
    severity: str  # info | warning | critical
    confidence: float
    explanation: str
    remediation: str = ""
    evidences: List[CodeEvidenceSchema] = Field(default_factory=list)


class VisualCodeConsistencyResponse(BaseModel):
    filename: str
    asset_type: str
    scanned_repo_root: str
    scanned_files_count: int
    indexed_symbols_count: int
    consistency_score: float
    overall_status: str  # consistent | partial_drift | major_drift
    total_claims: int
    consistent_count: int
    drifted_count: int
    unverified_count: int
    semantic_summary: str
    verification_results: List[ClaimVerificationResultSchema] = Field(default_factory=list)
    vision_context: VisionContextExtractionResponse